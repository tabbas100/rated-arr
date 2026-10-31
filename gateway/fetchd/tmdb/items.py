"""TMDB films and shows as the TV sees them: the same fields as Radarr's and Sonarr's, from TMDB's data.

Films are keyed by their TMDB id, which Radarr adds by; shows by their TVDB id, which Sonarr adds by.
"""
from __future__ import annotations

from ..arr import catalog

TMDB_IMAGE = "https://image.tmdb.org/t/p/{size}{path}"


def tmdb_film_item(film: dict, owned: dict, genres: dict[int, str]) -> dict:
    """A TMDB film as the TV sees it; owned maps the library's TMDB ids to whether the file is there."""
    tmdb_id = film["id"]
    rating = film.get("vote_average") or 0
    names = [genres[g] for g in film.get("genre_ids") or [] if g in genres]
    return {
        "kind": "film",
        "id": tmdb_id,
        "title": catalog.plain_text(film.get("title")),
        "year": catalog.as_int((film.get("release_date") or "")[:4]),
        "overview": catalog.plain_text(film.get("overview"), catalog.MAX_OVERVIEW),
        "poster": tmdb_image(film.get("poster_path"), "w342"),
        "fanart": tmdb_image(film.get("backdrop_path"), "w1280"),
        "runtime": 0,
        "genres": ", ".join(names[:3]),
        "rating": round(float(rating), 1) if isinstance(rating, (int, float)) and 0 < rating <= 10 else 0.0,
        "network": "",
        "seasons": 0,
        "inLibrary": tmdb_id in owned,
        "downloaded": owned.get(tmdb_id, False),
    }


def tmdb_show_item(show: dict) -> dict | None:
    """A TMDB show as the TV sees it, keyed by its TVDB id; None when it has no TVDB id."""
    tvdb_id = (show.get("external_ids") or {}).get("tvdb_id")
    if not isinstance(tvdb_id, int) or tvdb_id <= 0:
        return None
    runtimes = [r for r in show.get("episode_run_time") or [] if isinstance(r, int)]
    networks = [n.get("name", "") for n in show.get("networks") or [] if isinstance(n, dict)]
    genres = [g.get("name", "") for g in show.get("genres") or [] if isinstance(g, dict)]
    rating = show.get("vote_average") or 0
    return {
        "kind": "show",
        "id": tvdb_id,
        "title": catalog.plain_text(show.get("name")),
        "year": catalog.as_int((show.get("first_air_date") or "")[:4]),
        "overview": catalog.plain_text(show.get("overview"), catalog.MAX_OVERVIEW),
        "poster": tmdb_image(show.get("poster_path"), "w342"),
        "fanart": tmdb_image(show.get("backdrop_path"), "w1280"),
        "runtime": runtimes[0] if runtimes else 0,
        "genres": ", ".join(g for g in genres[:3] if g),
        "rating": round(float(rating), 1) if isinstance(rating, (int, float)) and 0 < rating <= 10 else 0.0,
        "network": networks[0][:80] if networks else "",
        "seasons": catalog.as_int(show.get("number_of_seasons")),
        "inLibrary": False,
        "downloaded": False,
    }


def tmdb_image(path: object, size: str) -> str:
    """A TMDB image path as a URL at the given size; "" for anything that is not a plain file name."""
    if not isinstance(path, str) or not path.startswith("/") or "/" in path[1:] or ".." in path:
        return ""
    return TMDB_IMAGE.format(size=size, path=path)
