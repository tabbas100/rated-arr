"""The only things the gateway does with Radarr and Sonarr: search, add, and report progress."""
from __future__ import annotations

import threading
import time
from typing import Callable

from . import catalog
from ..upstream import Upstream, UpstreamError

MAX_RESULTS = 20
QUEUE_PAGE = 500
# "Up to 1080p" takes anything from SD to 1080p, so old and obscure titles can be found; HD-1080p is the
# fallback on servers without it.
PREFERRED_PROFILES = ("Up to 1080p", "HD-1080p")
DISCOVER_ROW = 20
DISCOVER_TTL_SECONDS = 15 * 60
# Row ids in the order the TV shows them; a film appears only in the first row it belongs to.
DISCOVER_ROWS = (("recommended", "isRecommendation"), ("trending", "isTrending"), ("popular", "isPopular"))


def allows_disc_images(profile: dict) -> bool:
    """True when the profile lets Radarr grab a full Blu-ray disc image (quality BR-DISK)."""
    for item in profile.get("items") or []:
        qualities = [item] + list(item.get("items") or [])
        for quality in qualities:
            name = ((quality.get("quality") or {}).get("name") or "").upper()
            if name == "BR-DISK" and item.get("allowed") and quality.get("allowed", True):
                return True
    return False


class AlreadyAdded(Exception):
    """The title is already in the library."""

    def __init__(self, item: dict) -> None:
        super().__init__(item.get("title", ""))
        self.item = item


class NotFound(Exception):
    """No title with that id exists."""


class NoRootFolder(Exception):
    """The server has no root folder to put new titles in."""


class _Library:
    """What Radarr and Sonarr have in common: profiles, root folders, the queue and the newest titles."""

    def __init__(self, upstream: Upstream, root_folder: str = "", profile_name: str = "") -> None:
        self.upstream = upstream
        self._root_folder = root_folder
        self._profile_name = profile_name

    def profiles(self) -> list[dict]:
        """Quality profiles as {id, name}."""
        return [
            {"id": int(p["id"]), "name": str(p.get("name", ""))[:80]}
            for p in self.upstream.get("/api/v3/qualityprofile") or []
            if isinstance(p, dict) and isinstance(p.get("id"), int)
        ]

    def default_profile(self) -> int:
        """The configured profile by name, else Up to 1080p or HD-1080p, else the first that refuses disc images.

        Never a profile that accepts BR-DISK when another exists: Radarr then grabs whole Blu-ray
        .iso images, which Plex cannot play or list.
        """
        raw = [p for p in self.upstream.get("/api/v3/qualityprofile") or [] if isinstance(p, dict)
               and isinstance(p.get("id"), int)]
        if not raw:
            raise UpstreamError(self.upstream.name, "no quality profiles")
        for wanted in (self._profile_name, *PREFERRED_PROFILES):
            named = [p["id"] for p in raw if wanted and str(p.get("name", "")).lower() == wanted.lower()]
            if named:
                return named[0]
        playable = [p["id"] for p in raw if not allows_disc_images(p)]
        return playable[0] if playable else raw[0]["id"]

    def checked_profile(self, profile_id: int | None) -> int:
        """The requested profile if the server has it, the default when none was requested."""
        if profile_id is None:
            return self.default_profile()
        if profile_id not in {p["id"] for p in self.profiles()}:
            raise ValueError("unknown quality profile")
        return profile_id

    def root_folder(self) -> str:
        """The configured root folder if the server knows it, else its first one."""
        folders = [f.get("path", "") for f in self.upstream.get("/api/v3/rootfolder") or [] if isinstance(f, dict)]
        folders = [f for f in folders if f]
        if self._root_folder:
            if self._root_folder not in folders:
                raise NoRootFolder(f"{self._root_folder} is not a root folder of {self.upstream.name}")
            return self._root_folder
        if not folders:
            raise NoRootFolder(f"{self.upstream.name} has no root folder")
        return folders[0]

    def _queue(self, kind: str, **include: bool) -> list[dict]:
        page = self.upstream.get("/api/v3/queue", page=1, pageSize=QUEUE_PAGE, **include) or {}
        records = page.get("records", []) if isinstance(page, dict) else page
        return [catalog.download_item(r, kind) for r in records if isinstance(r, dict)]

    def _recent(self, path: str, to_item: Callable[[dict], dict], count: int) -> list[tuple[str, dict]]:
        entries = [e for e in self.upstream.get(path) or [] if isinstance(e, dict)]
        entries.sort(key=lambda e: str(e.get("added", "")), reverse=True)
        return [(str(e.get("added", "")), to_item(e)) for e in entries[:count]]


class Films(_Library):
    """Radarr."""

    def __init__(self, upstream: Upstream, root_folder: str = "", profile_name: str = "",
                 clock: Callable[[], float] = time.monotonic) -> None:
        super().__init__(upstream, root_folder, profile_name)
        self._clock = clock
        self._discover_lock = threading.Lock()
        self._discover_cache: tuple[float, list[dict]] | None = None

    def discover(self) -> list[dict]:
        """Radarr's Discover as rows of films not in the library: recommended from your library, trending, popular."""
        with self._discover_lock:
            if self._discover_cache and self._clock() - self._discover_cache[0] < DISCOVER_TTL_SECONDS:
                return self._discover_cache[1]
            rows = self._discover_rows()
            self._discover_cache = (self._clock(), rows)
            return rows

    def _discover_rows(self) -> list[dict]:
        entries = self.upstream.get("/api/v3/importlist/movie", includeRecommendations=True, includeTrending=True,
                                    includePopular=True) or []
        fresh = [e for e in entries if isinstance(e, dict) and not e.get("isExisting") and not e.get("isExcluded")]
        shown: set[int] = set()
        rows = []
        for row_id, flag in DISCOVER_ROWS:
            items = []
            for entry in fresh:
                if entry.get(flag) and entry.get("tmdbId") not in shown and len(items) < DISCOVER_ROW:
                    shown.add(entry.get("tmdbId"))
                    items.append(catalog.film_item(entry))
            if items:
                rows.append({"id": row_id, "items": items})
        return rows

    def search(self, term: str) -> list[dict]:
        results = self.upstream.get("/api/v3/movie/lookup", term=term) or []
        return [catalog.film_item(r) for r in results[:MAX_RESULTS] if isinstance(r, dict)]

    def add(self, tmdb_id: int, profile_id: int | None = None) -> dict:
        """Adds the film and starts a search for it; AlreadyAdded if it is in the library."""
        existing = self._in_library(tmdb_id)
        if existing:
            raise AlreadyAdded(catalog.film_item(existing))
        lookup = self._lookup(tmdb_id)
        payload = catalog.film_payload(lookup, self.checked_profile(profile_id), self.root_folder())
        return catalog.film_item(self.upstream.post("/api/v3/movie", payload) or lookup)

    def _in_library(self, tmdb_id: int) -> dict | None:
        """The library entry for this film; Radarr's lookup by TMDB id does not say whether it is added."""
        matches = self.upstream.get("/api/v3/movie", tmdbId=tmdb_id) or []
        return next((m for m in matches if isinstance(m, dict) and m.get("tmdbId") == tmdb_id), None)

    def downloads(self) -> list[dict]:
        return self._queue("film", includeMovie=True)

    def library(self) -> list[dict]:
        return [catalog.library_film(m) for m in self.upstream.get("/api/v3/movie") or [] if isinstance(m, dict)]

    def delete_file(self, tmdb_id: int) -> int:
        """Deletes the film's file and stops Radarr fetching it again; returns the bytes freed."""
        movie = self._in_library(tmdb_id)
        movie_file = (movie or {}).get("movieFile") or {}
        if not movie or not movie_file.get("id"):
            raise NotFound(tmdb_id)
        self.upstream.delete(f"/api/v3/moviefile/{movie_file['id']}")
        movie = self.upstream.get(f"/api/v3/movie/{movie['id']}")
        movie["monitored"] = False
        self.upstream.put(f"/api/v3/movie/{movie['id']}", movie)
        return catalog.as_int(movie_file.get("size"))

    def remove(self, tmdb_id: int) -> int:
        """Removes the film from Radarr together with its file; returns the bytes freed."""
        movie = self._in_library(tmdb_id)
        if not movie:
            raise NotFound(tmdb_id)
        self.upstream.delete(f"/api/v3/movie/{movie['id']}", deleteFiles=True, addImportExclusion=False)
        return catalog.as_int(movie.get("sizeOnDisk"))

    def recent(self, count: int) -> list[tuple[str, dict]]:
        return self._recent("/api/v3/movie", catalog.film_item, count)

    def _lookup(self, tmdb_id: int) -> dict:
        try:
            lookup = self.upstream.get("/api/v3/movie/lookup/tmdb", tmdbId=tmdb_id)
        except UpstreamError as error:
            # Radarr answers an unknown TMDB id with a 404, or with a 500 saying "was not found".
            if error.status == 404 or "not found" in error.detail.lower():
                raise NotFound(tmdb_id) from error
            raise
        if not isinstance(lookup, dict) or lookup.get("tmdbId") != tmdb_id:
            raise NotFound(tmdb_id)
        return lookup


class Shows(_Library):
    """Sonarr, version 3 or 4."""

    def __init__(self, upstream: Upstream, root_folder: str = "", profile_name: str = "") -> None:
        super().__init__(upstream, root_folder, profile_name)
        self._major_version = 0

    def search(self, term: str) -> list[dict]:
        """Matching shows; one already in the library is described from the library, because Sonarr's
        lookup reports zero downloaded episodes even for a show with hundreds on disk."""
        results = self.upstream.get("/api/v3/series/lookup", term=term) or []
        library = {s.get("tvdbId"): s for s in self.upstream.get("/api/v3/series") or [] if isinstance(s, dict)}
        return [catalog.show_item(library.get(r.get("tvdbId"), r))
                for r in results[:MAX_RESULTS] if isinstance(r, dict)]

    def add(self, tvdb_id: int, seasons: str, profile_id: int | None = None) -> dict:
        """Adds the show with the chosen seasons and searches for them; AlreadyAdded if it is in the library."""
        if seasons not in catalog.SEASON_CHOICES:
            raise ValueError("unknown season choice")
        lookup = self._lookup(tvdb_id)
        if catalog.show_item(lookup)["inLibrary"]:
            raise AlreadyAdded(catalog.show_item(lookup))
        payload = catalog.show_payload(lookup, self.checked_profile(profile_id), self.root_folder(), seasons,
                                       self._language_profile())
        return catalog.show_item(self.upstream.post("/api/v3/series", payload) or lookup)

    def library_series(self, tvdb_id: int) -> dict | None:
        """The series as Sonarr has it, or None when it is not in the library."""
        return next((s for s in self.upstream.get("/api/v3/series") or []
                     if isinstance(s, dict) and s.get("tvdbId") == tvdb_id), None)

    def add_unmonitored(self, tvdb_id: int, profile_id: int | None = None) -> dict:
        """Adds the show with nothing monitored and no search, so chosen episodes can be applied after."""
        lookup = self._lookup(tvdb_id)
        payload = catalog.show_payload(lookup, self.checked_profile(profile_id), self.root_folder(),
                                       catalog.NOTHING_YET, self._language_profile())
        return self.upstream.post("/api/v3/series", payload)

    def downloads(self) -> list[dict]:
        return self._queue("show", includeSeries=True, includeEpisode=True)

    def library(self) -> list[dict]:
        return [catalog.library_show(s) for s in self.upstream.get("/api/v3/series") or [] if isinstance(s, dict)]

    def remove(self, tvdb_id: int) -> int:
        """Removes the show from Sonarr together with its files; returns the bytes freed."""
        series = self.library_series(tvdb_id)
        if not series:
            raise NotFound(tvdb_id)
        self.upstream.delete(f"/api/v3/series/{series['id']}", deleteFiles=True, addImportListExclusion=False)
        return catalog.as_int((series.get("statistics") or {}).get("sizeOnDisk"))

    def recent(self, count: int) -> list[tuple[str, dict]]:
        return self._recent("/api/v3/series", catalog.show_item, count)

    def _lookup(self, tvdb_id: int) -> dict:
        results = self.upstream.get("/api/v3/series/lookup", term=f"tvdb:{tvdb_id}") or []
        for result in results:
            if isinstance(result, dict) and result.get("tvdbId") == tvdb_id:
                return result
        raise NotFound(tvdb_id)

    def _language_profile(self) -> int:
        """Sonarr 3 needs a language profile on every new series; Sonarr 4 has none."""
        if self._version() >= 4:
            return 0
        profiles = self.upstream.get("/api/v3/languageprofile") or []
        ids = [p["id"] for p in profiles if isinstance(p, dict) and isinstance(p.get("id"), int)]
        return ids[0] if ids else 0

    def _version(self) -> int:
        if not self._major_version:
            version = str((self.upstream.get("/api/v3/system/status") or {}).get("version", "0"))
            self._major_version = int(version.split(".")[0] or 0) if version.split(".")[0].isdigit() else 0
        return self._major_version
