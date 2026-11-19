"""Pure domain objects of the agent loop: messages, model replies and explicit state."""

from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

GOAL_MAX_CHARS = 300


class Role(StrEnum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass(frozen=True)
class ToolCall:
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class ChatMessage:
    role: Role
    content: str = ""
    tool_calls: tuple[ToolCall, ...] = ()
    tool_name: str | None = None  # set for TOOL messages: the tool that produced the result

    @classmethod
    def system(cls, text: str) -> "ChatMessage":
        return cls(Role.SYSTEM, text)

    @classmethod
    def user(cls, text: str) -> "ChatMessage":
        return cls(Role.USER, text)

    @classmethod
    def assistant(cls, text: str, tool_calls: tuple[ToolCall, ...] = ()) -> "ChatMessage":
        return cls(Role.ASSISTANT, text, tool_calls)

    @classmethod
    def tool(cls, tool_name: str, content: str) -> "ChatMessage":
        return cls(Role.TOOL, content, tool_name=tool_name)


@dataclass(frozen=True)
class ModelReply:
    content: str
    tool_calls: tuple[ToolCall, ...]
    prompt_tokens: int = 0
    completion_tokens: int = 0


class LLMUnavailable(Exception):
    """The model cannot answer: connection, timeout, HTTP error or malformed reply."""


class StopReason(StrEnum):
    ANSWER = "answer"
    MAX_STEPS = "max_steps"
    LLM_UNAVAILABLE = "llm_unavailable"
    INVALID_TOOL_CALLS = "invalid_tool_calls"
    UNGROUNDED_ANSWER = "ungrounded_answer"
    INVALID_ANSWER = "invalid_answer"  # final reply not valid JSON for the schema after a retry


@dataclass(frozen=True)
class ShownProduct:
    product_id: str
    name: str


@dataclass(frozen=True)
class ToolUse:
    name: str
    ok: bool
    step: int


@dataclass
class AgentState:
    """Explicit state of one conversation, kept apart from the message history."""

    goal: str = ""
    shown_products: list[ShownProduct] = field(default_factory=list)
    tools_used: list[ToolUse] = field(default_factory=list)
    step: int = 0
    # The last answer asked a clarifying question, so the next message completes the goal.
    awaiting_clarification: bool = False

    def record_products(self, products: Iterable[ShownProduct]) -> None:
        known = {product.product_id for product in self.shown_products}
        for product in products:
            if product.product_id not in known:
                known.add(product.product_id)
                self.shown_products.append(product)

    def record_tool(self, name: str, ok: bool) -> None:
        self.tools_used.append(ToolUse(name, ok, self.step))

    def set_goal(self, text: str) -> None:
        cleaned = text.strip()
        if cleaned:
            self.goal = cleaned[:GOAL_MAX_CHARS]

    def to_dict(self) -> dict[str, Any]:
        """JSON-serializable form, to keep the state between turns of a conversation."""
        return {
            "goal": self.goal,
            "shown_products": [
                {"product_id": p.product_id, "name": p.name} for p in self.shown_products
            ],
            "tools_used": [
                {"name": use.name, "ok": use.ok, "step": use.step} for use in self.tools_used
            ],
            "step": self.step,
            "awaiting_clarification": self.awaiting_clarification,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentState":
        """Rebuild a state from `to_dict`; missing keys fall back to the defaults."""
        return cls(
            goal=data.get("goal", ""),
            shown_products=[
                ShownProduct(p.get("product_id", ""), p.get("name", ""))
                for p in data.get("shown_products", [])
            ],
            tools_used=[
                ToolUse(use.get("name", ""), bool(use.get("ok", False)), use.get("step", 0))
                for use in data.get("tools_used", [])
            ],
            step=data.get("step", 0),
            awaiting_clarification=bool(data.get("awaiting_clarification", False)),
        )

    def describe(self) -> str:
        """English text for the model prompt. The numbering lets 'the first one' be resolved."""
        goal = self.goal or "not stated yet"
        if self.shown_products:
            items = "; ".join(
                f"{position}. {product.product_id} - {product.name}"
                for position, product in enumerate(self.shown_products, start=1)
            )
            products = f"Products already shown to the customer, in order: {items}"
        else:
            products = "No products shown yet"
        tools = ", ".join(use.name for use in self.tools_used) or "none"
        return f"Goal: {goal}\n{products}\nTools used so far: {tools}\nStep: {self.step}"
