"""Issue #32 — интерфейсы STT/TTS и опциональные хуки (в вебе выключены).

Тесты не зависят от ambient .env (в деплое STT может быть включён) — сами задают
бэкенд/флаги через monkeypatch.
"""
from app import media
from app.media import (
    NullTranscriber,
    Synthesizer,
    Transcriber,
    get_synthesizer,
    maybe_synthesize,
    maybe_transcribe,
)


async def test_synthesizer_produces_valid_wav():
    synth = get_synthesizer()
    assert isinstance(synth, Synthesizer)
    audio = await synth.synthesize("привет, это тест озвучки")
    assert audio[:4] == b"RIFF" and len(audio) > 44   # валидный WAV с данными


async def test_transcriber_contract(monkeypatch):
    # контракт заглушки (null): возвращает строку, не бросает
    monkeypatch.setattr(media, "_transcriber", None)
    monkeypatch.setattr(media.settings, "stt_backend", "null")
    tr = media.get_transcriber()
    assert isinstance(tr, Transcriber) and isinstance(tr, NullTranscriber)
    assert isinstance(await tr.transcribe(b"\x00\x01", "audio/wav"), str)


async def test_hooks_disabled_by_default(monkeypatch):
    # при выключенных STT/TTS хуки не трогают ход
    monkeypatch.setattr(media.settings, "stt_enabled", False)
    monkeypatch.setattr(media.settings, "tts_enabled", False)
    assert await maybe_transcribe(b"audio", "audio/wav") == ""
    assert await maybe_synthesize("текст") is None
