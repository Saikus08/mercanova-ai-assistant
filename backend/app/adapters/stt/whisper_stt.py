"""SpeechToText port implemented with faster-whisper, running locally on CPU.

faster-whisper is imported inside the functions: it loads CTranslate2 and ONNX Runtime, which
would slow down the start of the API and of every test run that never transcribes.
"""

import io
import logging
import threading
from collections.abc import Callable
from typing import Any

from app.domain.speech import AudioUnreadable, InvalidAudio, SpeechToTextUnavailable, Transcript

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16000  # faster-whisper resamples every input to 16 kHz mono
# 8-bit weights on CPU: less memory and faster than float32 (faster-whisper README).
COMPUTE_TYPE = "int8"

_models: dict[str, Any] = {}
_models_lock = threading.Lock()


def load_whisper_model(model_name: str) -> Any:
    """One model per process, loaded on first use (it downloads on the very first run)."""
    with _models_lock:
        if model_name not in _models:
            from faster_whisper import WhisperModel

            logger.info("Loading faster-whisper model %s", model_name)
            _models[model_name] = WhisperModel(model_name, device="cpu", compute_type=COMPUTE_TYPE)
        return _models[model_name]


class FasterWhisperSpeechToText:
    def __init__(
        self,
        model_name: str,
        language: str,
        load_model: Callable[[], Any] | None = None,
    ) -> None:
        self._language = language
        self._load_model = load_model or (lambda: load_whisper_model(model_name))

    def transcribe(self, audio: bytes, max_seconds: float) -> Transcript:
        samples = _decode(audio)
        duration = len(samples) / SAMPLE_RATE
        if duration > max_seconds:
            raise InvalidAudio(f"Audio must be at most {max_seconds:g} seconds")

        try:
            model = self._load_model()
            # Silence filter (VAD) so pauses do not turn into invented words.
            segments, info = model.transcribe(samples, language=self._language, vad_filter=True)
            # Segments are produced lazily: the model runs while they are read.
            text = "".join(segment.text for segment in segments)
        except Exception as error:
            logger.exception("Speech-to-text failed")
            raise SpeechToTextUnavailable("The speech-to-text model failed") from error

        return Transcript(text=text.strip(), language=info.language, duration_s=round(duration, 2))


def _decode(audio: bytes) -> Any:
    from faster_whisper import decode_audio

    try:
        samples = decode_audio(io.BytesIO(audio), sampling_rate=SAMPLE_RATE)
    except Exception as error:
        raise AudioUnreadable("The audio cannot be decoded") from error
    if len(samples) == 0:
        raise AudioUnreadable("The audio has no samples")
    return samples
