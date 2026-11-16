"""Runs one tool call proposed by the model after the harness checks it.

Every failure comes back as ``{"error": ..., "hint": ...}`` for the model to act on; dispatch
never raises.
"""

import json
import logging
import time
from dataclasses import dataclass
from difflib import get_close_matches
from typing import Any

from pydantic import ValidationError

from app.application.agent.permissions import PERMISSIONS, Permission
from app.application.agent.registry import ToolRegistry
from app.application.agent.tool import Tool, ToolContext, ToolDataUnavailable
from app.domain.catalog import InvalidComparison, ProductNotFound
from app.domain.search import SearchUnavailable

logger = logging.getLogger(__name__)

MAX_REPORTED_PROBLEMS = 3


@dataclass(frozen=True)
class ToolResult:
    tool: str
    ok: bool
    payload: dict[str, Any]
    duration_ms: float


def _failure(error: str, hint: str, **extra: Any) -> dict[str, Any]:
    return {"error": error, "hint": hint, **extra}


class ToolDispatcher:
    def __init__(self, registry: ToolRegistry) -> None:
        self._registry = registry

    def dispatch(self, name: str, arguments: object, context: ToolContext) -> ToolResult:
        started = time.perf_counter()
        ok, payload = self._run(name, arguments, context)
        return ToolResult(name, ok, payload, (time.perf_counter() - started) * 1000)

    def _run(
        self, name: str, arguments: object, context: ToolContext
    ) -> tuple[bool, dict[str, Any]]:
        parsed = _as_object(arguments)
        if parsed is None:
            return False, _failure(
                "Tool arguments must be a JSON object",
                "Send the arguments as a JSON object with the fields of the tool schema",
            )
        if PERMISSIONS.get(name) is Permission.FORBIDDEN:
            return False, _failure(
                f"Tool {name} is not available to the assistant",
                "Purchases are confirmed or cancelled only by the user in the interface; "
                "tell the user to use the buttons there",
            )
        tool = self._registry.get(name)
        if tool is None:
            return False, self._unknown(name)
        if "session_id" in parsed:
            return False, _failure(
                "session_id is set by the system", "Remove session_id from the arguments"
            )
        try:
            args = tool.args_model.model_validate(parsed)
        except ValidationError as error:
            return False, _invalid_arguments(tool, error)
        return self._execute(tool, args, context)

    def _unknown(self, name: str) -> dict[str, Any]:
        names = self._registry.names()
        hint = f"Available tools: {', '.join(names)}"
        close = get_close_matches(name, names, n=1)
        if close:
            hint += f". Did you mean {close[0]}?"
        return _failure(f"Unknown tool: {name}", hint)

    def _execute(
        self, tool: Tool, args: Any, context: ToolContext
    ) -> tuple[bool, dict[str, Any]]:
        try:
            return True, tool.handler(args, context)
        except ProductNotFound as error:
            return False, _failure(str(error), "Use search_products to find valid product ids")
        except InvalidComparison as error:
            return False, _failure(
                str(error),
                "Call compare_products again to compare between 2 and 4 different products",
            )
        except SearchUnavailable:
            return False, _failure(
                "Product search is unavailable",
                "The product search is temporarily unavailable; "
                "tell the user and do not invent results",
                retryable=True,
            )
        except ToolDataUnavailable as error:
            return False, _failure(
                str(error), "Tell the user this information is not available; do not guess it"
            )
        except ValueError as error:
            return False, _failure(str(error), "Fix the arguments and call the tool again")
        except Exception:
            logger.exception("Tool %s failed unexpectedly", tool.name)
            return False, _failure(
                "Unexpected tool failure",
                "Do not retry with the same arguments; "
                "tell the user you could not complete this step",
            )


def _as_object(arguments: object) -> dict[str, Any] | None:
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except ValueError:
            return None
    return arguments if isinstance(arguments, dict) else None


def _invalid_arguments(tool: Tool, error: ValidationError) -> dict[str, Any]:
    # Only field names and messages: the raw values may hold personal data.
    problems = [
        f"{'.'.join(str(part) for part in item['loc']) or 'arguments'}: "
        f"{item['msg'].removeprefix('Value error, ')}"
        for item in error.errors(include_input=False, include_url=False)[:MAX_REPORTED_PROBLEMS]
    ]
    schema = json.dumps(tool.parameters_schema(), separators=(",", ":"))
    return _failure(
        "; ".join(problems),
        f"Fix the arguments and call the tool again. Expected schema: {schema}",
    )
