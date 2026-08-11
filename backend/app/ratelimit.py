"""Per-client rate limiting.

The service is free and every compile costs real CPU, so the expensive
endpoints are capped. This is an in-memory sliding-window counter — correct
for a single process, and the obvious place to swap in Redis when the API runs
on more than one.
"""

from __future__ import annotations

import os
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Deque, Dict

from fastapi import Request


@dataclass
class Limit:
    max_events: int
    window_seconds: int


COMPILE_LIMIT = Limit(
    max_events=int(os.getenv("RATE_LIMIT_COMPILES", "10")),
    window_seconds=int(os.getenv("RATE_LIMIT_WINDOW", "600")),
)
# Extraction burns a third-party API quota that is shared by every user, so it
# is capped tighter than compilation.
EXTRACT_LIMIT = Limit(
    max_events=int(os.getenv("RATE_LIMIT_EXTRACTIONS", "5")),
    window_seconds=int(os.getenv("RATE_LIMIT_WINDOW", "600")),
)
# Polling job status and downloading are cheap; they only need a ceiling that
# stops a runaway client, not a real budget.
POLL_LIMIT = Limit(max_events=600, window_seconds=600)


class SlidingWindow:
    def __init__(self) -> None:
        self._events: Dict[str, Deque[float]] = defaultdict(deque)

    def check(self, key: str, limit: Limit) -> tuple[bool, int]:
        """Record an event. Returns ``(allowed, retry_after_seconds)``."""
        now = time.time()
        cutoff = now - limit.window_seconds
        events = self._events[key]
        while events and events[0] < cutoff:
            events.popleft()
        if len(events) >= limit.max_events:
            return False, max(1, int(events[0] + limit.window_seconds - now))
        events.append(now)
        if len(self._events) > 10_000:
            self._evict(cutoff)
        return True, 0

    def _evict(self, cutoff: float) -> None:
        for key, events in list(self._events.items()):
            while events and events[0] < cutoff:
                events.popleft()
            if not events:
                del self._events[key]


limiter = SlidingWindow()


def client_key(request: Request) -> str:
    """Identify the caller.

    Behind a proxy, ``X-Forwarded-For``'s left-most entry is the client. Only
    trust it when ``TRUST_PROXY_HEADERS`` is set — otherwise anyone can spoof
    the header and sidestep the limit entirely.
    """
    if os.getenv("TRUST_PROXY_HEADERS") == "1":
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
