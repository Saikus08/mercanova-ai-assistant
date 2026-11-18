"""Speech-to-text use case and POST /api/transcribe, with a fake model."""

from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.adapters.api.transcribe import get_speech_to_text
from app.application.transcription import MAX_AUDIO_BYTES, MAX_AUDIO_SECONDS, transcribe_audio
from app.domain.speech import (
    AudioUnreadable,
    InvalidAudio,
    SpeechToTextUnavailable,
    Transcript,
)
from app.main import app

SAMPLE = Path(__file__).parent.parent / "fixtures" / "necesito_auriculares.wav"


class FakeSpeechToText:
    def __init__(self, result: Transcript | Exception) -> None:
        self._result = result
        self.calls: list[tuple[bytes, float]] = []

    def transcribe(self, audio: bytes, max_seconds: float) -> Transcript:
        self.calls.append((audio, max_seconds))
        if isinstance(self._result, Exception):
            raise self._result
        return self._result


HEARD = Transcript(text="necesito auriculares", language="es", duration_s=3.1)


# --- use case -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "content_type",
    ["audio/webm", "audio/webm;codecs=opus", "audio/ogg; codecs=opus", "audio/wav", "audio/x-wav"],
)
def test_accepts_the_contract_formats(content_type: str) -> None:
    stt = FakeSpeechToText(HEARD)

    assert transcribe_audio(stt, b"audio", content_type) == HEARD
    assert stt.calls == [(b"audio", MAX_AUDIO_SECONDS)]


@pytest.mark.parametrize("content_type", [None, "audio/mpeg", "text/plain", "application/json"])
def test_rejects_other_formats_without_calling_the_model(content_type: str | None) -> None:
    stt = FakeSpeechToText(HEARD)

    with pytest.raises(InvalidAudio):
        transcribe_audio(stt, b"audio", content_type)
    assert stt.calls == []


def test_empty_audio_is_unreadable() -> None:
    stt = FakeSpeechToText(HEARD)

    with pytest.raises(AudioUnreadable):
        transcribe_audio(stt, b"", "audio/webm")
    assert stt.calls == []


def test_audio_over_the_size_limit_is_rejected() -> None:
    stt = FakeSpeechToText(HEARD)

    with pytest.raises(InvalidAudio):
        transcribe_audio(stt, b"x" * (MAX_AUDIO_BYTES + 1), "audio/webm")
    assert stt.calls == []


def test_audio_without_speech_is_unreadable() -> None:
    stt = FakeSpeechToText(Transcript(text="  ", language="es", duration_s=2.0))

    with pytest.raises(AudioUnreadable):
        transcribe_audio(stt, b"audio", "audio/webm")


def test_text_is_trimmed() -> None:
    stt = FakeSpeechToText(Transcript(text="  hola  ", language="es", duration_s=1.0))

    assert transcribe_audio(stt, b"audio", "audio/webm").text == "hola"


# --- endpoint -------------------------------------------------------------------------------


@pytest.fixture
def use_stt() -> Iterator[Callable[[Transcript | Exception], FakeSpeechToText]]:
    def install(result: Transcript | Exception) -> FakeSpeechToText:
        fake = FakeSpeechToText(result)
        app.dependency_overrides[get_speech_to_text] = lambda: fake
        return fake

    try:
        yield install
    finally:
        app.dependency_overrides.clear()


def post_audio(data: bytes, content_type: str = "audio/wav"):
    with TestClient(app, raise_server_exceptions=False) as client:
        return client.post("/api/transcribe", files={"audio": ("voice.wav", data, content_type)})


def test_endpoint_returns_the_transcript(use_stt) -> None:
    fake = use_stt(HEARD)

    response = post_audio(SAMPLE.read_bytes())

    assert response.status_code == 200
    assert response.json() == {"text": "necesito auriculares", "language": "es", "duration_s": 3.1}
    assert fake.calls[0][0] == SAMPLE.read_bytes()


def test_endpoint_reports_empty_audio_as_unreadable(use_stt) -> None:
    use_stt(HEARD)

    response = post_audio(b"")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "AUDIO_UNREADABLE"


def test_endpoint_reports_undecodable_audio_as_unreadable(use_stt) -> None:
    use_stt(AudioUnreadable("not audio"))

    response = post_audio(b"not audio at all")

    assert response.status_code == 422
    body = response.json()["error"]
    assert body["code"] == "AUDIO_UNREADABLE"
    assert "not audio" not in body["message"]


def test_endpoint_rejects_an_unsupported_format(use_stt) -> None:
    use_stt(HEARD)

    response = post_audio(b"id3", "audio/mpeg")

    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert error["details"]["errors"][0]["field"] == "audio"


def test_endpoint_requires_the_audio_field(use_stt) -> None:
    use_stt(HEARD)

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post("/api/transcribe", data={"other": "x"})

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_endpoint_reports_the_model_down_as_unavailable(use_stt) -> None:
    use_stt(SpeechToTextUnavailable("model download failed"))

    response = post_audio(SAMPLE.read_bytes())

    assert response.status_code == 503
    body = response.json()["error"]
    assert body["code"] == "STT_UNAVAILABLE"
    assert "download" not in body["message"]
