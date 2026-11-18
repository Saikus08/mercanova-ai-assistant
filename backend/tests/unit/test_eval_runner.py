"""Runner of the model comparison with fakes: no DB, network or LLM."""

import json
from datetime import UTC, datetime
from typing import Any

import pytest

from app.application.agent.tool import ToolContext
from app.domain.agent import AgentState, ChatMessage, Role, StopReason
from tests.eval.golden_cases import GOLDEN_CASES, SETUPS, GoldenCase, Setup
from tests.eval.runner import (
    ModelUnavailable,
    build_header,
    execute_run,
    parse_args,
    progress_line,
    required_product_ids,
    result_file_name,
    select_cases,
    write_results,
)
from tests.eval.scoring import not_called, reply_includes_any
from tests.unit.test_chat_blocks import turn


class FakeCart:
    def __init__(self) -> None:
        self.lines: dict[str, dict[str, int]] = {}
        self.events: list[str] = []

    def add(self, session_id: str, product_id: str, quantity: int) -> None:
        self.events.append(f"add:{product_id}:{quantity}")
        lines = self.lines.setdefault(session_id, {})
        lines[product_id] = lines.get(product_id, 0) + quantity

    def quantities(self, session_id: str) -> dict[str, int]:
        return dict(self.lines.get(session_id, {}))

    def clear(self, session_id: str) -> None:
        self.events.append("clear")
        self.lines.pop(session_id, None)


class FakeLoop:
    def __init__(self, cart: FakeCart, result: Any = None, raises: Exception | None = None):
        self.cart = cart
        self.result = result if result is not None else turn(reply="Hola")
        self.raises = raises
        self.seen: dict[str, Any] = {}

    def run_turn(self, state, history, user_message, context, on_event=None, trace_id=None):
        self.seen = {
            "goal": state.goal,
            "shown": [(p.product_id, p.name) for p in state.shown_products],
            "history": [(m.role, m.content) for m in history],
            "message": user_message,
            "context": context,
            "cart": self.cart.quantities(context.session_id),
        }
        if self.raises:
            raise self.raises
        return self.result


def make_case(setup: Setup | None = None) -> GoldenCase:
    return GoldenCase(
        "CX",
        "edge",
        "Hola",
        setup or Setup(shown=(), goal="", history=(), cart=()),
        (not_called("add_to_cart"), reply_includes_any("Hola")),
        hard=False,
    )


def ticking_clock(*values: float):
    iterator = iter(values)
    return lambda: next(iterator)


def run(case: GoldenCase, loop: FakeLoop, cart: FakeCart, clock=None) -> dict[str, Any]:
    return execute_run(case, 2, loop, cart, "eval-x", clock=clock or ticking_clock(0.0, 1.5))


def test_execute_run_seeds_state_history_and_cart_before_the_turn():
    cart = FakeCart()
    setup = SETUPS["S3"]
    loop = FakeLoop(cart)

    run(make_case(setup), loop, cart)

    assert loop.seen["goal"] == setup.goal
    assert loop.seen["shown"] == [("MN-MON-0005", "Quanta Vision 27 Full HD IPS")]
    assert [(role, text) for role, text in loop.seen["history"]] == [
        (Role.USER, setup.history[0][1]),
        (Role.ASSISTANT, setup.history[1][1]),
    ]
    assert loop.seen["cart"] == {"MN-MON-0005": 1}
    assert loop.seen["message"] == "Hola"
    assert loop.seen["context"] == ToolContext("eval-x")


def test_execute_run_clears_the_cart_before_seeding_and_after_the_turn():
    cart = FakeCart()
    cart.lines["eval-x"] = {"LEFTOVER": 9}
    loop = FakeLoop(cart)

    record = run(make_case(SETUPS["S3"]), loop, cart)

    assert loop.seen["cart"] == {"MN-MON-0005": 1}
    assert cart.events[0] == "clear"
    assert cart.events[-1] == "clear"
    assert cart.quantities("eval-x") == {}
    assert record["cart_after"] == {"MN-MON-0005": 1}


def test_execute_run_clears_the_cart_when_the_loop_raises():
    cart = FakeCart()
    loop = FakeLoop(cart, raises=RuntimeError("boom"))

    run(make_case(SETUPS["S3"]), loop, cart)

    assert cart.quantities("eval-x") == {}
    assert cart.events[-1] == "clear"


def test_execute_run_raises_model_unavailable_and_clears_the_cart():
    cart = FakeCart()
    loop = FakeLoop(cart, result=turn(stop_reason=StopReason.LLM_UNAVAILABLE, degraded=True))

    with pytest.raises(ModelUnavailable):
        run(make_case(SETUPS["S3"]), loop, cart)

    assert cart.quantities("eval-x") == {}


def test_execute_run_returns_an_error_record_when_the_loop_raises():
    cart = FakeCart()
    record = run(make_case(), FakeLoop(cart, raises=RuntimeError("boom")), cart)

    assert record["case_id"] == "CX"
    assert record["run"] == 2
    assert "boom" in record["error"]
    assert record["scores"] == {"task": None, "tool": None, "grounding": None}
    json.dumps(record)


def test_execute_run_scores_a_successful_run_and_is_json_serializable():
    cart = FakeCart()
    result = turn(
        reply="Hola, ¿qué buscás?",
        steps=3,
        prompt_tokens=100,
        completion_tokens=20,
        fallback_used=True,
        tools_used=[
            {
                "name": "search_products",
                "arguments": {"query": "monitor"},
                "ok": False,
                "duration_ms": 1,
                "result": {"error": "The request is too vague to search", "hint": "ask"},
            }
        ],
    )

    record = run(make_case(), FakeLoop(cart, result=result), cart)

    assert record["error"] is None
    assert record["case_id"] == "CX"
    assert record["kind"] == "edge"
    assert record["run"] == 2
    assert record["scores"]["task"] == 1.0
    assert record["scores"]["tool"] < 1.0  # the blocked search counts as an invalid call
    assert record["conditions"]["not_called:add_to_cart"] is True
    assert record["cost"] == {
        "seconds": 1.5,
        "prompt_tokens": 100,
        "completion_tokens": 20,
        "steps": 3,
    }
    assert record["corrections"] == {
        "fallback_used": True,
        "degraded": False,
        "stop_reason": "answer",
        "failed_tool_calls": 1,
        "invalid_tool_calls": 1,
    }
    assert record["reply"] == "Hola, ¿qué buscás?"
    json.dumps(record)


def test_record_never_contains_tool_results():
    cart = FakeCart()
    result = turn(
        tools_used=[
            {
                "name": "get_price",
                "arguments": {"product_id": "MN-MON-0005"},
                "ok": True,
                "duration_ms": 1,
                "result": {"secret_marker": "RESULT-PAYLOAD"},
            }
        ]
    )

    record = run(make_case(), FakeLoop(cart, result=result), cart)

    assert record["tools"] == [
        {"name": "get_price", "arguments": {"product_id": "MN-MON-0005"}, "ok": True}
    ]
    assert "RESULT-PAYLOAD" not in json.dumps(record)


# --- arguments, selection and files ---------------------------------------------------------


def test_parse_args_defaults():
    args = parse_args(["--model", "qwen3:8b"])

    assert args.model == "qwen3:8b"
    assert args.runs == 3
    assert args.think is None
    assert args.cases is None
    assert args.hard_only is False
    assert args.label is None
    assert str(args.out_dir).endswith("tests/eval/results")


@pytest.mark.parametrize(
    ("value", "expected"), [("true", True), ("false", False), ("default", None)]
)
def test_parse_args_maps_think(value, expected):
    assert parse_args(["--model", "m", "--think", value]).think is expected


def test_parse_args_rejects_an_unknown_think_value():
    with pytest.raises(SystemExit):
        parse_args(["--model", "m", "--think", "maybe"])


def test_parse_args_requires_a_model():
    with pytest.raises(SystemExit):
        parse_args([])


def test_parse_args_splits_the_cases_list_and_takes_runs():
    args = parse_args(["--model", "m", "--cases", "C01, C05", "--runs", "2"])

    assert args.cases == ["C01", "C05"]
    assert args.runs == 2


def test_select_cases_returns_all_by_default():
    assert select_cases(None, hard_only=False) == list(GOLDEN_CASES)


def test_select_cases_filters_by_ids_keeping_dataset_order():
    assert [c.case_id for c in select_cases(["C05", "C01"], hard_only=False)] == ["C01", "C05"]


def test_select_cases_hard_only_keeps_the_hard_cases():
    assert [c.case_id for c in select_cases(None, hard_only=True)] == [
        f"C{n:02d}" for n in range(8, 15)
    ]


def test_select_cases_rejects_unknown_ids():
    with pytest.raises(SystemExit):
        select_cases(["C99"], hard_only=False)


def test_required_product_ids_collects_setups_and_condition_ids():
    cases = [c for c in GOLDEN_CASES if c.case_id in {"C03", "C07"}]

    assert required_product_ids(cases) == {"MN-MON-0005", "MN-MON-0029"}


def test_required_product_ids_is_empty_for_cases_without_products():
    assert required_product_ids([c for c in GOLDEN_CASES if c.case_id == "C02"]) == set()


def test_result_file_name_sanitizes_the_model_and_names_think():
    started = datetime(2026, 5, 17, 14, 30, 5, tzinfo=UTC)

    assert result_file_name("hf.co/org/Qwen3:8b", True, started) == (
        "20260517T143005Z_hf.co-org-Qwen3-8b_think-true.json"
    )
    assert result_file_name("m", None, started) == "20260517T143005Z_m_think-default.json"
    assert result_file_name("m", False, started).endswith("_think-false.json")


def test_agent_state_and_chat_message_types_are_what_the_loop_receives():
    cart = FakeCart()
    captured: dict[str, Any] = {}

    class Spy(FakeLoop):
        def run_turn(self, state, history, user_message, context, **kwargs):
            captured["state"] = state
            captured["history"] = history
            return super().run_turn(state, history, user_message, context)

    run(make_case(SETUPS["S2"]), Spy(cart), cart)

    assert isinstance(captured["state"], AgentState)
    assert all(isinstance(m, ChatMessage) for m in captured["history"])


def test_write_results_writes_header_and_cases_and_refreshes_the_file(tmp_path):
    args = parse_args(["--model", "m", "--label", "smoke"])
    started = datetime(2026, 5, 17, 14, 30, 5, tzinfo=UTC)
    header = build_header(args, 0.1, 8192, started)
    path = tmp_path / "nested" / "out.json"

    write_results(path, header, [{"case_id": "C01", "runs": []}])
    write_results(path, header, [{"case_id": "C01", "runs": []}, {"case_id": "C02", "runs": []}])

    data = json.loads(path.read_text(encoding="utf-8"))
    assert {k: data[k] for k in ("model", "think", "temperature", "num_ctx", "runs", "label")} == {
        "model": "m",
        "think": None,
        "temperature": 0.1,
        "num_ctx": 8192,
        "runs": 3,
        "label": "smoke",
    }
    assert data["started_at"] == "2026-05-17T14:30:05+00:00"
    assert [c["case_id"] for c in data["cases"]] == ["C01", "C02"]
    assert [p.name for p in path.parent.iterdir()] == ["out.json"]


def test_progress_line_shows_scores_and_seconds_or_the_error():
    cart = FakeCart()
    ok = run(make_case(), FakeLoop(cart, result=turn(reply="Hola")), cart)
    failed = run(make_case(), FakeLoop(cart, raises=RuntimeError("boom")), cart)

    assert progress_line(ok) == "CX run 2: task=1.00 tool=1.00 grounding=1.00 1.5s"
    assert progress_line(failed) == "CX run 2: ERROR RuntimeError: boom"
