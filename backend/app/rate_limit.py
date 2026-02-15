from __future__ import annotations

import time
from collections import defaultdict, deque
from collections.abc import Callable

from fastapi import HTTPException, Request


class InMemoryRateLimiter:
    def __init__(self, max_per_minute: int):
        self.max_per_minute = max_per_minute
        self.bucket: dict[str, deque[float]] = defaultdict(deque)

    def dependency(self) -> Callable[[Request], None]:
        def _check(request: Request) -> None:
            identifier = request.client.host if request.client else "unknown"
            now = time.time()
            window = self.bucket[identifier]

            while window and (now - window[0]) > 60:
                window.popleft()

            if len(window) >= self.max_per_minute:
                raise HTTPException(status_code=429, detail="Rate limit exceeded")

            window.append(now)

        return _check
