"""TASK-0104 — тесты моделей данных по ER (против настоящего Postgres+pgvector)."""
from sqlalchemy import select

from app.database import Base
from app.models import (
    ActivityLog,
    Agent,
    ChatHistory,
    Conversation,
    KBChunk,
    KBDocument,
    ModelConfig,
    UploadedFile,
    User,
)

EXPECTED_TABLES = {
    "users", "conversations", "chat_history", "uploaded_files", "activity_log",
    "kb_documents", "kb_chunks", "agents", "model_configs",
}


def test_schema_matches_er():
    """Все таблицы из ER-диаграммы присутствуют в метаданных."""
    assert EXPECTED_TABLES.issubset(set(Base.metadata.tables.keys()))


def test_kb_chunks_embedding_dim():
    """embedding — вектор фиксированной размерности 1024 (bge-m3)."""
    col = KBChunk.__table__.c.embedding
    assert col.type.dim == 1024


async def test_user_conversation_message_flow(session):
    """CRUD-цепочка user → conversation → chat_history с FK."""
    user = User(username="ivan", full_name="Иван Петров", password_hash="x$y", role="user")
    session.add(user)
    await session.flush()

    conv = Conversation(user_id=user.id, title="КП на XCMG")
    session.add(conv)
    await session.flush()

    msg = ChatHistory(
        conversation_id=conv.id, user_id=user.id, role="user",
        content={"type": "text", "text": "Сделай КП"},
    )
    session.add(msg)
    await session.commit()

    got = (await session.execute(select(ChatHistory))).scalars().all()
    assert len(got) == 1
    assert got[0].content["text"] == "Сделай КП"
    assert got[0].conversation_id == conv.id


async def test_uploaded_file_and_activity(session):
    user = User(username="anna", password_hash="a$b", role="admin")
    session.add(user)
    await session.flush()
    session.add(UploadedFile(
        user_id=user.id, kind="docx", file_name="kp.docx",
        file_path="/data/kp.docx", direction="output",
    ))
    session.add(ActivityLog(user_id=user.id, action="login", detail="Вход"))
    await session.commit()
    files = (await session.execute(select(UploadedFile))).scalars().all()
    logs = (await session.execute(select(ActivityLog))).scalars().all()
    assert files[0].direction == "output"
    assert logs[0].action == "login"


async def test_kb_vector_similarity_search(session):
    """Векторный поиск pgvector: ближайший чанк по косинусной близости."""
    doc = KBDocument(file_name="catalog.pdf", source="upload", owner_role="user")
    session.add(doc)
    await session.flush()

    # три чанка с ортогональными/близкими векторами (dim 1024)
    def vec(i):
        v = [0.0] * 1024
        v[i] = 1.0
        return v

    session.add_all([
        KBChunk(document_id=doc.id, chunk_text="про экскаватор", embedding=vec(0), meta={"p": 1}),
        KBChunk(document_id=doc.id, chunk_text="про погрузчик", embedding=vec(1)),
        KBChunk(document_id=doc.id, chunk_text="про каток", embedding=vec(2)),
    ])
    await session.commit()

    query = vec(1)  # ближе всего ко второму чанку
    stmt = (
        select(KBChunk)
        .order_by(KBChunk.embedding.cosine_distance(query))
        .limit(1)
    )
    nearest = (await session.execute(stmt)).scalars().first()
    assert nearest.chunk_text == "про погрузчик"


async def test_agent_model_config_fk(session):
    """agents.default_model → model_configs (маршрутизация моделей)."""
    mc = ModelConfig(alias="claude", provider="anthropic",
                     endpoint="https://proxy/claude", fallback_to="yandex")
    session.add(mc)
    await session.flush()
    agent = Agent(
        name="Продажник", system_prompt="Ты менеджер по продажам",
        tools=["create_docx", "search_knowledge_base"],
        default_model=mc.id, allowed_roles="user,admin",
    )
    session.add(agent)
    await session.commit()

    got = (await session.execute(select(Agent))).scalars().first()
    assert got.default_model == mc.id
    assert "create_docx" in got.tools
    loaded_model = await session.get(ModelConfig, got.default_model)
    assert loaded_model.fallback_to == "yandex"
