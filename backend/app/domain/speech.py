"""Speech-to-text: the transcript of a recorded voice query and its errors."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Transcript:
    text: str
    language: str
    duration_s: float


class AudioUnreadable(Exception):
    """The audio is empty, cannot be decoded or has no recognizable speech."""


class InvalidAudio(Exception):
    """The upload breaks a limit of the contract: format, size or duration."""


class SpeechToTextUnavailable(Exception):
    """The speech-to-text model cannot be loaded or fails while transcribing."""
