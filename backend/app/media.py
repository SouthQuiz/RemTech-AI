"""Issue #32 (ADR-011) — интерфейсы медиа-трансформаций для голосовых каналов.

Контракты Transcriber (речь→текст, STT) и Synthesizer (текст→речь, TTS) с
локальными дефолтами. Полноценные Whisper (STT) и Silero (TTS) — TASK-1002/1003;
здесь интерфейсы + минимальная локальная реализация и опциональные хуки,
которые в веб-канале по умолчанию ВЫКЛЮЧЕНЫ (STT_ENABLED/TTS_ENABLED=false).

ADR-010/011: локальные модели держат голос/ПДн в контуре без egress в облако.
"""
import io
import struct
import wave
from abc import ABC, abstractmethod

from app.config import get_settings

settings = get_settings()


class Transcriber(ABC):
    """Речь → текст."""
    @abstractmethod
    async def transcribe(self, audio: bytes, mime: str = "") -> str: ...


class Synthesizer(ABC):
    """Текст → речь (аудио-байты)."""
    @abstractmethod
    async def synthesize(self, text: str) -> bytes: ...


class NullTranscriber(Transcriber):
    """Заглушка STT (реальный Whisper — TASK-1002)."""
    async def transcribe(self, audio: bytes, mime: str = "") -> str:
        return ""


class SilenceSynthesizer(Synthesizer):
    """Минимальный локальный TTS: валидный WAV-тишина длиной ~по тексту.
    Настоящий голос (Silero) — TASK-1003; здесь рабочий аудио-выход для контракта."""
    async def synthesize(self, text: str) -> bytes:
        seconds = max(0.3, min(len(text or "") * 0.06, 30.0))
        rate = 16000
        frames = int(rate * seconds)
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(rate)
            w.writeframes(struct.pack("<%dh" % frames, *([0] * frames)))
        return buf.getvalue()


def get_transcriber() -> Transcriber:
    # Локальный дефолт STT — Whisper (TASK-1002); пока безопасная заглушка.
    return NullTranscriber()


def get_synthesizer() -> Synthesizer:
    # Локальный дефолт TTS — Silero (TASK-1003); пока валидный WAV-выход.
    return SilenceSynthesizer()


async def maybe_transcribe(audio: bytes, mime: str = "") -> str:
    """Опциональный STT-хук на входе хода (в вебе выключен по умолчанию)."""
    if not settings.stt_enabled or not audio:
        return ""
    return await get_transcriber().transcribe(audio, mime)


async def maybe_synthesize(text: str) -> bytes | None:
    """Опциональный TTS-хук на выходе хода (в вебе выключен по умолчанию)."""
    if not settings.tts_enabled or not (text or "").strip():
        return None
    return await get_synthesizer().synthesize(text)
