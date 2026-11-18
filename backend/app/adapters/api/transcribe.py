"""POST /api/transcribe: voice to text (RF-08).

The route is synchronous so FastAPI runs it in a worker thread: transcription takes seconds of
CPU and must not block the event loop. It does not need X-Session-Id because it stores nothing.
"""

from fastapi import APIRouter, Depends, File, UploadFile
from pydantic import BaseModel

from app.adapters.stt.whisper_stt import FasterWhisperSpeechToText
from app.application.ports import SpeechToText
from app.application.transcription import MAX_AUDIO_BYTES, transcribe_audio
from app.config import get_settings

router = APIRouter(prefix="/api", tags=["speech"])


class TranscriptResponse(BaseModel):
    text: str
    language: str
    duration_s: float


def get_speech_to_text() -> SpeechToText:
    settings = get_settings()
    return FasterWhisperSpeechToText(settings.stt_model, settings.stt_language)


@router.post("/transcribe", response_model=TranscriptResponse)
def transcribe(
    audio: UploadFile = File(...),
    stt: SpeechToText = Depends(get_speech_to_text),
) -> TranscriptResponse:
    # One byte over the limit is enough to know the upload is too large.
    data = audio.file.read(MAX_AUDIO_BYTES + 1)
    transcript = transcribe_audio(stt, data, audio.content_type)
    return TranscriptResponse(
        text=transcript.text, language=transcript.language, duration_s=transcript.duration_s
    )
