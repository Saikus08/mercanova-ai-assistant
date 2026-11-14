# Contrato de la API

Este documento define cómo se comunican el frontend y el backend: qué direcciones (endpoints) existen, qué datos reciben y qué devuelven. Lo acordamos antes de programar para trabajar en paralelo. El frontend se construye contra datos simulados que respetan este formato y el backend lo implementa por su lado. Si después hay que cambiar algo, el cambio se hace con un pull request que revisan las dos personas del equipo.

## Reglas generales

- **Dirección base:** todas las rutas empiezan con `/api`.
- **Formato:** JSON. Los nombres de campos van en inglés y en `snake_case` (por ejemplo `product_id`). Los montos son números en dólares con dos decimales. Las fechas usan el formato ISO 8601 en hora UTC.
- **Sesión del usuario:** no hay login, porque la letra lo deja fuera del alcance. La primera vez que se abre la aplicación, el frontend genera un identificador al azar, lo guarda en el navegador y lo manda en cada pedido en el encabezado `X-Session-Id`. El carrito, la conversación y el historial de órdenes quedan asociados a ese identificador.
- **Precio y stock siempre actuales:** cada respuesta que incluye precio o disponibilidad los lee de la base de datos en ese momento. Nunca salen de una copia guardada ni del modelo de lenguaje. Así lo pide la letra para la información sensible de la compra (RF-07).

## 1. Errores

Cuando algo sale mal, la respuesta siempre tiene la misma forma:

```json
{ "error": { "code": "INSUFFICIENT_STOCK", "message": "Solo hay 7 unidades disponibles.", "details": { "product_id": "MN-MON-0001", "available_qty": 7 } } }
```

`message` está en español y el frontend lo puede mostrar tal cual al usuario. `code` le permite al frontend reaccionar distinto según el caso.

| Código HTTP | `code` | Cuándo ocurre |
|---|---|---|
| 400 | `VALIDATION_ERROR` | Faltan datos o tienen un formato incorrecto |
| 400 | `MISSING_SESSION` | El pedido no trae el encabezado `X-Session-Id` |
| 404 | `PRODUCT_NOT_FOUND` | El producto no existe |
| 404 | `ORDER_NOT_FOUND` | La orden no existe o es de otra sesión |
| 409 | `INSUFFICIENT_STOCK` | Se pide más cantidad de la disponible, al agregar al carrito o al confirmar |
| 409 | `PRODUCT_INACTIVE` | El producto existe pero ya no se vende |
| 409 | `CART_EMPTY` | Se intenta pasar al checkout con el carrito vacío |
| 409 | `PRICE_CHANGED` | Al confirmar, el precio de algún producto cambió desde que se armó la orden |
| 409 | `ORDER_NOT_PENDING` | Se intenta confirmar o cancelar una orden ya confirmada o cancelada |
| 422 | `AUDIO_UNREADABLE` | El audio llegó vacío o no se puede procesar |
| 503 | `LLM_UNAVAILABLE` | El modelo de lenguaje no responde |
| 503 | `STT_UNAVAILABLE` | El servicio de voz a texto no responde |
| 500 | `INTERNAL_ERROR` | Error inesperado. Nunca muestra detalles técnicos al usuario |

## 2. Estructuras de datos que se repiten

### Producto (versión resumida)

Se usa en listados y en las tarjetas que muestra el asistente.

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

`available_qty` es la suma de las unidades disponibles en los cinco depósitos.

### Producto (detalle)

Incluye todo lo anterior y además:

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
  "specifications": [ { "group": "Display", "name": "Screen Size", "value": "24", "unit": "in" } ],
  "availability": [ { "warehouse_id": "WH-MVD-CEN", "warehouse_name": "MercaNova Centro", "city": "Montevideo", "available_qty": 7, "pickup_enabled": true } ],
  "related": [ { "product_id": "MN-MON-0013", "name": "…", "relation_type": "alternative_to", "strength": 0.82 } ]
}
```

### Carrito

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

### Orden

```json
{
  "order_id": "ORD-20261112-0001",
  "status": "pending_confirmation",
  "created_at": "2026-11-12T22:00:00Z",
  "confirmed_at": null,
  "customer": { "name": "Ana Pérez", "email": "ana@example.com", "address": "Av. 18 de Julio 1234, Montevideo" },
  "delivery": { "method": "pickup", "warehouse_id": "WH-MVD-CEN" },
  "items": [ { "product_id": "MN-MON-0001", "name": "…", "unit_price": 468.62, "quantity": 2, "line_total": 937.24 } ],
  "total": 937.24,
  "currency": "USD"
}
```

- `status` puede ser `pending_confirmation` (creada y esperando que el usuario confirme), `confirmed` (compra registrada) o `cancelled`.
- `delivery.method` es `pickup` (retiro en un depósito, indicado en `warehouse_id`) o `shipping` (envío a `customer.address`).
- `unit_price` guarda el precio de cada producto en el momento de la compra. Si el precio cambia después, la orden confirmada mantiene el que pagó el usuario.

## 3. Endpoints

### Estado y datos de referencia

| Método | Ruta | Devuelve |
|---|---|---|
| GET | `/api/health` | Si cada servicio está funcionando: `{ "status": "ok", "db": "ok", "llm": "ok", "stt": "down" }` |
| GET | `/api/categories` | Categorías con sus subcategorías, para los filtros |
| GET | `/api/warehouses` | Los depósitos y si permiten retiro o envío |

`/api/categories` devuelve una lista con una entrada por categoría y sus subcategorías, en el orden en que se muestran en los filtros:

```json
[
  { "category": "Monitors", "subcategories": ["Gaming", "Office"] }
]
```

Los nombres son los mismos que aparecen en `category` y `subcategory` de cada producto, así el frontend los manda tal cual como filtro a `/api/products`.

### Catálogo (RF-01: consultar y ver los productos)

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/products` | Lista paginada de productos (versión resumida). Filtros opcionales: texto `q`, `category`, `subcategory`, `brand`, `min_price`, `max_price`, `in_stock`. Orden con `sort`: `price_asc`, `price_desc` o `rating`. Paginación con `page` y `page_size` (20 por defecto, máximo 100). Devuelve `{ "items": [...], "page", "page_size", "total" }`. |
| GET | `/api/products/{product_id}` | Detalle de un producto. |
| GET | `/api/products/compare?ids=A,B,C` | Compara de 2 a 4 productos (RF-06). Devuelve los productos y una tabla de atributos con el valor de cada uno: `{ "products": [...], "attributes": [{ "group", "name", "unit", "values": { "A": "…", "B": "…" } }] }`. |

### Carrito (RF-09: agregar, quitar, cambiar cantidades y ver el total · RF-10: no permitir más de lo disponible)

| Método | Ruta | Envía | Devuelve |
|---|---|---|---|
| GET | `/api/cart` | – | El carrito |
| POST | `/api/cart/items` | `{ "product_id", "quantity" }`. Si el producto ya estaba, suma la cantidad. | El carrito actualizado. Error `INSUFFICIENT_STOCK` o `PRODUCT_INACTIVE` |
| PATCH | `/api/cart/items/{product_id}` | `{ "quantity" }` (mínimo 1) | El carrito actualizado. Error `INSUFFICIENT_STOCK` |
| DELETE | `/api/cart/items/{product_id}` | – | El carrito sin ese producto |
| DELETE | `/api/cart` | – | El carrito vacío |

Agregar al carrito **no reserva stock**: solo verifica que haya suficiente en ese momento. El stock se descuenta recién cuando la compra se confirma.

### Compra (RF-11 a RF-16: checkout, confirmación, compra ficticia, orden, actualización de stock e historial)

La compra se hace en **dos pasos**. Así la letra se cumple de forma verificable: ninguna compra se registra sin confirmación explícita del usuario (RF-12).

| Método | Ruta | Envía | Devuelve |
|---|---|---|---|
| POST | `/api/checkout` | `{ "customer": { "name", "email", "address" }, "delivery": { "method": "pickup", "warehouse_id": "WH-MVD-CEN" } }`, o con `"method": "shipping"` para enviar a la dirección del cliente. Los tres datos del cliente son obligatorios. | **Paso 1.** Una orden en estado `pending_confirmation`, con los precios del momento. Verifica que haya stock, pero **no lo descuenta**. Errores: `CART_EMPTY`, `INSUFFICIENT_STOCK` |
| POST | `/api/orders/{order_id}/confirm` | – | **Paso 2.** La orden en estado `confirmed`. Errores: `INSUFFICIENT_STOCK`, `PRICE_CHANGED`, `ORDER_NOT_PENDING` |
| POST | `/api/orders/{order_id}/cancel` | – | La orden en estado `cancelled` |
| GET | `/api/orders` | – | Las órdenes de la sesión, de la más nueva a la más vieja |
| GET | `/api/orders/{order_id}` | – | Una orden |

**Qué pasa al confirmar (paso 2).** Todo ocurre dentro de una única transacción de la base de datos, así que o se hace completo o no se hace nada:

1. Bloquea las filas de stock de los productos de la orden, para que dos compras simultáneas no vendan la misma unidad.
2. Vuelve a verificar que haya stock suficiente. Si no alcanza, responde `INSUFFICIENT_STOCK` con la cantidad disponible.
3. Vuelve a verificar que el precio no haya cambiado desde el paso 1. Si cambió, responde `PRICE_CHANGED` con el precio nuevo. El frontend se lo muestra al usuario y le ofrece armar la orden otra vez.
4. Descuenta el stock (RF-15). Para retiro, descuenta del depósito elegido. Para envío, del depósito con más unidades disponibles y, si no alcanza, sigue con el siguiente.
5. Marca la orden como `confirmed`, guarda la fecha y vacía el carrito.

**Por qué las órdenes pendientes no vencen.** Al principio consideramos que una orden sin confirmar venciera a los 15 minutos. Lo descartamos porque el riesgo que cubría, confirmar con un precio o un stock viejos, ya queda cubierto al **revalidar todo al confirmar** (pasos 2 y 3). Comparado con un vencimiento por tiempo:

- **Es más simple:** no hay que programar tareas que expiren órdenes, ni manejar un estado "vencida", ni elegir un tiempo arbitrario.
- **Es más correcto:** un vencimiento solo reduce la probabilidad de usar datos viejos. Revalidar al confirmar la elimina, porque siempre se compara contra el estado actual de la base.
- **Es mejor para el usuario:** si tarda en decidirse, no pierde la orden. Solo se le avisa si algo cambió.

El costo es que pueden quedar órdenes pendientes que nadie confirma. En el prototipo no afecta nada, porque no reservan stock. En producción se limpiarían con una tarea periódica.

No se piden ni se guardan datos de tarjeta: la compra es ficticia (RF-13). **El asistente nunca confirma una compra.** Solo el frontend llama al paso 2, cuando el usuario hace clic en "Confirmar compra".

### Asistente (RF-02 a RF-08: búsqueda en lenguaje natural, conversación, recomendaciones, aclaraciones, comparación, información actual y voz)

#### POST `/api/chat/stream` — respuesta en tiempo real (la que usa el frontend)

Envía:
```json
{ "message": "Necesito auriculares para videollamadas, máximo USD 200", "conversation_id": null, "input_mode": "text" }
```
- `conversation_id` va en `null` en el primer mensaje. Después se manda el que devolvió el servidor, para que el asistente recuerde la conversación.
- `input_mode` es `text` o `voice`. Solo se guarda como dato: el asistente responde igual en los dos casos.

Devuelve una secuencia de eventos (*Server-Sent Events*). Así el usuario ve la respuesta mientras se escribe y sabe qué está haciendo el asistente, en lugar de esperar varios segundos frente a una pantalla quieta. Como el pedido es un POST, el frontend lo lee con `fetch` y no con `EventSource`.

| Evento | Contenido | Qué hace el frontend |
|---|---|---|
| `meta` | `{ "conversation_id": "c1f0…" }` | Guarda el identificador de la conversación |
| `tool_call` | `{ "name": "search_products", "args": { … } }` | Muestra qué está haciendo: "Buscando productos…", "Consultando stock…" |
| `token` | `{ "text": "Te recom" }` | Agrega el texto a la burbuja del asistente |
| `block` | Un bloque (ver tabla de bloques) | Muestra tarjetas, una tabla o la ventana de confirmación |
| `done` | `{ "reply": "texto completo", "tools_used": [ … ] }` | Cierra la respuesta |
| `error` | `{ "error": { "code": "LLM_UNAVAILABLE", "message": "…" } }` | Muestra el mensaje. El resto de la tienda sigue funcionando (RNF-04) |

Ejemplo:
```
event: meta
data: {"conversation_id":"c1f0"}

event: tool_call
data: {"name":"search_products","args":{"query":"auriculares videollamadas","max_price":200}}

event: token
data: {"text":"Te recomiendo"}

event: block
data: {"type":"product_recommendations","items":[…]}

event: done
data: {"reply":"Te recomiendo estas tres opciones…","tools_used":[…]}
```

Un evento `block` solo se envía después de que terminaron las herramientas que lo respaldan. Así una tarjeta nunca muestra un precio que no se leyó de la base en ese mismo turno (RF-07 y RF-18: no inventar información).

#### POST `/api/chat` — misma respuesta, completa de una vez

Recibe lo mismo que `/api/chat/stream` y devuelve todo junto cuando termina:
```json
{ "conversation_id": "c1f0…", "reply": "Te recomiendo estas tres opciones…", "blocks": [ … ], "tools_used": [ { "name": "search_products", "args": { … } } ] }
```
El frontend lo usa como alternativa si la conexión en tiempo real falla. También sirve para los tests automáticos.

#### Bloques que puede devolver el asistente

El frontend tiene un componente visual para cada tipo de bloque.

| `type` | Contenido | Cómo se muestra |
|---|---|---|
| `product_recommendations` | `{ "items": [ { "product": <producto resumido>, "reason": "Tiene cancelación de ruido y micrófono, ideal para llamadas." } ] }` | Tarjetas de producto con el motivo de la recomendación y un botón "Agregar al carrito" (RF-04) |
| `comparison` | Igual que la respuesta de `/api/products/compare` | Tabla comparativa (RF-06) |
| `clarification` | `{ "question": "¿Para qué lo vas a usar?", "options": ["Trabajo", "Gaming", "Diseño"] }` | La pregunta con botones de respuesta rápida (RF-05) |
| `cart_updated` | `{ "cart": <carrito> }` | Aviso breve y actualización del ícono del carrito |
| `checkout_draft` | `{ "order": <orden pendiente> }` | Abre la ventana de confirmación de compra (RF-12) |
| `not_found` | `{ "query": "PlayStation 9" }` | Aviso de que eso no está en el catálogo (RF-18) |

`tools_used` lista las herramientas que usó el asistente para responder. El frontend las muestra en un panel desplegable, "Cómo lo resolví". Sirve para la demostración y para explicar el funcionamiento en la defensa.

#### GET `/api/chat/{conversation_id}`

Devuelve los mensajes de una conversación, para restaurar el chat si el usuario recarga la página: `{ "conversation_id", "messages": [ { "role": "user", "content", "blocks", "created_at" } ] }`.

#### POST `/api/transcribe` — voz a texto (RF-08)

Recibe el audio grabado en el navegador como `multipart/form-data`, en el campo `audio`. Formatos webm, ogg o wav, de hasta 60 segundos y 10 MB.

Devuelve `{ "text": "necesito auriculares…", "language": "es", "duration_s": 4.2 }`. Errores: `AUDIO_UNREADABLE`, `STT_UNAVAILABLE`.

Con ese texto, el frontend llama a `/api/chat/stream` con `input_mode: "voice"`. Desde ahí la consulta sigue el mismo camino que una escrita, como pide la letra.

## 4. Decisiones tomadas en la revisión

| Tema | Decisión |
|---|---|
| Respuesta del chat | Tiempo real con *Server-Sent Events* (`/api/chat/stream`), con `/api/chat` como alternativa |
| Datos del cliente | Nombre, email y dirección. La letra pide "los datos mínimos necesarios para simular una compra" (RF-11) |
| Vencimiento de órdenes pendientes | No vencen. Se revalida stock y precio al confirmar (ver la sección de compra) |
