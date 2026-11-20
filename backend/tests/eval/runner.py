"""Runs the golden cases against the real agent and stores one JSON file per invocation.

Usage (inside the backend container, with Ollama and the database up):
    python -m tests.eval.runner --model qwen3:8b --runs 3 --think false

The testable core (``execute_run`` and the helpers) imports no adapter: the real wiring
(Ollama, PostgreSQL) lives only in ``main``. The agent is measured, never changed.

Result file: a header (model, think, temperature, num_ctx, runs, label, started_at) plus
``cases``: [{"case_id", "kind", "hard", "runs": [run record, ...]}]. A run record holds scores,
condition results, cost, software corrections, the reply and the tools called (name, arguments
and ok flag, never the tool results).
"""

import argparse
import json
import re
import time
import uuid
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from app.application.agent.answer import TurnResult
from app.application.agent.tool import ToolContext
from app.domain.agent import AgentState, ChatMessage, Role, ShownProduct, StopReason
from tests.eval import scoring
from tests.eval.golden_cases import GOLDEN_CASES, GoldenCase

DEFAULT_RUNS = 3
DEFAULT_OUT_DIR = Path(__file__).resolve().parent / "results"
THINK_VALUES = {"true": True, "false": False, "default": None}
_PRODUCT_ID_RE = re.compile(r"MN-[A-Z]+-\d{4}")


class ModelUnavailable(Exception):
    """The model did not answer: there is no point in running more cases."""


class CartPort(Protocol):
    def add(self, session_id: str, product_id: str, quantity: int) -> None: ...

    def quantities(self, session_id: str) -> dict[str, int]: ...

    def clear(self, session_id: str) -> None: ...


class TurnRunner(Protocol):
    def run_turn(
        self,
        state: AgentState,
        history: list[ChatMessage],
        user_message: str,
        context: ToolContext,
        on_event: Callable[[dict[str, Any]], None] | None = None,
        trace_id: str | None = None,
    ) -> TurnResult: ...


# --- one run --------------------------------------------------------------------------------


def _record(case: GoldenCase, run_index: int) -> dict[str, Any]:
    return {"case_id": case.case_id, "kind": case.kind, "run": run_index}


def _error_record(case: GoldenCase, run_index: int, error: Exception) -> dict[str, Any]:
    return {
        **_record(case, run_index),
        "error": f"{type(error).__name__}: {error}",
        "scores": {"task": None, "tool": None, "grounding": None},
        "conditions": {},
        "cost": None,
        "corrections": None,
        "reply": None,
        "tools": [],
        "cart_after": {},
    }


def _scored_record(case: GoldenCase, run_index: int, facts: scoring.RunFacts) -> dict[str, Any]:
    score = scoring.score_run(case.conditions, facts)
    cost = scoring.run_cost(facts)
    fixes = scoring.corrections(facts)
    return {
        **_record(case, run_index),
        "error": None,
        "scores": {"task": score.task, "tool": score.tool, "grounding": score.grounding},
        "conditions": score.passed,
        "cost": {
            "seconds": cost.seconds,
            "prompt_tokens": cost.prompt_tokens,
            "completion_tokens": cost.completion_tokens,
            "steps": cost.steps,
        },
        "corrections": {
            "fallback_used": fixes.fallback_used,
            "degraded": fixes.degraded,
            "stop_reason": fixes.stop_reason,
            "failed_tool_calls": fixes.failed_tool_calls,
            "invalid_tool_calls": fixes.invalid_tool_calls,
        },
        "reply": facts.reply,
        "tools": [
            {"name": entry["name"], "arguments": entry["arguments"], "ok": entry["ok"]}
            for entry in facts.result.tools_used
        ],
        "cart_after": facts.cart_after,
    }


def execute_run(
    case: GoldenCase,
    run_index: int,
    loop: TurnRunner,
    cart: CartPort,
    session_id: str,
    clock: Callable[[], float] = time.perf_counter,
) -> dict[str, Any]:
    """Seed the setup, run the case message once and score it. The cart is always cleaned."""
    setup = case.setup
    try:
        cart.clear(session_id)
        for product_id, quantity in setup.cart:
            cart.add(session_id, product_id, quantity)
        state = AgentState(
            goal=setup.goal,
            shown_products=[ShownProduct(pid, name) for pid, name in setup.shown],
        )
        history = [ChatMessage(Role(role), text) for role, text in setup.history]
        started = clock()
        result = loop.run_turn(state, history, case.message, ToolContext(session_id))
        seconds = clock() - started
        if result.stop_reason is StopReason.LLM_UNAVAILABLE:
            raise ModelUnavailable(f"The model did not answer in {case.case_id}")
        user_texts = tuple(text for role, text in case.setup.history if role == "user") + (
            case.message,
        )
        facts = scoring.RunFacts(result, cart.quantities(session_id), seconds, user_texts)
        return _scored_record(case, run_index, facts)
    except ModelUnavailable:
        raise
    except Exception as error:
        return _error_record(case, run_index, error)
    finally:
        cart.clear(session_id)


# --- arguments, selection and files ---------------------------------------------------------


def _think(value: str) -> bool | None:
    if value not in THINK_VALUES:
        raise argparse.ArgumentTypeError("must be true, false or default")
    return THINK_VALUES[value]


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m tests.eval.runner", description=__doc__)
    parser.add_argument("--model", required=True)
    parser.add_argument("--runs", type=int, default=DEFAULT_RUNS)
    parser.add_argument("--think", type=_think, default=None, help="true, false or default")
    parser.add_argument(
        "--cases",
        type=lambda text: [part.strip() for part in text.split(",") if part.strip()],
        default=None,
        help="comma separated case ids (default: all)",
    )
    parser.add_argument("--hard-only", action="store_true")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--label", default=None)
    return parser.parse_args(argv)


def select_cases(ids: list[str] | None, hard_only: bool) -> list[GoldenCase]:
    known = {case.case_id for case in GOLDEN_CASES}
    unknown = sorted(set(ids or []) - known)
    if unknown:
        raise SystemExit(f"Unknown case ids: {', '.join(unknown)}")
    return [
        case
        for case in GOLDEN_CASES
        if (ids is None or case.case_id in ids) and (case.hard or not hard_only)
    ]


def required_product_ids(cases: Sequence[GoldenCase]) -> set[str]:
    """Product ids the cases rely on: their setups and the ids named in their conditions."""
    ids: set[str] = set()
    for case in cases:
        ids |= {pid for pid, _ in case.setup.shown}
        ids |= {pid for pid, _ in case.setup.cart}
        for condition in case.conditions:
            ids |= set(_PRODUCT_ID_RE.findall(condition.name))
    return ids


def result_file_name(model: str, think: bool | None, started_at: datetime) -> str:
    safe_model = model.replace(":", "-").replace("/", "-")
    think_label = "default" if think is None else str(think).lower()
    return f"{started_at.strftime('%Y%m%dT%H%M%SZ')}_{safe_model}_think-{think_label}.json"


def build_header(
    args: argparse.Namespace, temperature: float, num_ctx: int, started_at: datetime
) -> dict[str, Any]:
    return {
        "model": args.model,
        "think": args.think,
        "temperature": temperature,
        "num_ctx": num_ctx,
        "runs": args.runs,
        "label": args.label,
        "started_at": started_at.isoformat(),
    }


def write_results(path: Path, header: dict[str, Any], cases: list[dict[str, Any]]) -> None:
    """Write the whole file through a temporary one so a crash never leaves it half written."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps({**header, "cases": cases}, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    temporary.replace(path)


def progress_line(record: dict[str, Any]) -> str:
    label = f"{record['case_id']} run {record['run']}"
    if record["error"]:
        return f"{label}: ERROR {record['error']}"
    scores = record["scores"]
    task = "-" if scores["task"] is None else f"{scores['task']:.2f}"
    return (
        f"{label}: task={task} tool={scores['tool']:.2f} grounding={scores['grounding']:.2f} "
        f"{record['cost']['seconds']:.1f}s"
    )


# --- real wiring ----------------------------------------------------------------------------


def main(argv: Sequence[str] | None = None) -> int:
    from sqlalchemy import delete
    from sqlalchemy.orm import Session

    from app.adapters.llm.ollama_chat import OllamaChat
    from app.adapters.llm.ollama_embeddings import OllamaEmbeddings
    from app.adapters.persistence.cart_repository import SqlAlchemyCartRepository
    from app.adapters.persistence.catalog_repository import SqlAlchemyCatalogRepository
    from app.adapters.persistence.orm.purchase import Cart as CartRow
    from app.adapters.persistence.semantic_search_repository import SqlAlchemySemanticSearch
    from app.adapters.persistence.session import get_session_factory
    from app.application.agent.cart_tools import build_cart_tools
    from app.application.agent.catalog_tools import build_catalog_tools
    from app.application.agent.dispatcher import ToolDispatcher
    from app.application.agent.loop import AgentLoop
    from app.application.agent.registry import ToolRegistry
    from app.application.cart import add_item, view_cart
    from app.config import get_settings

    args = parse_args(argv)
    cases = select_cases(args.cases, args.hard_only)
    settings = get_settings()
    session_factory = get_session_factory()

    with session_factory() as session:
        wanted = required_product_ids(cases)
        found = {
            s.product_id for s in SqlAlchemyCatalogRepository(session).get_summaries(sorted(wanted))
        }
    if wanted - found:
        raise SystemExit(f"Products missing from the catalog: {', '.join(sorted(wanted - found))}")

    chat = OllamaChat(
        settings.ollama_base_url,
        args.model,
        settings.llm_timeout_seconds,
        temperature=settings.llm_temperature,
        num_ctx=settings.llm_num_ctx,
        think=args.think,
    )
    embedder = OllamaEmbeddings(
        settings.ollama_base_url, settings.embedding_model, settings.embedding_timeout_seconds
    )

    class SqlCart:
        def __init__(self, session: Session, repository: SqlAlchemyCartRepository) -> None:
            self._session = session
            self._repository = repository

        def add(self, session_id: str, product_id: str, quantity: int) -> None:
            add_item(self._repository, session_id, product_id, quantity)

        def quantities(self, session_id: str) -> dict[str, int]:
            lines = view_cart(self._repository, session_id).items
            return {line.product_id: line.quantity for line in lines}

        def clear(self, session_id: str) -> None:
            self._repository.clear(session_id)
            # clear() empties the items; the cart row of an eval session must not stay either.
            self._session.execute(delete(CartRow).where(CartRow.session_id == session_id))
            self._session.commit()

    started_at = datetime.now(UTC)
    header = build_header(args, settings.llm_temperature, settings.llm_num_ctx, started_at)
    path = args.out_dir / result_file_name(args.model, args.think, started_at)
    results: list[dict[str, Any]] = []
    try:
        for case in cases:
            entry: dict[str, Any] = {
                "case_id": case.case_id,
                "kind": case.kind,
                "hard": case.hard,
                "runs": [],
            }
            results.append(entry)
            for run_index in range(1, args.runs + 1):
                session_id = f"eval-{uuid.uuid4().hex[:12]}"
                with session_factory() as session:
                    cart_repository = SqlAlchemyCartRepository(session)
                    tools = build_catalog_tools(
                        SqlAlchemyCatalogRepository(session),
                        embedder,
                        SqlAlchemySemanticSearch(session),
                        settings.search_min_similarity,
                    ) + build_cart_tools(cart_repository)
                    registry = ToolRegistry(tools)
                    loop = AgentLoop(
                        chat,
                        ToolDispatcher(registry),
                        registry.specs(),
                        settings.agent_max_steps,
                        settings.agent_history_messages,
                        settings.agent_turn_timeout_seconds,
                    )
                    record = execute_run(
                        case, run_index, loop, SqlCart(session, cart_repository), session_id
                    )
                entry["runs"].append(record)
                print(progress_line(record), flush=True)
            write_results(path, header, results)
    except ModelUnavailable as error:
        write_results(path, header, results)
        print(f"Aborted: {error}. Partial results: {path}")
        return 2
    finally:
        chat.close()
    print(f"Results: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
