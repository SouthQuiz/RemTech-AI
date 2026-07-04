"""Issue #22 — батчинг эмбеддингов (конкурентно) с сохранением порядка."""
import asyncio

from app.embeddings import OllamaEmbedder


async def test_embed_many_preserves_order(monkeypatch):
    emb = OllamaEmbedder("http://x", "bge-m3", 4)

    async def fake_one(client, text):
        # первый вход искусственно задерживаем — если порядок не сохраняется,
        # результат "a" оказался бы не на месте
        await asyncio.sleep(0.02 if text == "a" else 0.0)
        return [float(len(text))] * 4

    monkeypatch.setattr(emb, "_one", fake_one)
    out = await emb.embed_many(["a", "bb", "ccc"])
    assert out == [[1.0] * 4, [2.0] * 4, [3.0] * 4]


async def test_embed_many_empty():
    emb = OllamaEmbedder("http://x", "bge-m3", 4)
    assert await emb.embed_many([]) == []


def test_celery_ingest_task_registered():
    import app.tasks  # noqa: F401 — регистрирует задачу в реестре Celery
    from app.celery_app import celery_app
    assert "kb.ingest" in celery_app.tasks
