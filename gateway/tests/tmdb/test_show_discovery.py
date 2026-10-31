"""show_discovery and tmdb: suggestions from real TMDB replies, with fakes for TMDB and Sonarr."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from fetchd.tmdb.show_discovery import ShowDiscovery
from fetchd.tmdb.items import tmdb_show_item
from fetchd.tmdb.client import Tmdb
from fetchd.upstream import UpstreamError

FIXTURES = Path(__file__).resolve().parents[3] / "fixtures"
TMDB = json.loads((FIXTURES / "tmdb.json").read_text())


class FakeTmdb:
    def __init__(self, available=True):
        self._available = available
        self.detail_calls = 0

    def available(self):
        return self._available

    def trending_shows(self):
        return TMDB["trending"]["results"]

    def top_rated_shows(self):
        return [{"id": 1396}]

    def recommendations(self, tmdb_id):
        if tmdb_id == 1434:
            return TMDB["recommendations_1434"]["results"]
        return [{"id": 9001}, {"id": 9002}]

    def show(self, tmdb_id):
        self.detail_calls += 1
        if tmdb_id == 1396:
            return TMDB["details_1396"]
        return {"id": tmdb_id, "name": f"Show {tmdb_id}", "external_ids": {"tvdb_id": 100000 + tmdb_id}}


class FakeUpstream:
    def __init__(self, series):
        self.series = series

    def get(self, path, **query):
        return self.series


class FakeShows:
    def __init__(self, series):
        self.upstream = FakeUpstream(series)


LIBRARY = [{"title": "Family Guy", "tvdbId": 75978, "tmdbId": 1434, "added": "2026-10-20T00:00:00Z"},
           {"title": "Breaking Bad", "tvdbId": 81189, "tmdbId": 1396, "added": "2026-01-01T00:00:00Z"}]


class ShowDiscoveryTest(unittest.TestCase):
    def rows(self, tmdb=None, library=LIBRARY):
        return ShowDiscovery(FakeShows(library), tmdb or FakeTmdb()).rows()

    def test_rows_in_order(self):
        self.assertEqual([r["id"] for r in self.rows()], ["becauseYouHave", "becauseYouHave", "trendingShows"])

    def test_because_row_names_its_show(self):
        self.assertEqual(self.rows()[0]["subject"], "Family Guy")

    def test_shows_in_the_library_are_left_out(self):
        ids = {i["id"] for r in self.rows() for i in r["items"]}
        self.assertNotIn(81189, ids)

    def test_a_show_appears_only_once(self):
        ids = [i["id"] for r in self.rows() for i in r["items"]]
        self.assertEqual(len(ids), len(set(ids)))

    def test_no_key_means_no_rows(self):
        self.assertEqual(self.rows(FakeTmdb(available=False)), [])

    def test_rows_are_marked_as_tmdb(self):
        self.assertTrue(all(r["source"] == "tmdb" for r in self.rows()))

    def test_rows_are_cached(self):
        tmdb = FakeTmdb()
        discovery = ShowDiscovery(FakeShows(LIBRARY), tmdb)
        discovery.rows()
        calls = tmdb.detail_calls
        discovery.rows()
        self.assertEqual(tmdb.detail_calls, calls)


class TmdbShowItemTest(unittest.TestCase):
    def test_breaking_bad_from_tmdb_is_keyed_by_tvdb_id(self):
        item = tmdb_show_item(TMDB["details_1396"])
        self.assertEqual((item["id"], item["title"], item["seasons"], item["network"]), (81189, "Breaking Bad", 5, "AMC"))

    def test_poster_comes_from_tmdb_images(self):
        self.assertRegex(tmdb_show_item(TMDB["details_1396"])["poster"], r"^https://image\.tmdb\.org/t/p/w342/")

    def test_show_without_tvdb_id_is_skipped(self):
        self.assertIsNone(tmdb_show_item({"name": "Unknown", "external_ids": {"tvdb_id": None}}))

    def test_odd_image_paths_are_dropped(self):
        item = tmdb_show_item({"name": "X", "external_ids": {"tvdb_id": 5}, "poster_path": "/../evil.jpg"})
        self.assertEqual(item["poster"], "")


class Reply:
    def __init__(self, body):
        self.body = body

    def read(self, limit):
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class TmdbKeyTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.key = Path(self.dir.name) / "tmdb.key"

    def tearDown(self):
        self.dir.cleanup()

    def request_for(self, key_text):
        self.key.write_text(key_text)
        with mock.patch("urllib.request.urlopen", return_value=Reply(b'{"results": []}')) as opened:
            Tmdb(self.key).trending_shows()
        return opened.call_args[0][0]

    def test_short_key_goes_in_the_query(self):
        request = self.request_for("0123456789abcdef0123456789abcdef\n")
        self.assertIn("api_key=0123456789abcdef0123456789abcdef", request.full_url)

    def test_read_token_goes_in_a_header_not_the_url(self):
        request = self.request_for("eyJhbGciOiJIUzI1NiJ9.token")
        self.assertEqual((request.get_header("Authorization"), "eyJ" in request.full_url),
                         ("Bearer eyJhbGciOiJIUzI1NiJ9.token", False))

    def test_only_tmdb_is_called(self):
        self.assertTrue(self.request_for("k" * 32).full_url.startswith("https://api.themoviedb.org/3/"))

    def test_missing_key_is_unavailable(self):
        self.assertFalse(Tmdb(self.key).available())
        with self.assertRaises(UpstreamError):
            Tmdb(self.key).trending_shows()


if __name__ == "__main__":
    unittest.main()
