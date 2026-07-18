"""Дайджест новостей по ИИ (#42): форматирование, дедуп внутри выпуска, веб-лента,
общий сборщик выпуска (Celery beat / админ-эндпоинт / бот)."""
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.orchestrator as orch
from app import repositories as repo
from app.config import get_settings
from services import news_digest

_OWNER = ({"user_id": 7, "username": "dir", "name": "Директор", "role": "руководство"}, 555)


def _bind(monkeypatch):
    url = get_settings().database_url.rsplit("/", 1)[0] + "/remtech_test"
    monkeypatch.setattr(orch, "SessionLocal",
                        async_sessionmaker(create_async_engine(url), expire_on_commit=False))


async def _noop(_e):
    pass


async def test_ai_news_digest_formats_dedups_and_posts(session, monkeypatch):
    _bind(monkeypatch)
    res = await orch.Orchestrator()._execute_tool(
        "ai_news_digest",
        {"title": "ИИ за сутки", "items": [
            {"text": "OpenAI выпустил модель", "url": "http://a"},
            {"text": "OpenAI выпустил модель", "url": "http://a"},   # дубль → отсеять
            {"text": "Google представил Gemini", "url": "http://b"}]},
        _noop, 1, None, None)
    assert "OpenAI выпустил модель" in res and "Google представил Gemini" in res
    assert res.count("•") == 2                       # дубль отсеян
    async with orch.SessionLocal() as s:             # опубликовано в веб-ленту
        notes = await repo.list_notifications(s, "руководство")
    assert any("ИИ за сутки" in n.title for n in notes)


async def test_ai_news_digest_empty(session, monkeypatch):
    _bind(monkeypatch)
    res = await orch.Orchestrator()._execute_tool(
        "ai_news_digest", {"items": []}, _noop, 1, None, None)
    assert "не набралось" in res.lower()


# ── общий сборщик выпуска: beat / админ-эндпоинт / бот зовут одну функцию ──────

async def test_news_digest_run_once_delivers(session):
    # собранный выпуск доставляется владельцу (первому лицу) в Telegram
    sent = []

    async def fake_collect(user, agent_id):
        assert user["user_id"] == 7          # владелец проброшен в сборку
        return "• OpenAI выпустил модель\n  http://a"

    async def fake_tg(chat_id, text):
        sent.append((chat_id, text))

    r = await news_digest.run_once(session, collect=fake_collect, tg_sender=fake_tg,
                                   owner=_OWNER, agent_id=1, require_enabled=False)
    assert r["delivered"] is True and "OpenAI" in r["text"] and r["skipped"] is None
    assert sent == [(555, "• OpenAI выпустил модель\n  http://a")]


async def test_news_digest_source_unavailable_no_crash(session):
    # недоступность источника / сбой сбора НЕ роняет задачу и не шлёт в Telegram
    async def boom(user, agent_id):
        raise RuntimeError("источник недоступен")

    sent = []

    async def fake_tg(chat_id, text):
        sent.append(text)

    r = await news_digest.run_once(session, collect=boom, tg_sender=fake_tg,
                                   owner=_OWNER, require_enabled=False)
    assert r["delivered"] is False and r["skipped"] == "collect_failed"
    assert sent == []


async def test_news_digest_empty_not_delivered(session):
    # пустой выпуск (значимых новостей нет) — не доставляем
    async def empty_collect(user, agent_id):
        return ""

    r = await news_digest.run_once(session, collect=empty_collect, owner=_OWNER,
                                   require_enabled=False)
    assert r["delivered"] is False and r["skipped"] == "empty"


async def test_news_digest_no_owner_skips(session):
    # нет владельца (allow-list пуст/неактивен) — сбор не запускаем
    async def collect(user, agent_id):
        raise AssertionError("не должно вызываться без владельца")

    r = await news_digest.run_once(session, collect=collect, owner=(None, None),
                                   require_enabled=False)
    assert r["skipped"] == "no_owner" and r["delivered"] is False


async def test_news_digest_disabled_noop(session, monkeypatch):
    # флаг выключен + require_enabled=True (режим Celery beat) → no-op
    import types
    monkeypatch.setattr(news_digest, "get_settings",
                        lambda: types.SimpleNamespace(ai_news_enabled=False))

    async def collect(user, agent_id):
        raise AssertionError("не должно вызываться при выключенном флаге")

    r = await news_digest.run_once(session, collect=collect, owner=_OWNER, require_enabled=True)
    assert r["skipped"] == "disabled"
