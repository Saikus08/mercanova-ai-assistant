"""Voice query to text (RF-08). The text then follows the same chat path as a typed one."""

from app.application.ports import SpeechToText
from app.domain.speech import AudioUnreadable, InvalidAudio, Transcript

# Limits from the API contract (POST /api/transcribe).
MAX_AUDIO_BYTES = 10 * 1024 * 1024
MAX_AUDIO_SECONDS = 60.0
# Formats the browser records: MediaRecorder gives webm (Chrome) or ogg (Firefox); wav for tests.
ALLOWED_MEDIA_TYPES = frozenset(
    {"audio/webm", "video/webm", "audio/ogg", "audio/wav", "audio/x-wav", "audio/wave"}
)


def transcribe_audio(stt: SpeechToText, audio: bytes, content_type: str | None) -> Transcript:
    """Check the upload against the contract limits, transcribe it and trim the text.

    Raises InvalidAudio (format, size or duration), AudioUnreadable (empty, undecodable or no
    speech) or SpeechToTextUnavailable.
    """
    media_type = (content_type or "").split(";", 1)[0].strip().lower()
    if media_type not in ALLOWED_MEDIA_TYPES:
        raise InvalidAudio("Audio must be webm, ogg or wav")
    if not audio:
        raise AudioUnreadable("The audio is empty")
    if len(audio) > MAX_AUDIO_BYTES:
        raise InvalidAudio("Audio must be at most 10 MB")

    transcript = stt.transcribe(audio, MAX_AUDIO_SECONDS)
    text = transcript.text.strip()
    if not text:
        raise AudioUnreadable("No speech was recognized")
    return Transcript(text=text, language=transcript.language, duration_s=transcript.duration_s)
