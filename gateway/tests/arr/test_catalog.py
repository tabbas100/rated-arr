"""catalog: public items from real Radarr 6, Sonarr 4 and Sonarr 3 replies, and the add payloads."""
import json
import unittest
from pathlib import Path

from fetchd.arr import catalog

FIXTURES = Path(__file__).resolve().parents[3] / "fixtures"


def fixture(name: str):
    return json.loads((FIXTURES / name).read_text("utf-8"))


class FilmItemTest(unittest.TestCase):
    def setUp(self):
        self.inception = next(r for r in fixture("radarr-lookup.json") if r["tmdbId"] == 27205)

    def test_reads_title_year_and_tmdb_id(self):
        item = catalog.film_item(self.inception)
        self.assertEqual((item["title"], item["year"], item["id"]), ("Inception", 2010, 27205))

    def test_prefers_imdb_rating_from_nested_ratings(self):
        self.assertEqual(catalog.film_item(self.inception)["rating"], 8.8)

    def test_poster_uses_small_tmdb_size(self):
        self.assertRegex(catalog.film_item(self.inception)["poster"], r"^https://image\.tmdb\.org/t/p/w342/")

    def test_lookup_result_is_not_in_library(self):
        self.assertFalse(catalog.film_item(self.inception)["inLibrary"])

    def test_library_entry_with_file_is_downloaded(self):
        entry = dict(self.inception, id=7, hasFile=True)
        item = catalog.film_item(entry)
        self.assertEqual((item["inLibrary"], item["downloaded"]), (True, True))

    def test_exposes_only_public_fields(self):
        self.assertEqual(set(catalog.film_item(self.inception)), {
            "kind", "id", "title", "year", "overview", "poster", "fanart", "runtime", "genres", "rating",
            "network", "seasons", "inLibrary", "downloaded"})


class ShowItemTest(unittest.TestCase):
    def test_sonarr4_breaking_bad(self):
        lookup = next(r for r in fixture("sonarr4-lookup.json") if r["tvdbId"] == 81189)
        item = catalog.show_item(lookup)
        self.assertEqual((item["title"], item["seasons"], item["network"]), ("Breaking Bad", 5, "AMC"))

    def test_sonarr3_reads_the_same_fields(self):
        lookup = next(r for r in fixture("sonarr3-lookup.json") if r["tvdbId"] == 81189)
        item = catalog.show_item(lookup)
        self.assertEqual((item["title"], item["year"], item["seasons"]), ("Breaking Bad", 2008, 5))

    def test_tvdb_poster_is_kept(self):
        lookup = next(r for r in fixture("sonarr4-lookup.json") if r["tvdbId"] == 81189)
        self.assertTrue(catalog.show_item(lookup)["poster"].startswith("https://artworks.thetvdb.com/"))


class ImageTest(unittest.TestCase):
    def test_drops_images_on_other_hosts(self):
        self.assertEqual(catalog._image("https://evil.example/x.jpg", "w342"), "")

    def test_drops_plain_http_images(self):
        self.assertEqual(catalog._image("http://image.tmdb.org/t/p/original/x.jpg", "w342"), "")

    def test_drops_relative_server_paths(self):
        self.assertEqual(catalog._image("/MediaCoverProxy/abc/x.jpg", "w342"), "")


class TextLimitTest(unittest.TestCase):
    def test_overview_is_cut_to_limit(self):
        item = catalog.film_item({"overview": "x" * 5000, "tmdbId": 1})
        self.assertEqual(len(item["overview"]), catalog.MAX_OVERVIEW)

    def test_non_string_values_become_empty(self):
        item = catalog.film_item({"title": {"nested": "object"}, "tmdbId": 1})
        self.assertEqual(item["title"], "")


class FilmPayloadTest(unittest.TestCase):
    def setUp(self):
        self.lookup = fixture("radarr-lookup.json")[0]
        self.payload = catalog.film_payload(self.lookup, 4, "/movies")

    def test_sets_profile_folder_and_search(self):
        self.assertEqual((self.payload["qualityProfileId"], self.payload["rootFolderPath"],
                          self.payload["addOptions"]["searchForMovie"]), (4, "/movies", True))

    def test_does_not_change_the_lookup(self):
        self.assertNotIn("rootFolderPath", self.lookup)


class ShowPayloadTest(unittest.TestCase):
    def setUp(self):
        self.lookup = next(r for r in fixture("sonarr4-lookup.json") if r["tvdbId"] == 81189)

    def monitored(self, choice):
        payload = catalog.show_payload(self.lookup, 1, "/tv", choice, 0)
        return sorted(s["seasonNumber"] for s in payload["seasons"] if s["monitored"])

    def test_all_monitors_every_regular_season(self):
        self.assertEqual(self.monitored("all"), [1, 2, 3, 4, 5])

    def test_latest_monitors_only_the_last_season(self):
        self.assertEqual(self.monitored("latest"), [5])

    def test_first_monitors_only_season_one(self):
        self.assertEqual(self.monitored("first"), [1])

    def test_future_monitors_no_existing_season(self):
        self.assertEqual(self.monitored("future"), [])

    def test_future_skips_the_search_for_old_episodes(self):
        payload = catalog.show_payload(self.lookup, 1, "/tv", "future", 0)
        self.assertEqual((payload["addOptions"]["monitor"], payload["addOptions"]["searchForMissingEpisodes"]),
                         ("future", False))

    def test_language_profile_is_set_for_sonarr3(self):
        self.assertEqual(catalog.show_payload(self.lookup, 1, "/tv", "all", 3)["languageProfileId"], 3)

    def test_language_profile_is_left_alone_for_sonarr4(self):
        payload = catalog.show_payload(self.lookup, 1, "/tv", "all", 0)
        self.assertEqual(payload.get("languageProfileId"), self.lookup.get("languageProfileId"))

    def test_unknown_choice_is_refused(self):
        with self.assertRaises(ValueError):
            catalog.show_payload(self.lookup, 1, "/tv", "everything", 0)


class LibraryFilmTest(unittest.TestCase):
    def movie(self, quality, name):
        return {"tmdbId": 62, "title": "2001: A Space Odyssey", "id": 71, "hasFile": True,
                "movieFile": {"id": 51, "size": 37421776896, "relativePath": name,
                              "quality": {"quality": {"name": quality}}}}

    def test_disc_image_is_a_problem(self):
        item = catalog.library_film(self.movie("BR-DISK", "2001.A.Space.Odyssey.1968.BluRay.iso"))
        self.assertEqual((item["problem"], item["size"], item["quality"]), ("discImage", 37421776896, "BR-DISK"))

    def test_iso_name_alone_is_a_problem(self):
        self.assertEqual(catalog.library_film(self.movie("Bluray-1080p", "x.ISO"))["problem"], "discImage")

    def test_normal_file_has_no_problem(self):
        self.assertEqual(catalog.library_film(self.movie("Bluray-1080p", "x.mkv"))["problem"], "")

    def test_no_file_path_leaves_the_box(self):
        item = catalog.library_film(self.movie("Bluray-1080p", "2001.A.Space.Odyssey.mkv"))
        self.assertNotIn("2001.A.Space.Odyssey.mkv", str(item))


class SeasonListTest(unittest.TestCase):
    def setUp(self):
        self.guide = fixture("skyhook-81189.json")["episodes"]

    def test_regular_seasons_in_order_and_specials_last(self):
        numbers = [s["number"] for s in catalog.season_list(self.guide)]
        self.assertEqual(numbers, [1, 2, 3, 4, 5, 0])

    def test_episode_counts_per_season(self):
        counts = {s["number"]: len(s["episodes"]) for s in catalog.season_list(self.guide)}
        self.assertEqual((counts[1], counts[5], counts[0]), (7, 16, 18))

    def test_guide_episodes_are_neither_downloaded_nor_wanted(self):
        pilot = catalog.season_list(self.guide)[0]["episodes"][0]
        self.assertEqual((pilot["number"], pilot["downloaded"], pilot["wanted"], pilot["aired"]), (1, False, False, True))

    def test_library_flags_come_through(self):
        episode = {"seasonNumber": 1, "episodeNumber": 2, "title": "Cat's in the Bag", "hasFile": True,
                   "monitored": True, "airDateUtc": "2008-01-28T03:00:00Z"}
        listed = catalog.season_list([episode])[0]["episodes"][0]
        self.assertEqual((listed["downloaded"], listed["wanted"]), (True, True))

    def test_future_and_undated_episodes_have_not_aired(self):
        future = {"seasonNumber": 9, "episodeNumber": 1, "airDateUtc": "2999-01-01T00:00:00Z"}
        undated = {"seasonNumber": 9, "episodeNumber": 2}
        listed = catalog.season_list([future, undated])[0]["episodes"]
        self.assertEqual([e["aired"] for e in listed], [False, False])


class DownloadTest(unittest.TestCase):
    def test_episode_progress_and_detail(self):
        record = {"series": {"title": "Severance"}, "episode": {"seasonNumber": 2, "episodeNumber": 5, "title": "Trojan's Horse"},
                  "size": 1000, "sizeleft": 250, "status": "downloading", "timeleft": "00:12:30"}
        item = catalog.download_item(record, "show")
        self.assertEqual((item["title"], item["detail"], item["progress"], item["state"], item["timeLeft"]),
                         ("Severance", "S02E05 · Trojan's Horse", 0.75, "downloading", "12m"))

    def test_download_names_its_title(self):
        record = {"series": {"title": "Severance", "tvdbId": 371980}, "size": 0}
        self.assertEqual(catalog.download_item(record, "show")["id"], 371980)

    def test_problem_message_comes_from_status_messages(self):
        record = {"movie": {"title": "China Salesman"}, "status": "warning",
                  "statusMessages": [{"title": "x", "messages": ["The download is stalled with no connections"]}]}
        self.assertEqual(catalog.download_item(record, "film")["message"], "The download is stalled with no connections")

    def test_problem_message_falls_back_to_error_message(self):
        record = {"movie": {"title": "X"}, "status": "warning", "errorMessage": "Not enough disk space"}
        self.assertEqual(catalog.download_item(record, "film")["message"], "Not enough disk space")

    def test_film_detail_is_quality(self):
        record = {"movie": {"title": "Heat"}, "quality": {"quality": {"name": "Bluray-1080p"}}, "size": 0}
        self.assertEqual(catalog.download_item(record, "film")["detail"], "Bluray-1080p")

    def test_warning_is_a_problem(self):
        self.assertEqual(catalog.download_state({"status": "downloading", "trackedDownloadStatus": "warning"}), "problem")

    def test_import_pending_is_importing(self):
        self.assertEqual(catalog.download_state({"status": "completed", "trackedDownloadState": "importPending"}),
                         "importing")


class TimeLeftTest(unittest.TestCase):
    def test_formats(self):
        cases = {"01:05:30": "1h 05m", "1.02:00:00": "1d 2h", "00:00:20": "<1m", "00:00:00": "", "": "", "junk": ""}
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(catalog.time_left(raw), expected)


if __name__ == "__main__":
    unittest.main()
