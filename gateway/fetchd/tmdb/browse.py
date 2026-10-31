"""Browse by genre: TMDB's discover lists as rows, with "So bad it's good" first among film genres.

"So bad it's good" has three rows: films TMDB users tagged so-bad-it's-good, B-movies, and famous
flops (rated under 4.5 by at least 300 people). Each genre has a popular and a best-rated row.
Titles already in the library carry their badge. Rows are cached for six hours.
"""
from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Callable

from ..arr.library import Films, Shows
from .client import Tmdb
from .items import tmdb_film_item, tmdb_show_item
from ..upstream import UpstreamError

BAD = "bad"
FILM_GENRES = [(BAD, "So bad it's good"), ("28", "Action"), ("35", "Comedy"), ("27", "Horror"), ("878", "Science Fiction"),
               ("53", "Thriller"), ("80", "Crime"), ("12", "Adventure"), ("14", "Fantasy"), ("16", "Animation"),
               ("18", "Drama"), ("9648", "Mystery"), ("10749", "Romance"), ("10752", "War"), ("37", "Western"),
               ("99", "Documentary"), ("10751", "Family")]
SHOW_GENRES = [("35", "Comedy"), ("80", "Crime"), ("18", "Drama"), ("10765", "Sci-Fi & Fantasy"),
               ("10759", "Action & Adventure"), ("9648", "Mystery"), ("16", "Animation"), ("99", "Documentary"),
               ("10764", "Reality"), ("10768", "War & Politics"), ("37", "Western"), ("10751", "Family"), ("10762", "Kids")]
SO_BAD_KEYWORDS = "323812|383390"
B_MOVIE_KEYWORD = "11034"
CACHE_SECONDS = 6 * 3600


def genres() -> dict:
    return {"films": [{"id": i, "name": n} for i, n in FILM_GENRES], "shows": [{"id": i, "name": n} for i, n in SHOW_GENRES]}


def row_queries(kind: str, genre: str) -> list[tuple[str, dict]]:
    """The rows of one genre as (row id, TMDB discover query); ValueError for a genre not offered."""
    offered = {i for i, _ in (FILM_GENRES if kind == "film" else SHOW_GENRES)}
    if kind not in ("film", "show") or genre not in offered:
        raise ValueError("unknown genre")
    if genre == BAD:
        return [("soBad", {"with_keywords": SO_BAD_KEYWORDS, "sort_by": "vote_count.desc"}),
                ("bMovies", {"with_keywords": B_MOVIE_KEYWORD, "sort_by": "vote_count.desc"}),
                ("flops", {"vote_average.lte": 4.5, "vote_count.gte": 300, "sort_by": "vote_count.desc"})]
    return [("popular", {"with_genres": genre, "sort_by": "popularity.desc", "vote_count.gte": 50}),
            ("topRated", {"with_genres": genre, "sort_by": "vote_average.desc", "vote_count.gte": 300})]


class Browse:
    def __init__(self, films: Films, shows: Shows, tmdb: Tmdb, clock: Callable[[], float] = time.monotonic) -> None:
        self.films = films
        self.shows = shows
        self.tmdb = tmdb
        self.clock = clock
        self._lock = threading.Lock()
        self._cache: dict[tuple[str, str], tuple[float, list[dict]]] = {}
        self._pool = ThreadPoolExecutor(max_workers=8)

    def rows(self, kind: str, genre: str) -> list[dict]:
        """The genre's rows; ValueError for an unknown genre, UpstreamError when TMDB does not answer."""
        queries = row_queries(kind, genre)
        with self._lock:
            cached = self._cache.get((kind, genre))
            if cached and self.clock() - cached[0] < CACHE_SECONDS:
                return cached[1]
        built = [{"id": row_id, "source": "tmdb", "items": self._items(kind, query)} for row_id, query in queries]
        rows = [row for row in built if row["items"]]
        with self._lock:
            self._cache[(kind, genre)] = (self.clock(), rows)
        return rows

    def _items(self, kind: str, query: dict) -> list[dict]:
        if kind == "film":
            owned = {m.get("tmdbId"): bool(m.get("hasFile")) for m in self.films.upstream.get("/api/v3/movie") or []
                     if isinstance(m, dict)}
            genre_names = self.tmdb.film_genres()
            return [tmdb_film_item(r, owned, genre_names) for r in self.tmdb.discover("movie", query)
                    if isinstance(r.get("id"), int)]
        owned = {s.get("tvdbId") for s in self.shows.upstream.get("/api/v3/series") or [] if isinstance(s, dict)}
        ids = [r["id"] for r in self.tmdb.discover("tv", query) if isinstance(r.get("id"), int)]
        items = [tmdb_show_item(show) for show in self._pool.map(self._details_or_none, ids) if show]
        return [{**item, "inLibrary": item["id"] in owned} for item in items if item]

    def _details_or_none(self, tmdb_id: int) -> dict | None:
        try:
            return self.tmdb.show(tmdb_id)
        except UpstreamError:
            return None
