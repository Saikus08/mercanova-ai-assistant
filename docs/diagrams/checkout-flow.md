# Flujo de la compra

Estos diagramas muestran lo que está implementado en el checkout y la confirmación (decisión 0007). La compra se hace en dos pasos, y **solo el usuario**, con un botón de la interfaz, ejecuta el segundo.

## 1. Paso 1: crear la orden pendiente

`POST /api/checkout`

```mermaid
sequenceDiagram
    participant U as Usuario (interfaz)
    participant R as Router (adapters/api)
    participant C as Caso de uso checkout
    participant A as Repositorios
    participant DB as PostgreSQL

    U->>R: POST /api/checkout (cliente, entrega) + X-Session-Id
    R->>C: checkout(sesión, cliente, entrega)
    C->>C: valida nombre, email, dirección y entrega
    C->>A: líneas del carrito con precios actuales
    A->>DB: lee carrito, precios y stock
    alt carrito vacío
        C-->>U: 409 CART_EMPTY
    else hay un producto inactivo
        C-->>U: 409 PRODUCT_INACTIVE
    else no alcanza el stock
        C-->>U: 409 INSUFFICIENT_STOCK
    else todo en orden
        C->>A: crear la orden
        A->>DB: bloquea el contador del día y calcula ORD-AAAAMMDD-NNNN
        A->>DB: inserta la orden pendiente y sus líneas con el precio copiado
        DB-->>A: commit
        C-->>U: 201 orden en pending_confirmation
    end
```

En este paso **no se descuenta stock, no se reserva nada y el carrito no se vacía**. La orden pendiente es un borrador sin efectos.

## 2. Paso 2: confirmar (una sola transacción)

`POST /api/orders/{order_id}/confirm`, que se ejecuta cuando el usuario hace clic en "Confirmar compra".

```mermaid
sequenceDiagram
    participant U as Usuario (botón Confirmar compra)
    participant R as Router
    participant C as Caso de uso confirm_order
    participant A as Repositorio de órdenes
    participant D as Dominio (plan_confirmation)
    participant DB as PostgreSQL

    U->>R: POST /api/orders/ORD-.../confirm + X-Session-Id
    R->>C: confirm_order(sesión, orden)
    C->>A: confirm(orden, sesión, decide)
    A->>DB: BEGIN
    A->>DB: bloquea la fila de la orden (FOR UPDATE)
    alt no existe o es de otra sesión
        A->>DB: ROLLBACK
        C-->>U: 404 ORDER_NOT_FOUND
    else ya confirmada o cancelada
        A->>DB: ROLLBACK
        C-->>U: 409 ORDER_NOT_PENDING
    else pendiente
        A->>DB: bloquea el inventario de sus productos, ordenado por producto y depósito
        A->>DB: lee precios actuales y stock ya bloqueado
        A->>D: decide(orden, precios, stock)
        alt no alcanza el stock
            D-->>A: InsufficientStock
            A->>DB: ROLLBACK
            C-->>U: 409 INSUFFICIENT_STOCK
        else el precio cambió
            D-->>A: PriceChanged(viejo, nuevo)
            A->>DB: ROLLBACK
            C-->>U: 409 PRICE_CHANGED
        else todo coincide
            D-->>A: plan de asignación por depósito
            A->>DB: descuenta on_hand y available de cada depósito
            A->>DB: registra las asignaciones
            A->>DB: marca la orden como confirmada y vacía el carrito
            A->>DB: COMMIT
            C-->>U: 200 orden en confirmed
        end
    end
```

Si cualquier paso falla, la transacción se deshace entera: o se confirma todo, o no cambia nada.

## 3. Dos personas confirman la última unidad a la vez

```mermaid
sequenceDiagram
    participant X as Compra de Ana
    participant Y as Compra de Bruno
    participant DB as PostgreSQL (inventario: 1 unidad)

    X->>DB: bloquea la fila de inventario
    Y->>DB: intenta bloquear la misma fila
    Note over Y,DB: Bruno espera
    X->>DB: revalida (alcanza), descuenta, COMMIT. Stock: 0
    DB-->>Y: la fila queda libre
    Y->>DB: revalida con el stock actualizado: 0 disponible
    DB-->>Y: 409 INSUFFICIENT_STOCK, ROLLBACK
```

Hay un test con dos hilos reales que reproduce esta carrera: siempre una compra tiene éxito, la otra recibe `INSUFFICIENT_STOCK` y el stock nunca queda negativo.

## 4. Estados de la orden

```mermaid
stateDiagram-v2
    [*] --> pending_confirmation: POST /api/checkout
    pending_confirmation --> confirmed: confirmar (usuario, botón)
    pending_confirmation --> cancelled: cancelar (usuario)
    confirmed --> [*]
    cancelled --> [*]
```

`confirmed` y `cancelled` son finales: confirmar o cancelar de nuevo da `ORDER_NOT_PENDING`.

## 5. Historial de órdenes (RF-16)

`GET /api/orders` devuelve las órdenes de la sesión, de la más nueva a la más vieja. `GET /api/orders/{order_id}` devuelve una sola. Las dos son de solo lectura.

```mermaid
sequenceDiagram
    participant U as Usuario (interfaz)
    participant R as Router
    participant C as Caso de uso list_orders / get_order
    participant A as Repositorio de órdenes
    participant DB as PostgreSQL

    alt historial
        U->>R: GET /api/orders + X-Session-Id
        R->>C: list_orders(sesión)
        C->>A: list_for_session(sesión)
        A->>DB: órdenes de la sesión, de la más nueva a la más vieja
        A->>DB: las líneas de todas esas órdenes en una sola consulta
        C-->>U: 200 lista de órdenes (vacía si no hay)
    else una orden
        U->>R: GET /api/orders/ORD-... + X-Session-Id
        R->>C: get_order(sesión, orden)
        C->>A: get(orden, sesión)
        A->>DB: busca la orden filtrando por sesión
        alt no existe o es de otra sesión
            C-->>U: 404 ORDER_NOT_FOUND
        else existe
            C-->>U: 200 la orden con sus líneas
        end
    end
```

El historial incluye órdenes en los tres estados: pendientes, confirmadas y canceladas. Cada línea muestra el nombre y el precio copiados al crear la orden. Si después cambia el precio o el nombre del producto, el historial sigue mostrando lo que se pagó (precio congelado en la orden, RF-14). Una sesión nunca ve las órdenes de otra: buscar una orden ajena responde lo mismo que una que no existe.

## 6. Clases

```mermaid
classDiagram
    direction LR

    namespace Dominio {
        class Order {
            order_id
            status
            customer
            delivery
            items
            total
        }
        class OrderLine {
            product_id
            name
            unit_price
            quantity
            line_total
        }
        class plan_confirmation {
            <<función pura>>
            revalida stock y precio
            arma las asignaciones
        }
        class ConfirmationPlan {
            allocations
        }
        class excepciones {
            CartEmpty
            OrderNotFound
            OrderNotPending
            PriceChanged
            InsufficientStock
        }
    }

    namespace Aplicacion {
        class casos_de_uso {
            <<funciones>>
            checkout
            confirm_order
            cancel_order
            list_orders
            get_order
        }
        class OrderRepository {
            <<puerto>>
            create()
            confirm(decide)
            cancel()
            list_for_session()
            get()
        }
    }

    namespace Adaptadores {
        class SqlAlchemyOrderRepository {
            transacción y bloqueos
        }
        class orders_router {
            <<FastAPI>>
        }
    }

    orders_router ..> casos_de_uso : invoca
    casos_de_uso ..> OrderRepository : usa
    casos_de_uso ..> plan_confirmation : se la pasa como decide
    OrderRepository <|.. SqlAlchemyOrderRepository : implementa
    plan_confirmation ..> ConfirmationPlan : devuelve
    plan_confirmation ..> excepciones : lanza
    Order o-- OrderLine
```

El repositorio es dueño de la transacción y de los bloqueos. El dominio es dueño de las decisiones y no sabe nada de la base: recibe el stock y los precios ya leídos y devuelve un plan.
