"""Choosing everything, whole seasons or single episodes of a show.

Sonarr is the record: an episode is wanted exactly when it is monitored. Applying a choice makes
the monitored episodes equal the picked ones, marks a season monitored when all of it is picked
(so its later episodes come too), and searches for the picked episodes that have aired.
"""
from __future__ import annotations

import time
from typing import Callable

from . import catalog
from .guide import EpisodeGuide
from .library import NotFound, Shows
from ..upstream import UpstreamError

WAIT_FOR_EPISODES_SECONDS = 40
POLL_SECONDS = 1.5
MONITOR_BATCH = 500

Pick = tuple[int, int]


class Episodes:
    def __init__(self, shows: Shows, guide: EpisodeGuide,
                 sleep: Callable[[float], None] = time.sleep, clock: Callable[[], float] = time.monotonic) -> None:
        self.shows = shows
        self.guide = guide
        self.sleep = sleep
        self.clock = clock

    def list(self, tvdb_id: int) -> dict:
        """The show's episodes by season, with what is downloaded and wanted when Sonarr has it."""
        series = self.shows.library_series(tvdb_id)
        if series is None:
            return {"inLibrary": False, "seasons": catalog.season_list(self.guide.episodes(tvdb_id))}
        return {"inLibrary": True, "seasons": catalog.season_list(self._with_file_sizes(series["id"]))}

    def delete_files(self, tvdb_id: int, picks: set[Pick]) -> dict:
        """Deletes the files of the picked episodes and stops Sonarr fetching them again."""
        series = self.shows.library_series(tvdb_id)
        if series is None:
            raise NotFound(tvdb_id)
        episodes = self._with_file_sizes(series["id"])
        doomed = [e for e in episodes if (e.get("seasonNumber"), e.get("episodeNumber")) in picks and e.get("hasFile")]
        file_ids = sorted({e["episodeFileId"] for e in doomed if e.get("episodeFileId")})
        sizes = {e["episodeFileId"]: catalog.as_int(e.get("fileSize")) for e in doomed if e.get("episodeFileId")}
        for file_id in file_ids:
            self.shows.upstream.delete(f"/api/v3/episodefile/{file_id}")
        self._monitor(sorted(e["id"] for e in doomed), False)
        return {"deleted": len(doomed), "freed": sum(sizes[f] for f in file_ids)}

    def _with_file_sizes(self, series_id: int) -> list[dict]:
        """Sonarr's episodes, each with the size of its file (0 when it has none)."""
        files = self.shows.upstream.get("/api/v3/episodefile", seriesId=series_id) or []
        sizes = {f.get("id"): catalog.as_int(f.get("size")) for f in files if isinstance(f, dict)}
        episodes = self._episodes(series_id)
        for episode in episodes:
            episode["fileSize"] = sizes.get(episode.get("episodeFileId"), 0)
        return episodes

    def choose(self, tvdb_id: int, picks: set[Pick], profile_id: int | None = None) -> dict:
        """Makes the picked episodes the wanted ones, adding the show first if needed, and searches for them."""
        series = self.shows.library_series(tvdb_id)
        just_added = series is None
        if just_added:
            series = self.shows.add_unmonitored(tvdb_id, profile_id)
        episodes = self._wait_for_episodes(series["id"]) if just_added else self._episodes(series["id"])
        numbered = {(e.get("seasonNumber"), e.get("episodeNumber")): e for e in episodes}
        chosen = [numbered[p] for p in sorted(picks) if p in numbered]

        self._set_seasons(series["id"], picks, episodes)
        chosen_ids = {e["id"] for e in chosen}
        self._monitor(sorted(chosen_ids), True)
        self._monitor(sorted(e["id"] for e in episodes if e["id"] not in chosen_ids), False)
        to_search = [e["id"] for e in chosen if not e.get("hasFile") and catalog.has_aired(e)]
        if to_search:
            self.shows.upstream.post("/api/v3/command", {"name": "EpisodeSearch", "episodeIds": to_search})
        fresh = self.shows.upstream.get(f"/api/v3/series/{series['id']}") or series
        return {"item": catalog.show_item(fresh), "chosen": len(chosen), "searching": len(to_search),
                "unmatched": len(picks) - len(chosen)}

    def _episodes(self, series_id: int) -> list[dict]:
        return [e for e in self.shows.upstream.get("/api/v3/episode", seriesId=series_id) or []
                if isinstance(e, dict) and isinstance(e.get("id"), int)]

    def _wait_for_episodes(self, series_id: int) -> list[dict]:
        """A new series gets its episodes from Sonarr's refresh a few seconds after it is added."""
        deadline = self.clock() + WAIT_FOR_EPISODES_SECONDS
        previous: list[dict] = []
        while self.clock() < deadline:
            episodes = self._episodes(series_id)
            if episodes and len(episodes) == len(previous):
                return episodes
            previous = episodes
            self.sleep(POLL_SECONDS)
        if previous:
            return previous
        raise UpstreamError("Sonarr", "the new show's episodes did not arrive in time")

    def _set_seasons(self, series_id: int, picks: set[Pick], episodes: list[dict]) -> None:
        """A season is monitored when every one of its episodes is picked; the series when anything is."""
        series = self.shows.upstream.get(f"/api/v3/series/{series_id}")
        by_season: dict[int, set[Pick]] = {}
        for e in episodes:
            by_season.setdefault(e.get("seasonNumber"), set()).add((e.get("seasonNumber"), e.get("episodeNumber")))
        for season in series.get("seasons") or []:
            numbers = by_season.get(season.get("seasonNumber"), set())
            season["monitored"] = bool(numbers) and numbers <= picks
        series["monitored"] = bool(picks)
        if "monitorNewItems" in series:
            regular = set().union(*(n for s, n in by_season.items() if s and s > 0)) if by_season else set()
            series["monitorNewItems"] = "all" if regular and regular <= picks else "none"
        self.shows.upstream.put(f"/api/v3/series/{series_id}", series)

    def _monitor(self, episode_ids: list[int], monitored: bool) -> None:
        for start in range(0, len(episode_ids), MONITOR_BATCH):
            batch = episode_ids[start:start + MONITOR_BATCH]
            self.shows.upstream.put("/api/v3/episode/monitor", {"episodeIds": batch, "monitored": monitored})

