"""Search by person: the films and shows of the actor or director whose name matches the search.

Title search alone misses people; "seagal" finds documentaries about Steven Seagal, not his films.
TMDB knows the credits. Films are keyed by their TMDB id, which Radarr adds by; shows are resolved to
their TVDB id for Sonarr, and shows without one are left out. Results are cached for an hour.
"""
from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Callable

from ..arr import catalog
from ..arr.library import Films, Shows
from .client import Tmdb
from .items import tmdb_film_item, tmdb_show_item
from ..upstream import UpstreamError

MAX_FILMS = 40
MAX_SHOWS = 10
MIN_SHOW_EPISODES = 3
CACHE_SECONDS = 3600
MAX_CACHED = 200


class People:
    def __init__(self, films: Films, shows: Shows, tmdb: Tmdb, clock: Callable[[], float] = time.monotonic) -> None:
        self.films = films
        self.shows = shows
        self.tmdb = tmdb
        self.clock = clock
        self._lock = threading.Lock()
        self._cache: dict[str, tuple[float, list[dict]]] = {}
        self._pool = ThreadPoolExecutor(max_workers=8)

    def search(self, term: str) -> list[dict]:
        """The best-known person whose name matches the search, with their films and shows; [] for none."""
        if not self.tmdb.available():
            return []
        key = term.strip().lower()
        with self._lock:
            cached = self._cache.get(key)
            if cached and self.clock() - cached[0] < CACHE_SECONDS:
                return cached[1]
        person = best_match(term, self.tmdb.people(term))
        found = [{**self._credits(person), "named": is_name(term, str(person.get("name", "")))}] if person else []
        with self._lock:
            if len(self._cache) >= MAX_CACHED:
                self._cache.clear()
            self._cache[key] = (self.clock(), found)
        return found

    def _credits(self, person: dict) -> dict:
        return {"name": catalog.plain_text(person.get("name"), 80),
                "directing": person.get("known_for_department") == "Directing",
                "films": self._films(person["id"]),
                "shows": self._shows(person["id"])}

    def _films(self, person_id: int) -> list[dict]:
        credits = self.tmdb.person_films(person_id)
        directed = [c for c in credits.get("crew") or [] if isinstance(c, dict) and c.get("job") == "Director"]
        acted = [c for c in credits.get("cast") or [] if isinstance(c, dict)]
        films = {c["id"]: c for c in acted + directed if isinstance(c.get("id"), int) and c.get("release_date")}
        known = sorted(films.values(), key=lambda c: c.get("vote_count") or 0, reverse=True)[:MAX_FILMS]
        owned = {m.get("tmdbId"): bool(m.get("hasFile")) for m in self.films.upstream.get("/api/v3/movie") or []
                 if isinstance(m, dict)}
        genres = self.tmdb.film_genres()
        return [tmdb_film_item(film, owned, genres) for film in known]

    def _shows(self, person_id: int) -> list[dict]:
        credits = self.tmdb.person_shows(person_id)
        regular = [c for c in credits.get("cast") or [] if isinstance(c, dict) and isinstance(c.get("id"), int)
                   and (c.get("episode_count") or 0) >= MIN_SHOW_EPISODES and not is_chatter(c)]
        regular.sort(key=lambda c: c.get("episode_count") or 0, reverse=True)
        details = self._pool.map(self._details_or_none, [c["id"] for c in regular[:MAX_SHOWS]])
        owned = {s.get("tvdbId") for s in self.shows.upstream.get("/api/v3/series") or [] if isinstance(s, dict)}
        items = {}
        for item in (tmdb_show_item(show) for show in details if show):
            if item:
                items.setdefault(item["id"], {**item, "inLibrary": item["id"] in owned})
        return list(items.values())

    def _details_or_none(self, tmdb_id: int) -> dict | None:
        try:
            return self.tmdb.show(tmdb_id)
        except UpstreamError:
            return None


def best_match(term: str, people: list[dict]) -> dict | None:
    """The most popular person whose name has a word starting with each word of the search."""
    words = term.lower().split()
    if not words or len("".join(words)) < 3:
        return None
    matches = [p for p in people if isinstance(p.get("id"), int) and _name_matches(words, str(p.get("name", "")))]
    return max(matches, key=lambda p: p.get("popularity") or 0, default=None)


def is_name(term: str, name: str) -> bool:
    """True when the search is the person's full name or surname: they are what was asked for, so they go first."""
    words, name_words = term.lower().split(), name.lower().split()
    return bool(words) and (words == name_words or words == name_words[-1:])


def _name_matches(words: list[str], name: str) -> bool:
    name_words = name.lower().split()
    return all(any(part.startswith(word) for part in name_words) for word in words)


def is_chatter(show: dict) -> bool:
    """Talk and news shows: a guest appearance there is not the person's show."""
    news, talk = 10763, 10767
    return bool({news, talk} & set(show.get("genre_ids") or []))
