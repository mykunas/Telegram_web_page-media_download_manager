from __future__ import annotations

import time
from collections import defaultdict, deque
from threading import Lock

from fastapi import Request

from app.core.exceptions import AppException


class InMemoryRateLimiter:
    def __init__(self) -> None:
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def check(self, key: str, *, limit: int, window_seconds: int) -> None:
        now = time.monotonic()
        threshold = now - window_seconds
        with self._lock:
            events = self._events[key]
            while events and events[0] <= threshold:
                events.popleft()
            if len(events) >= limit:
                raise AppException("too many sensitive operations; try again later", status_code=429)
            events.append(now)


rate_limiter = InMemoryRateLimiter()


def sensitive_rate_limit(bucket: str, *, limit: int, window_seconds: int):
    def dependency(request: Request) -> None:
        client = request.client.host if request.client else "unknown"
        rate_limiter.check(f"{bucket}:{client}", limit=limit, window_seconds=window_seconds)

    return dependency


AUTH_START_LIMIT = sensitive_rate_limit("auth-start", limit=3, window_seconds=300)
AUTH_VERIFY_LIMIT = sensitive_rate_limit("auth-verify", limit=8, window_seconds=300)
CONFIG_WRITE_LIMIT = sensitive_rate_limit("config-write", limit=20, window_seconds=60)
