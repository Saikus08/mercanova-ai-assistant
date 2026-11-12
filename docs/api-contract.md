# API contract (v0, draft)

Contract between `frontend/` and `backend/`. Once both owners approve it, the frontend can build against a mock (MSW) and the backend implements it independently. Changes after approval go through a PR that both review.

- Base URL: `/api` (frontend proxy to `http://backend:8000/api`)
- Format: JSON, `snake_case` fields, money as numbers in **USD** with 2 decimals, dates ISO 8601 UTC.
- Session: no authentication (out of scope). The frontend generates a UUID on first load, stores it in `localStorage` and sends it on every request as header **`X-Session-Id`**. The cart, the conversation and the order history belong to that session.
- Source of truth: `price` and `available_qty` in every response are read from the database at request time (RF-07).

---

## 1. Errors

Every non-2xx response has this shape:

```json
{ "error": { "code": "INSUFFICIENT_STOCK", "message": "Solo hay 7 unidades disponibles.", "details": { "product_id": "MN-MON-0001", "available_qty": 7 } } }
```

`message` is in Spanish and can be shown to the user as is.

| HTTP | code | When |
|---|---|---|
| 400 | `VALIDATION_ERROR` | Invalid body or query params |
| 400 | `MISSING_SESSION` | No `X-Session-Id` header |
| 404 | `PRODUCT_NOT_FOUND` | Unknown product id |
| 404 | `ORDER_NOT_FOUND` | Unknown order or not owned by the session |
| 409 | `INSUFFICIENT_STOCK` | Quantity above availability (cart or confirm) |
| 409 | `PRODUCT_INACTIVE` | Product exists but `active = false` |
| 409 | `CART_EMPTY` | Checkout with an empty cart |
| 409 | `ORDER_NOT_PENDING` | Confirm/cancel an order that is not `pending_confirmation` |
| 410 | `ORDER_DRAFT_EXPIRED` | Draft older than 15 minutes |
| 422 | `AUDIO_UNREADABLE` | Empty or undecodable audio |
| 503 | `LLM_UNAVAILABLE` | Ollama not reachable or timed out |
| 503 | `STT_UNAVAILABLE` | Speech-to-text not available |
| 500 | `INTERNAL_ERROR` | Unexpected; never exposes a stack trace |

---

## 2. Shared schemas

### ProductSummary
```json
{
  "product_id": "MN-MON-0001",
  "sku": "MON-10000",
  "name": "Flux Vision 24 QHD IPS",
  "brand": "Flux",
  "category": "Monitors",
  "subcategory": "Gaming",
  "short_description": "24-inch QHD IPS monitor with 240 Hz refresh rate.",
  "image_url": "https://placehold.co/800x600/png?text=MON-10000",
  "rating": 4.3,
  "review_count": 1088,
  "price": { "current": 468.62, "list": 493.28, "discount_percent": 5, "currency": "USD" },
  "available_qty": 14,
  "in_stock": true
}
```

### ProductDetail = ProductSummary +
```json
{
  "description": "…",
  "recommended_for": ["office work", "programming"],
  "not_recommended_for": ["competitive gaming"],
  "key_features": ["24-inch", "QHD", "IPS", "240 Hz"],
  "tags": ["monitor", "display"],
  "color": "Black",
  "dimensions_cm": { "width": 50.4, "height": 32.4, "depth": 23.9 },
  "weight_kg": 6.74,
  "warranty_months": 12,
  "return_days": 30,
  "specifications": [
    { "group": "Display", "name": "Screen Size", "value": "24", "unit": "in" }
  ],
  "availability": [
    { "warehouse_id": "WH-MVD-CEN", "warehouse_name": "MercaNova Centro", "city": "Montevideo", "available_qty": 7, "pickup_enabled": true }
  ],
  "related": [
    { "product_id": "MN-MON-0013", "name": "…", "relation_type": "alternative_to", "strength": 0.82 }
  ]
}
```

### Cart
```json
{
  "items": [
    { "product_id": "MN-MON-0001", "name": "Flux Vision 24 QHD IPS", "image_url": "…", "unit_price": 468.62, "quantity": 2, "line_total": 937.24, "available_qty": 14 }
  ],
  "item_count": 2,
  "total": 937.24,
  "currency": "USD"
}
```

### Order
```json
{
  "order_id": "ORD-20261112-0001",
  "status": "pending_confirmation | confirmed | cancelled",
  "created_at": "2026-11-12T22:00:00Z",
  "confirmed_at": null,
  "expires_at": "2026-11-12T22:15:00Z",
  "customer": { "name": "Ana Pérez", "email": "ana@example.com" },
  "delivery": { "method": "pickup | shipping", "warehouse_id": "WH-MVD-CEN", "address": null },
  "items": [ { "product_id": "MN-MON-0001", "name": "…", "unit_price": 468.62, "quantity": 2, "line_total": 937.24 } ],
  "total": 937.24,
  "currency": "USD"
}
```
`unit_price` is frozen when the draft is created (see ADR on new entities).

---

## 3. Endpoints

### Health and reference data
| Method | Path | Response |
|---|---|---|
| GET | `/api/health` | `{ "status": "ok", "db": "ok", "llm": "ok \| down", "stt": "ok \| down" }` |
| GET | `/api/categories` | `[{ "category": "Monitors", "subcategories": ["Office", "Gaming"] }]` |
| GET | `/api/warehouses` | `[{ "warehouse_id", "warehouse_name", "city", "pickup_enabled", "shipping_enabled" }]` |

### Catalog (RF-01)
| Method | Path | Notes |
|---|---|---|
| GET | `/api/products` | Query: `q` (plain text, not semantic), `category`, `subcategory`, `brand`, `min_price`, `max_price`, `in_stock` (bool), `sort` (`price_asc`, `price_desc`, `rating`), `page` (1), `page_size` (20, max 100). Response: `{ "items": [ProductSummary], "page", "page_size", "total" }` |
| GET | `/api/products/{product_id}` | `ProductDetail` · 404 `PRODUCT_NOT_FOUND` |
| GET | `/api/products/compare?ids=A,B,C` | 2–4 ids. `{ "products": [ProductDetail], "attributes": [{ "group", "name", "unit", "values": { "A": "…", "B": "…" } }] }` (RF-06) |

### Cart (RF-09, RF-10)
| Method | Path | Body | Response |
|---|---|---|---|
| GET | `/api/cart` | – | `Cart` |
| POST | `/api/cart/items` | `{ "product_id", "quantity" }` (adds to existing quantity) | `Cart` · 409 `INSUFFICIENT_STOCK` / `PRODUCT_INACTIVE` |
| PATCH | `/api/cart/items/{product_id}` | `{ "quantity" }` (≥ 1) | `Cart` · 409 `INSUFFICIENT_STOCK` |
| DELETE | `/api/cart/items/{product_id}` | – | `Cart` |
| DELETE | `/api/cart` | – | empty `Cart` |

The cart **does not reserve stock**. Availability is validated when adding/updating and again on confirm.

### Checkout and orders (RF-11..RF-16)
| Method | Path | Body | Response |
|---|---|---|---|
| POST | `/api/checkout` | `{ "customer": { "name", "email" }, "delivery": { "method": "pickup", "warehouse_id": "WH-MVD-CEN" } }` or `{ …, "delivery": { "method": "shipping", "address": "…" } }` | `201 Order` with `status = pending_confirmation`. Validates stock, freezes prices, **does not touch stock**. 409 `CART_EMPTY` / `INSUFFICIENT_STOCK` |
| POST | `/api/orders/{order_id}/confirm` | – | `Order` with `status = confirmed`. In one transaction: re-validate and decrement stock (row lock), empty the cart. 409 `INSUFFICIENT_STOCK` / `ORDER_NOT_PENDING`, 410 `ORDER_DRAFT_EXPIRED` |
| POST | `/api/orders/{order_id}/cancel` | – | `Order` with `status = cancelled` |
| GET | `/api/orders` | – | `[Order]` of the session, newest first |
| GET | `/api/orders/{order_id}` | – | `Order` |

No payment data is collected (RF-13). Stock allocation: `pickup` decrements the chosen warehouse; `shipping` decrements warehouses in order of highest availability (see ADR to be written in BE-03).

**Explicit confirmation (RF-12):** only `POST /orders/{id}/confirm` places an order, and only the frontend calls it after the user clicks "Confirmar compra". The assistant never calls it.

### Assistant (RF-02..RF-08, RF-17, RF-18)

#### POST `/api/chat`
Request:
```json
{ "message": "Necesito auriculares para videollamadas, máximo USD 200", "conversation_id": null, "input_mode": "text | voice" }
```
Response `200`:
```json
{
  "conversation_id": "c1f0…",
  "reply": "Te recomiendo estas tres opciones…",
  "blocks": [ Block ],
  "tools_used": [ { "name": "search_products", "args": { "query": "…", "max_price": 200 } }, { "name": "get_stock", "args": { "product_id": "…" } } ]
}
```
`tools_used` is shown in a collapsible "cómo lo resolví" panel (useful for the demo and the defense).

**Block types** (the frontend renders one component per type):

| type | Payload | Rendered as |
|---|---|---|
| `product_recommendations` | `{ "items": [ { "product": ProductSummary, "reason": "Cancelación de ruido y micrófono boom, ideal para llamadas." } ] }` | Product cards with reason + "Agregar al carrito" (RF-04) |
| `comparison` | Same shape as `/api/products/compare` | Comparison table (RF-06) |
| `clarification` | `{ "question": "¿Para qué lo vas a usar?", "options": ["Trabajo", "Gaming", "Diseño"] }` | Quick-reply chips (RF-05) |
| `cart_updated` | `{ "cart": Cart }` | Toast + refreshes cart badge |
| `checkout_draft` | `{ "order": Order }` | Opens the **confirmation modal** (RF-12) |
| `not_found` | `{ "query": "PlayStation 9" }` | Inline notice (RF-18) |

Errors: 503 `LLM_UNAVAILABLE` (the UI shows a message and the rest of the app keeps working, RNF-04).

#### GET `/api/chat/{conversation_id}`
`{ "conversation_id", "messages": [ { "role": "user | assistant", "content", "blocks", "created_at" } ] }`, used to restore the chat after a reload.

#### POST `/api/transcribe` (RF-08)
`multipart/form-data` with field `audio` (webm/ogg/wav, max 60 s, max 10 MB).
Response: `{ "text": "necesito auriculares…", "language": "es", "duration_s": 4.2 }` · 422 `AUDIO_UNREADABLE`, 503 `STT_UNAVAILABLE`.
The frontend then calls `/api/chat` with that text and `input_mode = "voice"`.

---

## 4. Open questions for review

1. Is a non-streaming `/chat` enough for v1? (SSE can be added later without changing the payload.)
2. Draft expiration of 15 minutes: OK?
3. Do we need `customer` beyond name and email (address only for shipping)?
