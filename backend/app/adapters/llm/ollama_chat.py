"""ChatModel port implemented over the Ollama HTTP API (POST /api/chat)."""

import json
from typing import Any

import httpx

from app.application.agent.tool import ToolSpec
from app.domain.agent import ChatMessage, LLMUnavailable, ModelReply, Role, ToolCall


class OllamaChat:
    def __init__(
        self,
        base_url: str,
        model: str,
        timeout_seconds: float,
        temperature: float = 0.1,
        num_ctx: int = 8192,
        think: bool | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._model = model
        self._temperature = temperature
        self._num_ctx = num_ctx
        self._think = think
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"), timeout=timeout_seconds, transport=transport
        )

    def close(self) -> None:
        self._client.close()

    def chat(
        self,
        messages: list[ChatMessage],
        tools: list[ToolSpec],
        response_schema: dict[str, Any] | None = None,
    ) -> ModelReply:
        body: dict[str, Any] = {
            "model": self._model,
            "messages": [_message_to_wire(message) for message in messages],
            "stream": False,
            "options": {"temperature": self._temperature, "num_ctx": self._num_ctx},
        }
        if response_schema is not None:
            body["format"] = response_schema
        elif tools:
            body["tools"] = [_tool_to_wire(spec) for spec in tools]
        if self._think is not None:
            body["think"] = self._think
        # Error messages never include the request body: it holds the conversation.
        try:
            response = self._client.post("/api/chat", json=body)
            response.raise_for_status()
            answer = response.json()
        except httpx.TimeoutException as error:
            raise LLMUnavailable("The chat request timed out") from error
        except httpx.HTTPStatusError as error:
            raise LLMUnavailable(f"Ollama answered HTTP {error.response.status_code}") from error
        except httpx.HTTPError as error:
            raise LLMUnavailable(f"Could not reach Ollama: {type(error).__name__}") from error
        except ValueError as error:
            raise LLMUnavailable("Ollama answered with a body that is not JSON") from error
        return _parse_reply(answer)


def _message_to_wire(message: ChatMessage) -> dict[str, Any]:
    if message.role is Role.TOOL:
        return {"role": "tool", "tool_name": message.tool_name, "content": message.content}
    wire: dict[str, Any] = {"role": message.role.value, "content": message.content}
    if message.role is Role.ASSISTANT and message.tool_calls:
        wire["tool_calls"] = [
            {"function": {"name": call.name, "arguments": call.arguments}}
            for call in message.tool_calls
        ]
    return wire


def _tool_to_wire(spec: ToolSpec) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": spec.name,
            "description": spec.description,
            "parameters": spec.parameters,
        },
    }


def _count(body: dict[str, Any], key: str) -> int:
    value = body.get(key, 0)
    if not isinstance(value, int) or isinstance(value, bool):
        raise LLMUnavailable(f"Ollama returned a non-integer {key}")
    return value


def _parse_arguments(raw: object) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except ValueError as error:
            raise LLMUnavailable("Ollama returned tool arguments that are not JSON") from error
        if isinstance(parsed, dict):
            return parsed
    raise LLMUnavailable("Ollama returned tool arguments that are not a JSON object")


def _parse_tool_call(item: object) -> ToolCall:
    function = item.get("function") if isinstance(item, dict) else None
    if not isinstance(function, dict):
        raise LLMUnavailable("Ollama returned a tool call without a function")
    name = function.get("name")
    if not isinstance(name, str) or not name:
        raise LLMUnavailable("Ollama returned a tool call without a name")
    return ToolCall(name, _parse_arguments(function.get("arguments")))


def _parse_reply(body: object) -> ModelReply:
    message = body.get("message") if isinstance(body, dict) else None
    if not isinstance(message, dict) or not isinstance(body, dict):
        raise LLMUnavailable("Ollama response has no message")
    content = message.get("content", "")
    if not isinstance(content, str):
        raise LLMUnavailable("Ollama returned content that is not text")
    raw_calls = message.get("tool_calls", [])
    if not isinstance(raw_calls, list):
        raise LLMUnavailable("Ollama returned tool_calls that is not a list")
    return ModelReply(
        content=content,
        tool_calls=tuple(_parse_tool_call(item) for item in raw_calls),
        prompt_tokens=_count(body, "prompt_eval_count"),
        completion_tokens=_count(body, "eval_count"),
    )
