"""stuck: a download that makes no progress for a day is replaced; anything else is left alone."""
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fetchd.jobs.stuck import STUCK_HOURS, StuckDownloads, dead_downloads

NOW = datetime(2026, 10, 28, 12, 0, tzinfo=timezone.utc)
LONG_AGO = (NOW - timedelta(hours=STUCK_HOURS + 1)).isoformat()


def record(download_id="glimmer", left=1000, status="warning", state="downloading", monitored=True, record_id=1):
    return {"id": record_id, "downloadId": download_id, "sizeleft": left, "status": status, "title": "The Glimmer Man",
            "trackedDownloadState": state, "movie": {"title": "The Glimmer Man", "monitored": monitored}}


class DeadDownloadsTest(unittest.TestCase):
    def test_a_download_first_seen_is_not_dead(self):
        dead, _ = dead_downloads([record()], {}, NOW)
        self.assertEqual(dead, [])

    def test_no_progress_for_a_day_is_dead(self):
        dead, _ = dead_downloads([record()], {"glimmer": {"sizeleft": 1000, "since": LONG_AGO}}, NOW)
        self.assertEqual(len(dead), 1)

    def test_progress_starts_the_day_again(self):
        _, remembered = dead_downloads([record(left=900)], {"glimmer": {"sizeleft": 1000, "since": LONG_AGO}}, NOW)
        self.assertEqual(remembered["glimmer"]["since"], NOW.isoformat())

    def test_a_slow_download_that_moves_is_never_dead(self):
        dead, _ = dead_downloads([record(left=900)], {"glimmer": {"sizeleft": 1000, "since": LONG_AGO}}, NOW)
        self.assertEqual(dead, [])

    def test_a_paused_download_is_left_alone(self):
        dead, _ = dead_downloads([record(status="paused")], {"glimmer": {"sizeleft": 1000, "since": LONG_AGO}}, NOW)
        self.assertEqual(dead, [])

    def test_an_unmonitored_title_is_left_alone(self):
        dead, _ = dead_downloads([record(monitored=False)], {"glimmer": {"sizeleft": 1000, "since": LONG_AGO}}, NOW)
        self.assertEqual(dead, [])

    def test_a_download_waiting_to_import_is_left_alone(self):
        dead, _ = dead_downloads([record(state="importBlocked")], {"glimmer": {"sizeleft": 1000, "since": LONG_AGO}}, NOW)
        self.assertEqual(dead, [])

    def test_a_season_pack_is_one_download(self):
        pack = [record(download_id="pack", record_id=n) for n in range(1, 4)]
        dead, _ = dead_downloads(pack, {"pack": {"sizeleft": 1000, "since": LONG_AGO}}, NOW)
        self.assertEqual(len(dead), 1)


class FakeApp:
    name = "Radarr"

    def __init__(self, records):
        self.records = records
        self.deleted = []

    def get(self, path, **query):
        return {"records": self.records}

    def delete(self, path, **query):
        self.deleted.append((path, query))


class StuckDownloadsTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.state = Path(self.folder.name) / "stalled.json"

    def tearDown(self):
        self.folder.cleanup()

    def test_a_dead_download_is_removed_blocklisted_and_searched_again(self):
        self.state.write_text(json.dumps({"glimmer": {"sizeleft": 1000, "since": LONG_AGO}}))
        app = FakeApp([record(record_id=7)])
        StuckDownloads([app], self.state, clock=lambda: NOW).replace_dead()
        self.assertEqual(app.deleted, [("/api/v3/queue/7", {"removeFromClient": "true", "blocklist": "true",
                                                            "skipRedownload": "false"})])

    def test_the_first_run_only_remembers(self):
        app = FakeApp([record()])
        StuckDownloads([app], self.state, clock=lambda: NOW).replace_dead()
        self.assertEqual((app.deleted, list(json.loads(self.state.read_text()))), ([], ["glimmer"]))

    def test_downloads_that_left_the_queue_are_forgotten(self):
        self.state.write_text(json.dumps({"gone": {"sizeleft": 5, "since": LONG_AGO}}))
        StuckDownloads([FakeApp([])], self.state, clock=lambda: NOW).replace_dead()
        self.assertEqual(json.loads(self.state.read_text()), {})


if __name__ == "__main__":
    unittest.main()
