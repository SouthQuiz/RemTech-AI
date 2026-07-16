"""Чтение почты (IMAP): парсинг писем, порядок, не настроено, инструмент агента."""
from email.message import EmailMessage

import pytest

import app.orchestrator as orch
from services import mail_svc


def _raw(frm: str, subject: str, body: str) -> bytes:
    m = EmailMessage()
    m["From"] = frm
    m["Subject"] = subject
    m["Date"] = "Wed, 16 Jul 2026 10:00:00 +0700"
    m.set_content(body)
    return m.as_bytes()


class FakeIMAP:
    def __init__(self, messages):
        self._msgs = messages   # oldest-first, как в IMAP (id = индекс+1)

    def select(self, mbox):
        return ("OK", [str(len(self._msgs)).encode()])

    def search(self, charset, criterion):
        ids = " ".join(str(i + 1) for i in range(len(self._msgs))).encode()
        return ("OK", [ids])

    def fetch(self, mid, spec):
        return ("OK", [(b"hdr", self._msgs[int(mid) - 1]), b")"])

    def logout(self):
        pass


def test_fetch_recent_parses_and_orders():
    msgs = [_raw("Дима <d@ya.ru>", "Отчёт Q2", "Прибыль выросла на 18 процентов."),
            _raw("Anna <a@gmail.com>", "Счёт на оплату", "Оплатите счёт 2455.")]
    res = mail_svc.fetch_recent("yandex", count=10, connect=lambda s: FakeIMAP(msgs))
    assert len(res) == 2
    assert res[0]["subject"] == "Счёт на оплату"      # newest-first
    assert "Дима" in res[1]["from"] and res[1]["email"] == "d@ya.ru"
    assert res[1]["subject"] == "Отчёт Q2"            # MIME-заголовок декодирован
    assert "Прибыль" in res[1]["snippet"]


def test_fetch_recent_count_limit():
    msgs = [_raw(f"u{i}@ya.ru", f"тема {i}", "тело") for i in range(10)]
    res = mail_svc.fetch_recent("yandex", count=3, connect=lambda s: FakeIMAP(msgs))
    assert len(res) == 3                               # только 3 последних


def test_not_configured_raises():
    # gmail/yandex не заданы в тестовом конфиге → понятный отказ, без сети
    with pytest.raises(mail_svc.MailError):
        mail_svc.fetch_recent("gmail")


def test_unknown_source_raises():
    with pytest.raises(mail_svc.MailError):
        mail_svc.fetch_recent("outlook")


async def test_read_email_tool_formats(monkeypatch):
    monkeypatch.setattr(orch.mail_svc, "fetch_recent",
                        lambda src, count, unread: [
                            {"from": "Дима", "email": "d@ya.ru", "subject": "Отчёт",
                             "date": "Wed, 16 Jul 2026", "snippet": "суть письма", "unread": False}])

    async def emit(_e):
        pass
    res = await orch.Orchestrator()._execute_tool(
        "read_email", {"source": "yandex"}, emit, 1, None, None)
    assert "Дима" in res and "Отчёт" in res


async def test_read_email_tool_handles_unconfigured(monkeypatch):
    def boom(src, count, unread):
        raise orch.mail_svc.MailError("почта «gmail» не настроена")
    monkeypatch.setattr(orch.mail_svc, "fetch_recent", boom)

    async def emit(_e):
        pass
    res = await orch.Orchestrator()._execute_tool(
        "read_email", {"source": "gmail"}, emit, 1, None, None)
    assert "недоступна" in res.lower()
