"""Plex's Continue Watching, for the Continue watching row on the TV's home screen.

The owner's Plex token stays in Plex's own Preferences.xml and is read on each call, so it is never
copied. Pictures come from TMDB (a film's backdrop, an episode's still), so the TV needs no Plex token
to show them.
"""
from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Callable
from xml.etree import ElementTree

from ..arr import catalog
from ..tmdb.client import Tmdb
from ..tmdb.items import tmdb_image
from ..upstream import Upstream, UpstreamError

DEFAULT_PREFERENCES = Path.home() / "Library" / "Application Support" / "Plex Media Server" / "Preferences.xml"
MAX_ITEMS = 20
ART_SECONDS = 24 * 3600
MAX_CACHED_ART = 500
log = logging.getLogger("fetchd")


class Plex:
    """The owner's Plex Media Server on this machine; base_url "" when there is none."""

    def __init__(self, base_url: str, preferences: Path) -> None:
        self.base_url = base_url.rstrip("/")
        self.preferences = preferences

    def continue_watching(self) -> list[dict]:
        """The films and episodes on Plex's Continue Watching hub, newest first, with their TMDB, TVDB and IMDb ids."""
        reply = self._server().get("/hubs/continueWatching/items", includeGuids=1) or {}
        entries = (reply.get("MediaContainer") or {}).get("Metadata") or []
        return [entry for entry in entries if isinstance(entry, dict)]

    def machine_id(self) -> str:
        """The server's id, which Plex links name to play from it."""
        return self._setting("ProcessedMachineIdentifier")

    def _server(self) -> Upstream:
        if not self.base_url:
            raise UpstreamError("Plex", "not configured")
        return Upstream("Plex", self.base_url, self._setting("PlexOnlineToken"), "X-Plex-Token")

    def _setting(self, name: str) -> str:
        try:
            value = ElementTree.parse(self.preferences).getroot().get(name, "")
        except (OSError, ElementTree.ParseError) as error:
            raise UpstreamError("Plex", "Preferences.xml unreadable", 0, type(error).__name__) from error
        if not value:
            raise UpstreamError("Plex", f"no {name} in Preferences.xml")
        return value


class Watching:
    def __init__(self, plex: Plex, tmdb: Tmdb, clock: Callable[[], float] = time.monotonic) -> None:
        self.plex = plex
        self.tmdb = tmdb
        self.clock = clock
        self._lock = threading.Lock()
        self._art: dict[str, tuple[float, str]] = {}

    def items(self) -> dict:
        """What to resume, newest first, and the Plex server it plays from."""
        entries = [entry for entry in self.plex.continue_watching() if _resumable(entry)][:MAX_ITEMS]
        items = [dict(_item(entry), art=self._art_for(entry)) for entry in entries]
        return {"server": self.plex.machine_id(), "items": _in_order(items)}

    def _art_for(self, entry: dict) -> str:
        """A 16:9 picture from TMDB, cached for a day; "" when TMDB has none or does not answer."""
        key = str(entry["ratingKey"])
        with self._lock:
            cached = self._art.get(key)
            if cached and self.clock() - cached[0] < ART_SECONDS:
                return cached[1]
        try:
            art = tmdb_image(self._art_path(entry), "w780")
        except UpstreamError as error:
            log.info("no art for Plex item %s: %s", key, error)
            return ""
        with self._lock:
            if len(self._art) >= MAX_CACHED_ART:
                self._art.clear()
            self._art[key] = (self.clock(), art)
        return art

    def _art_path(self, entry: dict) -> object:
        ids = _external_ids(entry)
        film = entry.get("type") == "movie"
        if film and ids.get("tmdb", "").isdigit():
            return self.tmdb.film(int(ids["tmdb"])).get("backdrop_path")
        results, picture = ("movie_results", "backdrop_path") if film else ("tv_episode_results", "still_path")
        for source in ("tvdb", "imdb"):
            if source in ids:
                found = self.tmdb.find(ids[source], source + "_id").get(results) or []
                return found[0].get(picture) if found and isinstance(found[0], dict) else None
        return None


def _resumable(entry: dict) -> bool:
    return entry.get("type") in ("movie", "episode") and str(entry.get("ratingKey", "")).isdigit()


def _item(entry: dict) -> dict:
    episode = entry.get("type") == "episode"
    return {
        "kind": "episode" if episode else "film",
        "key": str(entry["ratingKey"]),
        "showKey": _digits(entry.get("grandparentRatingKey")) if episode else "",
        "seasonKey": _digits(entry.get("parentRatingKey")) if episode else "",
        "title": catalog.plain_text(entry.get("grandparentTitle") if episode else entry.get("title")),
        "episodeTitle": catalog.plain_text(entry.get("title")) if episode else "",
        "season": catalog.as_int(entry.get("parentIndex")) if episode else 0,
        "episode": catalog.as_int(entry.get("index")) if episode else 0,
        "position": catalog.as_int(entry.get("viewOffset")),
        "duration": catalog.as_int(entry.get("duration")),
        "watchedAt": catalog.as_int(entry.get("lastViewedAt")),
    }


def _digits(value: object) -> str:
    """Plex's id for a show or season, which the TV's link to an episode names; "" when it is not a number."""
    text = str(value or "")
    return text if text.isdigit() else ""


def _in_order(items: list[dict]) -> list[dict]:
    """Plex lists the next episode of a show without a time of its own; it takes the one before it."""
    for before, item in zip(items, items[1:]):
        if not item["watchedAt"]:
            item["watchedAt"] = before["watchedAt"]
    return items


def _external_ids(entry: dict) -> dict[str, str]:
    """{"tmdb": "9625", "imdb": "tt0116421", "tvdb": "..."} from Plex's Guid list."""
    ids = {}
    for guid in entry.get("Guid") or []:
        source, _, value = str(guid.get("id", "") if isinstance(guid, dict) else "").partition("://")
        if source in ("tmdb", "tvdb", "imdb") and value.isalnum():
            ids.setdefault(source, value)
    return ids
