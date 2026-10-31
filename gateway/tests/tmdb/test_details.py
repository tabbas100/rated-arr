"""details: what the title page shows from TMDB."""
import unittest

from fetchd.tmdb.details import CAST_SIZE, Details, NoDetails

GLIMMER = {"tagline": "Two good cops. One bad situation.", "overview": "Jack Cole...", "runtime": 91,
           "vote_average": 5.9, "vote_count": 612,
           "credits": {"cast": [{"name": "Steven Seagal", "character": "Jack Cole", "profile_path": "/seagal.jpg"},
                                {"name": "Keenen Ivory Wayans", "character": "Jim Campbell", "profile_path": None}],
                       "crew": [{"name": "John Gray", "job": "Director"}, {"name": "Someone", "job": "Writer"}]}}
LAWMAN = {"tagline": "", "overview": "Seagal as a deputy.", "episode_run_time": [22], "vote_average": 5.4, "vote_count": 20,
          "created_by": [], "aggregate_credits": {"cast": [{"name": "Steven Seagal", "roles": [{"character": ""},
                                                                                           {"character": "Himself"}]}]}}


class FakeTmdb:
    def __init__(self):
        self.calls = 0

    def film_details(self, tmdb_id):
        self.calls += 1
        return GLIMMER

    def find_by_tvdb(self, tvdb_id):
        return [{"id": 31380}] if tvdb_id == 126841 else []

    def show_details(self, tmdb_id):
        return LAWMAN


class DetailsTest(unittest.TestCase):
    def setUp(self):
        self.tmdb = FakeTmdb()
        self.details = Details(self.tmdb)

    def test_a_film_has_its_director(self):
        film = self.details.of("film", 9625)
        self.assertEqual((film["makersRole"], film["makers"]), ("Director", ["John Gray"]))

    def test_cast_comes_with_roles_and_photos(self):
        actor = self.details.of("film", 9625)["cast"][0]
        self.assertEqual((actor["name"], actor["character"], actor["photo"]),
                         ("Steven Seagal", "Jack Cole", "https://image.tmdb.org/t/p/w185/seagal.jpg"))

    def test_an_actor_without_a_photo_has_none(self):
        self.assertEqual(self.details.of("film", 9625)["cast"][1]["photo"], "")

    def test_a_film_has_tagline_and_votes(self):
        film = self.details.of("film", 9625)
        self.assertEqual((film["tagline"], film["votes"], film["rating"]), ("Two good cops. One bad situation.", 612, 5.9))

    def test_a_show_is_found_by_its_tvdb_id(self):
        self.assertEqual(self.details.of("show", 126841)["cast"][0]["name"], "Steven Seagal")

    def test_a_shows_role_is_the_first_one_named(self):
        self.assertEqual(self.details.of("show", 126841)["cast"][0]["character"], "Himself")

    def test_a_show_tmdb_does_not_know_is_no_details(self):
        with self.assertRaises(NoDetails):
            self.details.of("show", 1)

    def test_details_are_cached(self):
        self.details.of("film", 9625)
        self.details.of("film", 9625)
        self.assertEqual(self.tmdb.calls, 1)

    def test_the_cast_is_capped(self):
        GLIMMER_BIG = dict(GLIMMER, credits={"cast": [{"name": f"Actor {n}"} for n in range(40)], "crew": []})
        self.tmdb.film_details = lambda tmdb_id: GLIMMER_BIG
        self.assertEqual(len(self.details.of("film", 1)["cast"]), CAST_SIZE)

    def test_other_kinds_are_refused(self):
        with self.assertRaises(ValueError):
            self.details.of("song", 1)


if __name__ == "__main__":
    unittest.main()
