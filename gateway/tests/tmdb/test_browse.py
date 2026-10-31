"""browse: TMDB's discover lists by genre, with "So bad it's good" for films."""
import unittest

from fetchd.tmdb.browse import Browse, row_queries


class FakeTmdb:
    def __init__(self):
        self.queries = []

    def discover(self, kind, query):
        self.queries.append((kind, query))
        if kind == "movie":
            return [{"id": 26914, "title": "Troll 2", "release_date": "1990-10-12", "vote_average": 3.9}]
        return [{"id": 873}]

    def film_genres(self):
        return {}

    def show(self, tmdb_id):
        return {"id": 873, "name": "Columbo", "external_ids": {"tvdb_id": 73215}}


class FakeApp:
    def __init__(self, records):
        self.records = records

    def get(self, path, **query):
        return self.records


class FakeLibrary:
    def __init__(self, records):
        self.upstream = FakeApp(records)


def browse(tmdb, films=(), shows=()):
    return Browse(FakeLibrary(list(films)), FakeLibrary(list(shows)), tmdb)


class RowQueriesTest(unittest.TestCase):
    def test_so_bad_its_good_has_three_rows(self):
        self.assertEqual([row for row, _ in row_queries("film", "bad")], ["soBad", "bMovies", "flops"])

    def test_a_genre_has_popular_and_best_rated(self):
        self.assertEqual([row for row, _ in row_queries("film", "27")], ["popular", "topRated"])

    def test_famous_flops_need_many_votes(self):
        flops = dict(row_queries("film", "bad"))["flops"]
        self.assertEqual((flops["vote_average.lte"], flops["vote_count.gte"]), (4.5, 300))

    def test_shows_have_no_bad_genre(self):
        with self.assertRaises(ValueError):
            row_queries("show", "bad")

    def test_unknown_genres_are_refused(self):
        with self.assertRaises(ValueError):
            row_queries("film", "28 OR 1")


class BrowseTest(unittest.TestCase):
    def test_films_in_the_library_are_marked(self):
        rows = browse(FakeTmdb(), films=[{"tmdbId": 26914, "hasFile": True}]).rows("film", "bad")
        self.assertEqual(rows[0]["items"][0]["downloaded"], True)

    def test_shows_are_keyed_by_tvdb_id(self):
        self.assertEqual(browse(FakeTmdb()).rows("show", "80")[0]["items"][0]["id"], 73215)

    def test_rows_are_cached(self):
        tmdb = FakeTmdb()
        finder = browse(tmdb)
        finder.rows("film", "27")
        finder.rows("film", "27")
        self.assertEqual(len(tmdb.queries), 2)


if __name__ == "__main__":
    unittest.main()
