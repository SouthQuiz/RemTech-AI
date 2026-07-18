"""Генерация изображений (модель из IMAGE_MODEL, по умолч. FLUX 1.1 Pro Ultra),
редактирование (FLUX Kontext) и видео (Kling) через Replicate.
Портировано из mybot/services/replicate_svc.py."""
import asyncio
import base64
import random
import time

import httpx
import replicate

from app.config import get_settings
from app.logging_config import get_logger

log = get_logger("remtech.media")
_token = get_settings().replicate_api_token
_client = replicate.Client(api_token=_token) if _token else None
_IMAGE_TIMEOUT = 180    # сек — генерация/редактирование изображения
_VIDEO_TIMEOUT = 600    # сек — генерация видео


async def _run_with_timeout(fn, *args, timeout: int):
    """Внешний вызов с таймаутом (#15): по истечении — None, без зависания потока."""
    try:
        return await asyncio.wait_for(asyncio.to_thread(fn, *args), timeout=timeout)
    except asyncio.TimeoutError:
        log.warning("replicate call timed out after %ss", timeout)
        return None


def _read_output(output) -> bytes | None:
    """Универсальное чтение результата Replicate (file-like / url / список)."""
    try:
        if hasattr(output, "read"):
            return output.read()
        if hasattr(output, "url"):
            return httpx.get(str(output.url), timeout=120).content
        url = str(output[0]) if hasattr(output, "__getitem__") else str(output)
        return httpx.get(url, timeout=120).content
    except Exception:
        log.exception("Replicate read error")
        return None


def _run_model(model: str, inp: dict) -> bytes | None:
    """Вызов модели Replicate с ретраем на троттлинг (429). На аккаунтах с балансом
    < $5 лимит жёсткий (≈6/мин, burst 1) — при параллельной генерации картинок для
    презентации часть запросов отбивается 429; ждём сброса и повторяем (с джиттером,
    чтобы повторы не столкнулись снова)."""
    for attempt in range(5):
        try:
            return _read_output(_client.run(model, input=inp))
        except replicate.exceptions.ReplicateError as e:
            if getattr(e, "status", None) == 429 and attempt < 4:
                delay = 11 + attempt * 4 + random.uniform(0, 5)
                log.warning("Replicate throttled (429), retry #%d in %.0fs", attempt + 1, delay)
                time.sleep(delay)
                continue
            log.exception("Replicate model error (model=%s)", model)
            return None
        except Exception:
            log.exception("Replicate model error (model=%s)", model)
            return None
    return None


def _generate_flux_sync(prompt: str, aspect_ratio: str = "1:1") -> bytes | None:
    if not _client:
        return None
    model = get_settings().image_model or "black-forest-labs/flux-1.1-pro-ultra"
    # Общие для FLUX/Imagen/Recraft параметры; специфичные модели игнорируют лишнее
    # не всегда, поэтому держим минимальный переносимый набор.
    inp = {"prompt": prompt, "aspect_ratio": aspect_ratio, "output_format": "jpg"}
    if model.startswith("black-forest-labs/flux"):
        inp["safety_tolerance"] = 2
    return _run_model(model, inp)


async def generate_image_flux(prompt: str, aspect_ratio: str = "1:1") -> bytes | None:
    return await _run_with_timeout(_generate_flux_sync, prompt, aspect_ratio,
                                   timeout=_IMAGE_TIMEOUT)


def _edit_image_flux_sync(image_bytes: bytes, instruction: str) -> bytes | None:
    if not _client:
        return None
    try:
        data_uri = f"data:image/jpeg;base64,{base64.b64encode(image_bytes).decode()}"
        output = _client.run(
            "black-forest-labs/flux-kontext-pro",
            input={
                "prompt": instruction,
                "input_image": data_uri,
                "output_format": "jpg",
                "output_quality": 92,
                "safety_tolerance": 2,
            },
        )
        return _read_output(output)
    except Exception:
        log.exception("FLUX edit error")
        return None


async def edit_image_flux(image_bytes: bytes, instruction: str) -> bytes | None:
    return await _run_with_timeout(_edit_image_flux_sync, image_bytes, instruction,
                                   timeout=_IMAGE_TIMEOUT)


def _generate_video_sync(prompt: str, image_bytes: bytes | None = None, duration: int = 5) -> bytes | None:
    if not _client:
        return None
    try:
        dur = 10 if duration >= 10 else 5
        params = {"prompt": prompt, "duration": dur, "aspect_ratio": "16:9"}
        if image_bytes:
            params["start_image"] = f"data:image/jpeg;base64,{base64.b64encode(image_bytes).decode()}"
        output = _client.run("kwaivgi/kling-v2.6", input=params)
        return _read_output(output)
    except Exception:
        log.exception("Kling video error")
        return None


async def generate_video(prompt: str, image_bytes: bytes | None = None, duration: int = 5) -> bytes | None:
    return await _run_with_timeout(_generate_video_sync, prompt, image_bytes, duration,
                                   timeout=_VIDEO_TIMEOUT)
