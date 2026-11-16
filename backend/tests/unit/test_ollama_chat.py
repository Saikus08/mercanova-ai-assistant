"""Ollama chat adapter against a mocked HTTP transport (no network)."""

import json

import httpx
import pytest

from app.adapters.llm.ollama_chat import OllamaChat
from app.application.agent.tool import ToolSpec
from app.domain.agent import ChatMessage, LLMUnavailable, ToolCall

SECRET_PROMPT = "my secret prompt text"

SEARCH_SPEC = ToolSpec(
    "search_products",
    "Search the catalog.",
    {"type": "object", "properties": {"query": {"type": "string"}}},
)


def adapter(handler, **kwargs) -> OllamaChat:
    return OllamaChat(
        "http://ollama:11434",
        "qwen3:8b",
        timeout_seconds=5,
        transport=httpx.MockTransport(handler),
        **kwargs,
    )


def reply_with(message: dict, **extra) -> httpx.Response:
    return httpx.Response(200, json={"message": message, **extra})


def capture(response: httpx.Response | None = None):
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return response or reply_with({"role": "assistant", "content": "ok"})

    return requests, handler


def sent_body(requests: list[httpx.Request]) -> dict:
    return json.loads(requests[0].content)


def test_plain_chat_posts_the_expected_body():
    requests, handler = capture()

    reply = adapter(handler).chat([ChatMessage.user("hi")], [])

    assert reply.content == "ok"
    assert requests[0].url == "http://ollama:11434/api/chat"
    assert sent_body(requests) == {
        "model": "qwen3:8b",
        "messages": [{"role": "user", "content": "hi"}],
        "stream": False,
        "options": {"temperature": 0.1, "num_ctx": 8192},
    }


def test_options_carry_the_configured_temperature_and_context():
    requests, handler = capture()

    adapter(handler, temperature=0.3, num_ctx=4096).chat([ChatMessage.user("hi")], [])

    assert sent_body(requests)["options"] == {"temperature": 0.3, "num_ctx": 4096}


def test_think_is_absent_by_default_and_sent_when_set():
    requests, handler = capture()
    adapter(handler).chat([ChatMessage.user("hi")], [])
    assert "think" not in sent_body(requests)

    requests, handler = capture()
    adapter(handler, think=False).chat([ChatMessage.user("hi")], [])
    assert sent_body(requests)["think"] is False


def test_tools_are_mapped_to_the_function_wire_format_without_format():
    requests, handler = capture()

    adapter(handler).chat([ChatMessage.user("hi")], [SEARCH_SPEC])

    body = sent_body(requests)
    assert body["tools"] == [
        {
            "type": "function",
            "function": {
                "name": "search_products",
                "description": "Search the catalog.",
                "parameters": SEARCH_SPEC.parameters,
            },
        }
    ]
    assert "format" not in body


def test_schema_sends_format_and_no_tools():
    requests, handler = capture()
    schema = {"type": "object", "properties": {"ok": {"type": "boolean"}}}

    adapter(handler).chat([ChatMessage.user("hi")], [SEARCH_SPEC], response_schema=schema)

    body = sent_body(requests)
    assert body["format"] == schema
    assert "tools" not in body


def test_messages_are_mapped_by_role():
    requests, handler = capture()
    messages = [
        ChatMessage.system("rules"),
        ChatMessage.user("a laptop"),
        ChatMessage.assistant("", tool_calls=(ToolCall("search_products", {"query": "laptop"}),)),
        ChatMessage.tool("search_products", '{"items": []}'),
        ChatMessage.assistant("Nothing found."),
    ]

    adapter(handler).chat(messages, [])

    assert sent_body(requests)["messages"] == [
        {"role": "system", "content": "rules"},
        {"role": "user", "content": "a laptop"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {"function": {"name": "search_products", "arguments": {"query": "laptop"}}}
            ],
        },
        {"role": "tool", "tool_name": "search_products", "content": '{"items": []}'},
        {"role": "assistant", "content": "Nothing found."},
    ]


def test_reply_parses_content_tokens_and_ignores_thinking():
    _, handler = capture(
        reply_with(
            {"role": "assistant", "content": "Hello", "thinking": "private reasoning"},
            prompt_eval_count=12,
            eval_count=5,
        )
    )

    reply = adapter(handler).chat([ChatMessage.user("hi")], [])

    assert reply.content == "Hello"
    assert reply.tool_calls == ()
    assert (reply.prompt_tokens, reply.completion_tokens) == (12, 5)


def test_missing_content_and_counts_default():
    _, handler = capture(reply_with({"role": "assistant"}))

    reply = adapter(handler).chat([ChatMessage.user("hi")], [])

    assert reply.content == ""
    assert (reply.prompt_tokens, reply.completion_tokens) == (0, 0)


def test_tool_calls_accept_dict_and_json_string_arguments():
    _, handler = capture(
        reply_with(
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {"function": {"name": "get_price", "arguments": {"product_id": "P1"}}},
                    {"function": {"name": "get_stock", "arguments": '{"product_id": "P2"}'}},
                ],
            }
        )
    )

    reply = adapter(handler).chat([ChatMessage.user("hi")], [SEARCH_SPEC])

    assert reply.tool_calls == (
        ToolCall("get_price", {"product_id": "P1"}),
        ToolCall("get_stock", {"product_id": "P2"}),
    )


@pytest.mark.parametrize(
    "tool_calls",
    [
        "not a list",
        [{"function": {"arguments": {}}}],
        [{"function": {"name": 3, "arguments": {}}}],
        [{"function": {"name": "a", "arguments": 5}}],
        [{"function": {"name": "a", "arguments": "not json"}}],
        [{"function": {"name": "a", "arguments": "[1, 2]"}}],
        [{"function": {"name": "a"}}],
        [{"name": "a"}],
        ["a"],
    ],
)
def test_malformed_tool_calls_raise_unavailable(tool_calls):
    _, handler = capture(reply_with({"role": "assistant", "content": "", "tool_calls": tool_calls}))

    with pytest.raises(LLMUnavailable):
        adapter(handler).chat([ChatMessage.user("hi")], [SEARCH_SPEC])


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, json={"done": True}),
        httpx.Response(200, json=["not", "an", "object"]),
        httpx.Response(200, json={"message": "text"}),
        httpx.Response(200, json={"message": {"content": 5}}),
        httpx.Response(200, json={"message": {"content": "x"}, "eval_count": "many"}),
        httpx.Response(200, content=b"<html>not json</html>"),
        httpx.Response(500, text="boom"),
    ],
    ids=[
        "message-missing",
        "body-not-object",
        "message-not-dict",
        "content-not-str",
        "count-not-int",
        "non-json",
        "http-500",
    ],
)
def test_bad_answers_raise_unavailable(response):
    _, handler = capture(response)

    with pytest.raises(LLMUnavailable):
        adapter(handler).chat([ChatMessage.user("hi")], [])


def test_timeout_and_connection_errors_raise_unavailable():
    def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    def refused(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    with pytest.raises(LLMUnavailable, match="timed out"):
        adapter(timeout).chat([ChatMessage.user("hi")], [])
    with pytest.raises(LLMUnavailable):
        adapter(refused).chat([ChatMessage.user("hi")], [])


def test_error_messages_never_include_the_prompt():
    def failing(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    def malformed(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"nope")

    for handler in (failing, malformed):
        with pytest.raises(LLMUnavailable) as caught:
            adapter(handler).chat([ChatMessage.user(SECRET_PROMPT)], [])
        assert SECRET_PROMPT not in str(caught.value)


def test_close_releases_the_http_client():
    chat = adapter(lambda request: reply_with({"content": "ok"}))

    chat.close()

    with pytest.raises(RuntimeError):
        chat.chat([ChatMessage.user("hi")], [])
