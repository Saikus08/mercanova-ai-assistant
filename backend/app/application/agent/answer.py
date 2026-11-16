"""Structured final answer the model must produce, and the result of one chat turn."""

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.domain.agent import StopReason

MAX_RECOMMENDATIONS = 3
MIN_OPTIONS = 2
MAX_OPTIONS = 4


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Recommendation(_Strict):
    product_id: str = Field(description="Id of a product returned by a tool in this turn")
    reason: str = Field(description="Why it fits the customer, based on catalog data")


class Clarification(_Strict):
    question: str
    options: list[str] = Field(min_length=MIN_OPTIONS, max_length=MAX_OPTIONS)


class FinalAnswer(_Strict):
    reply: str = Field(description="Message for the customer, in Spanish")
    recommendations: list[Recommendation] = Field(default=[], max_length=MAX_RECOMMENDATIONS)
    clarification: Clarification | None = None
    not_found: str | None = Field(
        default=None, description="The searched item when nothing in the catalog matched"
    )


FINAL_ANSWER_SCHEMA: dict[str, Any] = FinalAnswer.model_json_schema()

# Used by the harness when a vague request was blocked and the model still did not ask.
FALLBACK_CLARIFICATION: dict[str, Any] = {
    "question": "¿Para qué lo vas a usar y cuál es tu presupuesto máximo?",
    "options": ["Trabajo", "Juegos", "Estudio", "Uso general"],
}


@dataclass(frozen=True)
class TurnResult:
    reply: str
    recommendations: list[dict[str, Any]]  # {"product": card from a tool result, "reason": str}
    clarification: dict[str, Any] | None
    not_found: str | None
    tools_used: list[dict[str, Any]]  # {"name", "arguments", "ok", "duration_ms", "result"}
    steps: int
    stop_reason: StopReason
    degraded: bool
    prompt_tokens: int
    completion_tokens: int
    trace_id: str
