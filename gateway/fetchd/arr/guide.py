"""The episode guide for shows Sonarr does not have yet, from Sonarr's own metadata service.

Sonarr can only list episodes of series in its library. Its metadata service (SkyHook) is where
Sonarr gets those episodes from, so the season and episode numbers here are the ones Sonarr will
use once the show is added. The host is fixed and the only input is an integer TVDB id.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request

from ..upstream import UpstreamError

GUIDE_URL = "https://skyhook.sonarr.tv/v1/tvdb/shows/en/{tvdb_id}"
MAX_BYTES = 10 * 1024 * 1024
TIMEOUT_SECONDS = 20
NAME = "Episode guide"


class EpisodeGuide:
    """Fetches a show's episode list by TVDB id."""

    def episodes(self, tvdb_id: int) -> list[dict]:
        if not isinstance(tvdb_id, int) or isinstance(tvdb_id, bool) or tvdb_id <= 0:
            raise ValueError("invalid TVDB id")
        request = urllib.request.Request(GUIDE_URL.format(tvdb_id=tvdb_id), headers={"Accept": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
                raw = response.read(MAX_BYTES + 1)
        except urllib.error.HTTPError as error:
            raise UpstreamError(NAME, f"HTTP {error.code}", error.code) from error
        except (urllib.error.URLError, TimeoutError, ConnectionError) as error:
            raise UpstreamError(NAME, "unreachable", 0, str(getattr(error, "reason", error))) from error
        if len(raw) > MAX_BYTES:
            raise UpstreamError(NAME, "reply too large")
        try:
            episodes = json.loads(raw).get("episodes", [])
        except (ValueError, AttributeError) as error:
            raise UpstreamError(NAME, "reply is not a show") from error
        return [e for e in episodes if isinstance(e, dict)]
