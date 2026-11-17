# Flujo de la compra en la interfaz

Este diagrama muestra lo que hace la pantalla de checkout (`/checkout`) y qué endpoints llama. El flujo del backend (qué pasa dentro de cada endpoint) está en `checkout-flow.md`.

## 1. De "Continuar con la compra" a la compra confirmada

La orden se crea al enviar el formulario, pero **solo se confirma con el clic en "Confirmar compra"** (confirmación explícita, RF-12). Antes de llamar a la API, la pantalla valida los datos en español (nombre, email y dirección no vacíos, email con formato válido, largos máximos).

```mermaid
sequenceDiagram
    participant U as Usuario
    participant F as Pantalla de checkout
    participant API as API del backend

    U->>F: abre /checkout desde el carrito
    F->>API: GET /api/warehouses
    API-->>F: depósitos (retiro y envío)
    U->>F: completa nombre, email, dirección y entrega
    U->>F: "Revisar compra"
    F->>F: valida los datos (mensajes en español)
    F->>API: POST /api/checkout
    Note over API: crea la orden pendiente, no toca el stock
    API-->>F: 201, orden en pending_confirmation
    F->>U: diálogo "Confirmá tu compra" con el resumen

    alt el usuario hace clic en "Confirmar compra"
        U->>F: "Confirmar compra"
        F->>API: POST /api/orders/{id}/confirm
        Note over API: una transacción: revalida stock y precio, descuenta stock, vacía el carrito
        API-->>F: orden confirmed
        F->>API: GET /api/cart (recarga el carrito, ahora vacío)
        F->>U: "¡Compra confirmada!" con el número de orden
    else el usuario hace clic en "Cancelar compra" o cierra con Escape
        U->>F: "Cancelar compra"
        F->>API: POST /api/orders/{id}/cancel
        API-->>F: orden cancelled
        F->>U: vuelve al formulario con los datos escritos
    end
```

## 2. Qué muestra la pantalla cuando algo falla

```mermaid
flowchart TD
    A["Revisar compra (POST /api/checkout)"] --> B{"Respuesta"}
    B -->|"VALIDATION_ERROR"| C["Marca cada campo con un mensaje en español, sin mostrar el texto en inglés del backend"]
    B -->|"CART_EMPTY o INSUFFICIENT_STOCK"| D["Mensaje y enlace 'Volver al carrito', recarga el carrito"]
    B -->|"201"| E["Diálogo de confirmación"]
    E --> F["Confirmar compra (POST /api/orders/id/confirm)"]
    F --> G{"Respuesta"}
    G -->|"200"| H["Compra confirmada, recarga el carrito"]
    G -->|"INSUFFICIENT_STOCK"| I["Cancela la orden pendiente, nombra el producto y las unidades disponibles, enlace 'Volver al carrito'"]
    G -->|"PRICE_CHANGED"| J["Muestra el precio anterior y el nuevo, oculta 'Confirmar compra' y ofrece 'Armar la orden de nuevo'"]
    G -->|"ORDER_NOT_PENDING u ORDER_NOT_FOUND"| K["Cierra el diálogo, informa y ofrece volver al carrito"]
    G -->|"error de red"| L["El diálogo queda abierto con el mensaje, para reintentar"]
    J --> M["Cancela la orden pendiente, recarga el carrito y vuelve al formulario"]
```

Mientras hay un pedido en curso, los botones quedan deshabilitados y se ignoran los clics repetidos: una orden no se envía ni se confirma dos veces. Nombre, email y dirección solo viajan en el cuerpo de `POST /api/checkout`: no se escriben en la consola ni se guardan en el navegador.
