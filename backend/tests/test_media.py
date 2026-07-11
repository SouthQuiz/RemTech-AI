"""Issue #32 — интерфейсы STT/TTS и опциональные хуки (в вебе выключены)."""
from app.media import (
    Synthesizer,
    Transcriber,
    get_synthesizer,
    get_transcriber,
    maybe_synthesize,
    maybe_transcribe,
)


async def test_synthesizer_produces_valid_wav():
    synth = get_synthesizer()
    assert isinstance(synth, Synthesizer)
    audio = await synth.synthesize("привет, это тест озвучки")
    assert audio[:4] == b"RIFF" and len(audio) > 44   # валидный WAV с данными


async def test_transcriber_contract():
    tr = get_transcriber()
    assert isinstance(tr, Transcriber)
    text = await tr.transcribe(b"\x00\x01", "audio/wav")
    assert isinstance(text, str)   # контракт: возвращает строку


async def test_hooks_disabled_by_default():
    # в веб-канале STT/TTS по умолчанию выключены (issue #32)
    assert await maybe_transcribe(b"audio", "audio/wav") == ""
    assert await maybe_synthesize("текст") is None
