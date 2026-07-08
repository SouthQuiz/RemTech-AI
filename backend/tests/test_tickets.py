"""Issue #4 — одноразовые короткоживущие тикеты для WebSocket."""
import time

from app.tickets import TicketStore


def test_ticket_is_single_use():
    ts = TicketStore(ttl=100)
    t = ts.issue(7)
    assert ts.consume(t) == 7
    assert ts.consume(t) is None   # повторно — уже нельзя


def test_ticket_expires():
    ts = TicketStore(ttl=0.02)
    t = ts.issue(3)
    time.sleep(0.05)
    assert ts.consume(t) is None


def test_ticket_unknown_rejected():
    ts = TicketStore()
    assert ts.consume("nope") is None
    assert ts.consume("") is None
