"""Conversation tables (not in the dataset): chat history per browser session."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, Uuid, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.adapters.persistence.base import Base, sql_in
from app.domain.conversation import MessageRole


class Conversation(Base):
    __tablename__ = "conversations"

    conversation_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    session_id: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    # Explicit agent state (AgentState.to_dict), kept apart from the message history.
    agent_state: Mapped[dict[str, Any]] = mapped_column(
        JSONB, server_default=text("'{}'::jsonb")
    )


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        CheckConstraint(sql_in("role", [r.value for r in MessageRole]), name="role_valid"),
        Index("ix_messages_conversation_id_created_at", "conversation_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.conversation_id", ondelete="CASCADE")
    )
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text, server_default="")
    # UI blocks (product cards, comparison, checkout draft) as defined in the API contract.
    blocks: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB)
    tool_calls: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
