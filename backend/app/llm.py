"""EPIC-02 (2a) — шлюз моделей (LLM gateway).

Маршрутизация запросов к моделям через реестр model_configs: по алиасу
выбирается провайдер и модель; при сбое основного провайдера — переключение
на fallback. Пока реализован провайдер Anthropic (через прямой API или
обратный прокси egress_proxy_url); Gemini/OpenAI/Yandex/vLLM — в стадии 2b.
"""
from typing import Awaitable, Callable

import anthropic

from app import repositories as repo
from app.config import get_settings
from app.database import SessionLocal
from app.logging_config import get_logger

settings = get_settings()
log = get_logger("remtech.llm")
OnDelta = Callable[[str], Awaitable[None]]


class AnthropicProvider:
    """Провайдер Anthropic (Claude). base_url задаёт обратный прокси, если указан."""

    def __init__(self, model: str, api_key: str, base_url: str | None = None):
        self.model = model
        kwargs = {"api_key": api_key or "missing"}
        if base_url:
            kwargs["base_url"] = base_url
        self.client = anthropic.AsyncAnthropic(**kwargs)

    async def run(self, system, tools, messages, on_delta: OnDelta):
        async with self.client.messages.stream(
            model=self.model, max_tokens=settings.max_tokens,
            system=system, tools=tools, messages=messages, timeout=120.0,
        ) as stream:
            async for chunk in stream.text_stream:
                await on_delta(chunk)
            return await stream.get_final_message()


def make_provider(provider: str, model: str):
    """Фабрика провайдера по имени. Anthropic реализован (в т.ч. через egress-прокси
    base_url). Yandex/vLLM/OpenAI/Gemini — стадия 2b (нужны ключи/локальный сервер)."""
    base_url = settings.egress_proxy_url or None
    if provider in ("anthropic", "claude"):
        return AnthropicProvider(model=model or settings.model,
                                 api_key=settings.anthropic_api_key, base_url=base_url)
    raise NotImplementedError(
        f"Провайдер «{provider}» пока не реализован (стадия 2b: нужны ключи/сервер). "
        f"Настройте агента на доступный провайдер (anthropic).")


async def _load_config(alias: str):
    async with SessionLocal() as s:
        return await repo.get_model_config_by_alias(s, alias)


class ModelGateway:
    async def run(self, alias: str | None, system, tools, messages, on_delta: OnDelta):
        """Маршрутизирует запрос: основной провайдер по алиасу (или дефолт),
        при сбое — fallback из model_configs."""
        alias = alias or settings.default_model
        cfg = await _load_config(alias)
        provider_name = cfg.provider if cfg else "anthropic"
        model = (cfg.endpoint if cfg and cfg.endpoint else settings.model)
        fallback = cfg.fallback_to if cfg else None

        try:
            return await make_provider(provider_name, model).run(system, tools, messages, on_delta)
        except Exception as primary:
            # #15/#21 — не глотаем первопричину: логируем и, если fallback недоступен,
            # пробрасываем именно ИСХОДНУЮ ошибку основного провайдера.
            log.warning("provider '%s' failed: %s: %s", provider_name,
                        type(primary).__name__, primary)
            fb = await _load_config(fallback) if fallback else None
            if fb:
                try:
                    log.info("switching to fallback '%s'", fallback)
                    return await make_provider(
                        fb.provider, fb.endpoint or settings.model
                    ).run(system, tools, messages, on_delta)
                except Exception as fb_err:
                    log.warning("fallback '%s' unavailable: %s: %s", fallback,
                                type(fb_err).__name__, fb_err)
            raise primary


gateway = ModelGateway()
