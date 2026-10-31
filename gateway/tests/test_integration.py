"""The library against real Radarr and Sonarr (3 and 4) started by tools/test-servers.sh.

Run with: FETCHD_IT=1 python3 -m unittest tests.test_integration
Skipped otherwise. The test servers have no download clients, so nothing is downloaded.
"""
import os
import subprocess
import time
import unittest
from pathlib import Path

from fetchd.arr.episodes import Episodes
from fetchd.arr.guide import EpisodeGuide
from fetchd.arr.library import AlreadyAdded, Films, NotFound, Shows
from fetchd.upstream import Upstream

SERVERS_FILE = Path(__file__).resolve().parents[2] / "test-servers.local.properties"
INCEPTION, BREAKING_BAD, SEVERANCE = 27205, 81189, 371980


def servers() -> dict:
    values = {}
    for line in SERVERS_FILE.read_text().splitlines():
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip()
    return values


def place_dummy_file(container: str, path: str) -> None:
    """A 2 GB sparse file, so Radarr or Sonarr treat it as real media without using disk space."""
    folder = os.path.dirname(path)
    subprocess.run(["docker", "exec", container, "sh", "-c",
                    f'mkdir -p "{folder}" && truncate -s 2G "{path}" && chown -R abc:abc "{folder}"'], check=True)


def exists_in(container: str, path: str) -> bool:
    return subprocess.run(["docker", "exec", container, "test", "-f", path]).returncode == 0


def run_command(upstream_: Upstream, name: str, **ids) -> None:
    command = upstream_.post("/api/v3/command", {"name": name, **ids})
    for _ in range(60):
        if upstream_.get(f"/api/v3/command/{command['id']}")["status"] in ("completed", "failed"):
            return
        time.sleep(1)


def upstream(name: str, prefix: str) -> Upstream:
    values = servers()
    return Upstream(name, values[f"{prefix}.url"].replace(values[f"{prefix}.url"].split("//")[1].split(":")[0],
                                                          "127.0.0.1"), values[f"{prefix}.api_key"])


@unittest.skipUnless(os.environ.get("FETCHD_IT") == "1" and SERVERS_FILE.exists(), "needs tools/test-servers.sh up")
class FilmsIntegrationTest(unittest.TestCase):
    def setUp(self):
        self.films = Films(upstream("Radarr", "radarr"))
        self.remove(INCEPTION)

    def tearDown(self):
        self.remove(INCEPTION)

    def remove(self, tmdb_id):
        for movie in self.films.upstream.get("/api/v3/movie") or []:
            if movie.get("tmdbId") == tmdb_id:
                self.films.upstream.delete(f"/api/v3/movie/{movie['id']}", deleteFiles=False)

    def test_search_finds_inception(self):
        self.assertIn(INCEPTION, [item["id"] for item in self.films.search("inception")])

    def test_add_puts_the_film_in_the_library(self):
        item = self.films.add(INCEPTION)
        self.assertEqual((item["id"], item["inLibrary"]), (INCEPTION, True))

    def test_search_marks_an_added_film(self):
        self.films.add(INCEPTION)
        found = next(i for i in self.films.search("inception") if i["id"] == INCEPTION)
        self.assertTrue(found["inLibrary"])

    def test_adding_twice_is_already_added(self):
        self.films.add(INCEPTION)
        with self.assertRaises(AlreadyAdded):
            self.films.add(INCEPTION)

    def test_added_film_is_monitored_with_the_default_profile_and_folder(self):
        self.films.add(INCEPTION)
        movie = next(m for m in self.films.upstream.get("/api/v3/movie") if m["tmdbId"] == INCEPTION)
        self.assertEqual((movie["monitored"], movie["qualityProfileId"], movie["rootFolderPath"].rstrip("/")),
                         (True, self.films.default_profile(), "/movies"))

    def test_unknown_tmdb_id_is_not_found(self):
        with self.assertRaises(NotFound):
            self.films.add(999_999_999)

    def test_recent_lists_the_new_film_first(self):
        self.films.add(INCEPTION)
        self.assertEqual(self.films.recent(5)[0][1]["id"], INCEPTION)

    def test_downloads_is_a_list(self):
        self.assertIsInstance(self.films.downloads(), list)

    def film_with_a_file(self):
        self.films.add(INCEPTION)
        movie = next(m for m in self.films.upstream.get("/api/v3/movie") if m["tmdbId"] == INCEPTION)
        path = movie["path"] + "/Inception.2010.1080p.BluRay.x264-TEST.mkv"
        place_dummy_file("fetch-test-radarr", path)
        run_command(self.films.upstream, "RescanMovie", movieIds=[movie["id"]])
        return movie, path

    def test_delete_file_removes_it_and_stops_radarr_fetching_it(self):
        movie, path = self.film_with_a_file()
        self.assertTrue(self.films.upstream.get(f"/api/v3/movie/{movie['id']}")["hasFile"])
        self.films.delete_file(INCEPTION)
        after = self.films.upstream.get(f"/api/v3/movie/{movie['id']}")
        self.assertEqual((exists_in("fetch-test-radarr", path), after["hasFile"], after["monitored"]), (False, False, False))

    def test_remove_takes_the_film_and_its_file(self):
        movie, path = self.film_with_a_file()
        self.films.remove(INCEPTION)
        self.assertEqual((exists_in("fetch-test-radarr", path), self.remove_check()), (False, True))

    def remove_check(self):
        return all(m["tmdbId"] != INCEPTION for m in self.films.upstream.get("/api/v3/movie"))

    def test_library_reports_size_and_quality(self):
        self.film_with_a_file()
        film = next(f for f in self.films.library() if f["id"] == INCEPTION)
        self.assertEqual((film["size"] > 0, film["quality"].endswith("1080p")), (True, True))

    def test_discover_gives_trending_and_popular_films(self):
        rows = {r["id"]: r["items"] for r in self.films.discover()}
        self.assertTrue(rows.get("trending") and rows.get("popular"))

    def test_discover_leaves_out_films_in_the_library(self):
        self.films.add(INCEPTION)
        self.films._discover_cache = None
        ids = {i["id"] for r in self.films.discover() for i in r["items"]}
        self.assertNotIn(INCEPTION, ids)


class ShowsIntegration:
    """Run for Sonarr 4 and Sonarr 3 by the two subclasses below."""

    prefix = ""

    def setUp(self):
        self.shows = Shows(upstream("Sonarr", self.prefix))
        self.remove_all()

    def tearDown(self):
        self.remove_all()

    def remove_all(self):
        for series in self.shows.upstream.get("/api/v3/series") or []:
            if series.get("tvdbId") in (BREAKING_BAD, SEVERANCE):
                self.shows.upstream.delete(f"/api/v3/series/{series['id']}", deleteFiles=False)

    def stored(self, tvdb_id):
        return next(s for s in self.shows.upstream.get("/api/v3/series") if s["tvdbId"] == tvdb_id)

    def monitored_seasons(self, tvdb_id):
        return sorted(s["seasonNumber"] for s in self.stored(tvdb_id)["seasons"] if s["monitored"])

    def test_search_finds_breaking_bad(self):
        self.assertIn(BREAKING_BAD, [item["id"] for item in self.shows.search("breaking bad")])

    def test_all_seasons(self):
        self.shows.add(BREAKING_BAD, "all")
        self.assertEqual(self.monitored_seasons(BREAKING_BAD), [1, 2, 3, 4, 5])

    def test_latest_season(self):
        self.shows.add(BREAKING_BAD, "latest")
        self.assertEqual(self.monitored_seasons(BREAKING_BAD), [5])

    def test_first_season(self):
        self.shows.add(BREAKING_BAD, "first")
        self.assertEqual(self.monitored_seasons(BREAKING_BAD), [1])

    def test_future_episodes_only(self):
        self.shows.add(BREAKING_BAD, "future")
        series = self.stored(BREAKING_BAD)
        self.assertEqual((series["monitored"], self.monitored_seasons(BREAKING_BAD)), (True, []))

    def test_adding_twice_is_already_added(self):
        self.shows.add(SEVERANCE, "all")
        with self.assertRaises(AlreadyAdded):
            self.shows.add(SEVERANCE, "all")

    def test_downloads_is_a_list(self):
        self.assertIsInstance(self.shows.downloads(), list)

    def episodes(self):
        return Episodes(self.shows, EpisodeGuide())

    def monitored_episodes(self, tvdb_id):
        series = self.stored(tvdb_id)
        return {(e["seasonNumber"], e["episodeNumber"])
                for e in self.shows.upstream.get("/api/v3/episode", seriesId=series["id"]) if e["monitored"]}

    def test_list_of_a_show_not_in_the_library_comes_from_the_guide(self):
        listed = self.episodes().list(BREAKING_BAD)
        self.assertEqual((listed["inLibrary"], [s["number"] for s in listed["seasons"]][:5]), (False, [1, 2, 3, 4, 5]))

    def test_choosing_single_episodes_adds_the_show_with_only_those_wanted(self):
        picks = {(1, 1), (1, 2), (3, 7)}
        result = self.episodes().choose(BREAKING_BAD, picks)
        self.assertEqual((result["chosen"], result["unmatched"], self.monitored_episodes(BREAKING_BAD)), (3, 0, picks))

    def test_choosing_a_whole_season_monitors_the_season(self):
        season_two = {(2, n) for n in range(1, 14)}
        self.episodes().choose(BREAKING_BAD, season_two)
        seasons = {s["seasonNumber"]: s["monitored"] for s in self.stored(BREAKING_BAD)["seasons"]}
        self.assertEqual((seasons[2], seasons[1], seasons[3]), (True, False, False))

    def test_choosing_again_replaces_the_previous_choice(self):
        self.episodes().choose(BREAKING_BAD, {(1, 1), (1, 2)})
        self.episodes().choose(BREAKING_BAD, {(5, 16)})
        self.assertEqual(self.monitored_episodes(BREAKING_BAD), {(5, 16)})

    def test_delete_episode_files_takes_only_the_picked(self):
        container = "fetch-test-sonarr" if self.prefix == "sonarr" else "fetch-test-sonarr3"
        self.episodes().choose(BREAKING_BAD, {(1, 1), (1, 2)})
        series = self.stored(BREAKING_BAD)
        paths = [series["path"] + f"/Season 01/Breaking.Bad.S01E0{n}.1080p.BluRay.x264-TEST.mkv" for n in (1, 2)]
        for path in paths:
            place_dummy_file(container, path)
        run_command(self.shows.upstream, "RescanSeries", seriesId=series["id"])
        result = self.episodes().delete_files(BREAKING_BAD, {(1, 1)})
        self.assertEqual((result["deleted"], exists_in(container, paths[0]), exists_in(container, paths[1]),
                          (1, 1) in self.monitored_episodes(BREAKING_BAD)), (1, False, True, False))

    def test_remove_show(self):
        self.episodes().choose(BREAKING_BAD, {(1, 1)})
        self.shows.remove(BREAKING_BAD)
        self.assertIsNone(self.shows.library_series(BREAKING_BAD))

    def test_list_of_a_library_show_shows_what_is_wanted(self):
        self.episodes().choose(BREAKING_BAD, {(4, 13)})
        listed = self.episodes().list(BREAKING_BAD)
        wanted = {(s["number"], e["number"]) for s in listed["seasons"] for e in s["episodes"] if e["wanted"]}
        self.assertEqual((listed["inLibrary"], wanted), (True, {(4, 13)}))


@unittest.skipUnless(os.environ.get("FETCHD_IT") == "1" and SERVERS_FILE.exists(), "needs tools/test-servers.sh up")
class Sonarr4IntegrationTest(ShowsIntegration, unittest.TestCase):
    prefix = "sonarr"


@unittest.skipUnless(os.environ.get("FETCHD_IT") == "1" and SERVERS_FILE.exists(), "needs tools/test-servers.sh up")
class Sonarr3IntegrationTest(ShowsIntegration, unittest.TestCase):
    prefix = "sonarr3"


if __name__ == "__main__":
    unittest.main()
