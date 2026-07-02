"""EPIC-03 (3a) — тесты конвейера базы знаний (RAG) против Postgres+pgvector."""
from app import kb
from app import repositories as repo
from app.embeddings import FakeEmbedder

EMB = FakeEmbedder(1024)


def test_chunking():
    assert kb.chunk_text("") == []
    small = kb.chunk_text("Абзац один.\nАбзац два.")
    assert len(small) == 1
    long = kb.chunk_text("сл " * 2000, max_chars=1200, overlap=200)
    assert len(long) >= 2  # длинный текст режется на несколько окон


async def test_ingest_and_search_relevance(session):
    await kb.ingest_document(session, EMB, "kat1.txt", "Гусеничный экскаватор XCMG XE215C для земляных работ.")
    await kb.ingest_document(session, EMB, "kat2.txt", "Фронтальный погрузчик XCMG LW300 для склада.")
    await kb.ingest_document(session, EMB, "kat3.txt", "Дорожный каток XCMG XS143 для укладки асфальта.")
    await session.commit()

    res = await kb.search(session, EMB, "нужен экскаватор для земляных работ", k=3)
    assert res, "поиск вернул пусто"
    assert "экскаватор" in res[0]["text"].lower()  # самый релевантный — про экскаватор
    assert res[0]["distance"] <= res[-1]["distance"]  # отсортировано по близости


async def test_role_filtering(session):
    await kb.ingest_document(session, EMB, "public.txt", "Общий прайс на запчасти.", owner_role=None)
    await kb.ingest_document(session, EMB, "secret.txt", "Финансовый отчёт директора.", owner_role="admin")
    await session.commit()

    # сотрудник (roles=["user"]) видит только публичный документ
    as_user = await kb.search(session, EMB, "отчёт прайс запчасти", roles=["user"], k=10)
    files = {r["file_name"] for r in as_user}
    assert "public.txt" in files and "secret.txt" not in files

    # админ (roles=None → без фильтра) видит оба
    as_admin = await kb.search(session, EMB, "отчёт прайс запчасти", roles=None, k=10)
    files_admin = {r["file_name"] for r in as_admin}
    assert "public.txt" in files_admin and "secret.txt" in files_admin


async def test_document_listing_and_delete(session):
    r = await kb.ingest_document(session, EMB, "doc.txt", "Текст документа про XCMG.", owner_role="user")
    await session.commit()
    docs = await repo.list_kb_documents(session)
    assert any(d["file_name"] == "doc.txt" and d["chunks"] >= 1 for d in docs)

    await repo.delete_kb_document(session, r["document_id"])
    await session.commit()
    assert not await repo.list_kb_documents(session)
