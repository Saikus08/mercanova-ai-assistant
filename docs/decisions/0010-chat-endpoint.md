# Decisión 0010: El endpoint de chat guarda el estado en la base y emite la respuesta solo después de verificarla

- **Estado:** propuesta
- **Fecha:** 16/11/2026
- **Autores:** Agustín Vignolo y Florencia Mendoza (Grupo 8, N8B)

## Problema

El ciclo del agente (decisión 0009) resuelve un turno. Falta el endpoint que lo expone al frontend: recibe el mensaje, recuerda la conversación, muestra el avance en tiempo real y devuelve la respuesta con tarjetas, tablas y la ventana de compra. La letra pide un asistente conversacional (RF-03) y que nunca presente información que no esté en el sistema (RF-18).

Hay que decidir siete cosas:

1. Dónde se guarda el estado del agente entre un mensaje y el siguiente.
2. Cómo se transmite la respuesta y qué se muestra mientras el modelo trabaja.
3. Quién construye los bloques de la interfaz (tarjetas, comparación, aclaración).
4. Qué lleva el bloque de compra (`checkout_draft`).
5. Qué pasa cuando el modelo no está disponible.
6. Qué se hace con `input_mode`.
7. Qué pasa si el cliente se desconecta a mitad de un turno.

## Alternativas

**1. Dónde vive el estado del agente**

| Opción | A favor | En contra |
|---|---|---|
| **Columna JSONB `conversations.agent_state` (elegida)** | Sobrevive a reinicios y funciona con varios procesos. Se lee y se escribe en la misma transacción que los mensajes. Guarda el orden de los productos mostrados. Sin tablas nuevas. | Una columna más y una migración. El JSON no tiene esquema en la base: lo valida el código al leerlo (`AgentState.from_dict`, que tolera claves faltantes). |
| En memoria, por proceso | Cero código de persistencia. | Se pierde al reiniciar. Con varios procesos (workers) el segundo mensaje puede caer en otro proceso que no conoce el estado. Hoy corremos uno solo, pero es un supuesto frágil. |
| Reconstruirlo desde los mensajes guardados | No hay estado extra que mantener. | El texto guardado no tiene el orden de los productos mostrados ni sus ids. Sin eso, "compará el primero con el segundo" deja de resolverse. Habría que volver a interpretar los bloques de cada mensaje. |

**2. Transporte y emisión de la respuesta**

| Opción | A favor | En contra |
|---|---|---|
| **Server-Sent Events con `POST` y respuesta en streaming (elegida)** | Es una respuesta HTTP común con `text/event-stream` [1][2]. Va en un sentido (servidor a cliente), que es lo que necesitamos. FastAPI transmite un generador con `StreamingResponse` [3]. | `EventSource` solo hace `GET`, así que el frontend lo lee con `fetch`. No hay reconexión automática. |
| WebSocket | Dos sentidos. Podría cancelar un turno en curso. | Más piezas (protocolo propio, estado de la conexión) para un caso que es un pedido y una respuesta. No lo probamos. |
| Respuesta común `POST /api/chat` | La más simple. | El usuario espera varios segundos frente a una pantalla quieta. Se deja igual, como alternativa si el flujo falla y para los tests. |

**3. Cuándo se emite el texto**

| Opción | A favor | En contra |
|---|---|---|
| **Eventos `tool_call` en vivo, y el texto recién después de las verificaciones, partido en palabras (elegida)** | Los controles de la decisión 0009 (montos, nombres de herramientas) necesitan el texto completo. Lo que el usuario ve ya fue verificado. | El primer texto aparece cuando el modelo terminó todo. El efecto de escritura es cosmético. |
| Reenviar los tokens del modelo a medida que salen | Aparece texto antes. | Un token con un precio inventado llegaría a la pantalla antes del control, y no se puede retirar. Con la fase final en JSON, el texto además va dentro de un objeto que recién es válido al final. |

**4. Quién arma los bloques**

| Opción | A favor | En contra |
|---|---|---|
| **El software, desde los resultados de las herramientas y la respuesta final (elegida)** | El precio y el stock de una tarjeta son los leídos en ese turno (regla de datos dinámicos). Se prueba sin modelo. | Más código en el servidor. |
| Que el modelo escriba los bloques | Menos código. | Puede inventar o deformar un precio, y un modelo chico lo hace (decisión 0009). |

## Decisión

- **Estado.** La migración `0002` agrega `conversations.agent_state` (JSONB, no nulo, por defecto `{}`). Al empezar un turno se carga el estado de esa conversación y de esa sesión. Al terminar, `append_turn` lo guarda junto con los mensajes. Guarda el objetivo, los productos mostrados (id y nombre, en orden), las herramientas usadas (nombre, `ok` y paso) y el paso. No guarda los resultados de las herramientas.
- **Transporte.** `POST /api/chat/stream` responde `text/event-stream` con los eventos `meta`, `tool_call`, `token`, `block`, `done` y `error`. El turno corre en un hilo aparte que deja los eventos en una cola, y el generador los envía a medida que llegan. El hilo abre su propia sesión de base de datos, su cliente del modelo y su cliente de embeddings, y los cierra al terminar: así una desconexión del cliente no le cierra los recursos mientras trabaja. El hilo siempre deja un evento final en la cola; si el hilo muriera sin dejarlo, el generador lo detecta (espera con tope de 1 s) y envía un evento `error` en lugar de quedarse colgado. Así `tool_call` sale en el momento en que el ciclo ejecuta la herramienta. `POST /api/chat` devuelve lo mismo de una vez.
- **Texto.** Cuando el turno termina, el texto ya verificado se parte en palabras y se envía con una pausa de 0,02 s entre una y otra. Después salen los bloques y `done`.
- **Bloques.** `chat_blocks.py` los construye. `comparison` sale del último `compare_products` correcto. `product_recommendations`, `clarification` y `not_found` salen de la respuesta final. `cart_updated` sale del último `add_to_cart` correcto. `checkout_draft` solo sale si `start_checkout` devolvió `ready: true`. Las tarjetas se completan con `sku`, imagen, puntaje y cantidad de reseñas leídos del catálogo, porque las herramientas no los devuelven. Nombre, precio y stock quedan como los devolvió la herramienta. Una respuesta degradada no tiene bloques.
- **Bloque de compra.** `checkout_draft` lleva `cart`, el resumen del carrito que devuelve `start_checkout` (decisión 0008), y no una orden: `start_checkout` no crea ninguna orden, solo avisa que la ventana está lista. Hoy el contrato de la API todavía dice `order: <orden pendiente>`. Hay que actualizarlo en la tarea del contrato de la API.
- **Errores.** Si el modelo no está disponible, `POST /api/chat` responde 503 con el código `LLM_UNAVAILABLE`. En el flujo, la respuesta HTTP ya empezó con 200, así que el error viaja como evento `error` con el mismo código. Los demás fallos (conversación inexistente, mensaje inválido, error inesperado) también salen como evento `error`, sin el texto de la excepción. Un encabezado `X-Session-Id` ausente se rechaza antes de empezar el flujo, con un error HTTP normal.
- **Nada a medias.** Los mensajes y el estado se guardan en una sola transacción al final, y solo si el modelo respondió. Un turno fallido no deja mensajes ni cambia el estado. Una conversación creada en ese mismo pedido sí queda como fila vacía, porque se confirma antes de correr el turno.
- **`input_mode`.** Se valida (`text` o `voice`) y no se guarda: el asistente responde igual en los dos casos.
- **Desconexión.** Si el cliente corta la conexión, el turno en curso no se cancela (ver límites).

## Justificación

- **Estado en la base.** Es la única opción que conserva el orden de los productos mostrados sin depender de un solo proceso. La base ya guarda la conversación, y el estado viaja en la misma transacción que los mensajes.
- **Texto después de verificar.** El producto prefiere no mostrar un precio no verificado a mostrar texto antes (RF-18). La parte lenta del turno son las llamadas al modelo, y el usuario las ve a través de los eventos `tool_call`.
- **Bloques por software.** Mantiene la regla de que el precio y el stock salen de una herramienta leída en el turno actual.
- **Un solo formato de error.** El frontend maneja un único evento `error` con código y mensaje, y la tienda sigue funcionando (RNF-04: el fallo del asistente no tumba el resto).

## Costos y riesgos (trade-offs)

- **El efecto de escritura es cosmético y no reduce la espera.** El texto completo ya existe cuando empieza a enviarse. Un turno con `llama3.1:8b` tarda unos 11 segundos (decisión 0009). Lo único que se ve antes son los eventos `tool_call`. Un texto de unas 60 palabras suma cerca de 1,2 s de pausas.
- **El hilo sigue corriendo si el cliente se desconecta.** El generador deja de enviar, pero el turno termina, llama al modelo y guarda el resultado. Es una limitación conocida: gasta recursos y el mensaje queda guardado aunque el usuario no lo haya visto. Cancelarlo requeriría pasar una señal de corte al ciclo.
- **No hay límite de pedidos.** Un cliente puede lanzar muchos turnos a la vez, cada uno con su hilo y sus llamadas al modelo. En producción habría que limitar por sesión.
- **Un hilo por pedido.** Es simple y alcanza para la demostración. Con mucha carga se agotarían los hilos.
- **Un turno degradado se guarda.** El mensaje fijo queda en el historial y cuenta dentro de los últimos mensajes que se le mandan al modelo.
- **El contrato de la API está desactualizado en un punto** (`checkout_draft`, ver arriba).
- **La compra se completa por otro camino.** El bloque `checkout_draft` solo abre la ventana. La confirmación sigue siendo del usuario (decisión 0008).

## Fuentes

1. WHATWG, *HTML Living Standard, Server-sent events* (el tipo `text/event-stream` y su formato): https://html.spec.whatwg.org/multipage/server-sent-events.html
2. MDN, *Using server-sent events* (formato de los mensajes y comunicación del servidor al cliente solamente): https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events/Using_server-sent_events
3. FastAPI, *Custom Response, StreamingResponse* (acepta un generador y transmite el cuerpo): https://fastapi.tiangolo.com/advanced/custom-response/#streamingresponse
4. Decisiones 0008 (la compra desde el chat) y 0009 (el ciclo del agente y sus controles).
