"""watching: Plex's Continue Watching as the TV's Watch Next row needs it."""
import tempfile
import unittest
from pathlib import Path

from fetchd.upstream import UpstreamError
from fetchd.plex.watching import MAX_ITEMS, Plex, Watching

HARD_TARGET = {"type": "movie", "ratingKey": "1629", "title": "Hard Target", "viewOffset": 2575843,
               "duration": 5979008, "lastViewedAt": 1793132410, "Guid": [{"id": "imdb://tt0107076"},
                                                                         {"id": "tmdb://2019"}]}
COLUMBO = {"type": "episode", "ratingKey": "1730", "title": "The Greenhouse Jungle", "grandparentTitle": "Columbo",
           "parentIndex": 2, "index": 2, "parentRatingKey": "1686", "grandparentRatingKey": "1685", "viewOffset": 183431, "duration": 4429964, "lastViewedAt": 1793132631,
           "Guid": [{"id": "tvdb://174632"}]}
NEXT_EPISODE = {"type": "episode", "ratingKey": "1731", "title": "Dagger of the Mind", "grandparentTitle": "Columbo",
                "parentIndex": 2, "index": 3, "duration": 4400000}


class FakePlex:
    def __init__(self, entries):
        self.entries = entries

    def continue_watching(self):
        return self.entries

    def machine_id(self):
        return "0a1b2c3d"


class FakeTmdb:
    def __init__(self):
        self.calls = 0

    def film(self, tmdb_id):
        self.calls += 1
        return {"backdrop_path": "/hard-target.jpg"} if tmdb_id == 2019 else {}

    def find(self, external_id, source):
        self.calls += 1
        if (external_id, source) == ("174632", "tvdb_id"):
            return {"tv_episode_results": [{"still_path": "/greenhouse.jpg"}]}
        return {}


class OfflineTmdb:
    def film(self, tmdb_id):
        raise UpstreamError("TMDB", "unreachable")

    def find(self, external_id, source):
        raise UpstreamError("TMDB", "unreachable")


class WatchingTest(unittest.TestCase):
    def setUp(self):
        self.tmdb = FakeTmdb()

    def items(self, *entries):
        return Watching(FakePlex(list(entries)), self.tmdb).items()["items"]

    def test_a_film_keeps_where_it_stopped(self):
        film = self.items(HARD_TARGET)[0]
        self.assertEqual((film["kind"], film["key"], film["title"], film["position"], film["duration"]),
                         ("film", "1629", "Hard Target", 2575843, 5979008))

    def test_an_episode_is_titled_by_its_show(self):
        episode = self.items(COLUMBO)[0]
        self.assertEqual((episode["title"], episode["episodeTitle"], episode["season"], episode["episode"]),
                         ("Columbo", "The Greenhouse Jungle", 2, 2))

    def test_an_episode_names_its_show_and_season_in_plex(self):
        episode = self.items(COLUMBO)[0]
        self.assertEqual((episode["showKey"], episode["seasonKey"]), ("1685", "1686"))

    def test_a_film_has_no_show_or_season(self):
        film = self.items(HARD_TARGET)[0]
        self.assertEqual((film["showKey"], film["seasonKey"]), ("", ""))

    def test_a_film_shows_its_tmdb_backdrop(self):
        self.assertEqual(self.items(HARD_TARGET)[0]["art"], "https://image.tmdb.org/t/p/w780/hard-target.jpg")

    def test_an_episode_shows_its_still(self):
        self.assertEqual(self.items(COLUMBO)[0]["art"], "https://image.tmdb.org/t/p/w780/greenhouse.jpg")

    def test_art_is_looked_up_once(self):
        watching = Watching(FakePlex([HARD_TARGET]), self.tmdb)
        watching.items()
        watching.items()
        self.assertEqual(self.tmdb.calls, 1)

    def test_without_tmdb_there_is_no_art(self):
        self.tmdb = OfflineTmdb()
        self.assertEqual(self.items(HARD_TARGET)[0]["art"], "")

    def test_the_next_episode_takes_the_time_before_it(self):
        self.assertEqual(self.items(COLUMBO, NEXT_EPISODE)[1]["watchedAt"], 1793132631)

    def test_other_kinds_are_left_out(self):
        self.assertEqual(self.items({"type": "track", "ratingKey": "7", "title": "A song"}), [])

    def test_a_key_that_is_not_a_number_is_left_out(self):
        self.assertEqual(self.items(dict(HARD_TARGET, ratingKey="../1")), [])

    def test_the_list_is_capped(self):
        entries = [dict(HARD_TARGET, ratingKey=str(n)) for n in range(MAX_ITEMS + 5)]
        self.assertEqual(len(self.items(*entries)), MAX_ITEMS)

    def test_the_server_id_comes_along(self):
        self.assertEqual(Watching(FakePlex([]), self.tmdb).items()["server"], "0a1b2c3d")


class PlexTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.preferences = Path(self.dir.name) / "Preferences.xml"

    def tearDown(self):
        self.dir.cleanup()

    def test_the_machine_id_comes_from_preferences(self):
        self.preferences.write_text('<Preferences ProcessedMachineIdentifier="0a1b2c3d" PlexOnlineToken="t"/>')
        self.assertEqual(Plex("http://127.0.0.1:1", self.preferences).machine_id(), "0a1b2c3d")

    def test_missing_preferences_are_an_upstream_error(self):
        with self.assertRaises(UpstreamError):
            Plex("http://127.0.0.1:1", self.preferences).machine_id()

    def test_without_a_url_plex_is_not_configured(self):
        self.preferences.write_text('<Preferences PlexOnlineToken="t"/>')
        with self.assertRaises(UpstreamError):
            Plex("", self.preferences).continue_watching()


if __name__ == "__main__":
    unittest.main()
