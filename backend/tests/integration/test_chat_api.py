"""Chat endpoints against PostgreSQL with a scripted model and a fake embedder."""

import json
import time
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.adapters.api import chat as chat_module
from app.adapters.api.chat import get_chat_model, get_embedding_model
from app.adapters.persistence.orm.catalog import Brand, Category, Product, ProductEmbedding
from app.adapters.persistence.orm.conversation import Message
from app.adapters.persistence.orm.stock import Inventory, Price, Warehouse
from app.domain.agent import ChatMessage, LLMUnavailable, ModelReply, ToolCall
from app.main import app

pytestmark = pytest.mark.integration

HEADERS = {"X-Session-Id": "session-a"}
OTHER = {"X-Session-Id": "session-b"}
INDEX_ID = "fake-index"


class ScriptedModel:
    """Returns the scripted replies in order; an exception in the script is raised."""

    def __init__(self, *replies, delay: float = 0.0):
        self.replies = list(replies)
        self.calls: list[list[ChatMessage]] = []
        self.delay = delay
        self.closed_at_call: list[bool] = []
        self.closed = False

    def chat(self, messages, tools, response_schema=None):
        self.closed_at_call.append(self.closed)
        self.calls.append(list(messages))
        if self.delay:
            time.sleep(self.delay)
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


class FakeEmbedder:
    index_id = INDEX_ID

    def embed_documents(self, texts):
        return [self.embed_query(t) for t in texts]

    def embed_query(self, text):
        return [1.0] + [0.0] * 767


def text_reply(text="ok"):
    return ModelReply(text, (), prompt_tokens=10, completion_tokens=2)


def tool_reply(name, **arguments):
    return ModelReply("", (ToolCall(name, arguments),), prompt_tokens=10, completion_tokens=2)


def final(**fields):
    fields.setdefault("reply", "Respuesta")
    return ModelReply(json.dumps(fields), (), prompt_tokens=20, completion_tokens=5)


def plain_turn(reply: str) -> list[ModelReply]:
    return [text_reply("done"), final(reply=reply)]


def search_turn(reply: str) -> list[ModelReply]:
    return [
        tool_reply("search_products", query="gaming monitor", max_price=150),
        text_reply("done"),
        final(reply=reply, recommendations=[{"product_id": "MN-001", "reason": "Buen precio"}]),
    ]


@pytest.fixture(autouse=True)
def catalog_data(db_session: Session) -> None:
    """MN-001: Vision 24, 100.00 USD, 8 units, with image. MN-002: Office 27, 19.99, 7 units."""
    db_session.add_all(
        [
            Brand(brand_id="B1", brand_name="Flux"),
            Category(
                subcategory_id="SC-GAM",
                subcategory_name="Gaming",
                category_id="C-MON",
                category_name="Monitors",
            ),
            Warehouse(warehouse_id="W1", warehouse_name="Centro"),
        ]
    )
    db_session.flush()
    for pid, name, current, qty, image in [
        ("MN-001", "Vision 24", "100.00", 8, "https://example.com/1.png"),
        ("MN-002", "Office 27", "19.99", 7, None),
    ]:
        db_session.add(
            Product(
                product_id=pid,
                sku=f"SKU-{pid}",
                name=name,
                brand_id="B1",
                subcategory_id="SC-GAM",
                category_name="Monitors",
                subcategory_name="Gaming",
                image_url=image,
            )
        )
        db_session.flush()
        db_session.add_all(
            [
                Price(
                    product_id=pid,
                    currency="USD",
                    list_price=current,
                    current_price=current,
                    discount_percent=0,
                ),
                Inventory(
                    product_id=pid, warehouse_id="W1", on_hand_qty=qty, available_qty=qty
                ),
                ProductEmbedding(
                    product_id=pid,
                    content=name,
                    embedding=[1.0] + [0.0] * 767,
                    model=INDEX_ID,
                ),
            ]
        )
    db_session.flush()


@pytest.fixture(autouse=True)
def no_token_delay(monkeypatch) -> None:
    monkeypatch.setattr(chat_module, "TOKEN_DELAY_SECONDS", 0)


@pytest.fixture
def use_model(client: TestClient):
    """Install a scripted model for the chat endpoints; overrides are cleared by ``client``."""

    def install(model: ScriptedModel) -> ScriptedModel:
        def provide() -> Iterator[ScriptedModel]:
            try:
                yield model
            finally:
                model.closed = True

        app.dependency_overrides[get_chat_model] = provide
        app.dependency_overrides[get_embedding_model] = lambda: FakeEmbedder()
        return model

    return install


def post(client, message="Hola", conversation_id=None, headers=HEADERS, path="/api/chat", **extra):
    body = {"message": message, "conversation_id": conversation_id, **extra}
    return client.post(path, json=body, headers=headers)


def parse_sse(text: str) -> list[tuple[str, dict]]:
    events = []
    for frame in text.strip().split("\n\n"):
        event_line, data_line = frame.split("\n")
        events.append(
            (event_line.removeprefix("event: "), json.loads(data_line.removeprefix("data: ")))
        )
    return events


def message_count(db_session: Session) -> int:
    return db_session.scalar(select(func.count()).select_from(Message))


def test_plain_reply_is_returned_and_persisted(client, use_model, db_session):
    use_model(ScriptedModel(*plain_turn("Hola, ¿en qué te ayudo?")))

    response = post(client, "Hola")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["reply"] == "Hola, ¿en qué te ayudo?"
    assert body["blocks"] == []
    assert body["tools_used"] == []
    assert body["conversation_id"]
    assert message_count(db_session) == 2


def test_second_message_sees_the_history_and_get_returns_four_messages(client, use_model):
    model = use_model(ScriptedModel(*plain_turn("Primera"), *plain_turn("Segunda")))
    first = post(client, "Uno").json()

    second = post(client, "Dos", first["conversation_id"])

    assert second.status_code == 200, second.text
    assert second.json()["conversation_id"] == first["conversation_id"]
    seen = [m.content for call in model.calls[2:] for m in call]
    assert "Uno" in seen
    assert "Primera" in seen
    stored = client.get(f"/api/chat/{first['conversation_id']}", headers=HEADERS)
    assert stored.status_code == 200
    messages = stored.json()["messages"]
    assert [(m["role"], m["content"]) for m in messages] == [
        ("user", "Uno"),
        ("assistant", "Primera"),
        ("user", "Dos"),
        ("assistant", "Segunda"),
    ]
    assert all(m["created_at"] for m in messages)
    assert stored.json()["conversation_id"] == first["conversation_id"]


def test_recommendation_block_is_enriched_but_price_and_stock_come_from_the_tool(
    client, use_model
):
    use_model(ScriptedModel(*search_turn("Te recomiendo el Vision 24.")))

    response = post(client, "Quiero un monitor gamer de hasta 150 dólares")

    assert response.status_code == 200, response.text
    body = response.json()
    assert [t["name"] for t in body["tools_used"]] == ["search_products"]
    assert body["tools_used"][0]["args"]["query"] == "gaming monitor"
    [block] = body["blocks"]
    assert block["type"] == "product_recommendations"
    product = block["items"][0]["product"]
    assert product["product_id"] == "MN-001"
    assert product["sku"] == "SKU-MN-001"
    assert product["image_url"] == "https://example.com/1.png"
    assert product["price"]["current"] == 100.0
    assert product["available_qty"] == 8


def test_another_session_cannot_read_or_continue_the_conversation(client, use_model):
    use_model(ScriptedModel(*plain_turn("Hola")))
    conversation_id = post(client).json()["conversation_id"]

    read = client.get(f"/api/chat/{conversation_id}", headers=OTHER)
    continued = post(client, "Hola otra vez", conversation_id, headers=OTHER)

    assert read.status_code == 404
    assert read.json()["error"]["code"] == "CONVERSATION_NOT_FOUND"
    assert continued.status_code == 404
    assert continued.json()["error"]["code"] == "CONVERSATION_NOT_FOUND"


def test_unknown_conversation_is_404(client):
    response = client.get("/api/chat/not-a-uuid", headers=HEADERS)
    assert response.status_code == 404
    assert response.json()["error"]["message"] == "La conversación no existe."


def test_missing_session_header_is_400(client, use_model):
    use_model(ScriptedModel())
    response = client.post("/api/chat", json={"message": "Hola"})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "MISSING_SESSION"
    stream = client.post("/api/chat/stream", json={"message": "Hola"})
    assert stream.status_code == 400
    assert client.get("/api/chat/abc").status_code == 400


@pytest.mark.parametrize("message", ["", "   \n "])
def test_blank_message_is_400(client, use_model, message):
    use_model(ScriptedModel())
    response = post(client, message)
    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert error["details"]["errors"][0]["field"] == "message"


def test_invalid_input_mode_is_400(client, use_model):
    use_model(ScriptedModel())
    response = post(client, "Hola", input_mode="telepathy")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_voice_input_mode_is_accepted(client, use_model):
    use_model(ScriptedModel(*plain_turn("Hola")))
    assert post(client, "Hola", input_mode="voice").status_code == 200


def test_model_unavailable_is_503_and_nothing_is_persisted(client, use_model, db_session):
    use_model(ScriptedModel(LLMUnavailable("down")))

    response = post(client)

    assert response.status_code == 503
    error = response.json()["error"]
    assert error["code"] == "LLM_UNAVAILABLE"
    assert error["message"].startswith("El asistente no está disponible")
    assert message_count(db_session) == 0


def test_stream_sends_events_in_order(client, use_model):
    reply_text = "Te recomiendo el Vision 24 porque es ideal para jugar."
    use_model(ScriptedModel(*search_turn(reply_text)))

    response = post(
        client, "Quiero un monitor gamer de hasta 150 dólares", path="/api/chat/stream"
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["cache-control"] == "no-cache"
    assert response.headers["x-accel-buffering"] == "no"
    events = parse_sse(response.text)
    names = [name for name, _ in events]
    assert names[0] == "meta"
    assert names[1] == "tool_call"
    assert names[-1] == "done"
    assert names[-2] == "block"
    tokens = [data["text"] for name, data in events if name == "token"]
    assert len(tokens) > 1
    assert names[2 : 2 + len(tokens)] == ["token"] * len(tokens)
    done = events[-1][1]
    assert "".join(tokens) == done["reply"] == reply_text
    assert done["tools_used"][0]["name"] == "search_products"
    assert events[1][1]["name"] == "search_products"
    assert events[1][1]["args"]["max_price"] == 150
    assert events[-2][1]["type"] == "product_recommendations"
    conversation_id = events[0][1]["conversation_id"]
    stored = client.get(f"/api/chat/{conversation_id}", headers=HEADERS)
    assert len(stored.json()["messages"]) == 2


def test_stream_with_model_unavailable_ends_with_an_error_event(client, use_model):
    use_model(ScriptedModel(LLMUnavailable("down")))

    response = post(client, path="/api/chat/stream")

    assert response.status_code == 200
    events = parse_sse(response.text)
    assert [name for name, _ in events] == ["meta", "error"]
    assert events[-1][1]["error"]["code"] == "LLM_UNAVAILABLE"


def test_stream_with_unknown_conversation_ends_with_an_error_event(client, use_model):
    use_model(ScriptedModel())
    response = post(client, conversation_id="not-a-uuid", path="/api/chat/stream")
    assert [name for name, _ in parse_sse(response.text)] == ["error"]
    assert parse_sse(response.text)[0][1]["error"]["code"] == "CONVERSATION_NOT_FOUND"


def test_stream_internal_failure_hides_the_exception_text(client, use_model):
    use_model(ScriptedModel(RuntimeError("secret detail")))

    response = post(client, path="/api/chat/stream")

    assert "secret detail" not in response.text
    events = parse_sse(response.text)
    assert events[-1][0] == "error"
    assert events[-1][1]["error"]["code"] == "INTERNAL_ERROR"


def test_model_is_still_open_while_the_stream_worker_uses_it(client, use_model):
    model = use_model(ScriptedModel(*plain_turn("Hola"), delay=0.1))

    response = post(client, path="/api/chat/stream")

    assert parse_sse(response.text)[-1][0] == "done"
    assert model.closed_at_call == [False, False]
    assert model.closed is True
