"""Conversation value objects."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class MessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class ConversationNotFound(Exception):
    """No conversation exists with the requested id."""


@dataclass(frozen=True)
class StoredMessage:
    role: MessageRole
    content: str
    blocks: list[dict] | None
    tool_calls: list[dict] | None
    created_at: datetime
