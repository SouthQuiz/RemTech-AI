"""EPIC-03 — конвейер базы знаний (RAG): чанкинг → эмбеддинги → pgvector.

Индексация документа: извлечённый текст → чанки → эмбеддинги (bge-m3) → kb_chunks
с ролью-владельцем. Поиск: эмбеддинг вопроса → top-k по косинусной близости с
фильтром по ролям. Реранкер (bge-reranker через TEI) — стадия 3b.
"""
from app import repositories as repo
from app.config import get_settings

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


async def ingest_document(session, embedder, file_name: str, text: str,
                          owner_role: str | None = None, source: str = "upload") -> dict:
    """Индексирует документ: создаёт kb_document и его чанки с эмбеддингами."""
    pieces = chunk_text(text)
    doc = await repo.create_kb_document(session, file_name, source, owner_role)
    if pieces:
        embeddings = await embedder.embed_many(pieces)
        rows = [(pieces[i], embeddings[i], {"i": i}) for i in range(len(pieces))]
        await repo.add_chunks(session, doc.id, rows)
    return {"document_id": doc.id, "file_name": file_name, "chunks": len(pieces)}


async def search(session, embedder, query: str, roles: list[str] | None = None,
                 k: int | None = None) -> list[dict]:
    """Ищет релевантные чанки по вопросу с фильтром по ролям."""
    if not (query or "").strip():
        return []
    q_emb = await embedder.embed(query)
    return await repo.search_chunks(session, q_emb, roles=roles, k=k or settings.kb_top_k)
