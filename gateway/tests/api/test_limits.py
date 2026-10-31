"""limits: the sliding window that throttles failed sign-ins and pairing."""
import unittest

from fetchd.api import limits
from fetchd.api.limits import SlidingWindow


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


class SlidingWindowTest(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.window = SlidingWindow(limit=3, window=60, block=300, clock=self.clock)

    def test_events_within_limit_do_not_block(self):
        for _ in range(3):
            self.window.record("a")
        self.assertFalse(self.window.blocked("a"))

    def test_crossing_the_limit_blocks_the_key(self):
        for _ in range(4):
            self.window.record("a")
        self.assertTrue(self.window.blocked("a"))

    def test_block_is_per_key(self):
        for _ in range(4):
            self.window.record("a")
        self.assertFalse(self.window.blocked("b"))

    def test_block_ends_after_its_time(self):
        for _ in range(4):
            self.window.record("a")
        self.clock.now += 301
        self.assertFalse(self.window.blocked("a"))

    def test_old_events_fall_out_of_the_window(self):
        for _ in range(3):
            self.window.record("a")
        self.clock.now += 61
        self.window.record("a")
        self.assertFalse(self.window.blocked("a"))

    def test_allow_refuses_once_over_the_limit(self):
        results = [self.window.allow("a") for _ in range(5)]
        self.assertEqual(results, [True, True, True, False, False])

    def test_memory_stays_bounded_with_many_keys(self):
        for i in range(limits.MAX_KEYS + 10):
            self.window.record(f"key{i}")
        self.clock.now += 61
        self.window.record("late")
        self.assertLess(len(self.window._events), 10)


if __name__ == "__main__":
    unittest.main()
