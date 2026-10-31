"""storage: the plan's disk usage from xfs_quota, with a fallback to the disk itself."""
import subprocess
import tempfile
import unittest
from pathlib import Path

from fetchd.api.storage import Storage, parse_quota

# The real line from the Whatbox (KiB): used, soft quota, hard limit.
WHATBOX = "/dev/mapper/mpatha  1778710340 3808593752 3808593752   00 [--------] /mnt/mpatha\n"


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


class StorageTest(unittest.TestCase):
    def test_whatbox_quota_matches_the_plan(self):
        usage = parse_quota(WHATBOX)
        self.assertEqual((round(usage["limit"] / 1e12, 1), round(usage["used"] / 1e12, 2), usage["source"]),
                         (3.9, 1.82, "quota"))

    def test_free_is_limit_minus_used(self):
        usage = parse_quota(WHATBOX)
        self.assertEqual(usage["free"], usage["limit"] - usage["used"])

    def test_unreadable_output_is_no_quota(self):
        self.assertIsNone(parse_quota("xfs_quota: cannot find mount point"))

    def test_zero_limit_is_no_quota(self):
        self.assertIsNone(parse_quota("/dev/sda 100 0 0 00 [----] /"))

    def test_falls_back_to_the_disk_without_xfs_quota(self):
        def missing(command):
            raise FileNotFoundError(command[0])
        with tempfile.TemporaryDirectory() as home:
            self.assertEqual(Storage(Path(home), run=missing).usage()["source"], "disk")

    def test_falls_back_when_xfs_quota_fails(self):
        def failing(command):
            raise subprocess.CalledProcessError(1, command)
        with tempfile.TemporaryDirectory() as home:
            self.assertEqual(Storage(Path(home), run=failing).usage()["source"], "disk")

    def test_usage_is_cached_for_a_minute(self):
        calls = []
        clock = Clock()

        def counting(command):
            calls.append(command)
            return WHATBOX
        with tempfile.TemporaryDirectory() as home:
            storage = Storage(Path(home), run=counting, clock=clock)
            storage.usage()
            storage.usage()
            clock.now += 61
            storage.usage()
        self.assertEqual(len(calls), 2)


if __name__ == "__main__":
    unittest.main()
