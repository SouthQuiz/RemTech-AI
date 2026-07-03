"""Issue #3 — ограничение частоты запросов (in-memory, sliding window).

Простой потокобезопасный лимитер на процесс: для чувствительных эндпоинтов
(login/register/ws). Для нескольких воркеров лимит должен быть распределённым
(Redis) — см. issue #16; здесь достаточно на один процесс.
"""
import time
from collections import defaultdict, deque
from threading import Lock


class RateLimiter:
    def __init__(self, max_events: int, window_seconds: float):
        self.max = max_events
        self.window = window_seconds
        self._hits: dict[str, deque] = defaultdict(deque)
        self._lock = Lock()

    def allow(self, key: str, now: float | None = None) -> bool:
        """Регистрирует попытку и возвращает False, если лимит по ключу превышен."""
        now = time.monotonic() if now is None else now
        with self._lock:
            dq = self._hits[key]
            while dq and now - dq[0] > self.window:
                dq.popleft()
            if len(dq) >= self.max:
                return False
            dq.append(now)
            return True

    def reset(self, key: str) -> None:
        with self._lock:
            self._hits.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._hits.clear()
