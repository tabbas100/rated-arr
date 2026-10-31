"""The gateway's HTTP API. It listens on loopback only; Whatbox's HTTPS proxy is the way in.

GET  /v1/health                         no auth
POST /v1/pair        {"device"}         no auth, rate limited: starts pairing, returns a code to show
POST /v1/pair/poll   {"pairing"}        no auth, rate limited: the device token once approved
GET  /v1/search?q=                      films and shows matching q
GET  /v1/profiles                       quality profiles and the defaults
POST /v1/films       {"id", "profile"?} add a film by TMDB id
POST /v1/shows       {"id", "seasons", "profile"?}  add a show by TVDB id
GET  /v1/episodes?show=                 a show's episodes by season, with what is downloaded and wanted
POST /v1/episodes    {"show", "episodes": [[season, episode], ...], "profile"?}
                                        want exactly these episodes (adding the show if needed)
GET  /v1/discover                       rows to discover: films from Radarr, shows from TMDB when it has a key
GET  /v1/library                        films and shows in the library with sizes, and the plan's disk usage
POST /v1/library/delete  {"kind", "id", "what": "file"|"title", "confirm": "delete"}
POST /v1/library/episodes/delete  {"show", "episodes": [[s, e], ...], "confirm": "delete"}
GET  /v1/downloads                      the download queue
GET  /v1/recent                         newest titles in the library
GET  /v1/watching                       Plex's Continue Watching, for the TV's Watch Next row
"""
from __future__ import annotations

import ipaddress
import json
import logging
import socket
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable
from urllib.parse import parse_qs, urlsplit

from ..arr import catalog
from .devices import Registry, TooManyPairings, UnknownPairing
from ..arr.episodes import Episodes
from ..tmdb.show_discovery import ShowDiscovery
from .storage import Storage
from ..arr.library import AlreadyAdded, Films, NoRootFolder, NotFound, Shows
from .limits import SlidingWindow
from ..tmdb.browse import Browse, genres
from ..tmdb.details import Details, NoDetails
from ..tmdb.people import People
from ..tmdb.spelling import Spelling, any_close, closest_first
from ..upstream import UpstreamError
from ..plex.watching import Watching

API_VERSION = 1
MAX_BODY_BYTES = 64 * 1024  # room for 5,000 episode picks; still tiny
MAX_PATH = 512
MAX_QUERY = 100
MAX_ID = 2**31 - 1
MAX_PICKS = 5000
MAX_CONNECTIONS = 32
MAX_ACTIVE_REQUESTS = 16
RECENT_COUNT = 20
log = logging.getLogger("fetchd")


class HttpError(Exception):
    def __init__(self, status: int, code: str, message: str = "", extra: dict | None = None) -> None:
        super().__init__(code)
        self.status = status
        self.code = code
        self.message = message
        self.extra = extra or {}


@dataclass
class Gateway:
    """What every request needs: devices, the two libraries, and the limits."""

    registry: Registry
    films: Films
    shows: Shows
    episodes: Episodes
    show_discovery: ShowDiscovery
    storage: Storage
    people: People
    spelling: Spelling
    browse: Browse
    details: Details
    watching: Watching
    failed_auth_per_client: SlidingWindow = field(default_factory=lambda: SlidingWindow(20, 600, 900))
    failed_auth_total: SlidingWindow = field(default_factory=lambda: SlidingWindow(200, 600, 900))
    pair_starts: SlidingWindow = field(default_factory=lambda: SlidingWindow(10, 600, 600))
    pair_polls: SlidingWindow = field(default_factory=lambda: SlidingWindow(300, 60, 60))
    active: threading.BoundedSemaphore = field(default_factory=lambda: threading.BoundedSemaphore(MAX_ACTIVE_REQUESTS))
    pool: ThreadPoolExecutor = field(default_factory=lambda: ThreadPoolExecutor(max_workers=8))


class GatewayServer(ThreadingHTTPServer):
    """A threading server that refuses non-loopback binds and drops connections beyond a cap."""

    daemon_threads = True

    def __init__(self, address: tuple[str, int], gateway: Gateway) -> None:
        if not ipaddress.ip_address(address[0]).is_loopback:
            raise ValueError("fetchd only listens on loopback; Whatbox's HTTPS proxy is the way in")
        self.gateway = gateway
        self._connections = threading.BoundedSemaphore(MAX_CONNECTIONS)
        super().__init__(address, Handler)

    def process_request(self, request: socket.socket, client_address: Any) -> None:
        if not self._connections.acquire(blocking=False):
            self.shutdown_request(request)
            return
        super().process_request(request, client_address)

    def process_request_thread(self, request: socket.socket, client_address: Any) -> None:
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._connections.release()


class Handler(BaseHTTPRequestHandler):
    server_version = "fetchd"
    protocol_version = "HTTP/1.1"
    timeout = 20

    def version_string(self) -> str:
        """No Python or library version in the Server header."""
        return self.server_version

    def do_GET(self) -> None:
        self._dispatch("GET")

    def do_POST(self) -> None:
        self._dispatch("POST")

    def do_PUT(self) -> None:
        self._refuse_method()

    do_DELETE = do_PATCH = do_HEAD = do_OPTIONS = do_TRACE = do_CONNECT = do_PUT

    def _refuse_method(self) -> None:
        self._send(405, {"error": "method_not_allowed"}, {"Allow": "GET, POST"})

    def _dispatch(self, method: str) -> None:
        gateway: Gateway = self.server.gateway
        started = time.monotonic()
        if not gateway.active.acquire(blocking=False):
            self._send(503, {"error": "busy"}, {"Retry-After": "2"})
            return
        try:
            status, body, headers = self._handle(gateway, method)
        except HttpError as error:
            status, body, headers = error.status, {"error": error.code, "message": error.message, **error.extra}, {}
            if error.status == 401:
                headers["WWW-Authenticate"] = 'Bearer realm="fetchd"'
            if error.status == 429:
                headers["Retry-After"] = "900"
        except Exception:
            log.exception("unexpected error on %s %s", method, self._path_only())
            status, body, headers = 500, {"error": "internal"}, {}
        finally:
            gateway.active.release()
        self._send(status, body, headers)
        log.info("%s %s %d %.0fms %s", method, self._path_only(), status,
                 (time.monotonic() - started) * 1000, self._client_key())

    def _handle(self, gateway: Gateway, method: str) -> tuple[int, dict, dict]:
        if len(self.path) > MAX_PATH:
            raise HttpError(414, "uri_too_long")
        if self.headers.get("Origin"):
            raise HttpError(403, "browser_requests_not_allowed")
        path = urlsplit(self.path).path
        route = ROUTES.get((method, path))
        if route is None:
            known_paths = {p for _, p in ROUTES}
            raise HttpError(405 if path in known_paths else 404, "method_not_allowed" if path in known_paths else "not_found")
        handler, needs_auth = route
        device_id = self._authenticate(gateway) if needs_auth else ""
        return handler(self, gateway, device_id)

    def _authenticate(self, gateway: Gateway) -> str:
        """The device id for the bearer token; a wrong token counts toward the lockouts."""
        client = self._client_key()
        if gateway.failed_auth_per_client.blocked(client) or gateway.failed_auth_total.blocked("all"):
            device = gateway.registry.authenticate(self._bearer())
            if device:
                return device
            raise HttpError(429, "too_many_failed_attempts")
        device = gateway.registry.authenticate(self._bearer())
        if device:
            return device
        gateway.failed_auth_per_client.record(client)
        gateway.failed_auth_total.record("all")
        raise HttpError(401, "unauthorized")

    def _bearer(self) -> str:
        value = self.headers.get("Authorization", "")
        scheme, _, token = value.partition(" ")
        return token.strip() if scheme.lower() == "bearer" else ""

    def _client_key(self) -> str:
        """The caller's address: the proxy's forwarded address when the peer is loopback, else the peer."""
        peer = self.client_address[0] if self.client_address else ""
        if peer and ipaddress.ip_address(peer).is_loopback:
            real = self.headers.get("X-Real-IP", "").strip()
            forwarded = self.headers.get("X-Forwarded-For", "").split(",")[-1].strip()
            return (real or forwarded or peer)[:64]
        return peer

    def query_param(self, name: str) -> str:
        values = parse_qs(urlsplit(self.path).query, keep_blank_values=True).get(name, [""])
        return values[0]

    def json_body(self) -> dict:
        if self.headers.get("Transfer-Encoding"):
            raise HttpError(411, "length_required")
        if self.headers.get_content_type() != "application/json":
            raise HttpError(415, "json_required")
        try:
            length = int(self.headers.get("Content-Length", ""))
        except ValueError as error:
            raise HttpError(411, "length_required") from error
        if length < 0 or length > MAX_BODY_BYTES:
            raise HttpError(413, "body_too_large")
        try:
            body = json.loads(self.rfile.read(length) or b"null")
        except ValueError as error:
            raise HttpError(400, "invalid_json") from error
        if not isinstance(body, dict):
            raise HttpError(400, "invalid_json", "expected an object")
        return body

    def _path_only(self) -> str:
        return urlsplit(self.path).path[:MAX_PATH]

    def _send(self, status: int, body: dict, headers: dict) -> None:
        payload = json.dumps(body).encode("utf-8")
        self.send_response(status)
        for name, value in {**SECURITY_HEADERS, **headers}.items():
            self.send_header(name, value)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format: str, *args: Any) -> None:
        """http.server's own access log would print raw request lines; _dispatch logs a safe one instead."""

    def log_error(self, format: str, *args: Any) -> None:
        peer = self.client_address[0] if self.client_address else "?"
        log.warning("protocol error from %s: %s", peer, format % args)


SECURITY_HEADERS = {
    "Cache-Control": "no-store",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
    "Strict-Transport-Security": "max-age=31536000",
}


def _health(handler: Handler, gateway: Gateway, device_id: str) -> tuple[int, dict, dict]:
    return 200, {"ok": True, "api": API_VERSION}, {}


def _pair_start(handler: Handler, gateway: Gateway, device_id: str) -> tuple[int, dict, dict]:
    body = handler.json_body()
    if not gateway.pair_starts.allow("all"):
        raise HttpError(429, "too_many_pairing_requests")
    device = _optional_text(body, "device", 60) or "TV"
    try:
        pairing = gateway.registry.start_pairing(device)
    except TooManyPairings as error:
        raise HttpError(429, "too_many_pairing_requests") from error
    log.info("pairing requested by %r, code %s", device, pairing.code)
    return 201, {"pairing": pairing.pairing_id, "code": pairing.code, "expiresIn": pairing.expires_in}, {}


def _pair_poll(handler: Handler, gateway: Gateway, device_id: str) -> tuple[int, dict, dict]:
    body = handler.json_body()
    if not gateway.pair_polls.allow("all"):
        raise HttpError(429, "too_many_requests")
    pairing_id = _required_text(body, "pairing", 100)
    try:
        token = gateway.registry.poll(pairing_id)
    except UnknownPairing as error:
        raise HttpError(404, "pairing_expired") from error
    if token is None:
        return 200, {"status": "pending"}, {}
    log.info("pairing completed")
    return 200, {"status": "approved", "token": token}, {}


def _search(handler: Handler, gateway: Gateway, device_id: str) -> tuple[int, dict, dict]:
    term = handler.query_param("q").strip()
    if not 1 <= len(term) <= MAX_QUERY or not term.isprintable():
        raise HttpError(400, "invalid_query", f"1 to {MAX_QUERY} printable characters")
    people = gateway.pool.submit(gateway.people.search, term)
    results = _both(gateway, lambda: gateway.films.search(term), lambda: gateway.shows.search(term))
    found_people = _people_or_none(people)
    suggestion = ""
    titles = [item["title"] for item in (results["films"] or []) + (results["shows"] or [])]
    if not found_people and not results["unavailable"] and not any_close(term, titles):
        suggestion = gateway.spelling.suggest(term)
        if suggestion:
            results = _both(gateway, lambda: gateway.films.search(suggestion), lambda: gateway.shows.search(suggestion))
    searched = suggestion or term
    return 200, {"films": closest_first(searched, results["films"] or []),
                 "shows": closest_first(searched, results["shows"] or []), "people": found_people,
                 "suggestion": suggestion, "unavailable": results["unavailable"]}, {}


def _people_or_none(people: Future) -> list[dict]:
    """People are an extra; without TMDB the search still answers with titles."""
    try:
        return people.result(timeout=60)
    except (UpstreamError, OSError, TimeoutError) as error:
        log.warning("people search unavailable: %s", error)
        return []


def _profiles(handler: Handler, gateway: Gateway, device_id: str) -> tuple[int, dict, dict]:
    results = _both(gateway,
                    lambda: {"profiles": gateway.films.profiles(), "default": gateway.films.default_profile()},
                    lambda: {"profiles": gateway.shows.profiles(), "default": gateway.shows.default_profile()})
    return 200, {"films": results["films"] or {}, "shows": results["shows"] or {},
                 "unavailable": results["unavailable"]}, {}


def _add_film(handler: Handler, gateway: Gateway, device_id: str) -> tuple[int, dict, dict]:
    body = handler.json_body()
    tmdb_id, profile_id = _required_id(body, "id"), _optional_id(body, "profile")
    item = _added(lambda: gateway.films.add(tmdb_id, profile_id))
    log.info("device %s added film %d %r", device_id, tmdb_id, item["title"])
    return 201, {"item": item}, {}


def _add_show(handler: Handler, gateway: Gateway, device_id: str) -> tuple[int, dict, dict]:
    body = handler.json_body()
    tvdb_id, profile_id = _required_id(body, "id"), _optional_id(body, "profile")
    seasons = body.get("seasons")
    if seasons not in catalog.SEASON_CHOICES:
        raise HttpError(400, "invalid_seasons", "one of " + ", ".join(catalog.SEASON_CHOICES))
    item = _added(lambda: gateway.shows.add(tvdb_id, seasons, profile_id))
    log.info("device %s added show %d %r (%s)", device_id, tvdb_id, item["title"], seasons)
    return 201, {"item": item}, {}


def _list_episodes(handler: Handler, gateway: Gateway, device_id: str) -> tuple[int, dict, dict]:
    try:
        tvdb_id = int(handler.query_param("show"))
    except ValueError as error:
        raise HttpError(400, "invalid_show") from error
    if not 1 <= tvdb_id <= MAX_ID:
        raise HttpError(400, "invalid_show")
    try:
        return 200, gateway.episodes.list(tvdb_id), {}
    except UpstreamError as error:
        status = 404 if error.status == 404 else 502
        raise HttpError(status, "not_found" if status == 404 else "upstream_unavailable", error.service) from error


def _choose_episodes(handler: Handler, gateway: Gateway, device_id: str) -> tuple[int, dict, dict]:
    body = handler.json_body()
    tvdb_id, profile_id = _required_id(body, "show"), _optional_id(body, "profile")
    picks = _picks(body.get("episodes"))
    result = _added(lambda: gateway.episodes.choose(tvdb_id, picks, profile_id))
    log.info("device %s chose %d episodes of show %d %r", device_id, result["chosen"], tvdb_id, result["item"]["title"])
    return 200, result, {}


def _picks(value: object) -> set[tuple[int, int]]:
    """[[season, episode], ...] as a set; season 0 is specials."""
    if not isinstance(value, list) or len(value) > MAX_PICKS:
        raise HttpError(400, "invalid_episodes", f"a list of at most {MAX_PICKS} [season, episode] pairs")
    picks = set()
    for pair in value:
        if (not isinstance(pair, list) or len(pair) != 2
                or any(isinstance(n, bool) or not isinstance(n, int) for n in pair)
                or not 0 <= pair[0] <= 1000 or not 1 <= pair[1] <= 100_000):
            raise HttpError(400, "invalid_episodes", "each pick is [season, episode]")
        picks.add((pair[0], pair[1]))
    return picks


def _discover(handler: Handler, gateway: Gateway, device_id: str) -> tuple[int, dict, dict]:
    results = _both(gateway, gateway.films.discover, gateway.show_discovery.rows)
    return 200, {"rows": _interleave(results["films"] or [], results["shows"] or [])}, {}


def _genres(handler: Handler, gateway: Gateway, device_id: str) -> tuple[int, dict, dict]:
    return 200, genres(), {}


def _browse(handler: Handler, gateway: Gateway, device_id: str) -> tuple[int, dict, dict]:
    try:
        rows = gateway.browse.rows(handler.query_param("kind"), handler.query_param("genre"))
    except ValueError as error:
        raise HttpError(400, "invalid_request", str(error)) from error
    except UpstreamError as error:
        log.warning("browse unavailable: %s", error)
        raise HttpError(502, "upstream_unavailable", "TMDB did not answer") from error
    return 200, {"rows": rows}, {}


def _details(handler: Handler, gateway: Gateway, device_id: str) -> tuple[int, dict, dict]:
    title_id = handler.query_param("id")
    if not title_id.isdigit() or not 0 < int(title_id) < 2**31:
        raise HttpError(400, "invalid_request", "id must be a positive number")
    try:
        return 200, gateway.details.of(handler.query_param("kind"), int(title_id)), {}
    except ValueError as error:
        raise HttpError(400, "invalid_request", str(error)) from error
    except NoDetails as error:
        raise HttpError(404, "not_found") from error
    except UpstreamError as error:
        if error.status == 404:
            raise HttpError(404, "not_found") from error
        log.warning("details unavailable: %s", error)
        raise HttpError(502, "upstream_unavailable", "TMDB did not answer") from error


def _interleave(films: list, shows: list) -> list:
    """Film and show rows taking turns, starting with films, so neither kind is buried."""
    rows = []
    for index in range(max(len(films), len(shows))):
        rows.extend(films[index:index + 1] + shows[index:index + 1])
    return rows


def _library(handler: Handler, gateway: Gateway, device_id: str) -> tuple[int, dict, dict]:
    results = _both(gateway, gateway.films.library, gateway.shows.library)
    return 200, {"films": results["films"] or [], "shows": results["shows"] or [],
                 "storage": gateway.storage.usage(), "unavailable": results["unavailable"]}, {}


def _delete_title(handler: Handler, gateway: Gateway, device_id: str) -> tuple[int, dict, dict]:
    body = handler.json_body()
    _require_confirmation(body)
    kind, what, title_id = body.get("kind"), body.get("what"), _required_id(body, "id")
    actions = {
        ("film", "file"): lambda: gateway.films.delete_file(title_id),
        ("film", "title"): lambda: gateway.films.remove(title_id),
        ("show", "title"): lambda: gateway.shows.remove(title_id),
    }
    if (kind, what) not in actions:
        raise HttpError(400, "invalid_delete", "film file, film title or show title")
    freed = _deleted(actions[(kind, what)])
    log.info("device %s deleted %s %s %d (%d bytes)", device_id, kind, what, title_id, freed)
    return 200, {"freed": freed}, {}


def _delete_episodes(handler: Handler, gateway: Gateway, device_id: str) -> tuple[int, dict, dict]:
    body = handler.json_body()
    _require_confirmation(body)
    tvdb_id, picks = _required_id(body, "show"), _picks(body.get("episodes"))
    result = _deleted(lambda: gateway.episodes.delete_files(tvdb_id, picks))
    log.info("device %s deleted %d episode files of show %d (%d bytes)", device_id, result["deleted"], tvdb_id,
             result["freed"])
    return 200, result, {}


def _require_confirmation(body: dict) -> None:
    """Deletes must say so in the request itself, so no bug or retry can delete by accident."""
    if body.get("confirm") != "delete":
        raise HttpError(400, "confirmation_required", 'send "confirm": "delete"')


def _deleted(delete: Callable[[], object]) -> object:
    try:
        return delete()
    except NotFound as error:
        raise HttpError(404, "not_found") from error
    except UpstreamError as error:
        raise HttpError(502, "upstream_unavailable", error.service) from error


def _downloads(handler: Handler, gateway: Gateway, device_id: str) -> tuple[int, dict, dict]:
    results = _both(gateway, gateway.films.downloads, gateway.shows.downloads)
    return 200, {"downloads": (results["films"] or []) + (results["shows"] or []),
                 "unavailable": results["unavailable"]}, {}


def _recent(handler: Handler, gateway: Gateway, device_id: str) -> tuple[int, dict, dict]:
    results = _both(gateway, lambda: gateway.films.recent(RECENT_COUNT), lambda: gateway.shows.recent(RECENT_COUNT))
    merged = sorted((results["films"] or []) + (results["shows"] or []), key=lambda pair: pair[0], reverse=True)
    return 200, {"items": [item for _, item in merged[:RECENT_COUNT]], "unavailable": results["unavailable"]}, {}


def _watching(handler: Handler, gateway: Gateway, device_id: str) -> tuple[int, dict, dict]:
    try:
        return 200, gateway.watching.items(), {}
    except UpstreamError as error:
        log.warning("watching unavailable: %s", error)
        raise HttpError(502, "upstream_unavailable", "Plex did not answer") from error


def _both(gateway: Gateway, films_call: Callable[[], Any], shows_call: Callable[[], Any]) -> dict:
    """Runs the Radarr and Sonarr calls side by side; one failing leaves the other's result."""
    futures = {"films": gateway.pool.submit(films_call), "shows": gateway.pool.submit(shows_call)}
    results: dict = {"unavailable": []}
    for name, future in futures.items():
        try:
            results[name] = future.result(timeout=60)
        except (UpstreamError, OSError, TimeoutError) as error:
            log.warning("%s unavailable: %s", name, error)
            results[name] = None
            results["unavailable"].append(name)
    if len(results["unavailable"]) == 2:
        raise HttpError(502, "upstream_unavailable", "Radarr and Sonarr did not answer")
    return results


def _added(add: Callable[[], dict]) -> dict:
    """Runs an add and turns its failures into HTTP errors the TV can explain."""
    try:
        return add()
    except NotFound as error:
        raise HttpError(404, "not_found") from error
    except AlreadyAdded as error:
        raise HttpError(409, "already_added", "", {"item": error.item}) from error
    except ValueError as error:
        raise HttpError(400, "invalid_request", str(error)) from error
    except NoRootFolder as error:
        raise HttpError(502, "no_root_folder", str(error)) from error
    except UpstreamError as error:
        if 400 <= error.status < 500:
            raise HttpError(409, "rejected", error.detail[:300]) from error
        raise HttpError(502, "upstream_unavailable", error.service) from error


def _required_id(body: dict, name: str) -> int:
    value = body.get(name)
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= MAX_ID:
        raise HttpError(400, "invalid_" + name)
    return value


def _optional_id(body: dict, name: str) -> int | None:
    return None if body.get(name) is None else _required_id(body, name)


def _required_text(body: dict, name: str, limit: int) -> str:
    value = body.get(name)
    if not isinstance(value, str) or not 1 <= len(value) <= limit or not value.isprintable():
        raise HttpError(400, "invalid_" + name)
    return value


def _optional_text(body: dict, name: str, limit: int) -> str:
    return "" if body.get(name) is None else _required_text(body, name, limit)


ROUTES: dict[tuple[str, str], tuple[Callable[[Handler, Gateway, str], tuple[int, dict, dict]], bool]] = {
    ("GET", "/v1/health"): (_health, False),
    ("POST", "/v1/pair"): (_pair_start, False),
    ("POST", "/v1/pair/poll"): (_pair_poll, False),
    ("GET", "/v1/search"): (_search, True),
    ("GET", "/v1/profiles"): (_profiles, True),
    ("POST", "/v1/films"): (_add_film, True),
    ("POST", "/v1/shows"): (_add_show, True),
    ("GET", "/v1/episodes"): (_list_episodes, True),
    ("POST", "/v1/episodes"): (_choose_episodes, True),
    ("GET", "/v1/discover"): (_discover, True),
    ("GET", "/v1/genres"): (_genres, True),
    ("GET", "/v1/browse"): (_browse, True),
    ("GET", "/v1/details"): (_details, True),
    ("GET", "/v1/library"): (_library, True),
    ("POST", "/v1/library/delete"): (_delete_title, True),
    ("POST", "/v1/library/episodes/delete"): (_delete_episodes, True),
    ("GET", "/v1/downloads"): (_downloads, True),
    ("GET", "/v1/recent"): (_recent, True),
    ("GET", "/v1/watching"): (_watching, True),
}
