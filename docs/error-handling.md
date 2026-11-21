# Manejo de errores de punta a punta

Este documento recorre los cinco casos límite que pide la letra. Para cada uno muestra qué responde el backend, qué ve el usuario y qué test lo comprueba. Cubre el manejo de casos límite (RF-17), no permitir comprar más de lo disponible (RF-10) y la robustez: los errores previsibles no rompen la aplicación ni dejan datos inconsistentes (RNF-04).

**Regla general.** Todo error de la API tiene la forma del contrato: `{"error": {"code", "message", "details"}}` (ver `docs/api-contract.md`). El `message` está en español y la interfaz lo muestra tal cual. Si una respuesta no tiene esa forma (por ejemplo, un error 500 de un proxy), el cliente HTTP del frontend (`frontend/src/api/http.ts`) la reemplaza por "Ocurrió un error inesperado. Intentá de nuevo en unos minutos.". Si no hay conexión, muestra "No pudimos conectarnos con la tienda. Revisá tu conexión e intentá de nuevo.". El usuario nunca ve un código, una traza ni un texto en inglés.

**Verificación manual.** Los cinco casos se probaron el 20/11/2026 contra la aplicación levantada con Docker Compose. Las respuestas del backend que figuran abajo son las que se obtuvieron.

## 1. Ollama apagado

| | |
|---|---|
| **Backend** | El ciclo del agente captura la falla del modelo y no deja escapar la excepción. `POST /api/chat` responde `503 LLM_UNAVAILABLE`. `POST /api/chat/stream` envía un evento `error` con el mismo código. La conversación no guarda el turno fallido. |
| **Usuario** | En el chat aparece un aviso: "El asistente no está disponible por ahora. El resto de la tienda sigue funcionando.". Puede volver a escribir. El catálogo, el carrito y la compra no usan el modelo y siguen funcionando. |
| **Datos** | No cambia nada: el turno no se guarda y el carrito no se toca. |
| **Tests** | Backend: `test_model_unavailable_is_503_and_nothing_is_persisted` y `test_stream_with_model_unavailable_ends_with_an_error_event` (`tests/integration/test_chat_api.py`), `test_llm_unavailable_in_tool_phase_gives_the_fallback` y `test_llm_unavailable_in_final_phase_gives_the_fallback` (`tests/unit/test_agent_loop.py`). Frontend: "shows the error event message and lets the user write again" (`ChatContainer.test.tsx`). |

Para probarlo se levantó la aplicación con una dirección de Ollama que no responde (`OLLAMA_BASE_URL=http://127.0.0.1:9`).

## 2. Producto inexistente

| | |
|---|---|
| **Backend** | `GET /api/products/{id}` responde `404 PRODUCT_NOT_FOUND` ("El producto no existe."). En el chat, si `search_products` no encuentra nada, la respuesta trae un bloque `not_found` aunque el modelo se olvide de completarlo. Si el modelo usa un id que ninguna herramienta devolvió, el ciclo rechaza la llamada antes de ejecutarla. |
| **Usuario** | En el detalle: "Este producto no existe. Puede que el enlace esté mal o que el producto ya no esté en el catálogo.". En el chat: "No encontramos «…» en el catálogo de MercaNova.", sin productos inventados. |
| **Tests** | Backend: `test_not_found_is_derived_from_an_empty_search_when_the_model_forgets_it` y `test_not_found_is_kept_when_no_tool_returned_products` (`test_agent_loop.py`), `test_tools_return_a_not_found_error_when_the_product_id_does_not_exist` (`test_catalog_tools_db.py`). Frontend: "says the product does not exist instead of showing an error" (`ProductDetailContainer.test.tsx`) y el bloque `not_found` en `ChatBlockView.test.tsx`. |

## 3. Sin stock o con stock insuficiente

| | |
|---|---|
| **Backend** | Agregar más de lo disponible responde `409 INSUFFICIENT_STOCK` con `available_qty` en `details`. El mensaje es "Solo hay N unidades disponibles.", "Solo hay 1 unidad disponible." o, si no queda nada, "Este producto no tiene stock en este momento.". El checkout y la confirmación vuelven a revisar el stock. La confirmación descuenta el stock en una sola transacción con bloqueo de filas (decisión 0007). |
| **Usuario** | **Catálogo:** el producto sin stock muestra "Sin stock" y el botón de agregar está bloqueado. **Agregar de más:** aparece el mensaje del backend junto al botón. **Carrito:** si el stock bajó después de agregar el producto, la línea avisa "Ahora solo hay N unidades. Bajá la cantidad para poder comprar." o "Este producto se quedó sin stock. Quitalo para poder comprar.". **Checkout:** si al crear o confirmar la orden falta stock, la pantalla lo explica y ofrece "Volver al carrito". Una orden pendiente que ya no se puede confirmar se cancela. **Chat:** `add_to_cart` devuelve "Solo hay N unidades" con una sugerencia, y el asistente se lo dice al usuario. |
| **Datos** | El carrito no cambia cuando el pedido se rechaza, y el stock nunca queda negativo. |
| **Tests** | Backend: `test_add_beyond_stock_returns_insufficient_stock_and_keeps_cart`, `test_insufficient_stock_message_is_singular_for_one_unit` y `test_insufficient_stock_message_says_there_is_no_stock_instead_of_zero_units` (`test_cart_api.py`), `test_checkout_insufficient_stock_for_pickup` (`test_checkout_api.py`), `test_dispatch_maps_insufficient_stock_to_the_available_units_and_a_hint` (`test_tool_dispatcher.py`). Frontend: `AddToCart.test.tsx`, `CartLineItem.test.tsx`, `CartContainer.test.tsx` y `CheckoutFlow.test.tsx`. |

## 4. Consulta ambigua

| | |
|---|---|
| **Backend** | Si el pedido es vago (por ejemplo "Quiero un monitor"), el ciclo bloquea una búsqueda con tres palabras o menos, sin números y sin filtros. Le pide al modelo una sola pregunta de aclaración. Si el modelo no la hace, el software usa una pregunta fija y no recomienda nada. |
| **Usuario** | El chat muestra la pregunta con opciones rápidas (por ejemplo "Trabajo", "Juegos"). La respuesta del usuario completa el pedido original en lugar de reemplazarlo. |
| **Tests** | Backend: `test_use_case_2_vague_request_returns_a_clarification_without_tools`, `test_vague_search_is_blocked_and_the_model_then_asks_a_question`, `test_vague_blocked_still_without_clarification_gets_the_fallback_and_no_recommendations` y `test_a_short_answer_to_a_clarification_completes_the_goal` (`test_agent_loop.py`). Frontend: "sends the conversation id after the first answer and a quick reply as the next message" (`ChatContainer.test.tsx`). |

## 5. Audio vacío o que no se entiende

| | |
|---|---|
| **Backend** | `POST /api/transcribe` responde `422 AUDIO_UNREADABLE` para un archivo vacío, un archivo que no es audio y una grabación en silencio. Los formatos que no acepta el contrato y los archivos demasiado grandes tienen su propio error. |
| **Usuario** | Si la grabación no tiene datos, el navegador no la envía y muestra "No se grabó ningún sonido. Intentá de nuevo.". Si el backend no la entiende: "No pudimos entender el audio. Probá grabarlo de nuevo o escribí tu consulta.". También hay mensajes para el permiso del micrófono denegado, la falta de micrófono y un navegador que no puede grabar. |
| **Datos** | No se envía nada al chat. |
| **Tests** | Backend: `test_empty_audio_is_unreadable`, `test_audio_without_speech_is_unreadable`, `test_endpoint_reports_empty_audio_as_unreadable` y `test_endpoint_reports_undecodable_audio_as_unreadable` (`tests/unit/test_transcription.py`). Frontend: "does not send a recording without sound" y "shows the message of the backend when the audio cannot be understood" (`ChatContainer.voice.test.tsx`). |

## Limitaciones conocidas

- **Pedido mayor a 1000 unidades.** El backend lo rechaza con `VALIDATION_ERROR` y el mensaje genérico "Los datos enviados no son válidos.". La interfaz agrega de a una unidad y el carrito no deja pasar del stock, así que el caso solo se da llamando a la API directamente.
- **Agregar cuando el carrito ya tiene todo el stock.** El mensaje dice "Solo hay N unidades disponibles." sin aclarar que esas unidades ya están en el carrito. El botón del carrito se bloquea en el máximo, pero el del catálogo no lo sabe.
