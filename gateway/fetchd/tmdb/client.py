"""TMDB, for suggesting shows. The key stays on the box in an owner-only file and is read on each use,
so it can be added or replaced without a restart. Only api.themoviedb.org is ever called.
"""
from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Callable

from ..upstream import UpstreamError

API = "https://api.themoviedb.org/3"
NAME = "TMDB"
TIMEOUT_SECONDS = 20
MAX_BYTES = 5 * 1024 * 1024
DETAILS_TTL_SECONDS = 24 * 3600
MAX_CACHED_DETAILS = 1000


class Tmdb:
    def __init__(self, key_path: Path, clock: Callable[[], float] = time.monotonic) -> None:
        self.key_path = key_path
        self.clock = clock
        self._details: dict[int, tuple[float, dict]] = {}
        self._film_genres: dict[int, str] = {}
        self._lock = threading.Lock()

    def available(self) -> bool:
        return bool(self._key())

    def trending_shows(self) -> list[dict]:
        return self._results("/trending/tv/week")

    def top_rated_shows(self) -> list[dict]:
        return self._results("/tv/top_rated")

    def recommendations(self, tmdb_id: int) -> list[dict]:
        return self._results(f"/tv/{int(tmdb_id)}/recommendations")

    def film_details(self, tmdb_id: int) -> dict:
        return self._get(f"/movie/{int(tmdb_id)}", {"append_to_response": "credits"})

    def show_details(self, tmdb_id: int) -> dict:
        return self._get(f"/tv/{int(tmdb_id)}", {"append_to_response": "aggregate_credits"})

    def find_by_tvdb(self, tvdb_id: int) -> list[dict]:
        """The TMDB shows with this TVDB id, usually one."""
        found = self.find(str(int(tvdb_id)), "tvdb_id").get("tv_results", [])
        return [r for r in found if isinstance(r, dict) and isinstance(r.get("id"), int)]

    def find(self, external_id: str, source: str) -> dict:
        """TMDB's films, shows and episodes with this id from another site; source is "tvdb_id" or "imdb_id"."""
        return self._get(f"/find/{urllib.parse.quote(external_id, safe='')}", {"external_source": source})

    def film(self, tmdb_id: int) -> dict:
        return self._get(f"/movie/{int(tmdb_id)}", {})

    def discover(self, kind: str, query: dict) -> list[dict]:
        """TMDB's discover list for "movie" or "tv", first page."""
        return [r for r in self._get(f"/discover/{kind}", query).get("results", []) if isinstance(r, dict)]

    def people(self, query: str) -> list[dict]:
        return [r for r in self._get("/search/person", {"query": query}).get("results", []) if isinstance(r, dict)]

    def person_films(self, person_id: int) -> dict:
        return self._get(f"/person/{int(person_id)}/movie_credits", {})

    def person_shows(self, person_id: int) -> dict:
        return self._get(f"/person/{int(person_id)}/tv_credits", {})

    def film_genres(self) -> dict[int, str]:
        """TMDB's film genres by id, fetched once; they rarely change."""
        with self._lock:
            if self._film_genres:
                return self._film_genres
        genres = {g["id"]: g["name"] for g in self._get("/genre/movie/list", {}).get("genres", [])
                  if isinstance(g, dict) and isinstance(g.get("id"), int) and isinstance(g.get("name"), str)}
        with self._lock:
            self._film_genres = genres
        return genres

    def show(self, tmdb_id: int) -> dict:
        """A show's details with its external ids (the TVDB id Sonarr needs), cached for a day."""
        with self._lock:
            cached = self._details.get(tmdb_id)
            if cached and self.clock() - cached[0] < DETAILS_TTL_SECONDS:
                return cached[1]
        details = self._get(f"/tv/{int(tmdb_id)}", {"append_to_response": "external_ids"})
        with self._lock:
            if len(self._details) >= MAX_CACHED_DETAILS:
                self._details.clear()
            self._details[tmdb_id] = (self.clock(), details)
        return details

    def _results(self, path: str) -> list[dict]:
        return [r for r in self._get(path, {}).get("results", []) if isinstance(r, dict)]

    def _get(self, path: str, query: dict) -> dict:
        key = self._key()
        if not key:
            raise UpstreamError(NAME, "no key")
        headers = {"Accept": "application/json"}
        if key.startswith("eyJ"):
            headers["Authorization"] = f"Bearer {key}"
        else:
            query = {**query, "api_key": key}
        url = API + path + ("?" + urllib.parse.urlencode(query) if query else "")
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=TIMEOUT_SECONDS) as reply:
                raw = reply.read(MAX_BYTES + 1)
        except urllib.error.HTTPError as error:
            raise UpstreamError(NAME, f"HTTP {error.code}", error.code) from error
        except (urllib.error.URLError, TimeoutError, ConnectionError) as error:
            raise UpstreamError(NAME, "unreachable") from error
        if len(raw) > MAX_BYTES:
            raise UpstreamError(NAME, "reply too large")
        try:
            data = json.loads(raw)
        except ValueError as error:
            raise UpstreamError(NAME, "reply is not JSON") from error
        if not isinstance(data, dict):
            raise UpstreamError(NAME, "unexpected reply")
        return data

    def _key(self) -> str:
        try:
            return self.key_path.read_text("utf-8").strip()
        except OSError:
            return ""
