"""Issue #4 — короткоживущие тикеты для WebSocket.

WebSocket из браузера не может слать заголовок Authorization, поэтому раньше в URL
передавался long-lived JWT (утекал в логи/историю/Referer). Теперь клиент по
Authorization получает одноразовый тикет с коротким TTL и открывает /ws?ticket=...
Даже попав в лог, тикет бесполезен через несколько секунд и после первого использования.

In-memory на процесс (для нескольких воркеров нужен Redis — см. issue #16).
"""
import secrets
import time
from threading import Lock

_TTL = 60.0   # секунд


class TicketStore:
    def __init__(self, ttl: float = _TTL):
        self._ttl = ttl
        self._data: dict[str, tuple[int, float]] = {}   # ticket -> (user_id, expiry)
        self._lock = Lock()

    def issue(self, user_id: int) -> str:
        ticket = secrets.token_urlsafe(24)
        with self._lock:
            self._purge()
            self._data[ticket] = (user_id, time.monotonic() + self._ttl)
        return ticket

    def consume(self, ticket: str) -> int | None:
        """Одноразовое использование: возвращает user_id и удаляет тикет."""
        with self._lock:
            self._purge()
            item = self._data.pop(ticket or "", None)
        if not item:
            return None
        user_id, expiry = item
        return user_id if expiry >= time.monotonic() else None

    def _purge(self) -> None:
        now = time.monotonic()
        for t in [t for t, (_, exp) in self._data.items() if exp < now]:
            self._data.pop(t, None)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()


tickets = TicketStore()
