"""Pure helpers of the chat stream: SSE framing, word chunks and error events."""

import json

import pytest

from app.adapters.api.chat import error_event, format_sse, split_words
from app.domain.agent import LLMUnavailable
from app.domain.conversation import ConversationNotFound, InvalidMessage


def test_format_sse_has_event_and_json_data_lines():
    frame = format_sse("meta", {"conversation_id": "c1"})
    assert frame == 'event: meta\ndata: {"conversation_id": "c1"}\n\n'


def test_format_sse_keeps_non_ascii_characters():
    frame = format_sse("token", {"text": "¿Qué tal? ñandú "})
    assert "¿Qué tal? ñandú " in frame
    assert "\\u" not in frame
    data_line = frame.split("\n")[1]
    assert json.loads(data_line.removeprefix("data: ")) == {"text": "¿Qué tal? ñandú "}


@pytest.mark.parametrize(
    "text",
    [
        "Te recomiendo estas tres opciones.",
        "  leading and trailing  ",
        "Line one\nLine two\n\nLine three",
        "single",
        "   ",
        "",
    ],
)
def test_split_words_joins_back_to_the_original_text(text):
    assert "".join(split_words(text)) == text


def test_split_words_gives_one_word_with_its_trailing_whitespace_per_chunk():
    assert split_words("Te recomiendo  esto\nya") == ["Te ", "recomiendo  ", "esto\n", "ya"]


def test_split_words_of_empty_text_has_no_chunks():
    assert split_words("") == []


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (LLMUnavailable("down"), "LLM_UNAVAILABLE"),
        (ConversationNotFound("x"), "CONVERSATION_NOT_FOUND"),
        (InvalidMessage("Message must have 1 to 2000 characters"), "VALIDATION_ERROR"),
        (RuntimeError("secret detail"), "INTERNAL_ERROR"),
    ],
)
def test_error_event_maps_exceptions_to_codes(error, code):
    name, data = error_event(error)
    assert name == "error"
    assert data["error"]["code"] == code
    assert data["error"]["message"]


def test_internal_error_event_never_includes_the_exception_text():
    _, data = error_event(RuntimeError("secret detail"))
    assert "secret detail" not in json.dumps(data)
