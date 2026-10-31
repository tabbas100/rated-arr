"""library: behaviour that needs no real server, with a fake upstream."""
import unittest

from fetchd.arr.library import DISCOVER_ROW, DISCOVER_TTL_SECONDS, Films, Shows


class FakeUpstream:
    name = "Sonarr"

    def __init__(self, replies):
        self.replies = replies

    def get(self, path, **query):
        return self.replies[path]


class ShowSearchTest(unittest.TestCase):
    def test_library_show_is_described_from_the_library(self):
        lookup = {"tvdbId": 75897, "title": "South Park", "id": 12,
                  "statistics": {"episodeFileCount": 0, "seasonCount": 29}}
        library = {"tvdbId": 75897, "title": "South Park", "id": 12,
                   "statistics": {"episodeFileCount": 305, "seasonCount": 29}}
        shows = Shows(FakeUpstream({"/api/v3/series/lookup": [lookup], "/api/v3/series": [library]}))
        self.assertTrue(shows.search("south park")[0]["downloaded"])


    def test_show_not_in_the_library_keeps_its_lookup(self):
        lookup = {"tvdbId": 371980, "title": "Severance", "statistics": {"episodeFileCount": 0}}
        shows = Shows(FakeUpstream({"/api/v3/series/lookup": [lookup], "/api/v3/series": []}))
        item = shows.search("severance")[0]
        self.assertEqual((item["title"], item["inLibrary"], item["downloaded"]), ("Severance", False, False))


def profile(profile_id, name, disc_images):
    return {"id": profile_id, "name": name, "items": [
        {"quality": {"name": "BR-DISK"}, "allowed": disc_images},
        {"quality": {"name": "Bluray-1080p"}, "allowed": True}]}


class DefaultProfileTest(unittest.TestCase):
    def default(self, profiles, configured=""):
        return Films(FakeUpstream({"/api/v3/qualityprofile": profiles}), profile_name=configured).default_profile()

    def test_prefers_hd_1080p_over_a_first_profile_that_takes_disc_images(self):
        self.assertEqual(self.default([profile(1, "Any", True), profile(4, "HD-1080p", False)]), 4)

    def test_prefers_up_to_1080p_over_hd_1080p(self):
        self.assertEqual(self.default([profile(4, "HD-1080p", False), profile(7, "Up to 1080p", False)]), 7)

    def test_without_hd_1080p_takes_the_first_profile_without_disc_images(self):
        self.assertEqual(self.default([profile(1, "Any", True), profile(3, "HD-720p", False)]), 3)

    def test_configured_name_wins(self):
        self.assertEqual(self.default([profile(1, "Any", True), profile(4, "HD-1080p", False)], "Any"), 1)

    def test_falls_back_to_the_first_when_every_profile_takes_disc_images(self):
        self.assertEqual(self.default([profile(1, "Any", True), profile(2, "Everything", True)]), 1)


def discover_entry(tmdb_id, **flags):
    return {"tmdbId": tmdb_id, "title": f"Film {tmdb_id}", "year": 2000, **flags}


class CountingUpstream(FakeUpstream):
    def __init__(self, replies):
        super().__init__(replies)
        self.calls = 0

    def get(self, path, **query):
        self.calls += 1
        return super().get(path, **query)


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


class DiscoverTest(unittest.TestCase):
    def films(self, entries, clock=None):
        self.upstream = CountingUpstream({"/api/v3/importlist/movie": entries})
        return Films(self.upstream, clock=clock or Clock())

    def test_rows_in_order_with_their_films(self):
        rows = self.films([discover_entry(1, isRecommendation=True), discover_entry(2, isTrending=True),
                           discover_entry(3, isPopular=True)]).discover()
        self.assertEqual([(r["id"], [i["id"] for i in r["items"]]) for r in rows],
                         [("recommended", [1]), ("trending", [2]), ("popular", [3])])

    def test_films_in_the_library_or_excluded_are_left_out(self):
        rows = self.films([discover_entry(1, isRecommendation=True, isExisting=True),
                           discover_entry(2, isRecommendation=True, isExcluded=True),
                           discover_entry(3, isRecommendation=True)]).discover()
        self.assertEqual([i["id"] for i in rows[0]["items"]], [3])

    def test_a_film_appears_only_in_its_first_row(self):
        rows = self.films([discover_entry(1, isRecommendation=True, isTrending=True),
                           discover_entry(2, isTrending=True)]).discover()
        self.assertEqual([(r["id"], [i["id"] for i in r["items"]]) for r in rows], [("recommended", [1]), ("trending", [2])])

    def test_empty_rows_are_dropped(self):
        rows = self.films([discover_entry(1, isTrending=True)]).discover()
        self.assertEqual([r["id"] for r in rows], ["trending"])

    def test_rows_are_capped(self):
        rows = self.films([discover_entry(n, isRecommendation=True) for n in range(1, 50)]).discover()
        self.assertEqual(len(rows[0]["items"]), DISCOVER_ROW)

    def test_cached_until_it_expires(self):
        clock = Clock()
        films = self.films([discover_entry(1, isTrending=True)], clock)
        films.discover()
        films.discover()
        clock.now += DISCOVER_TTL_SECONDS + 1
        films.discover()
        self.assertEqual(self.upstream.calls, 2)


if __name__ == "__main__":
    unittest.main()
