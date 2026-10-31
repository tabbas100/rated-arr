"""people: the actor or director a search names, with their films and shows."""
import unittest

from fetchd.tmdb.people import People, best_match, is_chatter, is_name
from fetchd.tmdb.items import tmdb_film_item

SEAGAL = {"id": 23880, "name": "Steven Seagal", "known_for_department": "Acting", "popularity": 3.1}
KENTARO = {"id": 592433, "name": "Kentaro Seagal", "known_for_department": "Acting", "popularity": 1.1}
BREEN = {"id": 1021805, "name": "Neil Breen", "known_for_department": "Directing", "popularity": 0.9}


def film(tmdb_id, title, votes, date="1996-10-04", **extra):
    return {"id": tmdb_id, "title": title, "vote_count": votes, "release_date": date, "vote_average": 5.9,
            "poster_path": f"/{tmdb_id}.jpg", "genre_ids": [28, 53], **extra}


class FakeTmdb:
    def __init__(self, people, films=None, shows=None, details=None):
        self._people, self._films, self._shows, self._details = people, films or {}, shows or {}, details or {}
        self.lookups = 0

    def available(self):
        return True

    def people(self, query):
        self.lookups += 1
        return self._people

    def person_films(self, person_id):
        return self._films

    def person_shows(self, person_id):
        return self._shows

    def film_genres(self):
        return {28: "Action", 53: "Thriller"}

    def show(self, tmdb_id):
        return self._details[tmdb_id]


class FakeApp:
    def __init__(self, path, records):
        self.path, self.records = path, records

    def get(self, path, **query):
        return self.records if path == self.path else []


class FakeLibrary:
    def __init__(self, path, records):
        self.upstream = FakeApp(path, records)


LAWMAN = {"id": 26402, "name": "Steven Seagal: Lawman", "first_air_date": "2009-12-02",
          "external_ids": {"tvdb_id": 126841}, "genres": [{"name": "Reality"}]}


def people(tmdb, owned_films=(), owned_shows=()):
    return People(FakeLibrary("/api/v3/movie", list(owned_films)), FakeLibrary("/api/v3/series", list(owned_shows)), tmdb)


class BestMatchTest(unittest.TestCase):
    def test_a_surname_finds_the_most_popular_match(self):
        self.assertEqual(best_match("seagal", [KENTARO, SEAGAL])["id"], 23880)

    def test_word_beginnings_match(self):
        self.assertEqual(best_match("steve seag", [SEAGAL])["id"], 23880)

    def test_a_word_not_in_the_name_is_no_match(self):
        self.assertIsNone(best_match("seagal films", [SEAGAL]))

    def test_very_short_searches_name_nobody(self):
        self.assertIsNone(best_match("st", [SEAGAL]))


class IsNameTest(unittest.TestCase):
    def test_a_surname_is_the_name(self):
        self.assertTrue(is_name("seagal", "Steven Seagal"))

    def test_the_full_name_is_the_name(self):
        self.assertTrue(is_name("Neil Breen", "Neil Breen"))

    def test_a_first_name_alone_is_not(self):
        self.assertFalse(is_name("steven", "Steven Seagal"))

    def test_word_beginnings_are_not(self):
        self.assertFalse(is_name("steve seag", "Steven Seagal"))


class PeopleTest(unittest.TestCase):
    def test_films_are_ordered_best_known_first(self):
        tmdb = FakeTmdb([SEAGAL], films={"cast": [film(1, "Attack Force", 80), film(2, "Under Siege", 1823)]})
        self.assertEqual([f["title"] for f in people(tmdb).search("seagal")[0]["films"]], ["Under Siege", "Attack Force"])

    def test_a_directors_films_are_included(self):
        tmdb = FakeTmdb([BREEN], films={"crew": [film(3, "Fateful Findings", 121, job="Director")]})
        found = people(tmdb).search("neil breen")[0]
        self.assertEqual((found["directing"], found["films"][0]["title"]), (True, "Fateful Findings"))

    def test_a_film_both_acted_in_and_directed_appears_once(self):
        tmdb = FakeTmdb([BREEN], films={"cast": [film(3, "Fateful Findings", 121)],
                                        "crew": [film(3, "Fateful Findings", 121, job="Director")]})
        self.assertEqual(len(people(tmdb).search("neil breen")[0]["films"]), 1)

    def test_unreleased_projects_are_left_out(self):
        tmdb = FakeTmdb([SEAGAL], films={"cast": [film(4, "Untitled", 0, date="")]})
        self.assertEqual(people(tmdb).search("seagal")[0]["films"], [])

    def test_films_in_the_library_are_marked(self):
        tmdb = FakeTmdb([SEAGAL], films={"cast": [film(2, "Under Siege", 1823)]})
        found = people(tmdb, owned_films=[{"tmdbId": 2, "hasFile": True}]).search("seagal")[0]["films"][0]
        self.assertEqual((found["inLibrary"], found["downloaded"]), (True, True))

    def test_a_show_they_lead_is_found_by_its_tvdb_id(self):
        tmdb = FakeTmdb([SEAGAL], shows={"cast": [{"id": 26402, "episode_count": 29, "genre_ids": [10764]}]},
                        details={26402: LAWMAN})
        self.assertEqual(people(tmdb).search("seagal")[0]["shows"][0]["id"], 126841)

    def test_two_tmdb_entries_for_one_tvdb_show_appear_once(self):
        tmdb = FakeTmdb([SEAGAL], shows={"cast": [{"id": 26402, "episode_count": 29}, {"id": 99, "episode_count": 20}]},
                        details={26402: LAWMAN, 99: dict(LAWMAN, id=99)})
        self.assertEqual(len(people(tmdb).search("seagal")[0]["shows"]), 1)

    def test_guest_spots_are_left_out(self):
        tmdb = FakeTmdb([SEAGAL], shows={"cast": [{"id": 1, "episode_count": 1, "genre_ids": [35]}]})
        self.assertEqual(people(tmdb).search("seagal")[0]["shows"], [])

    def test_shows_in_the_library_are_marked(self):
        tmdb = FakeTmdb([SEAGAL], shows={"cast": [{"id": 26402, "episode_count": 29, "genre_ids": [10764]}]},
                        details={26402: LAWMAN})
        found = people(tmdb, owned_shows=[{"tvdbId": 126841}]).search("seagal")[0]["shows"][0]
        self.assertTrue(found["inLibrary"])

    def test_no_matching_person_is_no_rows(self):
        self.assertEqual(people(FakeTmdb([KENTARO])).search("glimmer man"), [])

    def test_the_same_search_is_cached(self):
        tmdb = FakeTmdb([SEAGAL])
        finder = people(tmdb)
        finder.search("seagal")
        finder.search("Seagal ")
        self.assertEqual(tmdb.lookups, 1)


class ItemTest(unittest.TestCase):
    def test_film_item_names_its_genres(self):
        self.assertEqual(tmdb_film_item(film(2, "Under Siege", 1823), {}, {28: "Action", 53: "Thriller"})["genres"],
                         "Action, Thriller")

    def test_talk_shows_are_chatter(self):
        self.assertTrue(is_chatter({"genre_ids": [10767]}))


if __name__ == "__main__":
    unittest.main()
