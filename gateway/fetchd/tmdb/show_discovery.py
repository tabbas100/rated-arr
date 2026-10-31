"""Shows to discover from TMDB: recommendations from shows in the library, trending, top rated.

Every suggestion is resolved to its TVDB id, so it can be added through Sonarr like any other show;
shows already in the library, or without a TVDB id, are left out. Rows are cached for 3 hours.
"""
from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Callable

from ..arr.library import Shows
from .client import Tmdb
from .items import tmdb_show_item
from ..upstream import UpstreamError

ROW_SIZE = 20
ROWS_TTL_SECONDS = 3 * 3600
BECAUSE_YOU_HAVE = 2


class ShowDiscovery:
    def __init__(self, shows: Shows, tmdb: Tmdb, clock: Callable[[], float] = time.monotonic) -> None:
        self.shows = shows
        self.tmdb = tmdb
        self.clock = clock
        self._lock = threading.Lock()
        self._cache: tuple[float, list[dict]] | None = None
        self._pool = ThreadPoolExecutor(max_workers=8)

    def rows(self) -> list[dict]:
        """Rows of show suggestions; none when TMDB has no key or does not answer."""
        if not self.tmdb.available():
            return []
        with self._lock:
            if self._cache and self.clock() - self._cache[0] < ROWS_TTL_SECONDS:
                return self._cache[1]
            try:
                rows = self._build()
            except UpstreamError:
                return []
            self._cache = (self.clock(), rows)
            return rows

    def _build(self) -> list[dict]:
        library = [s for s in self.shows.upstream.get("/api/v3/series") or [] if isinstance(s, dict)]
        owned = {s.get("tvdbId") for s in library}
        shown: set[int] = set()
        rows = []
        newest = sorted((s for s in library if s.get("tmdbId")), key=lambda s: str(s.get("added", "")), reverse=True)
        for series in newest[:BECAUSE_YOU_HAVE]:
            rows.append(self._row("becauseYouHave", self.tmdb.recommendations(series["tmdbId"]), owned, shown,
                                  subject=str(series.get("title", ""))[:80]))
        rows.append(self._row("trendingShows", self.tmdb.trending_shows(), owned, shown))
        rows.append(self._row("topRatedShows", self.tmdb.top_rated_shows(), owned, shown))
        return [row for row in rows if row["items"]]

    def _row(self, row_id: str, results: list[dict], owned: set, shown: set, subject: str = "") -> dict:
        details = list(self._pool.map(self._details_or_none, [r.get("id") for r in results if isinstance(r.get("id"), int)]))
        items = []
        for show in details:
            item = tmdb_show_item(show) if show else None
            if item and item["id"] not in owned and item["id"] not in shown and len(items) < ROW_SIZE:
                shown.add(item["id"])
                items.append(item)
        row = {"id": row_id, "source": "tmdb", "items": items}
        if subject:
            row["subject"] = subject
        return row

    def _details_or_none(self, tmdb_id: int) -> dict | None:
        try:
            return self.tmdb.show(tmdb_id)
        except UpstreamError:
            return None
