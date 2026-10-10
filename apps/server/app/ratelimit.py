"""Tiny in-memory sliding-window rate limiter."""

from __future__ import annotations

import time
from collections import deque
from collections.abc import Callable

SWEEP_ABOVE = 1024


class RateLimiter:
    def __init__(self, max_events: int, window_s: float = 60.0, clock: Callable[[], float] = time.monotonic):
        self.max_events = max_events
        self.window_s = window_s
        self.clock = clock
        self._events: dict[str, deque[float]] = {}

    def _prune(self, key: str, now: float) -> deque[float] | None:
        """Drops expired events; removes the key when nothing is left. Never creates keys."""
        q = self._events.get(key)
        if q is None:
            return None
        while q and now - q[0] >= self.window_s:
            q.popleft()
        if not q:
            del self._events[key]
            return None
        return q

    def _sweep(self, now: float) -> None:
        if len(self._events) > SWEEP_ABOVE:
            for k in list(self._events):
                self._prune(k, now)

    def blocked(self, key: str) -> bool:
        """True if the key is over the limit (does not record an event nor create a key)."""
        q = self._prune(key, self.clock())
        return q is not None and len(q) >= self.max_events

    def allow(self, key: str) -> bool:
        now = self.clock()
        self._sweep(now)
        q = self._prune(key, now)
        if q is not None and len(q) >= self.max_events:
            return False
        if q is None:
            q = self._events[key] = deque()
        q.append(now)
        return True
