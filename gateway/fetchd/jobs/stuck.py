"""Dead downloads: torrents that make no progress for a day are replaced with another copy.

Radarr and Sonarr never give up on a stalled torrent; it stays in the queue and blocks other copies of
the title. Run hourly, this remembers how much each download still had to go and since when. One that
has not moved for STUCK_HOURS is removed from qBittorrent, blocklisted, and searched for again.
Paused downloads, unmonitored titles and downloads already importing are left alone.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

from ..arr.catalog import download_message
from ..upstream import Upstream

STUCK_HOURS = 24

log = logging.getLogger("fetchd")


def dead_downloads(records: list[dict], seen: dict, now: datetime) -> tuple[list[dict], dict]:
    """The downloads stuck for STUCK_HOURS (one record each), and what to remember for the next run."""
    remembered, dead = {}, []
    for record in _one_per_download(records):
        if not _watched(record):
            continue
        download_id, left = record["downloadId"], record.get("sizeleft") or 0
        before = seen.get(download_id)
        since = before["since"] if before and before["sizeleft"] == left else now.isoformat()
        remembered[download_id] = {"sizeleft": left, "since": since}
        if now - datetime.fromisoformat(since) >= timedelta(hours=STUCK_HOURS):
            dead.append(record)
    return dead, remembered


def _one_per_download(records: list[dict]) -> list[dict]:
    """A season pack is one queue record per episode; they share a download id."""
    return list({r["downloadId"]: r for r in reversed(records) if r.get("downloadId")}.values())


def _watched(record: dict) -> bool:
    """Only downloads still downloading, not paused, for a title Radarr or Sonarr is told to get."""
    title = record.get("movie") or record.get("series") or {}
    return (record.get("trackedDownloadState") == "downloading" and record.get("status") != "paused"
            and title.get("monitored", True))


class StuckDownloads:
    def __init__(self, apps: list[Upstream], state_path: Path,
                 clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc)) -> None:
        self.apps = apps
        self.state_path = state_path
        self.clock = clock

    def replace_dead(self) -> None:
        seen = self._seen()
        remembered = {}
        for app in self.apps:
            records = app.get("/api/v3/queue", pageSize=500, includeMovie="true", includeSeries="true").get("records") or []
            dead, kept = dead_downloads(records, seen, self.clock())
            remembered.update(kept)
            for record in dead:
                self._replace(app, record)
                remembered.pop(record["downloadId"], None)
        self.state_path.write_text(json.dumps(remembered))
        self.state_path.chmod(0o600)

    def _replace(self, app: Upstream, record: dict) -> None:
        app.delete(f"/api/v3/queue/{record['id']}", removeFromClient="true", blocklist="true", skipRedownload="false")
        log.info("%s: replaced dead download %s (%s)", app.name, record.get("title", "?"),
                 download_message(record) or "no progress")

    def _seen(self) -> dict:
        try:
            return json.loads(self.state_path.read_text())
        except (OSError, ValueError):
            return {}
