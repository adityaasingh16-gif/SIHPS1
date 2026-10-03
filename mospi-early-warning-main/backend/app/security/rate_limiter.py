import os, time
from collections import defaultdict, deque
from threading import Lock

class SlidingWindowRateLimiter:
    def __init__(self, limit=None, window_seconds=None):
        self.limit = limit or int(os.getenv("IDS_RATE_LIMIT", "300"))
        self.window_seconds = window_seconds or int(os.getenv("IDS_RATE_WINDOW_SECONDS", "60"))
        self._hits = defaultdict(deque)
        self._lock = Lock()

    def check(self, ip: str):
        now=time.monotonic()
        with self._lock:
            q=self._hits[ip]
            while q and now-q[0] > self.window_seconds: q.popleft()
            q.append(now)
            return len(q) <= self.limit, len(q)

    def reset(self):
        with self._lock: self._hits.clear()

rate_limiter=SlidingWindowRateLimiter()
