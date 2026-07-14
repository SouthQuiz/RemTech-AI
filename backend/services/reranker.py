"""Issue #39 (TASK-0301/0304, EPIC-03) — реранкер bge-reranker через TEI.

Двухстадийный поиск по базе знаний: pgvector отдаёт top-N кандидатов по косинусу
(грубо, быстро), затем bge-reranker переоценивает пары (вопрос, чанк) точнее и
даёт финальный порядок. Реранкер локальный (TEI на GPU), без egress.

Мягкая деградация (обязательна по критериям #39): пустой TEI_URL → одностадийный
путь; недоступность/ошибка TEI → откат на косинусный порядок, поиск не падает.
"""
import httpx

from app.config import get_settings
from app.logging_config import get_logger

settings = get_settings()
log = get_logger("remtech.reranker")


def enabled() -> bool:
    return bool(settings.tei_url)


async def rerank_order(query: str, texts: list[str]) -> list[int] | None:
    """Порядок индексов texts по убыванию релевантности к query (реранк TEI).
    None — если TEI выключен/недоступен/ответ некорректен (вызывающий берёт косинус)."""
    if not settings.tei_url or not texts:
        return None
    url = settings.tei_url.rstrip("/") + "/rerank"
    try:
        async with httpx.AsyncClient(timeout=10.0, trust_env=False) as c:
            r = await c.post(url, json={"query": query, "texts": texts})
            r.raise_for_status()
            data = r.json()   # TEI: [{"index": i, "score": s}, ...] по убыванию score
        order = [int(item["index"]) for item in data if 0 <= int(item["index"]) < len(texts)]
        return order or None
    except Exception as e:
        log.warning("TEI-реранкер недоступен, откат на косинус: %s", type(e).__name__)
        return None
