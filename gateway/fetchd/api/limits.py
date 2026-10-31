"""In-memory limits on failed sign-ins and unauthenticated calls."""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from typing import Callable

MAX_KEYS = 10_000


class SlidingWindow:
    """Allows at most `limit` events per key within `window` seconds, then blocks the key for `block` seconds."""

    def __init__(self, limit: int, window: float, block: float, clock: Callable[[], float] = time.monotonic) -> None:
        self.limit = limit
        self.window = window
        self.block = block
        self.clock = clock
        self._events: dict[str, deque] = defaultdict(deque)
        self._blocked_until: dict[str, float] = {}
        self._lock = threading.Lock()

    def blocked(self, key: str) -> bool:
        with self._lock:
            return self._blocked_until.get(key, 0) > self.clock()

    def record(self, key: str) -> bool:
        """Counts one event; True when this one crosses the limit and the key is now blocked."""
        with self._lock:
            now = self.clock()
            if len(self._events) > MAX_KEYS:
                self._forget_idle_keys(now)
            events = self._events[key]
            events.append(now)
            while events and now - events[0] > self.window:
                events.popleft()
            if len(events) > self.limit:
                self._blocked_until[key] = now + self.block
                events.clear()
                return True
            return False

    def _forget_idle_keys(self, now: float) -> None:
        """Bounds memory when many addresses call: drops keys with no recent event and no block."""
        for key in [k for k, events in self._events.items() if not events or now - events[-1] > self.window]:
            del self._events[key]
        for key in [k for k, until in self._blocked_until.items() if until <= now]:
            del self._blocked_until[key]

    def allow(self, key: str) -> bool:
        """Records an event and says whether it is within the limit; for calls that are limited outright."""
        if self.blocked(key):
            return False
        return not self.record(key)
