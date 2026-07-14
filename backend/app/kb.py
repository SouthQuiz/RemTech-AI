"""EPIC-03 — конвейер базы знаний (RAG): чанкинг → эмбеддинги → pgvector.

Индексация документа: извлечённый текст → чанки → эмбеддинги (bge-m3) → kb_chunks
с ролью-владельцем. Поиск: эмбеддинг вопроса → top-k по косинусной близости с
фильтром по ролям. Реранкер (bge-reranker через TEI) — стадия 3b.
"""
from app import repositories as repo
from app.config import get_settings
from services import reranker

settings = get_settings()


def chunk_text(text: str, max_chars: int = 1200, overlap: int = 200) -> list[str]:
    """Режет текст на перекрывающиеся окна по абзацам."""
    text = (text or "").strip()
    if not text:
        return []
    paras = [p.strip() for p in text.split("\n") if p.strip()]
    chunks, cur = [], ""
    for p in paras:
        if len(cur) + len(p) + 1 <= max_chars:
            cur = f"{cur}\n{p}".strip()
        else:
            if cur:
                chunks.append(cur)
            # длинный абзац — режем окнами с перекрытием
            if len(p) > max_chars:
                i = 0
                while i < len(p):
                    chunks.append(p[i:i + max_chars])
                    i += max_chars - overlap
                cur = ""
            else:
                cur = p
    if cur:
        chunks.append(cur)
    return chunks


async def ingest_chunks(session, embedder, document_id: int, text: str) -> int:
    """Тяжёлая часть конвейера: чанкинг + эмбеддинги + запись kb_chunks.
    Выделена отдельно, чтобы выполняться как фоновая Celery-задача (issue #22)."""
    pieces = chunk_text(text)
    if pieces:
        embeddings = await embedder.embed_many(pieces)
        rows = [(pieces[i], embeddings[i], {"i": i}) for i in range(len(pieces))]
        await repo.add_chunks(session, document_id, rows)
    return len(pieces)


async def ingest_document(session, embedder, file_name: str, text: str,
                          owner_role: str | None = None, source: str = "upload") -> dict:
    """Индексирует документ синхронно (inline): создаёт kb_document и его чанки."""
    doc = await repo.create_kb_document(session, file_name, source, owner_role)
    n = await ingest_chunks(session, embedder, doc.id, text)
    return {"document_id": doc.id, "file_name": file_name, "chunks": n}


async def search(session, embedder, query: str, roles: list[str] | None = None,
                 k: int | None = None) -> list[dict]:
    """Ищет релевантные чанки по вопросу с фильтром по ролям.

    #39 — двухстадийно, если включён TEI-реранкер: pgvector даёт top-N кандидатов по
    косинусу → bge-reranker переоценивает → финальный top_k. Без TEI (или при его
    недоступности) — одностадийный косинусный путь (обратная совместимость)."""
    if not (query or "").strip():
        return []
    k = k or settings.kb_top_k
    q_emb = await embedder.embed(query)
    if not reranker.enabled():
        return await repo.search_chunks(session, q_emb, roles=roles, k=k)
    # первая стадия: больше кандидатов для реранка
    n = max(k, settings.kb_rerank_candidates)
    hits = await repo.search_chunks(session, q_emb, roles=roles, k=n)
    order = await reranker.rerank_order(query, [h["text"] for h in hits])
    if order is None:               # TEI недоступен/ошибка — откат на косинус
        return hits[:k]
    return [hits[i] for i in order][:k]
