"""Details for the title page from TMDB: cast with photos, director or creators, tagline, plot and rating.

Films are looked up by their TMDB id; shows by their TVDB id, which TMDB maps to its own. Details are
cached for a day.
"""
from __future__ import annotations

import threading
import time
from typing import Callable

from ..arr import catalog
from .client import Tmdb
from .items import tmdb_image

CAST_SIZE = 15
CACHE_SECONDS = 24 * 3600
MAX_CACHED = 500


class NoDetails(Exception):
    """TMDB does not know the title."""


class Details:
    def __init__(self, tmdb: Tmdb, clock: Callable[[], float] = time.monotonic) -> None:
        self.tmdb = tmdb
        self.clock = clock
        self._lock = threading.Lock()
        self._cache: dict[tuple[str, int], tuple[float, dict]] = {}

    def of(self, kind: str, title_id: int) -> dict:
        """kind "film" with a TMDB id, or "show" with a TVDB id; NoDetails when TMDB does not know it."""
        if kind not in ("film", "show"):
            raise ValueError("kind is film or show")
        with self._lock:
            cached = self._cache.get((kind, title_id))
            if cached and self.clock() - cached[0] < CACHE_SECONDS:
                return cached[1]
        found = self._film(title_id) if kind == "film" else self._show(title_id)
        with self._lock:
            if len(self._cache) >= MAX_CACHED:
                self._cache.clear()
            self._cache[(kind, title_id)] = (self.clock(), found)
        return found

    def _film(self, tmdb_id: int) -> dict:
        film = self.tmdb.film_details(tmdb_id)
        credits = film.get("credits") or {}
        directors = [c.get("name", "") for c in credits.get("crew") or [] if isinstance(c, dict) and c.get("job") == "Director"]
        cast = [_actor(c.get("name"), c.get("character"), c.get("profile_path")) for c in credits.get("cast") or []
                if isinstance(c, dict)]
        return _details(film, "Director", directors, cast, catalog.as_int(film.get("runtime")))

    def _show(self, tvdb_id: int) -> dict:
        matches = self.tmdb.find_by_tvdb(tvdb_id)
        if not matches:
            raise NoDetails(f"TVDB {tvdb_id} is not on TMDB")
        show = self.tmdb.show_details(matches[0]["id"])
        creators = [c.get("name", "") for c in show.get("created_by") or [] if isinstance(c, dict)]
        cast = [_actor(c.get("name"), _first_role(c), c.get("profile_path"))
                for c in (show.get("aggregate_credits") or {}).get("cast") or [] if isinstance(c, dict)]
        runtimes = [r for r in show.get("episode_run_time") or [] if isinstance(r, int)]
        return _details(show, "Created by", creators, cast, runtimes[0] if runtimes else 0)


def _details(title: dict, makers_role: str, makers: list[str], cast: list[dict], runtime: int) -> dict:
    rating = title.get("vote_average") or 0
    return {
        "tagline": catalog.plain_text(title.get("tagline"), 200),
        "overview": catalog.plain_text(title.get("overview"), catalog.MAX_OVERVIEW),
        "runtime": runtime,
        "rating": round(float(rating), 1) if isinstance(rating, (int, float)) and 0 < rating <= 10 else 0.0,
        "votes": catalog.as_int(title.get("vote_count")),
        "makersRole": makers_role,
        "makers": [catalog.plain_text(name, 80) for name in makers if name][:3],
        "cast": [actor for actor in cast if actor["name"]][:CAST_SIZE],
    }


def _actor(name: object, character: object, photo: object) -> dict:
    return {"name": catalog.plain_text(name, 80), "character": catalog.plain_text(character, 80),
            "photo": tmdb_image(photo, "w185")}


def _first_role(member: dict) -> str:
    roles = [r.get("character", "") for r in member.get("roles") or [] if isinstance(r, dict)]
    return next((role for role in roles if role), "")
