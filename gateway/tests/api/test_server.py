"""server: the HTTP API end to end, with fake libraries behind it."""
import http.client
import json
import socket
import tempfile
import threading
import unittest
from unittest import mock
from pathlib import Path

from fetchd.api.devices import Registry
from fetchd.arr.library import AlreadyAdded, NotFound
from fetchd.api.server import MAX_BODY_BYTES, Gateway, GatewayServer, Handler
from fetchd.upstream import UpstreamError

FILM = {"kind": "film", "id": 27205, "title": "Inception", "year": 2010, "inLibrary": False}
SHOW = {"kind": "show", "id": 81189, "title": "Breaking Bad", "year": 2008, "inLibrary": False}


class FakeFilms:
    def __init__(self):
        self.added = []
        self.fail = False

    def search(self, term):
        if self.fail:
            raise UpstreamError("Radarr", "unreachable")
        return self.found(term) if hasattr(self, "found") else [FILM]

    def profiles(self):
        return [{"id": 1, "name": "Any"}, {"id": 4, "name": "HD-1080p"}]

    def default_profile(self):
        return 4

    def add(self, tmdb_id, profile_id=None):
        if tmdb_id == 404:
            raise NotFound(tmdb_id)
        if tmdb_id == 409:
            raise AlreadyAdded(dict(FILM, inLibrary=True))
        self.added.append((tmdb_id, profile_id))
        return dict(FILM, id=tmdb_id, inLibrary=True)

    def downloads(self):
        return [{"kind": "film", "title": "Inception", "progress": 0.5}]

    def recent(self, count):
        return [("2026-10-20T10:00:00Z", FILM)]

    def discover(self):
        return [{"id": "recommended", "items": [FILM]}, {"id": "trending", "items": [dict(FILM, id=62)]}]

    def library(self):
        return [dict(FILM, inLibrary=True, size=1000, quality="Bluray-1080p", problem="")]

    def delete_file(self, tmdb_id):
        self.added.append(("delete_file", tmdb_id))
        return 1000

    def remove(self, tmdb_id):
        if tmdb_id == 404:
            raise NotFound(tmdb_id)
        self.added.append(("remove", tmdb_id))
        return 2000


class FakeShows(FakeFilms):
    def search(self, term):
        return self.found(term) if hasattr(self, "found") else [SHOW]

    def add(self, tvdb_id, seasons, profile_id=None):
        self.added.append((tvdb_id, seasons, profile_id))
        return dict(SHOW, id=tvdb_id, inLibrary=True)

    def downloads(self):
        return [{"kind": "show", "title": "Breaking Bad", "progress": 0.1}]

    def recent(self, count):
        return [("2026-10-25T10:00:00Z", SHOW)]

    def library(self):
        return [dict(SHOW, inLibrary=True, size=5000, quality="", problem="")]


class FakeEpisodes:
    def __init__(self):
        self.chosen = []

    def list(self, tvdb_id):
        return {"inLibrary": False, "seasons": [{"number": 1, "episodes": [{"number": 1, "title": "Pilot"}]}]}

    def delete_files(self, tvdb_id, picks):
        self.chosen.append(("delete", tvdb_id, picks))
        return {"deleted": len(picks), "freed": 300}

    def choose(self, tvdb_id, picks, profile_id=None):
        self.chosen.append((tvdb_id, picks, profile_id))
        return {"item": dict(SHOW, id=tvdb_id, inLibrary=True), "chosen": len(picks), "searching": len(picks),
                "unmatched": 0}


class FakeStorage:
    def usage(self):
        return {"used": 1, "limit": 3, "free": 2, "source": "quota"}


class FakeShowDiscovery:
    def rows(self):
        return [{"id": "trendingShows", "source": "tmdb", "items": [SHOW]}]


class FakePeople:
    def __init__(self):
        self.fail = False

    def search(self, term):
        if self.fail:
            raise UpstreamError("TMDB", "unreachable")
        if hasattr(self, "found"):
            return self.found
        return [{"name": "Steven Seagal", "directing": False, "films": [FILM], "shows": [SHOW]}]


class FakeBrowse:
    def rows(self, kind, genre):
        if genre != "bad":
            raise ValueError("unknown genre")
        return [{"id": "soBad", "source": "tmdb", "items": [FILM]}]


class FakeDetails:
    def of(self, kind, title_id):
        if title_id == 404:
            from fetchd.tmdb.details import NoDetails
            raise NoDetails("unknown")
        return {"tagline": "Two good cops. One bad situation.", "cast": [{"name": "Steven Seagal"}]}


class FakeSpelling:
    def suggest(self, term):
        return "The Glimmer Man" if term == "glimer man" else ""


class FakeWatching:
    def __init__(self):
        self.reply = {"server": "e124", "items": [{"kind": "film", "key": "1629", "title": "Hard Target"}]}

    def items(self):
        if self.reply is None:
            from fetchd.upstream import UpstreamError
            raise UpstreamError("Plex", "unreachable")
        return self.reply


class ServerTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.registry = Registry(Path(self.dir.name) / "devices.json")
        self.films, self.shows, self.episodes = FakeFilms(), FakeShows(), FakeEpisodes()
        self.people = FakePeople()
        self.watching = FakeWatching()
        self.server = GatewayServer(("127.0.0.1", 0), Gateway(self.registry, self.films, self.shows, self.episodes,
                                                                   FakeShowDiscovery(), FakeStorage(), self.people,
                                                                   FakeSpelling(), FakeBrowse(), FakeDetails(),
                                                                   self.watching))
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.port = self.server.server_address[1]
        self.token = self.pair()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.dir.cleanup()

    def call(self, method, path, body=None, token=None, headers=None, raw=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        sent = dict(headers or {})
        if token:
            sent["Authorization"] = f"Bearer {token}"
        payload = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
        if payload is not None:
            sent.setdefault("Content-Type", "application/json")
        connection.request(method, path, body=payload, headers=sent)
        response = connection.getresponse()
        text = response.read()
        connection.close()
        return response.status, (json.loads(text) if text else None), response

    def pair(self):
        _, started, _ = self.call("POST", "/v1/pair", {"device": "Test TV"})
        self.registry.approve(started["code"])
        _, polled, _ = self.call("POST", "/v1/pair/poll", {"pairing": started["pairing"]})
        return polled["token"]

    def test_health_needs_no_token(self):
        status, body, _ = self.call("GET", "/v1/health")
        self.assertEqual((status, body["ok"]), (200, True))

    def test_pairing_hands_out_a_token(self):
        self.assertTrue(self.token.startswith("fd1_"))

    def test_poll_before_approval_is_pending(self):
        _, started, _ = self.call("POST", "/v1/pair", {"device": "TV"})
        _, polled, _ = self.call("POST", "/v1/pair/poll", {"pairing": started["pairing"]})
        self.assertEqual(polled, {"status": "pending"})

    def test_search_returns_films_and_shows(self):
        status, body, _ = self.call("GET", "/v1/search?q=breaking%20bad", token=self.token)
        self.assertEqual((status, body["films"][0]["id"], body["shows"][0]["id"]), (200, 27205, 81189))

    def test_search_without_token_is_unauthorized(self):
        status, _, response = self.call("GET", "/v1/search?q=x")
        self.assertEqual((status, response.getheader("WWW-Authenticate")), (401, 'Bearer realm="fetchd"'))

    def test_search_with_wrong_token_is_unauthorized(self):
        status, _, _ = self.call("GET", "/v1/search?q=x", token="fd1_" + "A" * 43)
        self.assertEqual(status, 401)

    def test_search_reports_one_side_unavailable(self):
        self.films.fail = True
        status, body, _ = self.call("GET", "/v1/search?q=x", token=self.token)
        self.assertEqual((status, body["films"], body["unavailable"]), (200, [], ["films"]))

    def test_search_includes_the_matching_person(self):
        status, body, _ = self.call("GET", "/v1/search?q=seagal", token=self.token)
        self.assertEqual((status, body["people"][0]["name"]), (200, "Steven Seagal"))

    def test_search_without_tmdb_still_returns_titles(self):
        self.people.fail = True
        status, body, _ = self.call("GET", "/v1/search?q=seagal", token=self.token)
        self.assertEqual((status, body["people"], body["films"][0]["id"]), (200, [], 27205))

    def test_a_search_that_finds_something_has_no_suggestion(self):
        _, body, _ = self.call("GET", "/v1/search?q=breaking%20bad", token=self.token)
        self.assertEqual(body["suggestion"], "")

    def test_a_search_that_finds_nothing_searches_the_closest_title(self):
        self.films.found = lambda term: [FILM] if term == "The Glimmer Man" else []
        self.shows.found = lambda term: []
        self.people.found = []
        _, body, _ = self.call("GET", "/v1/search?q=glimer%20man", token=self.token)
        self.assertEqual((body["suggestion"], body["films"][0]["id"]), ("The Glimmer Man", 27205))

    def test_unrelated_results_still_get_the_closest_title(self):
        self.films.found = lambda term: [FILM] if term == "The Glimmer Man" else []
        self.shows.found = lambda term: [dict(SHOW, title="Spider-Man")] if term == "glimer man" else []
        self.people.found = []
        _, body, _ = self.call("GET", "/v1/search?q=glimer%20man", token=self.token)
        self.assertEqual(body["suggestion"], "The Glimmer Man")

    def test_genres_start_with_so_bad_its_good(self):
        _, body, _ = self.call("GET", "/v1/genres", token=self.token)
        self.assertEqual(body["films"][0], {"id": "bad", "name": "So bad it's good"})

    def test_browse_returns_the_genres_rows(self):
        _, body, _ = self.call("GET", "/v1/browse?kind=film&genre=bad", token=self.token)
        self.assertEqual(body["rows"][0]["id"], "soBad")

    def test_browse_refuses_an_unknown_genre(self):
        status, body, _ = self.call("GET", "/v1/browse?kind=film&genre=1;drop", token=self.token)
        self.assertEqual((status, body["error"]), (400, "invalid_request"))

    def test_details_of_a_film(self):
        _, body, _ = self.call("GET", "/v1/details?kind=film&id=9625", token=self.token)
        self.assertEqual(body["cast"][0]["name"], "Steven Seagal")

    def test_details_of_an_unknown_title_are_not_found(self):
        status, _, _ = self.call("GET", "/v1/details?kind=film&id=404", token=self.token)
        self.assertEqual(status, 404)

    def test_details_need_a_numeric_id(self):
        status, _, _ = self.call("GET", "/v1/details?kind=film&id=9625abc", token=self.token)
        self.assertEqual(status, 400)

    def test_watching_lists_what_plex_has_half_watched(self):
        status, body, _ = self.call("GET", "/v1/watching", token=self.token)
        self.assertEqual((status, body["items"][0]["title"]), (200, "Hard Target"))

    def test_watching_without_plex_is_upstream_unavailable(self):
        self.watching.reply = None
        status, body, _ = self.call("GET", "/v1/watching", token=self.token)
        self.assertEqual((status, body["error"]), (502, "upstream_unavailable"))

    def test_watching_needs_a_token(self):
        status, _, _ = self.call("GET", "/v1/watching")
        self.assertEqual(status, 401)

    def test_empty_and_overlong_queries_are_refused(self):
        for query in ["", "%20", "x" * 101, "a%0Ab"]:
            with self.subTest(query=query):
                status, body, _ = self.call("GET", f"/v1/search?q={query}", token=self.token)
                self.assertEqual((status, body["error"]), (400, "invalid_query"))

    def test_add_film(self):
        status, body, _ = self.call("POST", "/v1/films", {"id": 27205, "profile": 4}, token=self.token)
        self.assertEqual((status, body["item"]["inLibrary"], self.films.added), (201, True, [(27205, 4)]))

    def test_add_show_with_seasons(self):
        status, _, _ = self.call("POST", "/v1/shows", {"id": 81189, "seasons": "latest"}, token=self.token)
        self.assertEqual((status, self.shows.added), (201, [(81189, "latest", None)]))

    def test_add_existing_film_is_a_conflict(self):
        status, body, _ = self.call("POST", "/v1/films", {"id": 409}, token=self.token)
        self.assertEqual((status, body["error"], body["item"]["inLibrary"]), (409, "already_added", True))

    def test_add_unknown_film_is_not_found(self):
        status, _, _ = self.call("POST", "/v1/films", {"id": 404}, token=self.token)
        self.assertEqual(status, 404)

    def test_add_validates_fields(self):
        bad = [({"id": "27205"}, "/v1/films"), ({"id": True}, "/v1/films"), ({"id": -1}, "/v1/films"),
               ({"id": 2**40}, "/v1/films"), ({"id": 1, "profile": "4"}, "/v1/films"),
               ({"id": 1, "seasons": "everything"}, "/v1/shows"), ({"id": 1}, "/v1/shows")]
        for body, path in bad:
            with self.subTest(body=body):
                status, _, _ = self.call("POST", path, body, token=self.token)
                self.assertEqual(status, 400)

    def test_extra_fields_cannot_steer_the_add(self):
        self.call("POST", "/v1/shows", {"id": 1, "seasons": "all", "rootFolderPath": "/etc", "path": "/"},
                  token=self.token)
        self.assertEqual(self.shows.added, [(1, "all", None)])

    def test_body_must_be_json(self):
        status, _, _ = self.call("POST", "/v1/films", raw=b"id=1", token=self.token,
                                 headers={"Content-Type": "application/x-www-form-urlencoded"})
        self.assertEqual(status, 415)

    def test_large_body_is_refused(self):
        status, _, _ = self.call("POST", "/v1/films", raw=b"{" + b" " * (MAX_BODY_BYTES + 1) + b"}",
                                 token=self.token)
        self.assertEqual(status, 413)

    def test_browser_requests_are_refused(self):
        status, body, _ = self.call("GET", "/v1/search?q=x", token=self.token,
                                    headers={"Origin": "https://evil.example"})
        self.assertEqual((status, body["error"]), (403, "browser_requests_not_allowed"))

    def test_other_methods_are_refused(self):
        status, _, response = self.call("DELETE", "/v1/films", token=self.token)
        self.assertEqual((status, response.getheader("Allow")), (405, "GET, POST"))

    def test_unknown_path_is_not_found(self):
        status, _, _ = self.call("GET", "/api/v3/system/status", token=self.token)
        self.assertEqual(status, 404)

    def test_security_headers_on_every_reply(self):
        _, _, response = self.call("GET", "/v1/health")
        self.assertEqual((response.getheader("Cache-Control"), response.getheader("X-Content-Type-Options"),
                          response.getheader("Server")), ("no-store", "nosniff", "fetchd"))

    def test_repeated_wrong_tokens_lock_out_the_client(self):
        for _ in range(21):
            self.call("GET", "/v1/downloads", token="fd1_" + "B" * 43, headers={"X-Real-IP": "203.0.113.9"})
        status, _, _ = self.call("GET", "/v1/downloads", token="fd1_" + "B" * 43, headers={"X-Real-IP": "203.0.113.9"})
        self.assertEqual(status, 429)

    def test_valid_token_still_works_during_a_lockout(self):
        for _ in range(21):
            self.call("GET", "/v1/downloads", token="fd1_" + "B" * 43, headers={"X-Real-IP": "203.0.113.9"})
        status, _, _ = self.call("GET", "/v1/downloads", token=self.token, headers={"X-Real-IP": "203.0.113.9"})
        self.assertEqual(status, 200)

    def test_downloads_and_recent_merge_both_libraries(self):
        _, downloads, _ = self.call("GET", "/v1/downloads", token=self.token)
        _, recent, _ = self.call("GET", "/v1/recent", token=self.token)
        self.assertEqual(([d["kind"] for d in downloads["downloads"]], [i["kind"] for i in recent["items"]]),
                         (["film", "show"], ["show", "film"]))

    def test_episode_list_for_a_show(self):
        status, body, _ = self.call("GET", "/v1/episodes?show=81189", token=self.token)
        self.assertEqual((status, body["seasons"][0]["number"]), (200, 1))

    def test_episode_list_needs_a_numeric_show(self):
        for query in ["", "show=abc", "show=-4", "show=0"]:
            with self.subTest(query=query):
                status, _, _ = self.call("GET", f"/v1/episodes?{query}", token=self.token)
                self.assertEqual(status, 400)

    def test_choose_episodes(self):
        status, body, _ = self.call("POST", "/v1/episodes", {"show": 81189, "episodes": [[1, 1], [1, 2], [0, 3]]},
                                    token=self.token)
        self.assertEqual((status, body["chosen"], self.episodes.chosen[0][1]), (200, 3, {(1, 1), (1, 2), (0, 3)}))

    def test_choose_validates_every_pick(self):
        bad = [None, "1x1", [[1]], [[1, 2, 3]], [["1", 2]], [[True, 1]], [[-1, 1]], [[1, 0]], [[1, 1]] * 5001]
        for episodes in bad:
            with self.subTest(episodes=str(episodes)[:40]):
                status, _, _ = self.call("POST", "/v1/episodes", {"show": 81189, "episodes": episodes},
                                         token=self.token)
                self.assertEqual(status, 400)

    def test_choose_needs_a_token(self):
        status, _, _ = self.call("POST", "/v1/episodes", {"show": 81189, "episodes": [[1, 1]]})
        self.assertEqual(status, 401)

    def test_discover_interleaves_film_and_show_rows(self):
        status, body, _ = self.call("GET", "/v1/discover", token=self.token)
        self.assertEqual((status, [r["id"] for r in body["rows"]]), (200, ["recommended", "trendingShows", "trending"]))

    def test_discover_needs_a_token(self):
        status, _, _ = self.call("GET", "/v1/discover")
        self.assertEqual(status, 401)

    def test_library_lists_both_and_the_disk(self):
        status, body, _ = self.call("GET", "/v1/library", token=self.token)
        self.assertEqual((status, len(body["films"]), len(body["shows"]), body["storage"]["source"]), (200, 1, 1, "quota"))

    def test_delete_needs_the_confirmation(self):
        status, body, _ = self.call("POST", "/v1/library/delete", {"kind": "film", "id": 62, "what": "file"},
                                    token=self.token)
        self.assertEqual((status, body["error"], self.films.added), (400, "confirmation_required", []))

    def test_delete_a_film_file(self):
        status, body, _ = self.call("POST", "/v1/library/delete",
                                    {"kind": "film", "id": 62, "what": "file", "confirm": "delete"}, token=self.token)
        self.assertEqual((status, body["freed"], self.films.added), (200, 1000, [("delete_file", 62)]))

    def test_remove_a_film(self):
        self.call("POST", "/v1/library/delete", {"kind": "film", "id": 62, "what": "title", "confirm": "delete"},
                  token=self.token)
        self.assertEqual(self.films.added, [("remove", 62)])

    def test_unknown_deletes_are_refused(self):
        for body in [{"kind": "show", "id": 1, "what": "file"}, {"kind": "folder", "id": 1, "what": "title"},
                     {"kind": "film", "id": 1, "what": "everything"}, {"kind": "film", "id": "1", "what": "title"}]:
            with self.subTest(body=body):
                status, _, _ = self.call("POST", "/v1/library/delete", dict(body, confirm="delete"), token=self.token)
                self.assertEqual(status, 400)

    def test_removing_a_missing_film_is_not_found(self):
        status, _, _ = self.call("POST", "/v1/library/delete",
                                 {"kind": "film", "id": 404, "what": "title", "confirm": "delete"}, token=self.token)
        self.assertEqual(status, 404)

    def test_delete_episodes(self):
        status, body, _ = self.call("POST", "/v1/library/episodes/delete",
                                    {"show": 81189, "episodes": [[1, 1]], "confirm": "delete"}, token=self.token)
        self.assertEqual((status, body["deleted"], self.episodes.chosen[0]), (200, 1, ("delete", 81189, {(1, 1)})))

    def test_deletes_need_a_token(self):
        status, _, _ = self.call("POST", "/v1/library/delete",
                                 {"kind": "film", "id": 62, "what": "file", "confirm": "delete"})
        self.assertEqual(status, 401)

    def test_profiles_include_defaults(self):
        _, body, _ = self.call("GET", "/v1/profiles", token=self.token)
        self.assertEqual((body["films"]["default"], len(body["shows"]["profiles"])), (4, 2))


class BindTest(unittest.TestCase):
    def test_refuses_to_listen_beyond_loopback(self):
        with self.assertRaises(ValueError):
            GatewayServer(("0.0.0.0", 0), None)


class SlowClientTest(unittest.TestCase):
    @mock.patch.object(Handler, "timeout", 1)
    def test_idle_connection_is_closed(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        server = GatewayServer(("127.0.0.1", 0), Gateway(Registry(Path(directory.name) / "d.json"),
                                                         FakeFilms(), FakeShows(), FakeEpisodes(),
                                                         FakeShowDiscovery(), FakeStorage(), FakePeople(),
                                                         FakeSpelling(), FakeBrowse(), FakeDetails(),
                                                     FakeWatching()))
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        sock = socket.create_connection(server.server_address, timeout=30)
        sock.sendall(b"GET /v1/health HTTP/1.1\r\n")
        sock.settimeout(10)
        self.assertEqual(sock.recv(1), b"")
        sock.close()


if __name__ == "__main__":
    unittest.main()
