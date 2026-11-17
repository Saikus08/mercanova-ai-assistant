"""SQLAlchemy implementation of the ConversationRepository port.

Messages created in one transaction share ``created_at`` (the transaction start time), so every
ordering uses ``(created_at, id)``: the serial id keeps the insertion order inside a turn.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.persistence.orm.conversation import Conversation, Message
from app.domain.agent import AgentState
from app.domain.conversation import ConversationNotFound, MessageRole, StoredMessage


def _to_stored(row: Message) -> StoredMessage:
    return StoredMessage(
        role=MessageRole(row.role),
        content=row.content,
        blocks=row.blocks,
        tool_calls=row.tool_calls,
        created_at=row.created_at,
    )


class SqlAlchemyConversationRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

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
