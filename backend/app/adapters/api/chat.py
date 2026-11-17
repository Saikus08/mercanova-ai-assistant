"""Chat endpoints. Every route needs the X-Session-Id header.

The agent loop and its tools are built per request because their repositories are bound to the
request's database session. The model and the embedder are separate dependencies so tests can
replace them.
"""

import json
import logging
import queue
import re
import threading
import time
from collections.abc import Iterator
from typing import Any, Literal

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.adapters.api.session import get_session_id
from app.adapters.llm.ollama_chat import OllamaChat
from app.adapters.llm.ollama_embeddings import OllamaEmbeddings
from app.adapters.persistence.cart_repository import SqlAlchemyCartRepository
from app.adapters.persistence.catalog_repository import SqlAlchemyCatalogRepository
from app.adapters.persistence.conversation_repository import SqlAlchemyConversationRepository
from app.adapters.persistence.semantic_search_repository import SqlAlchemySemanticSearch
from app.adapters.persistence.session import get_session
from app.application.agent.cart_tools import build_cart_tools
from app.application.agent.catalog_tools import build_catalog_tools
from app.application.agent.dispatcher import ToolDispatcher
from app.application.agent.loop import AgentLoop
from app.application.agent.registry import ToolRegistry
from app.application.chat import ChatReply, ChatService
from app.application.ports import ChatModel, EmbeddingModel
from app.config import get_settings
from app.domain.agent import LLMUnavailable
from app.domain.conversation import ConversationNotFound, InvalidMessage, MessageRole

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])

# Pause between token events so the UI shows the answer being written. Tests set it to 0.
TOKEN_DELAY_SECONDS = 0.02

_CHUNK = re.compile(r"\s*\S+\s*")

LLM_UNAVAILABLE_MESSAGE = (
    "El asistente no está disponible por ahora. El resto de la tienda sigue funcionando."
)
CONVERSATION_NOT_FOUND_MESSAGE = "La conversación no existe."
INTERNAL_ERROR_MESSAGE = "Ocurrió un error inesperado."


class ChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None
    # Validated only: the assistant answers the same way for text and voice.
    input_mode: Literal["text", "voice"] = "text"


class ChatResponse(BaseModel):
    conversation_id: str
    reply: str
    blocks: list[dict]
    tools_used: list[dict]


class MessageResponse(BaseModel):
    role: str
    content: str
    blocks: list[dict]
    created_at: str


class ConversationResponse(BaseModel):
    conversation_id: str
    messages: list[MessageResponse]


# --- pure helpers ---------------------------------------------------------------------------


def format_sse(event: str, data: Any) -> str:
    """One Server-Sent Event frame."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def split_words(text: str) -> list[str]:
    """Chunks of one word plus its trailing whitespace; joining them gives back ``text``."""
    chunks = _CHUNK.findall(text)
    if not chunks and text:
        return [text]  # whitespace only
    return chunks


def error_event(error: Exception) -> tuple[str, dict]:
    """The ``error`` event for a failed turn. The exception text is never sent."""
    if isinstance(error, LLMUnavailable):
        code, message = "LLM_UNAVAILABLE", LLM_UNAVAILABLE_MESSAGE
    elif isinstance(error, ConversationNotFound):
        code, message = "CONVERSATION_NOT_FOUND", CONVERSATION_NOT_FOUND_MESSAGE
    elif isinstance(error, InvalidMessage):
        code, message = "VALIDATION_ERROR", str(error)
    else:
        code, message = "INTERNAL_ERROR", INTERNAL_ERROR_MESSAGE
    return "error", {"error": {"code": code, "message": message}}


# --- dependencies ---------------------------------------------------------------------------


def get_chat_model() -> Iterator[ChatModel]:
    settings = get_settings()
    model = OllamaChat(
        settings.ollama_base_url,
        settings.llm_model,
        settings.llm_timeout_seconds,
        temperature=settings.llm_temperature,
        num_ctx=settings.llm_num_ctx,
        think=settings.llm_think,
    )
    try:
        yield model
    finally:
        model.close()


def get_embedding_model() -> EmbeddingModel:
    settings = get_settings()
    return OllamaEmbeddings(
        settings.ollama_base_url, settings.embedding_model, settings.embedding_timeout_seconds
    )


def get_chat_service(
    session: Session = Depends(get_session),
    model: ChatModel = Depends(get_chat_model),
    embedder: EmbeddingModel = Depends(get_embedding_model),
) -> ChatService:
    settings = get_settings()
    catalog = SqlAlchemyCatalogRepository(session)
    tools = build_catalog_tools(
        catalog, embedder, SqlAlchemySemanticSearch(session), settings.search_min_similarity
    ) + build_cart_tools(SqlAlchemyCartRepository(session))
    registry = ToolRegistry(tools)
    loop = AgentLoop(
        model,
        ToolDispatcher(registry),
        registry.specs(),
        settings.agent_max_steps,
        settings.agent_history_messages,
    )
    return ChatService(
        loop,
        SqlAlchemyConversationRepository(session),
        catalog,
        settings.agent_history_messages,
    )


def get_conversation_repository(
    session: Session = Depends(get_session),
) -> SqlAlchemyConversationRepository:
    return SqlAlchemyConversationRepository(session)


# --- routes ---------------------------------------------------------------------------------


@router.post("", response_model=ChatResponse)
def chat(
    body: ChatRequest,
    session_id: str = Depends(get_session_id),
    service: ChatService = Depends(get_chat_service),
) -> ChatResponse:
    reply = service.handle(session_id, body.message, body.conversation_id)
    return ChatResponse(
        conversation_id=reply.conversation_id,
        reply=reply.reply,
        blocks=reply.blocks,
        tools_used=reply.tools_used,
    )


def _stream_events(
    service: ChatService, session_id: str, body: ChatRequest
) -> Iterator[str]:
    """Run the turn in a worker thread and yield its events as they arrive."""
    events: queue.Queue[tuple[str, Any]] = queue.Queue()

    def work() -> None:
        try:
            reply = service.handle(
                session_id,
                body.message,
                body.conversation_id,
                on_event=lambda e: (
                    events.put(("tool_call", {"name": e["name"], "args": e["arguments"]}))
                    if e.get("type") == "tool_call"
                    else None
                ),
                on_conversation=lambda cid: events.put(("meta", {"conversation_id": cid})),
            )
            events.put(("reply", reply))
        except Exception as error:
            if error_event(error)[1]["error"]["code"] == "INTERNAL_ERROR":
                logger.exception("Chat stream failed")
            events.put(("failure", error))

    threading.Thread(target=work, daemon=True).start()

    while True:
        name, payload = events.get()
        if name in ("meta", "tool_call"):
            yield format_sse(name, payload)
        elif name == "failure":
            yield format_sse(*error_event(payload))
            return
        else:
            yield from _reply_events(payload)
            return


def _reply_events(reply: ChatReply) -> Iterator[str]:
    for chunk in split_words(reply.reply):
        yield format_sse("token", {"text": chunk})
        time.sleep(TOKEN_DELAY_SECONDS)
    for block in reply.blocks:
        yield format_sse("block", block)
    yield format_sse("done", {"reply": reply.reply, "tools_used": reply.tools_used})


@router.post("/stream")
def chat_stream(
    body: ChatRequest,
    session_id: str = Depends(get_session_id),
    service: ChatService = Depends(get_chat_service),
) -> StreamingResponse:
    return StreamingResponse(
        _stream_events(service, session_id, body),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/{conversation_id}", response_model=ConversationResponse)
def get_conversation(
    conversation_id: str,
    session_id: str = Depends(get_session_id),
    repository: SqlAlchemyConversationRepository = Depends(get_conversation_repository),
) -> ConversationResponse:
    stored = repository.list_messages(conversation_id, session_id)
    return ConversationResponse(
        conversation_id=conversation_id,
        messages=[
            MessageResponse(
                role=m.role.value,
                content=m.content,
                blocks=m.blocks or [],
                created_at=m.created_at.isoformat(),
            )
            for m in stored
            if m.role in (MessageRole.USER, MessageRole.ASSISTANT)
        ],
    )
