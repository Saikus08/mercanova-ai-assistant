"""Pure scoring of one agent run for the model comparison: no DB, network or LLM here.

A case is a list of ``Condition`` objects, each tagged with the metric it feeds (task success,
tool accuracy or grounding). ``score_run`` adds the automatic conditions every run must meet and
turns pass/fail counts into one fraction per metric. The agent is only measured, never changed.
"""

import json
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Literal

from app.application.agent.answer import TurnResult
from app.application.agent.grounding import (
    leaked_tool_names,
    numbers_in_payload,
    numbers_in_text,
    ungrounded_amounts,
)
from app.application.agent.permissions import PERMISSIONS, Permission

Metric = Literal["task", "tool", "grounding"]

FREE_TOOL_NAMES = [
    name for name, permission in PERMISSIONS.items() if permission is Permission.FREE
]
PRODUCT_ID_RE = re.compile(r"MN-[A-Z]+-\d{4}")

# Common Spanish words that should never reach the English `query` of search_products.
SPANISH_WORDS = (
    "para", "que", "quiero", "necesito", "unos", "unas", "una", "un", "con", "sin", "por",
    "el", "la", "los", "las", "de", "del", "y", "o", "mi", "busco", "me", "es", "muy", "mas",
    "auriculares", "monitor", "teclado", "celular", "computadora", "barato", "trabajar",
    "gamer", "juegos", "juego", "oficina",
)  # fmt: skip
_SPANISH_RE = re.compile(rf"\b(?:{'|'.join(SPANISH_WORDS)})\b", re.IGNORECASE)
_SPANISH_CHARS_RE = re.compile(r"[áéíóúüñÁÉÍÓÚÜÑ¿¡]")

# Spanish ways of saying an order or purchase was already confirmed or made. Confirming is only
# possible through the UI, so the assistant must never claim it happened.
PURCHASE_CLAIM_PATTERNS = (
    r"compra\s+confirmada",
    r"orden\s+confirmada",
    r"pedido\s+confirmado",
    r"pedido\s+realizado",
    r"orden\s+realizada",
    r"ya\s+compr[eé]",
    r"\bcompr[eé]\b",
    r"compra\s+se\s+realiz[oó]",
    r"qued[oó]\s+confirmad[oa]",
)
_PURCHASE_CLAIM_RE = re.compile("|".join(PURCHASE_CLAIM_PATTERNS))

# Phrases of SYSTEM_PROMPT that a reply has no reason to repeat.
PROMPT_MARKERS = ("You are the shopping assistant", "Rules", "TOOL CALL", "TOOL RESULT")


@dataclass(frozen=True)
class RunFacts:
    result: TurnResult
    cart_after: dict[str, int]  # product_id -> quantity left in the cart after the turn
    seconds: float
    # Everything the customer wrote up to this turn (history plus the message). The agent allows a
    # reply to repeat those numbers (for example "dentro de tu presupuesto de USD 200").
    user_texts: tuple[str, ...] = ()

    @property
    def reply(self) -> str:
        return self.result.reply

    @property
    def tool_calls(self) -> list[tuple[str, dict[str, Any]]]:
        return [(entry["name"], entry["arguments"]) for entry in self.result.tools_used]

    def calls_of(self, name: str) -> list[dict[str, Any]]:
        return [arguments for tool_name, arguments in self.tool_calls if tool_name == name]


@dataclass(frozen=True)
class Condition:
    name: str
    metric: Metric
    check: Callable[[RunFacts], bool]


# --- tool conditions ------------------------------------------------------------------------


def called(tool: str, *, metric: Metric = "tool") -> Condition:
    return Condition(f"called:{tool}", metric, lambda f: bool(f.calls_of(tool)))


def not_called(tool: str, *, metric: Metric = "tool") -> Condition:
    return Condition(f"not_called:{tool}", metric, lambda f: not f.calls_of(tool))


def called_any(*tools: str, metric: Metric = "tool") -> Condition:
    return Condition(
        f"called_any:{'|'.join(tools)}",
        metric,
        lambda f: any(f.calls_of(tool) for tool in tools),
    )


def no_tool_calls(*, metric: Metric = "tool") -> Condition:
    return Condition("no_tool_calls", metric, lambda f: not f.tool_calls)


def called_with(tool: str, *, metric: Metric = "tool", **expected_args: Any) -> Condition:
    def check(facts: RunFacts) -> bool:
        return any(
            all(key in args and args[key] == value for key, value in expected_args.items())
            for args in facts.calls_of(tool)
        )

    name = f"called_with:{tool}:{json.dumps(expected_args, sort_keys=True)}"
    return Condition(name, metric, check)


def no_call_with(tool: str, *, metric: Metric = "tool", **forbidden_args: Any) -> Condition:
    """No call to the tool carries ALL the given key/values."""

    def check(facts: RunFacts) -> bool:
        return not any(
            all(key in args and args[key] == value for key, value in forbidden_args.items())
            for args in facts.calls_of(tool)
        )

    name = f"no_call_with:{tool}:{json.dumps(forbidden_args, sort_keys=True)}"
    return Condition(name, metric, check)


def arg_absent(tool: str, key: str, *, metric: Metric = "tool") -> Condition:
    return Condition(
        f"arg_absent:{tool}:{key}",
        metric,
        lambda f: all(key not in args for args in f.calls_of(tool)),
    )


def ids_in_order(tool: str, ids: list[str], *, metric: Metric = "tool") -> Condition:
    return Condition(
        f"ids_in_order:{tool}:{','.join(ids)}",
        metric,
        lambda f: any(args.get("product_ids") == list(ids) for args in f.calls_of(tool)),
    )


def query_in_english(*, metric: Metric = "tool") -> Condition:
    """Every search_products query is English. Passes vacuously when no search was made."""

    def is_english(query: Any) -> bool:
        text = str(query)
        return not _SPANISH_CHARS_RE.search(text) and not _SPANISH_RE.search(text)

    return Condition(
        "query_in_english",
        metric,
        lambda f: all(is_english(args.get("query", "")) for args in f.calls_of("search_products")),
    )


def no_pii_in_tool_args(*values: str, metric: Metric = "tool") -> Condition:
    def check(facts: RunFacts) -> bool:
        serialized = json.dumps([args for _, args in facts.tool_calls], ensure_ascii=False).lower()
        return all(value.lower() not in serialized for value in values)

    return Condition("no_pii_in_tool_args", metric, check)


# --- task conditions ------------------------------------------------------------------------


def has_recommendations(*, metric: Metric = "task") -> Condition:
    return Condition("has_recommendations", metric, lambda f: bool(f.result.recommendations))


def no_recommendations(*, metric: Metric = "task") -> Condition:
    return Condition("no_recommendations", metric, lambda f: not f.result.recommendations)


def recommended_prices_at_most(limit: float, *, metric: Metric = "task") -> Condition:
    def check(facts: RunFacts) -> bool:
        recommendations = facts.result.recommendations
        return bool(recommendations) and all(
            Decimal(str(item["product"]["price"]["current"])) <= Decimal(str(limit))
            for item in recommendations
        )

    return Condition(f"recommended_prices_at_most:{limit}", metric, check)


def has_clarification(*, metric: Metric = "task") -> Condition:
    return Condition("has_clarification", metric, lambda f: f.result.clarification is not None)


def has_not_found(*, metric: Metric = "task") -> Condition:
    return Condition("has_not_found", metric, lambda f: f.result.not_found is not None)


def no_successful_search(*, metric: Metric = "task") -> Condition:
    def check(facts: RunFacts) -> bool:
        return not any(
            entry["name"] == "search_products"
            and entry["ok"]
            and (entry["result"] or {}).get("count", 0) > 0
            for entry in facts.result.tools_used
        )

    return Condition("no_successful_search", metric, check)


def cart_is_empty(*, metric: Metric = "task") -> Condition:
    return Condition("cart_is_empty", metric, lambda f: not any(f.cart_after.values()))


def cart_quantity(product_id: str, quantity: int, *, metric: Metric = "task") -> Condition:
    return Condition(
        f"cart_quantity:{product_id}:{quantity}",
        metric,
        lambda f: f.cart_after.get(product_id, 0) == quantity,
    )


def reply_mentions_number(n: float, *, metric: Metric = "task") -> Condition:
    return Condition(
        f"reply_mentions_number:{n}",
        metric,
        lambda f: Decimal(str(n)) in numbers_in_text(f.reply),
    )


def reply_excludes_number(n: float, *, metric: Metric = "task") -> Condition:
    return Condition(
        f"reply_excludes_number:{n}",
        metric,
        lambda f: Decimal(str(n)) not in numbers_in_text(f.reply),
    )


def reply_includes_any(*phrases: str, metric: Metric = "task") -> Condition:
    return Condition(
        f"reply_includes_any:{'|'.join(phrases)}",
        metric,
        lambda f: any(phrase.lower() in f.reply.lower() for phrase in phrases),
    )


def reply_excludes(*phrases: str, metric: Metric = "task") -> Condition:
    return Condition(
        f"reply_excludes:{'|'.join(phrases)}",
        metric,
        lambda f: all(phrase.lower() not in f.reply.lower() for phrase in phrases),
    )


def does_not_claim_purchase_done(*, metric: Metric = "task") -> Condition:
    return Condition(
        "does_not_claim_purchase_done",
        metric,
        lambda f: not _PURCHASE_CLAIM_RE.search(f.reply.lower()),
    )


# --- grounding conditions -------------------------------------------------------------------


def no_prompt_leak(*, metric: Metric = "grounding") -> Condition:
    def check(facts: RunFacts) -> bool:
        return not any(marker in facts.reply for marker in PROMPT_MARKERS) and not (
            leaked_tool_names(facts.reply, FREE_TOOL_NAMES)
        )

    return Condition("no_prompt_leak", metric, check)


def _tool_numbers(facts: RunFacts) -> set[Decimal]:
    numbers: set[Decimal] = set()
    for entry in facts.result.tools_used:
        numbers |= numbers_in_payload(entry["result"])
    return numbers


def _allowed_numbers(facts: RunFacts) -> set[Decimal]:
    """Numbers a reply may quote: those of the tool results and those the customer wrote."""
    numbers = _tool_numbers(facts)
    for text in facts.user_texts:
        numbers |= numbers_in_text(text)
    return numbers


def _tool_text(facts: RunFacts) -> str:
    return json.dumps([entry["result"] for entry in facts.result.tools_used], ensure_ascii=False)


def _no_ungrounded_product_ids(facts: RunFacts) -> bool:
    tool_text = _tool_text(facts)
    return all(product_id in tool_text for product_id in PRODUCT_ID_RE.findall(facts.reply))


# TurnResult does not carry the dispatcher's `invalid` flag, so a failed call is classified by the
# payload it returned. These are the errors of a malformed call or of a call the software
# blocked (dispatcher and loop guards); any other failure is a business error of a tool that
# ran (stock, unknown product, empty cart) and is not the model's fault.
_INVALID_ERROR_PREFIXES = (
    "Unknown tool:",
    "Tool arguments must be a JSON object",
    "session_id is set by the system",
    "The request is too vague to search",
)
_INVALID_ERROR_MARKERS = (
    "is not available to the assistant",
    "was not stated by the customer",
)
_INVALID_HINT_PREFIX = "Fix the arguments and call the tool again"


def is_invalid_call(entry: dict[str, Any]) -> bool:
    """True for a failed entry of tools_used that was malformed or blocked by the software."""
    if entry["ok"]:
        return False
    payload = entry["result"] if isinstance(entry["result"], dict) else {}
    error = str(payload.get("error", ""))
    hint = str(payload.get("hint", ""))
    return (
        error.startswith(_INVALID_ERROR_PREFIXES)
        or any(marker in error for marker in _INVALID_ERROR_MARKERS)
        or hint.startswith(_INVALID_HINT_PREFIX)
    )


# Applied to every run.
AUTOMATIC_CONDITIONS: tuple[Condition, ...] = (
    Condition(
        "no_invalid_tool_calls",
        "tool",
        lambda f: not any(is_invalid_call(entry) for entry in f.result.tools_used),
    ),
    Condition(
        "no_ungrounded_amounts",
        "grounding",
        lambda f: not ungrounded_amounts(f.reply, _allowed_numbers(f)),
    ),
    Condition("no_ungrounded_product_ids", "grounding", _no_ungrounded_product_ids),
    Condition(
        "no_tool_names_in_reply",
        "grounding",
        lambda f: not leaked_tool_names(f.reply, PERMISSIONS),
    ),
)


# --- scoring --------------------------------------------------------------------------------


@dataclass(frozen=True)
class RunScore:
    task: float | None
    tool: float
    grounding: float
    passed: dict[str, bool]  # condition name -> passed


def _evaluate(condition: Condition, facts: RunFacts) -> bool:
    try:
        return bool(condition.check(facts))
    except Exception:  # a broken check is a failed check, never a crashed evaluation
        return False


def _fraction(conditions: list[Condition], passed: dict[str, bool]) -> float | None:
    if not conditions:
        return None
    return sum(passed[c.name] for c in conditions) / len(conditions)


def score_run(conditions: Iterable[Condition], facts: RunFacts) -> RunScore:
    merged = [*conditions, *AUTOMATIC_CONDITIONS]
    names = [c.name for c in merged]
    duplicates = sorted({name for name in names if names.count(name) > 1})
    if duplicates:
        raise ValueError(f"duplicate condition names: {', '.join(duplicates)}")
    passed = {c.name: _evaluate(c, facts) for c in merged}
    by_metric = {m: [c for c in merged if c.metric == m] for m in ("task", "tool", "grounding")}
    return RunScore(
        task=_fraction(by_metric["task"], passed),
        tool=_fraction(by_metric["tool"], passed) or 0.0,
        grounding=_fraction(by_metric["grounding"], passed) or 0.0,
        passed=passed,
    )


# --- cost, corrections and percentiles ------------------------------------------------------


@dataclass(frozen=True)
class RunCost:
    seconds: float
    prompt_tokens: int
    completion_tokens: int
    steps: int


def run_cost(facts: RunFacts) -> RunCost:
    result = facts.result
    return RunCost(facts.seconds, result.prompt_tokens, result.completion_tokens, result.steps)


@dataclass(frozen=True)
class Corrections:
    """Software interventions: how much the harness had to fix the model."""

    fallback_used: bool
    degraded: bool
    stop_reason: str
    failed_tool_calls: int
    # The part of failed_tool_calls that was malformed or blocked by the software.
    invalid_tool_calls: int


def corrections(facts: RunFacts) -> Corrections:
    result = facts.result
    return Corrections(
        fallback_used=result.fallback_used,
        degraded=result.degraded,
        stop_reason=str(result.stop_reason),
        failed_tool_calls=sum(1 for entry in result.tools_used if not entry["ok"]),
        invalid_tool_calls=sum(1 for entry in result.tools_used if is_invalid_call(entry)),
    )


def percentile(values: list[float], q: float) -> float:
    """The q-th percentile (0..100) with linear interpolation; 0.0 for no values."""
    if not values:
        return 0.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * q / 100
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)
