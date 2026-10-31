"""Turns Radarr and Sonarr JSON into the gateway's public format, and builds the add requests.

Only plain values leave the gateway: no paths, ids of other systems or links outside the two image
hosts. Add requests are built here from the server's own lookup, never from what a client sends.
"""
from __future__ import annotations

import copy
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

IMAGE_HOSTS = {"image.tmdb.org", "artworks.thetvdb.com"}
SEASON_CHOICES = ("all", "latest", "first", "future")
# Internal: add with nothing monitored, so a list of chosen episodes can be applied afterwards.
NOTHING_YET = "none"
MAX_OVERVIEW = 1200
MAX_TEXT = 200


def film_item(lookup: dict) -> dict:
    """A Radarr movie (lookup result or library entry) as the TV sees it."""
    return {
        "kind": "film",
        "id": as_int(lookup.get("tmdbId")),
        "title": plain_text(lookup.get("title")),
        "year": as_int(lookup.get("year")),
        "overview": plain_text(lookup.get("overview"), MAX_OVERVIEW),
        "poster": _image(_poster_url(lookup), "w342"),
        "fanart": _image(_cover(lookup, "fanart"), "w1280"),
        "runtime": as_int(lookup.get("runtime")),
        "genres": _genres(lookup),
        "rating": _film_rating(lookup.get("ratings")),
        "network": "",
        "seasons": 0,
        "inLibrary": as_int(lookup.get("id")) > 0,
        "downloaded": bool(lookup.get("hasFile")) or as_int(lookup.get("movieFileId")) > 0,
    }


def show_item(lookup: dict) -> dict:
    """A Sonarr series (lookup result or library entry) as the TV sees it."""
    statistics = lookup.get("statistics") or {}
    return {
        "kind": "show",
        "id": as_int(lookup.get("tvdbId")),
        "title": plain_text(lookup.get("title")),
        "year": as_int(lookup.get("year")),
        "overview": plain_text(lookup.get("overview"), MAX_OVERVIEW),
        "poster": _image(_poster_url(lookup), "w342"),
        "fanart": _image(_cover(lookup, "fanart"), "w1280"),
        "runtime": as_int(lookup.get("runtime")),
        "genres": _genres(lookup),
        "rating": _rating_value(lookup.get("ratings")),
        "network": plain_text(lookup.get("network")),
        "seasons": _season_count(lookup),
        "inLibrary": as_int(lookup.get("id")) > 0,
        "downloaded": as_int(statistics.get("episodeFileCount")) > 0,
    }


def library_film(movie: dict) -> dict:
    """A film in Radarr's library with its size, file quality and any problem; no paths leave the box."""
    item = film_item(movie)
    movie_file = movie.get("movieFile") or {}
    item.update({
        "size": as_int(movie_file.get("size") or movie.get("sizeOnDisk")),
        "quality": plain_text(((movie_file.get("quality") or {}).get("quality") or {}).get("name"), 40),
        "problem": film_problem(movie),
    })
    return item


def film_problem(movie: dict) -> str:
    """"discImage" when the file is a whole Blu-ray or DVD image, which Plex cannot play; "" otherwise."""
    movie_file = movie.get("movieFile") or {}
    if not movie_file:
        return ""
    quality = ((movie_file.get("quality") or {}).get("quality") or {}).get("name") or ""
    name = str(movie_file.get("relativePath") or "").lower()
    return "discImage" if quality.upper() == "BR-DISK" or name.endswith((".iso", ".img")) else ""


def library_show(series: dict) -> dict:
    """A show in Sonarr's library with its size on disk."""
    item = show_item(series)
    statistics = series.get("statistics") or {}
    item.update({"size": as_int(statistics.get("sizeOnDisk")), "quality": "", "problem": ""})
    return item


def film_payload(lookup: dict, profile_id: int, root_folder: str) -> dict:
    """The body for POST /api/v3/movie: the lookup itself plus where and how to get it."""
    payload = copy.deepcopy(lookup)
    payload.update({
        "qualityProfileId": profile_id,
        "rootFolderPath": root_folder,
        "monitored": True,
        "minimumAvailability": "released",
        "addOptions": {"searchForMovie": True, "monitor": "movieOnly"},
    })
    return payload


def show_payload(lookup: dict, profile_id: int, root_folder: str, seasons: str, language_profile_id: int) -> dict:
    """The body for POST /api/v3/series. Season flags are set explicitly so Sonarr 3 and 4 agree."""
    if seasons not in SEASON_CHOICES and seasons != NOTHING_YET:
        raise ValueError(f"unknown season choice {seasons!r}")
    payload = copy.deepcopy(lookup)
    payload["seasons"] = _monitored_seasons(lookup.get("seasons") or [], seasons)
    payload.update({
        "qualityProfileId": profile_id,
        "rootFolderPath": root_folder,
        "seasonFolder": True,
        "monitored": True,
        "addOptions": {
            "monitor": {"future": "future", NOTHING_YET: "none"}.get(seasons, "unknown"),
            "searchForMissingEpisodes": seasons not in ("future", NOTHING_YET),
            "searchForCutoffUnmetEpisodes": False,
        },
    })
    if language_profile_id:
        payload["languageProfileId"] = language_profile_id
    return payload


def _monitored_seasons(seasons: list, choice: str) -> list:
    """Every season with its monitored flag for the choice; specials (season 0) are never monitored."""
    numbers = [as_int(s.get("seasonNumber")) for s in seasons if isinstance(s, dict)]
    regular = [n for n in numbers if n > 0]
    wanted = {
        "all": set(regular),
        "latest": {max(regular)} if regular else set(),
        "first": {min(regular)} if regular else set(),
        "future": set(),
        NOTHING_YET: set(),
    }[choice]
    return [{"seasonNumber": n, "monitored": n in wanted} for n in numbers]


def season_list(episodes: list, now: datetime | None = None) -> list[dict]:
    """Episodes grouped by season, regular seasons in order and specials (season 0) last.

    Works for Sonarr's own episodes (with hasFile and monitored) and for the episode guide of a
    show Sonarr does not have yet (neither field: nothing downloaded, nothing wanted).
    """
    now = now or datetime.now(timezone.utc)
    seasons: dict[int, list] = {}
    for episode in episodes:
        if not isinstance(episode, dict):
            continue
        season, number = as_int(episode.get("seasonNumber")), as_int(episode.get("episodeNumber"))
        if number <= 0 or season < 0:
            continue
        seasons.setdefault(season, []).append({
            "number": number,
            "title": plain_text(episode.get("title")),
            "airDate": plain_text(episode.get("airDate"), 10),
            "aired": has_aired(episode, now),
            "downloaded": bool(episode.get("hasFile")),
            "wanted": bool(episode.get("monitored")),
            "size": as_int(episode.get("fileSize")),
        })
    order = sorted(seasons, key=lambda n: (n == 0, n))
    return [{"number": n, "episodes": sorted(seasons[n], key=lambda e: e["number"])} for n in order]


def has_aired(episode: dict, now: datetime | None = None) -> bool:
    """True when the episode's air time is known and in the past."""
    now = now or datetime.now(timezone.utc)
    raw = plain_text(episode.get("airDateUtc"), 40)
    if not raw:
        return False
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")) <= now
    except ValueError:
        return False


def download_item(record: dict, kind: str) -> dict:
    """One queue record as the TV sees it."""
    media = record.get("movie" if kind == "film" else "series") or {}
    size, left = float(record.get("size") or 0), float(record.get("sizeleft") or 0)
    return {
        "kind": kind,
        "id": as_int(media.get("tmdbId" if kind == "film" else "tvdbId")),
        "title": plain_text(media.get("title") or record.get("title")),
        "detail": _download_detail(record, kind),
        "progress": round(max(0.0, min(1.0, (size - left) / size)), 3) if size > 0 else 0.0,
        "state": download_state(record),
        "message": download_message(record),
        "timeLeft": time_left(plain_text(record.get("timeleft"))),
        "poster": _image(_poster_url(media), "w342") if media else "",
    }


def download_message(record: dict) -> str:
    """Why a download needs attention, in Sonarr's or Radarr's words; "" when nothing is wrong."""
    for status in record.get("statusMessages") or []:
        for message in (status.get("messages") or []) if isinstance(status, dict) else []:
            if isinstance(message, str) and message.strip():
                return message.strip()[:160]
    return plain_text(record.get("errorMessage"), 160)


def download_state(record: dict) -> str:
    """One of queued, downloading, paused, importing or problem."""
    tracked = plain_text(record.get("trackedDownloadStatus")).lower()
    tracked_state = plain_text(record.get("trackedDownloadState")).lower()
    status = plain_text(record.get("status")).lower()
    if tracked in ("warning", "error") or status in ("failed", "warning"):
        return "problem"
    if tracked_state.startswith("import") or status == "completed":
        return "importing"
    if status == "paused":
        return "paused"
    if status == "downloading":
        return "downloading"
    return "queued"


def time_left(raw: str) -> str:
    """'01:05:30' as '1h 05m', '1.02:00:00' as '1d 2h', '' when unknown or done."""
    match = re.fullmatch(r"(?:(\d+)\.)?(\d+):(\d+):(\d+)(?:\.\d+)?", raw.strip())
    if not match:
        return ""
    days, hours, minutes, seconds = (int(part or 0) for part in match.groups())
    if days:
        return f"{days}d {hours}h"
    if hours:
        return f"{hours}h {minutes:02d}m"
    if minutes:
        return f"{minutes}m"
    return "<1m" if seconds else ""


def _download_detail(record: dict, kind: str) -> str:
    if kind == "show":
        episode = record.get("episode") or {}
        if not episode:
            return ""
        code = f"S{as_int(episode.get('seasonNumber')):02d}E{as_int(episode.get('episodeNumber')):02d}"
        name = plain_text(episode.get("title"))
        return f"{code} · {name}" if name else code
    quality = (record.get("quality") or {}).get("quality") or {}
    return plain_text(quality.get("name"))


def _poster_url(entry: dict) -> str:
    return plain_text(entry.get("remotePoster"), 2000) or _cover(entry, "poster")


def _cover(entry: dict, cover_type: str) -> str:
    for image in entry.get("images") or []:
        if isinstance(image, dict) and image.get("coverType") == cover_type:
            return plain_text(image.get("remoteUrl"), 2000) or plain_text(image.get("url"), 2000)
    return ""


def _image(url: str, tmdb_size: str) -> str:
    """The URL if it is https on an allowed image host, with TMDB's original size swapped for a smaller one."""
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in IMAGE_HOSTS:
        return ""
    if parsed.hostname == "image.tmdb.org":
        return url.replace("/t/p/original/", f"/t/p/{tmdb_size}/", 1)
    return url


def _film_rating(ratings: Any) -> float:
    """Radarr 4+ nests ratings by source; IMDb first, then TMDB, then the older flat value."""
    if not isinstance(ratings, dict):
        return 0.0
    for source in ("imdb", "tmdb"):
        value = _rating_value(ratings.get(source))
        if value > 0:
            return value
    return _rating_value(ratings)


def _rating_value(ratings: Any) -> float:
    if not isinstance(ratings, dict):
        return 0.0
    try:
        value = float(ratings.get("value") or 0)
    except (TypeError, ValueError):
        return 0.0
    return round(value, 1) if 0 < value <= 10 else 0.0


def _season_count(lookup: dict) -> int:
    statistics = lookup.get("statistics") or {}
    if as_int(statistics.get("seasonCount")) > 0:
        return as_int(statistics.get("seasonCount"))
    return sum(1 for s in lookup.get("seasons") or [] if isinstance(s, dict) and as_int(s.get("seasonNumber")) > 0)


def _genres(entry: dict) -> str:
    genres = [plain_text(g, 40) for g in entry.get("genres") or [] if isinstance(g, str)]
    return ", ".join(genres[:3])


def plain_text(value: Any, limit: int = MAX_TEXT) -> str:
    return value.strip()[:limit] if isinstance(value, str) else ""


def as_int(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0
