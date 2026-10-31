"""spelling: a search that finds nothing gets the title closest to it by spelling."""
import gzip
import json
import tempfile
import unittest
from pathlib import Path

from fetchd.tmdb.spelling import REFRESH_SECONDS, Spelling, any_close, closeness, closest_first, normalize

FILMS = [("The Glimmer Man", 3.97), ("Birdemic: Shock and Terror", 3.99), ("Birdman", 20.0), ("Troll 2", 3.29),
         ("Double Down", 0.47), ("Identity V STAGE Episode 2 [Double Down]", 5.0), ("千と千尋の神隠し", 50.0),
         ("Sharknado", 7.2), ("Sharknado 2: The Second One", 9.0)]
SHOWS = [("Columbo", 113.0), ("Breaking Bad", 990.0)]


def export(rows, field):
    lines = [json.dumps({"id": n, field: title, "popularity": pop, "adult": False}) for n, (title, pop) in enumerate(rows)]
    lines.append(json.dumps({"id": 99, field: "Glimmer Girls", "popularity": 1.0, "adult": True}))
    return gzip.compress("\n".join(lines).encode())


def fetch(url):
    return export(FILMS, "original_title") if "movie" in url else export(SHOWS, "original_name")


class NormalizeTest(unittest.TestCase):
    def test_punctuation_and_case_go(self):
        self.assertEqual(normalize("Birdemic: Shock and Terror!"), "birdemic shock and terror")

    def test_accents_go(self):
        self.assertEqual(normalize("Amélie"), "amelie")

    def test_titles_in_other_scripts_have_nothing_to_match(self):
        self.assertEqual(normalize("千と千尋の神隠し"), "")


class ClosenessTest(unittest.TestCase):
    def test_a_missing_letter_is_close(self):
        self.assertGreaterEqual(closeness("glimer man", "the glimmer man"), 0.9)

    def test_a_different_word_is_not(self):
        self.assertLess(closeness("birdmic", "birdman"), 0.8)


class AnyCloseTest(unittest.TestCase):
    def test_a_title_spelled_like_the_search_counts(self):
        self.assertTrue(any_close("colmbo", ["Kombo", "Columbo"]))

    def test_unrelated_titles_do_not(self):
        self.assertFalse(any_close("glimer man", ["Spider-Man (1981)", "Gadget Man"]))


class ClosestFirstTest(unittest.TestCase):
    def test_the_title_searched_for_comes_first(self):
        found = closest_first("glimmer man", [{"title": "Glimmer"}, {"title": "The Glimmer Man"}])
        self.assertEqual(found[0]["title"], "The Glimmer Man")

    def test_equally_close_titles_keep_their_order(self):
        found = closest_first("glimmer", [{"title": "Glimmer", "year": 2026}, {"title": "Glimmer", "year": 2012}])
        self.assertEqual([f["year"] for f in found], [2026, 2012])


class SpellingTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.spelling = Spelling(Path(self.folder.name) / "titles.sqlite", fetch=fetch)
        self.spelling.build()

    def tearDown(self):
        self.folder.cleanup()

    def test_a_missing_letter_finds_the_film(self):
        self.assertEqual(self.spelling.suggest("glimer man"), "The Glimmer Man")

    def test_one_word_finds_a_longer_title(self):
        self.assertEqual(self.spelling.suggest("birdmic"), "Birdemic: Shock and Terror")

    def test_shows_are_found_too(self):
        self.assertEqual(self.spelling.suggest("colmbo"), "Columbo")

    def test_a_swapped_letter_is_found(self):
        self.assertEqual(self.spelling.suggest("sharknato"), "Sharknado")

    def test_the_whole_title_wins_over_a_longer_one_with_the_same_words(self):
        self.assertEqual(self.spelling.suggest("dubble down"), "Double Down")

    def test_the_first_film_wins_over_its_sequel(self):
        self.assertEqual(self.spelling.suggest("sharknato"), "Sharknado")

    def test_nothing_close_is_no_suggestion(self):
        self.assertEqual(self.spelling.suggest("zebra crossing"), "")

    def test_short_searches_get_no_suggestion(self):
        self.assertEqual(self.spelling.suggest("tro 2"), "")

    def test_adult_titles_are_left_out(self):
        self.assertEqual(self.spelling.suggest("glimmer girls"), "")


class RefreshTest(unittest.TestCase):
    def test_without_lists_there_is_no_suggestion_yet(self):
        with tempfile.TemporaryDirectory() as folder:
            spelling = Spelling(Path(folder) / "titles.sqlite", fetch=fetch)
            spelling._building = True
            self.assertEqual(spelling.suggest("glimer man"), "")

    def test_fresh_lists_are_not_fetched_again(self):
        fetched = []
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "titles.sqlite"
            path.write_text("")
            spelling = Spelling(path, fetch=lambda url: fetched.append(url), clock=lambda: path.stat().st_mtime + 60)
            spelling.refresh_in_background()
            self.assertEqual((fetched, spelling._building), ([], False))

    def test_old_lists_are_fetched_again(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "titles.sqlite"
            path.write_text("")
            spelling = Spelling(path, fetch=fetch, clock=lambda: path.stat().st_mtime + REFRESH_SECONDS + 1)
            spelling._build_logged = lambda: None
            spelling.refresh_in_background()
            self.assertTrue(spelling._building)


if __name__ == "__main__":
    unittest.main()
