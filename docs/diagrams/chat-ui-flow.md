# Flujo del chat en la interfaz

Este diagrama muestra lo que hace la pantalla del asistente (`/chat`) y qué endpoints llama. Lo que pasa dentro de `POST /api/chat/stream` está en `chat-flow.md`.

## 1. Un mensaje, de punta a punta

La pantalla lee la respuesta con `fetch` y no con `EventSource`, porque el pedido es un POST (ver el contrato de la API, sección "Asistente"). Cada evento se muestra apenas llega: el usuario ve qué herramienta está usando el asistente y el texto mientras se escribe.

```mermaid
sequenceDiagram
    participant U as Usuario
    participant F as Pantalla del chat
    participant API as API del backend

    U->>F: escribe un mensaje o elige un ejemplo
    F->>F: agrega el mensaje y una respuesta vacía "Pensando…"
    F->>API: POST /api/chat/stream (message, conversation_id, input_mode text)
    API-->>F: event meta (conversation_id)
    F->>F: guarda el conversation_id para el próximo mensaje
    loop cada herramienta que usa el asistente
        API-->>F: event tool_call
        F->>U: "Buscando productos…", "Consultando el stock…"
    end
    loop texto de la respuesta
        API-->>F: event token
        F->>U: agrega el texto a la burbuja
    end
    loop cada bloque
        API-->>F: event block
        F->>U: un componente por tipo de bloque
    end
    API-->>F: event done (reply, tools_used)
    F->>U: texto final y panel "Cómo lo resolví"
```

## 2. Qué hace cada bloque

```mermaid
flowchart TD
    B{"type del bloque"}
    B -->|"product_recommendations"| R["Tarjetas con motivo, precio, stock y 'Agregar al carrito'"]
    R -->|"clic en 'Agregar al carrito'"| C1["POST /api/cart/items, aviso 'Agregado al carrito'"]
    B -->|"comparison"| T["Tabla: precio, stock y especificaciones lado a lado"]
    B -->|"clarification"| Q["Pregunta con botones de respuesta rápida"]
    Q -->|"clic en una opción"| S["Se envía como el próximo mensaje"]
    B -->|"cart_updated"| CU["Aviso con el total y GET /api/cart para actualizar el encabezado"]
    B -->|"checkout_draft"| CD["Resumen del carrito y botón 'Revisar y confirmar la compra'"]
    CD -->|"clic del usuario"| CK["Abre /checkout: datos y diálogo 'Confirmar compra'"]
    B -->|"not_found"| NF["Aviso: no está en el catálogo"]
```

El chat nunca confirma una compra. El bloque `checkout_draft` solo lleva a la pantalla de checkout, donde la orden se registra únicamente con el clic en "Confirmar compra" (confirmación explícita de la compra, RF-12). Las respuestas rápidas solo funcionan en la última respuesta, para no contestar dos veces la misma pregunta.

## 3. Qué muestra la pantalla cuando algo falla

```mermaid
flowchart TD
    A["POST /api/chat/stream"] --> B{"Resultado"}
    B -->|"event error (por ejemplo LLM_UNAVAILABLE)"| E["Muestra el mensaje en español del backend; el resto de la tienda sigue funcionando"]
    B -->|"falla la conexión antes del primer evento"| F["Pide la respuesta completa una vez con POST /api/chat"]
    F -->|"responde"| OK["Muestra la respuesta igual que si hubiera llegado en tiempo real"]
    F -->|"falla"| E2["Muestra el error de conexión"]
    B -->|"error HTTP (por ejemplo VALIDATION_ERROR)"| E3["Muestra el mensaje, sin reintentar"]
    B -->|"la conexión se corta sin event done"| E4["'La respuesta se cortó antes de terminar. Intentá de nuevo.'"]
```

Mientras una respuesta se escribe, el botón "Enviar" queda deshabilitado: el asistente atiende un mensaje por vez. La conversación vive en la memoria de la aplicación, así que se mantiene al ir al carrito y volver, pero se pierde al recargar la página.
