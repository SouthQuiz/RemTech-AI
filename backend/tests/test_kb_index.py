"""Issue #14 — HNSW-индекс на kb_chunks.embedding присутствует в схеме."""
from sqlalchemy import text


async def test_hnsw_index_present(session):
    indexdef = await session.scalar(text(
        "SELECT indexdef FROM pg_indexes WHERE indexname = 'ix_kb_chunks_embedding_hnsw'"))
    assert indexdef, "HNSW-индекс не создан"
    low = indexdef.lower()
    assert "hnsw" in low and "vector_cosine_ops" in low
