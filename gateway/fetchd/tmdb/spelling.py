"""The typo fallback: when a search finds no title spelled like it, the title closest to it by spelling.

TMDB, Radarr and Sonarr match whole words and word beginnings only, so "glimer man" finds nothing.
TMDB publishes daily lists of every film and show. Every title written in Latin letters, however
obscure, is kept in an SQLite file on the box with its words indexed; a failed search is compared
by spelling against titles that share a word spelled like its longest word. Popularity only breaks
ties, after closeness to the whole title. The lists are fetched again every two weeks, in the background.
"""
from __future__ import annotations

import gzip
import io
import json
import logging
import os
import sqlite3
import threading
import time
import unicodedata
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Callable, Iterator

EXPORT_URL = "https://files.tmdb.org/p/exports/{kind}_ids_{day}.json.gz"
EXPORTS = (("movie", "original_title"), ("tv_series", "original_name"))
REFRESH_SECONDS = 14 * 24 * 3600
MIN_CLOSENESS = 0.8
MIN_ANCHOR = 4
MAX_CANDIDATES = 5000

log = logging.getLogger("fetchd")


def normalize(text: str) -> str:
    """Lower case, accents dropped, anything but letters and digits as single spaces."""
    plain = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return " ".join("".join(c if c.isalnum() else " " for c in plain).split())


def closeness(query: str, title: str) -> float:
    """How alike a normalized search and title are, also against each run of the title's words as long as
    the search, so "glimer man" is close to "the glimmer man"."""
    best = SequenceMatcher(None, query, title).ratio()
    words, length = title.split(), len(query.split())
    for start in range(max(0, len(words) - length + 1)):
        best = max(best, SequenceMatcher(None, query, " ".join(words[start:start + length])).ratio())
    return best


def any_close(term: str, titles: list[str]) -> bool:
    """True when a title is spelled close to the search: then the search found what was meant."""
    query = normalize(term)
    return any(closeness(query, normalize(title)) >= MIN_CLOSENESS for title in titles)


def closest_first(term: str, items: list[dict]) -> list[dict]:
    """Search results with the titles spelled most like the search first; equal ones keep their order."""
    query = normalize(term)
    return sorted(items, key=lambda item: -round(closeness(query, normalize(item.get("title", ""))), 2))


class Spelling:
    def __init__(self, path: Path, fetch: Callable[[str], bytes] | None = None,
                 clock: Callable[[], float] = time.time) -> None:
        self.path = path
        self.fetch = fetch or _fetch
        self.clock = clock
        self._lock = threading.Lock()
        self._building = False

    def suggest(self, term: str) -> str:
        """The title closest to the search by spelling, "" when none is close or the lists are not built yet."""
        self.refresh_in_background()
        query = normalize(term)
        anchor = max(query.split(), key=len, default="")
        if len(anchor) < MIN_ANCHOR or not self.path.exists():
            return ""
        with sqlite3.connect(f"file:{self.path}?mode=ro", uri=True) as db:
            words = [w for (w,) in db.execute("SELECT word FROM vocab WHERE first = ? AND length BETWEEN ? AND ?",
                                              (anchor[0], len(anchor) - 2, len(anchor) + 2))
                     if SequenceMatcher(None, anchor, w).ratio() >= MIN_CLOSENESS]
            if not words:
                return ""
            marks = ",".join("?" * len(words))
            rows = db.execute(f"SELECT title, norm, popularity FROM titles WHERE id IN "
                              f"(SELECT title_id FROM words WHERE word IN ({marks})) LIMIT {MAX_CANDIDATES}", words).fetchall()
        # Ties go to the title closest as a whole ("Sharknado" before "Sharknado 2"), then to the more popular.
        scored = [(round(closeness(query, norm), 2), round(SequenceMatcher(None, query, norm).ratio(), 2), popularity, title)
                  for title, norm, popularity in rows]
        best = max((s for s in scored if s[0] >= MIN_CLOSENESS), default=None)
        return best[3] if best else ""

    def refresh_in_background(self) -> None:
        """Starts fetching the lists when there are none, or they are two weeks old."""
        with self._lock:
            fresh = self.path.exists() and self.clock() - self.path.stat().st_mtime < REFRESH_SECONDS
            if fresh or self._building:
                return
            self._building = True
        threading.Thread(target=self._build_logged, daemon=True).start()

    def build(self) -> None:
        """Fetches TMDB's lists and writes them to a new file that replaces the old one when complete."""
        partial = self.path.with_suffix(".partial")
        partial.unlink(missing_ok=True)
        with sqlite3.connect(partial) as db:
            db.executescript("CREATE TABLE titles (id INTEGER PRIMARY KEY, title TEXT, norm TEXT, popularity REAL);"
                             "CREATE TABLE words (word TEXT, title_id INTEGER);")
            for kind, field in EXPORTS:
                self._load(db, kind, field)
            db.executescript("CREATE INDEX words_by_word ON words (word);"
                             "CREATE TABLE vocab AS SELECT DISTINCT word, substr(word, 1, 1) AS first, "
                             "length(word) AS length FROM words;"
                             "CREATE INDEX vocab_by_shape ON vocab (first, length);")
        partial.chmod(0o600)
        os.replace(partial, self.path)

    def _load(self, db: sqlite3.Connection, kind: str, field: str) -> None:
        for title, popularity in _titles(self.fetch(_export_url(kind, self.clock())), field):
            norm = normalize(title)
            if not norm:
                continue
            title_id = db.execute("INSERT INTO titles (title, norm, popularity) VALUES (?, ?, ?)",
                                  (title[:200], norm, popularity)).lastrowid
            db.executemany("INSERT INTO words VALUES (?, ?)", [(w, title_id) for w in set(norm.split()) if len(w) >= 3])

    def _build_logged(self) -> None:
        try:
            self.build()
            log.info("typo fallback: title lists updated")
        except (OSError, ValueError, sqlite3.Error, urllib.error.URLError) as error:
            log.warning("typo fallback: could not fetch TMDB's title lists: %s", error)
        finally:
            with self._lock:
                self._building = False


def _titles(compressed: bytes, field: str) -> Iterator[tuple[str, float]]:
    """Read line by line: the film list is about 250 MB once unpacked."""
    for line in gzip.GzipFile(fileobj=io.BytesIO(compressed)):
        row = json.loads(line)
        title = row.get(field)
        if isinstance(title, str) and title and not row.get("adult"):
            yield title, float(row.get("popularity") or 0)


def _export_url(kind: str, now: float) -> str:
    """Yesterday's list: today's is published during the day."""
    day = datetime.fromtimestamp(now, timezone.utc) - timedelta(days=1)
    return EXPORT_URL.format(kind=kind, day=day.strftime("%m_%d_%Y"))


def _fetch(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=300) as reply:
        return reply.read()
