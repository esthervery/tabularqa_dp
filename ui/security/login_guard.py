"""로그인 무차별 대입 방어
"""
from __future__ import annotations

import threading
import time

MAX_FAIL = 5
WINDOW = 15 * 60      # 실패를 세는 구간(초)
LOCK = 5 * 60         # 잠금 시간(초)

_fails: dict[str, list[float]] = {}
_locked_until: dict[str, float] = {}
_lock = threading.Lock()


def _k(username: str) -> str:
    return (username or "").strip().lower()


def locked_for(username: str) -> float:
    """잠겨 있으면 남은 초, 아니면 0."""
    with _lock:
        left = _locked_until.get(_k(username), 0.0) - time.monotonic()
        return max(0.0, left)


def fail(username: str) -> None:
    k, now = _k(username), time.monotonic()
    with _lock:
        hist = [t for t in _fails.get(k, []) if now - t < WINDOW] + [now]
        _fails[k] = hist
        if len(hist) >= MAX_FAIL:
            _locked_until[k] = now + LOCK
            _fails[k] = []
            print(f"[login-guard] locked '{k}' for {LOCK}s")


def success(username: str) -> None:
    k = _k(username)
    with _lock:
        _fails.pop(k, None)
        _locked_until.pop(k, None)