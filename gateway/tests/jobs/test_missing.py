"""missing: the weekly search asks for missing films that are out, and for missing episodes."""
import unittest

from fetchd.jobs.missing import available_missing_films, search_missing

GLIMMER = {"id": 1, "title": "The Glimmer Man", "monitored": True, "hasFile": False, "isAvailable": True}
ODYSSEY = {"id": 72, "title": "The Odyssey", "monitored": True, "hasFile": False, "isAvailable": False}
HAVE = {"id": 3, "title": "Machete", "monitored": True, "hasFile": True, "isAvailable": True}
UNWANTED = {"id": 4, "title": "Cats", "monitored": False, "hasFile": False, "isAvailable": True}


class FakeApp:
    def __init__(self, movies=()):
        self.movies = list(movies)
        self.commands = []

    def get(self, path, **query):
        return self.movies

    def post(self, path, body):
        self.commands.append((path, body))


class AvailableMissingFilmsTest(unittest.TestCase):
    def test_a_released_missing_film_is_searched(self):
        self.assertEqual(available_missing_films([GLIMMER]), [1])

    def test_a_film_still_in_cinemas_is_not(self):
        self.assertEqual(available_missing_films([ODYSSEY]), [])

    def test_films_already_there_or_unwanted_are_not(self):
        self.assertEqual(available_missing_films([HAVE, UNWANTED]), [])


class SearchMissingTest(unittest.TestCase):
    def test_radarr_searches_only_released_missing_films_by_id(self):
        radarr, sonarr = FakeApp([GLIMMER, ODYSSEY, HAVE]), FakeApp()
        search_missing(radarr, sonarr)
        self.assertEqual(radarr.commands, [("/api/v3/command", {"name": "MoviesSearch", "movieIds": [1]})])

    def test_nothing_to_search_sends_nothing_to_radarr(self):
        radarr, sonarr = FakeApp([ODYSSEY]), FakeApp()
        search_missing(radarr, sonarr)
        self.assertEqual(radarr.commands, [])

    def test_sonarr_searches_only_monitored_episodes(self):
        radarr, sonarr = FakeApp(), FakeApp()
        search_missing(radarr, sonarr)
        self.assertEqual(sonarr.commands, [("/api/v3/command", {"name": "MissingEpisodeSearch", "monitored": True})])


if __name__ == "__main__":
    unittest.main()
