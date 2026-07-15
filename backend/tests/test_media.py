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


# ── Issue #40 — TTS (Silero) ─────────────────────────────────────────────────

def test_get_synthesizer_selection(monkeypatch):
    monkeypatch.setattr(media, "_synthesizer", None)
    monkeypatch.setattr(media.settings, "tts_backend", "silence")
    assert isinstance(media.get_synthesizer(), media.SilenceSynthesizer)

    monkeypatch.setattr(media, "_synthesizer", None)
    monkeypatch.setattr(media.settings, "tts_backend", "silero")
    s = media.get_synthesizer()
    assert isinstance(s, media.SileroSynthesizer) and s._model is None   # модель ещё не загружена


async def test_tts_disabled_by_default(monkeypatch):
    monkeypatch.setattr(media.settings, "tts_enabled", False)
    assert await media.maybe_synthesize("любой текст") is None


async def test_maybe_synthesize_swallows_error(monkeypatch):
    monkeypatch.setattr(media.settings, "tts_enabled", True)

    class _Boom(media.Synthesizer):
        async def synthesize(self, text):
            raise media.SynthesisError("сбой модели")
    monkeypatch.setattr(media, "_synthesizer", _Boom())
    # ошибка синтеза не роняет ход — откат на текст (None)
    assert await media.maybe_synthesize("текст") is None


async def test_wav_to_ogg_opus_valid():
    wav = await media.SilenceSynthesizer().synthesize("проверка")
    ogg = media.wav_to_ogg_opus(wav)
    assert ogg and ogg[:4] == b"OggS"     # валидный OGG-контейнер для sendVoice


async def test_silero_roundtrip_if_available():
    import pytest
    pytest.importorskip("torch")
    s = media.SileroSynthesizer("v4_ru", "xenia", 48000, "cpu")
    audio = await s.synthesize("Привет, это тест озвучки.")
    assert audio[:4] == b"RIFF" and len(audio) > 44   # валидный WAV с данными
