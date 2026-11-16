"""Fixed use cases (docs/use-cases.md) against the real Ollama model. Not part of CI.

Run with ``make eval``. The database is used read only: only catalog tools are registered, so
nothing here can add to a cart or start a checkout. Assertions check the trajectory (tools used,
filters, stop reason), never the wording of the reply.
"""

import os
import time
from collections.abc import Iterator

import pytest

from app.adapters.llm.ollama_chat import OllamaChat
from app.adapters.llm.ollama_embeddings import OllamaEmbeddings
from app.adapters.persistence.catalog_repository import SqlAlchemyCatalogRepository
from app.adapters.persistence.semantic_search_repository import SqlAlchemySemanticSearch
from app.adapters.persistence.session import get_session_factory
from app.application.agent.answer import TurnResult
from app.application.agent.catalog_tools import build_catalog_tools
from app.application.agent.dispatcher import ToolDispatcher
from app.application.agent.grounding import leaked_tool_names
from app.application.agent.loop import AgentLoop
from app.application.agent.registry import ToolRegistry
from app.application.agent.tool import ToolContext
from app.config import get_settings
from app.domain.agent import AgentState, ChatMessage, StopReason

pytestmark = [
    pytest.mark.eval,
    pytest.mark.skipif(os.environ.get("RUN_EVAL") != "1", reason="set RUN_EVAL=1 to run evals"),
]

CONTEXT = ToolContext(session_id="eval-session")
USE_CASE_1 = (
    "Necesito unos auriculares cómodos para trabajar y hacer videollamadas. "
    "No quiero gastar más de USD 200."
)
USE_CASE_2 = "Quiero un monitor"
USE_CASE_3 = "Compará el primero con el segundo"
BUDGET = 200


@pytest.fixture(scope="module")
def loop() -> Iterator[AgentLoop]:
    settings = get_settings()
    session = get_session_factory()()
    embedder = OllamaEmbeddings(
        settings.ollama_base_url, settings.embedding_model, settings.embedding_timeout_seconds
    )
    chat = OllamaChat(
        settings.ollama_base_url,
        settings.llm_model,
        settings.llm_timeout_seconds,
        temperature=settings.llm_temperature,
        num_ctx=settings.llm_num_ctx,
        think=settings.llm_think,
    )
    tools = build_catalog_tools(
        SqlAlchemyCatalogRepository(session),
        embedder,
        SqlAlchemySemanticSearch(session),
        settings.search_min_similarity,
    )
    registry = ToolRegistry(tools)
    try:
        yield AgentLoop(
            chat,
            ToolDispatcher(registry),
            registry.specs(),
            settings.agent_max_steps,
            settings.agent_history_messages,
        )
    finally:
        chat.close()
        session.close()


def run_case(
    label: str,
    loop: AgentLoop,
    message: str,
    state: AgentState,
    history: list[ChatMessage] | None = None,
) -> TurnResult:
    started = time.perf_counter()
    result = loop.run_turn(state, history or [], message, CONTEXT)
    seconds = time.perf_counter() - started
    tools = [t["name"] for t in result.tools_used]
    print(
        f"\n[eval] {label}: stop={result.stop_reason.value} tools={tools} steps={result.steps} "
        f"tokens={result.prompt_tokens}+{result.completion_tokens} seconds={seconds:.1f} "
        f"fallback_used={result.fallback_used}"
    )
    return result


def history_of(message: str, result: TurnResult) -> list[ChatMessage]:
    return [ChatMessage.user(message), ChatMessage.assistant(result.reply)]


def tool_names(loop: AgentLoop) -> list[str]:
    return [spec.name for spec in loop._tool_specs]


def test_use_case_1_recommends_headphones_within_budget(loop):
    result = run_case("use case 1", loop, USE_CASE_1, AgentState())
    model_recommendations = 0 if result.fallback_used else len(result.recommendations)
    print(f"[eval] use case 1: model_recommendations={model_recommendations}")

    assert "search_products" in [t["name"] for t in result.tools_used]
    assert result.stop_reason is StopReason.ANSWER
    assert not result.degraded
    assert result.not_found is None
    assert leaked_tool_names(result.reply, tool_names(loop)) == []
    assert 1 <= len(result.recommendations) <= 3
    for item in result.recommendations:
        assert item["product"]["price"]["current"] <= BUDGET
        assert item["product"]["category"] == "Headphones"


def test_use_case_2_asks_before_recommending(loop):
    result = run_case("use case 2", loop, USE_CASE_2, AgentState())

    searches = [t for t in result.tools_used if t["name"] == "search_products"]
    assert all(t["ok"] is False for t in searches)
    assert result.recommendations == []
    assert result.clarification is not None
    assert 2 <= len(result.clarification["options"]) <= 4


def test_use_case_3_compares_the_first_two_shown_products(loop):
    state = AgentState()
    first = run_case("use case 3 (setup: use case 1)", loop, USE_CASE_1, state)
    shown = [product.product_id for product in state.shown_products]
    assert len(shown) >= 2, "use case 1 did not show two products to compare"

    result = run_case("use case 3", loop, USE_CASE_3, state, history=history_of(USE_CASE_1, first))

    compares = [t for t in result.tools_used if t["name"] == "compare_products"]
    assert compares, "compare_products was not called"
    assert any(
        t["ok"] is True
        and t["arguments"].get("product_ids") == shown[:2]
        and "attributes" in t["result"]
        and [p["product_id"] for p in t["result"]["products"]] == shown[:2]
        for t in compares
    )
