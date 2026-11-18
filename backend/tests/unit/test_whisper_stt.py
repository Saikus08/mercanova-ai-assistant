"""faster-whisper adapter: real audio decoding, fake model (the real one only with -m stt)."""

import io
import os
import wave
from dataclasses import dataclass
from pathlib import Path

import pytest

from app.adapters.stt.whisper_stt import FasterWhisperSpeechToText
from app.domain.speech import AudioUnreadable, InvalidAudio, SpeechToTextUnavailable

SAMPLE = Path(__file__).parent.parent / "fixtures" / "necesito_auriculares.wav"
SAMPLE_SECONDS = 3.065


@dataclass
class FakeSegment:
    text: str


@dataclass
class FakeInfo:
    language: str


class FakeModel:
    def __init__(self, texts: list[str], error: Exception | None = None) -> None:
        self._texts = texts
        self._error = error
        self.kwargs: dict = {}

    def transcribe(self, audio, **kwargs):
        self.kwargs = kwargs
        if self._error:
            raise self._error
        return (FakeSegment(t) for t in self._texts), FakeInfo(language="es")


def adapter(model: FakeModel) -> FasterWhisperSpeechToText:
    return FasterWhisperSpeechToText("small", "es", load_model=lambda: model)


def silent_wav(seconds: float) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(16000)
        out.writeframes(b"\x00\x00" * int(16000 * seconds))
    return buffer.getvalue()


def test_joins_the_segments_and_reports_language_and_duration() -> None:
    model = FakeModel([" Necesito auriculares", " para videollamadas."])

    transcript = adapter(model).transcribe(SAMPLE.read_bytes(), max_seconds=60)

    assert transcript.text == "Necesito auriculares para videollamadas."
    assert transcript.language == "es"
    assert transcript.duration_s == pytest.approx(SAMPLE_SECONDS, abs=0.05)
    assert model.kwargs["language"] == "es"
    assert model.kwargs["vad_filter"] is True


def test_bytes_that_are_not_audio_are_unreadable() -> None:
    with pytest.raises(AudioUnreadable):
        adapter(FakeModel(["hola"])).transcribe(b"this is not audio", max_seconds=60)


def test_a_container_without_samples_is_unreadable() -> None:
    with pytest.raises(AudioUnreadable):
        adapter(FakeModel(["hola"])).transcribe(silent_wav(0), max_seconds=60)


def test_audio_longer_than_the_limit_is_rejected_before_transcribing() -> None:
    model = FakeModel(["hola"])

    with pytest.raises(InvalidAudio):
        adapter(model).transcribe(silent_wav(3), max_seconds=2)
    assert model.kwargs == {}


def test_a_model_that_cannot_load_is_unavailable() -> None:
    def fail() -> FakeModel:
        raise OSError("could not download the model")

    stt = FasterWhisperSpeechToText("small", "es", load_model=fail)

    with pytest.raises(SpeechToTextUnavailable):
        stt.transcribe(SAMPLE.read_bytes(), max_seconds=60)


def test_a_model_failure_while_transcribing_is_unavailable() -> None:
    model = FakeModel([], error=RuntimeError("out of memory"))

    with pytest.raises(SpeechToTextUnavailable):
        adapter(model).transcribe(SAMPLE.read_bytes(), max_seconds=60)


@pytest.mark.stt
@pytest.mark.skipif(not os.environ.get("RUN_STT"), reason="set RUN_STT=1 (make test-stt)")
def test_real_model_transcribes_the_spanish_sample() -> None:
    model_name = os.environ.get("STT_MODEL", "small")
    stt = FasterWhisperSpeechToText(model_name, "es")

    transcript = stt.transcribe(SAMPLE.read_bytes(), max_seconds=60)

    # Only the product word is asserted: Whisper may spell the rest differently between runs.
    assert "auriculares" in transcript.text.lower()
    assert transcript.language == "es"
