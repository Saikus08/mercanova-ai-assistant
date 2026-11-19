"""SQLAlchemy implementation of the ConversationRepository port.

Messages created in one transaction share ``created_at`` (the transaction start time), so every
ordering uses ``(created_at, id)``: the serial id keeps the insertion order inside a turn.
"""

import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.adapters.persistence.orm.conversation import Conversation, Message
from app.domain.agent import AgentState
from app.domain.conversation import (
    ConversationBusy,
    ConversationNotFound,
    MessageRole,
    StoredMessage,
)

TURN_LOCK_TIMEOUT_SECONDS = 30.0
TURN_LOCK_POLL_SECONDS = 0.1
_TRY_LOCK = text("SELECT pg_try_advisory_lock(hashtext(:key))")
_UNLOCK = text("SELECT pg_advisory_unlock(hashtext(:key))")


def _to_stored(row: Message) -> StoredMessage:
    return StoredMessage(
        role=MessageRole(row.role),
        content=row.content,
        blocks=row.blocks,
        tool_calls=row.tool_calls,
        created_at=row.created_at,
    )


class SqlAlchemyConversationRepository:
    def __init__(
        self, session: Session, lock_timeout_seconds: float | None = None
    ) -> None:
        self._session = session
        self._lock_timeout_seconds = (
            TURN_LOCK_TIMEOUT_SECONDS if lock_timeout_seconds is None else lock_timeout_seconds
        )

    @contextmanager
    def turn_lock(self, conversation_id: str, session_id: str) -> Iterator[None]:
        """Hold a Postgres advisory lock on the conversation for the whole turn.

        The lock lives on its own connection. A row lock or a lock on the session's connection
        would be released by the commits that the cart tools and ``append_turn`` make in the
        middle of a turn. Advisory locks are session-level, so only the explicit unlock frees it.
        """
        self._owned(conversation_id, session_id)  # a foreign id must not even queue for the lock
        key = {"key": f"conversation-turn:{conversation_id}"}
        engine = self._session.get_bind().engine
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
            deadline = time.monotonic() + self._lock_timeout_seconds
            while not connection.scalar(_TRY_LOCK, key):
                if time.monotonic() >= deadline:
                    raise ConversationBusy(conversation_id)
                time.sleep(TURN_LOCK_POLL_SECONDS)
            try:
                yield
            finally:
                try:
                    connection.execute(_UNLOCK, key)
                except Exception:
                    # A failed unlock would hand the pool a connection that still holds the
                    # lock: dropping the connection makes the server release it.
                    connection.invalidate()
                    raise

    def create(self, session_id: str) -> str:
        conversation = Conversation(session_id=session_id)
        self._session.add(conversation)
        try:
            self._session.flush()
            conversation_id = str(conversation.conversation_id)
            self._session.commit()
        except BaseException:
            self._session.rollback()
            raise
        return conversation_id

    def _owned(self, conversation_id: str, session_id: str) -> Conversation:
        try:
            parsed = uuid.UUID(conversation_id)
        except ValueError:
            raise ConversationNotFound(conversation_id) from None
        conversation = self._session.scalar(
            select(Conversation).where(
                Conversation.conversation_id == parsed, Conversation.session_id == session_id
            )
        )
        if conversation is None:
            raise ConversationNotFound(conversation_id)
        return conversation

    def load_state(self, conversation_id: str, session_id: str) -> AgentState:
        return AgentState.from_dict(self._owned(conversation_id, session_id).agent_state)

    def recent_messages(self, conversation_id: str, limit: int) -> list[StoredMessage]:
        rows = self._session.scalars(
            select(Message)
            .where(
                Message.conversation_id == uuid.UUID(conversation_id),
                Message.role.in_([MessageRole.USER.value, MessageRole.ASSISTANT.value]),
            )
            .order_by(Message.created_at.desc(), Message.id.desc())
            .limit(limit)
        ).all()
        return [_to_stored(row) for row in reversed(rows)]

    def list_messages(self, conversation_id: str, session_id: str) -> list[StoredMessage]:
        conversation = self._owned(conversation_id, session_id)
        rows = self._session.scalars(
            select(Message)
            .where(Message.conversation_id == conversation.conversation_id)
            .order_by(Message.created_at, Message.id)
        ).all()
        return [_to_stored(row) for row in rows]

    def append_turn(
        self,
        conversation_id: str,
        user_text: str,
        assistant_text: str,
        blocks: list[dict],
        tool_calls: list[dict],
        state: AgentState,
    ) -> None:
        parsed = uuid.UUID(conversation_id)
        try:
            conversation = self._session.get(Conversation, parsed)
            if conversation is None:
                raise ConversationNotFound(conversation_id)
            self._session.add(
                Message(conversation_id=parsed, role=MessageRole.USER.value, content=user_text)
            )
            self._session.add(
                Message(
                    conversation_id=parsed,
                    role=MessageRole.ASSISTANT.value,
                    content=assistant_text,
                    blocks=blocks,
                    tool_calls=tool_calls,
                )
            )
            conversation.agent_state = state.to_dict()
            self._session.commit()
        except BaseException:
            self._session.rollback()
            raise
