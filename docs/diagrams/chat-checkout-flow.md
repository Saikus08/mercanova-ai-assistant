# Flujo de "comprámelo" en el chat

Este diagrama muestra cómo se prepara una compra desde el chat (decisión 0008). Las herramientas `view_cart`, `add_to_cart` y `start_checkout` ya existen. El ciclo del agente, el endpoint de chat y la ventana de confirmación son otras tareas: acá se dibuja el flujo completo para ver dónde pasan los datos personales, y cada parte indica si está implementada.

## 1. Quién ve qué

```mermaid
sequenceDiagram
    participant U as Usuario
    participant L as Asistente (modelo)
    participant D as Dispatcher y herramientas (implementado)
    participant I as Interfaz, ventana de compra (otra tarea)
    participant B as API de compra (implementado)

    U->>L: "Comprámelo"
    L->>D: start_checkout() sin argumentos
    D->>D: lee el carrito con precios y stock actuales
    alt carrito vacío
        D-->>L: error con la pista "agregá productos primero"
    else hay cantidades que no alcanzan
        D-->>L: ready=false + lista de problemas
        L-->>U: explica qué no alcanza y pide ajustar el carrito
    else todo alcanza
        D-->>L: ready=true + resumen del carrito
        L-->>U: "La ventana de compra está lista"
        Note over L,I: el asistente solo prepara la ventana
        U->>I: abre la ventana y escribe nombre, email y dirección
        Note over U,I: los datos personales NO pasan por el modelo
        I->>B: POST /api/checkout (datos del cliente)
        B-->>I: orden pending_confirmation
        U->>I: clic en "Confirmar compra"
        I->>B: POST /api/orders/{id}/confirm
        B-->>I: orden confirmed y stock descontado
    end
```

## 2. Qué intenta el modelo y qué responde el dispatcher

| El modelo intenta | Respuesta del dispatcher |
|---|---|
| `start_checkout` con `name` y `email` | Rechaza los campos de más: la herramienta no tiene argumentos |
| `view_cart` con un `session_id` | "session_id lo pone el sistema" |
| `confirm_order` o `cancel_order` | "No disponible para el asistente: confirma el usuario en la interfaz" |
| `add_to_cart` con 50 unidades y 9 en stock | "Solo hay 9 unidades", y sugiere una cantidad menor o alternativas |
| `add_to_cart` de un producto inexistente | "Producto no encontrado", y sugiere buscarlo con `search_products` |
| `start_checkout` con el carrito vacío | "El carrito está vacío", y sugiere agregar productos primero |

El modelo nunca crea una orden, nunca confirma una compra y nunca recibe datos personales.
