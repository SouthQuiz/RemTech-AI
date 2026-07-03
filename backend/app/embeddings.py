"""EPIC-03 — эмбеддинги для базы знаний.

Абстракция эмбеддера: production — bge-m3 через Ollama; для тестов/без GPU —
детерминированный FakeEmbedder (bag-of-words по хешу токенов), дающий похожие
векторы для похожих текстов.
"""
import asyncio
import hashlib
import math
import re

from app.config import get_settings
from app.logging_config import get_logger

settings = get_settings()
log = get_logger("remtech.embed")
_TOKEN_RE = re.compile(r"[0-9a-zA-Zа-яёА-ЯЁ]{2,}", re.U)


def _tokenize(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text or "")]


class FakeEmbedder:
    """Детерминированный эмбеддер без внешних зависимостей (для тестов/без GPU)."""

    def __init__(self, dim: int = 1024):
        self.dim = dim

    def _vec(self, text: str) -> list[float]:
        v = [0.0] * self.dim
        for tok in _tokenize(text):
            idx = int(hashlib.md5(tok.encode()).hexdigest(), 16) % self.dim
            v[idx] += 1.0
        norm = math.sqrt(sum(x * x for x in v)) or 1.0
        return [x / norm for x in v]

    async def embed(self, text: str) -> list[float]:
        return self._vec(text)

    async def embed_many(self, texts: list[str]) -> list[list[float]]:
        return [self._vec(t) for t in texts]


class OllamaEmbedder:
    """bge-m3 через Ollama (локально, данные не покидают контур)."""

    def __init__(self, url: str, model: str, dim: int):
        self.url = url.rstrip("/")
        self.model = model
        self.dim = dim

    async def _one(self, client, text: str) -> list[float]:
        # #15 — короткий ретрай на сетевых сбоях, чтобы разовый обрыв не валил ингест
        last = None
        for attempt in range(3):
            try:
                r = await client.post(f"{self.url}/api/embeddings",
                                      json={"model": self.model, "prompt": text}, timeout=60)
                r.raise_for_status()
                return r.json()["embedding"]
            except Exception as e:
                last = e
                log.warning("ollama embed attempt %d failed: %s", attempt + 1, type(e).__name__)
                await asyncio.sleep(1.5 * (attempt + 1))
        raise last

    async def embed(self, text: str) -> list[float]:
        import httpx
        async with httpx.AsyncClient() as client:
            return await self._one(client, text)

    async def embed_many(self, texts: list[str]) -> list[list[float]]:
        import httpx
        async with httpx.AsyncClient() as client:
            return [await self._one(client, t) for t in texts]


def get_embedder():
    if settings.embed_backend == "fake":
        return FakeEmbedder(settings.embed_dim)
    return OllamaEmbedder(settings.ollama_url, settings.embed_model, settings.embed_dim)
