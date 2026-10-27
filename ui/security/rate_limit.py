"""질의 횟수 제한 — 계정별 INTERVAL 초에 1회.
"""
from __future__ import annotations

import threading
import time

INTERVAL = 6.0
_last: dict[str, float] = {}
_lock = threading.Lock()


def try_acquire(key: str, interval: float = INTERVAL) -> float:
    """허용이면 0.0 을 돌려주고 시각을 기록한다. 아니면 남은 초."""
    now = time.monotonic()
    with _lock:
        prev = _last.get(key)
        if prev is not None and now - prev < interval:
            return interval - (now - prev)
        _last[key] = now
        return 0.0