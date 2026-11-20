# Flujo del endpoint de chat

Estos diagramas muestran lo que está implementado en el endpoint de chat (decisión 0010): cómo viaja un mensaje, cómo se arman los bloques y qué se guarda en la base. El ciclo del agente que corre adentro está en `agent-flow.md`.

## 1. `POST /api/chat/stream`, de punta a punta

El turno corre en un hilo aparte y el hilo principal va enviando los eventos al navegador a medida que llegan por una cola. El hilo abre y cierra sus propios recursos (sesión de base de datos y clientes del modelo), y siempre deja un evento final en la cola; si el hilo muriera sin dejarlo, el generador lo detecta y envía un evento `error` (INTERNAL_ERROR).

```mermaid
sequenceDiagram
    participant U as Navegador
    participant A as Endpoint /api/chat/stream
    participant W as Hilo de trabajo
    participant S as ChatService
    participant L as Ciclo del agente
    participant DB as PostgreSQL

    U->>A: POST message, conversation_id, input_mode
    A->>W: inicia el hilo y espera en la cola
    W->>W: abre su sesión de base de datos y sus clientes del modelo
    W->>S: handle(mensaje, conversation_id)
    alt conversation_id nulo
        S->>DB: crea la conversación
        S->>S: estado vacío
    else conversation_id existente
        S->>DB: toma el candado de la conversación (espera hasta 30 s)
        S->>DB: carga agent_state de esa sesión
    end
    S-->>A: on_conversation, cola: meta
    A-->>U: event meta (conversation_id)
    S->>DB: últimos mensajes
    S->>L: run_turn(estado, historial, mensaje)
    loop cada herramienta que pide el modelo
        L-->>A: on_event, cola: tool_call
        A-->>U: event tool_call (name, args)
    end
    L-->>S: TurnResult (texto ya validado)
    alt el modelo no está disponible
        S-->>A: LLMUnavailable, cola: failure
        A-->>U: event error (LLM_UNAVAILABLE), sin guardar nada
    else turno normal o degradado
        S->>DB: lee sku, imagen y puntaje de las tarjetas
        S->>S: arma los bloques (diagrama 2)
        S->>DB: guarda el turno (diagrama 3)
        S->>DB: libera el candado de la conversación
        S-->>A: ChatReply, cola: reply
        loop cada palabra del texto
            A-->>U: event token (text)
            Note over A: pausa de 0,02 s
        end
        loop cada bloque
            A-->>U: event block
        end
        A-->>U: event done (reply, tools_used)
    end
```

Si otro turno de la misma conversación sigue corriendo y no termina en 30 s, el segundo no se ejecuta: llega un evento `error` con el código `CONVERSATION_BUSY` (409 en el endpoint sin stream) y no se guarda nada. El candado se libera siempre al terminar el turno, también cuando falla (decisión 0012).

Cualquier otro fallo del turno (conversación inexistente, mensaje inválido, error inesperado) también llega como un evento `error`, con otro código. La respuesta HTTP ya empezó con estado 200, así que el error viaja dentro del flujo. Si el fallo ocurre antes de empezar a transmitir, por ejemplo por un encabezado `X-Session-Id` ausente, responde con un error HTTP normal.

## 2. Cómo se arman los bloques

Los arma el software a partir del resultado del turno (`TurnResult`) y de los resultados de las herramientas. El modelo no escribe los bloques.

```mermaid
flowchart TD
    R[TurnResult] --> D{¿Respuesta degradada?}
    D -- sí --> N[Sin bloques]
    D -- no --> C1{¿compare_products terminó bien?}
    C1 -- sí --> B1[Bloque comparison<br/>productos y atributos de la herramienta]
    C1 -- no --> C2
    B1 --> C2{¿Hay recomendaciones?}
    C2 -- sí --> B2[Bloque product_recommendations<br/>tarjetas y motivo del modelo]
    C2 -- no --> C3
    B2 --> C3{¿Hay aclaración<br/>en la respuesta final?}
    C3 -- sí --> B3[Bloque clarification<br/>pregunta y opciones]
    C3 -- no --> C4
    B3 --> C4{¿Hay not_found<br/>en la respuesta final?}
    C4 -- sí --> B4[Bloque not_found<br/>consulta buscada]
    C4 -- no --> C5
    B4 --> C5{¿add_to_cart terminó bien?}
    C5 -- sí --> B5[Bloque cart_updated<br/>carrito que devolvió la herramienta]
    C5 -- no --> C6
    B5 --> C6{¿start_checkout terminó bien<br/>y ready es true?}
    C6 -- sí --> B6[Bloque checkout_draft<br/>resumen del carrito]
    C6 -- no --> F[Fin]
    B6 --> F
```

Las tarjetas de `comparison` y de `product_recommendations` se completan con `sku`, `image_url`, `rating` y `review_count`, que se leen del catálogo en una sola consulta. El nombre, el precio y el stock quedan como los devolvió la herramienta en ese turno. Si un producto no se encuentra en el catálogo, esos cuatro campos van en `null`. Cuando una herramienta se llamó varias veces, se usa el último resultado correcto. Si `start_checkout` devuelve `ready: false`, no hay bloque `checkout_draft`.

## 3. Qué se guarda en cada turno

Todo se guarda en una sola transacción, después de que el turno terminó bien.

```mermaid
flowchart LR
    T[Turno terminado] --> Q{¿El modelo<br/>no estaba disponible?}
    Q -- sí --> X[No se guarda nada]
    Q -- no --> TX[Una transacción]
    TX --> M1[(messages: mensaje del usuario)]
    TX --> M2[(messages: mensaje del asistente<br/>con texto, blocks y tool_calls)]
    TX --> CS[(conversations.agent_state<br/>estado del agente en JSON)]
```

- `tool_calls` guarda, por cada herramienta, el nombre, los argumentos, si salió bien (`ok`) y la duración (`duration_ms`). No guarda el resultado.
- `agent_state` guarda el objetivo, los productos mostrados en orden (id y nombre), las herramientas usadas y el paso. Se lee al empezar el turno siguiente.
- Un turno degradado (por ejemplo, por llegar al máximo de pasos) sí se guarda, con el mensaje fijo y sin bloques.
- Si el modelo no está disponible no se guarda ni el mensaje del usuario. Cuando la conversación se creó en ese mismo pedido, la fila de la conversación queda vacía, porque se confirma antes de correr el turno.
- `input_mode` se valida pero no se guarda.
