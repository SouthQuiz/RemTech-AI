"""Issue #32 — channel-agnostic turn-сервис."""
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app import repositories as repo
from app import turn
from app.config import get_settings


async def test_run_turn_creates_conversation_and_calls_core(session, monkeypatch):
    # SessionLocal внутри run_turn → тестовая БД
    base = get_settings().database_url
    test_url = base.rsplit("/", 1)[0] + "/remtech_test"
    engine = create_async_engine(test_url)
    monkeypatch.setattr(turn, "SessionLocal", async_sessionmaker(engine, expire_on_commit=False))

    u = await repo.create_user(session, "u", "h$1")
    await session.commit()

    calls = {}

    async def fake_process(cid, uid, text, attachments, emit, roles, agent_id):
        calls.update(cid=cid, uid=uid, text=text, roles=roles)
        await emit({"type": "done", "text": "ok"})

    monkeypatch.setattr(turn.orchestrator, "process", fake_process)

    events = []

    async def emit(e):
        events.append(e)

    cid = await turn.run_turn({"user_id": u.id, "role": "user"}, None, "привет", [], None, emit)
    assert cid and any(e["type"] == "conversation" for e in events)
    assert calls["text"] == "привет" and calls["cid"] == cid
    assert calls["roles"] == ["user"]   # сотрудник — фильтр по своей роли
    await engine.dispose()


async def test_run_turn_rejects_foreign_conversation(session, monkeypatch):
    base = get_settings().database_url
    test_url = base.rsplit("/", 1)[0] + "/remtech_test"
    engine = create_async_engine(test_url)
    monkeypatch.setattr(turn, "SessionLocal", async_sessionmaker(engine, expire_on_commit=False))

    owner = await repo.create_user(session, "owner", "h$1")
    other = await repo.create_user(session, "other", "h$1")
    conv = await repo.create_conversation(session, owner.id, "чужой")
    await session.commit()

    called = {"n": 0}

    async def fake_process(*a, **k):
        called["n"] += 1

    monkeypatch.setattr(turn.orchestrator, "process", fake_process)
    events = []

    async def emit(e):
        events.append(e)

    await turn.run_turn({"user_id": other.id, "role": "user"}, conv.id, "хочу чужой чат", [], None, emit)
    assert any(e["type"] == "error" for e in events)   # доступ запрещён
    assert called["n"] == 0                              # ядро не вызвано
    await engine.dispose()
