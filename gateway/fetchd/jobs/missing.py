"""The weekly search for what is still missing.

Radarr and Sonarr only watch new uploads; a title that was not found when it was added stays missing
until someone searches again. Radarr's own "search all missing" skips its availability rule when it is
started through the API, so it searched for The Odyssey while the film was only in cinemas and grabbed
a different film of the same name. So films are searched by id, and only those Radarr calls available.
Sonarr searches monitored episodes that have aired; unmonitored shows are left alone.
"""
from __future__ import annotations

from ..upstream import Upstream


def search_missing(radarr: Upstream, sonarr: Upstream) -> None:
    films = available_missing_films(radarr.get("/api/v3/movie") or [])
    if films:
        radarr.post("/api/v3/command", {"name": "MoviesSearch", "movieIds": films})
    sonarr.post("/api/v3/command", {"name": "MissingEpisodeSearch", "monitored": True})


def available_missing_films(movies: list[dict]) -> list[int]:
    """Films Radarr should get, has no file for, and considers released."""
    return [m["id"] for m in movies if isinstance(m, dict) and m.get("monitored") and not m.get("hasFile")
            and m.get("isAvailable")]
