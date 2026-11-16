# Flujo del carrito

Estos diagramas muestran lo que está implementado en el carrito (decisión 0006). Cada pedido lleva el encabezado `X-Session-Id`, que identifica el carrito.

## 1. Agregar un producto

`POST /api/cart/items` con `{ "product_id": "...", "quantity": 2 }`

```mermaid
sequenceDiagram
    participant C as Cliente
    participant R as Router (adapters/api)
    participant U as Caso de uso add_item
    participant A as Repositorio (adapters/persistence)
    participant DB as PostgreSQL

    C->>R: POST /api/cart/items + X-Session-Id
    alt falta la sesión
        R-->>C: 400 MISSING_SESSION
    else hay sesión
        R->>U: add_item(sesión, producto, cantidad)
        U->>U: la cantidad es un entero de 1 a 1000
        U->>A: product_stock_info(producto)
        A->>DB: nombre, activo, precio y stock total (leídos ahora)
        DB-->>A: datos actuales
        alt el producto no existe
            U-->>C: 404 PRODUCT_NOT_FOUND
        else inactivo o sin precio
            U-->>C: 409 PRODUCT_INACTIVE
        else se puede vender
            U->>A: add_quantity(sesión, producto, cantidad, verificación)
            A->>DB: crea el carrito si no existe y bloquea su fila (FOR UPDATE)
            A->>DB: lee la cantidad que ya había
            A->>A: verificación: cantidad total contra el stock disponible
            alt el total supera el stock
                A->>DB: rollback, sin cambios
                U-->>C: 409 INSUFFICIENT_STOCK con available_qty
            else alcanza
                A->>DB: guarda la cantidad total y commit
                U->>A: get_lines(sesión)
                A->>DB: líneas con precio y stock actuales
                U-->>C: 200 carrito con items, item_count y total
            end
        end
    end
```

El carrito no cambia el stock: solo lo consulta. El stock se descuenta al confirmar la compra.

## 2. Cambiar la cantidad, quitar y vaciar

```mermaid
flowchart TD
    A[PATCH /api/cart/items/id<br/>con quantity] --> B{¿El producto<br/>está en el carrito?}
    B -- no --> E1[404 PRODUCT_NOT_FOUND<br/>El producto no está en el carrito]
    B -- sí --> C{¿La cantidad nueva<br/>supera el stock?}
    C -- sí --> E2[409 INSUFFICIENT_STOCK]
    C -- no --> D[Fija la cantidad<br/>devuelve el carrito]

    F[DELETE /api/cart/items/id] --> G[Quita la línea si existe<br/>devuelve el carrito]
    H[DELETE /api/cart] --> I[Quita todas las líneas<br/>devuelve el carrito vacío]
```

Quitar es idempotente: quitar un producto que no está devuelve el carrito sin cambios.

## 3. Clases

```mermaid
classDiagram
    direction LR

    namespace Dominio {
        class Cart {
            items
            item_count
            total
        }
        class CartLine {
            product_id
            name
            unit_price
            quantity
            available_qty
            line_total
        }
        class ProductStockInfo {
            active
            has_price
            available_qty
        }
        class reglas {
            <<funciones>>
            validate_quantity()
            ensure_can_add()
        }
        class excepciones {
            InvalidQuantity
            InsufficientStock
            ProductInactive
            ItemNotInCart
        }
    }

    namespace Aplicacion {
        class casos_de_uso {
            <<funciones>>
            view_cart
            add_item
            set_quantity
            remove_item
            clear_cart
        }
        class CartRepository {
            <<puerto>>
            get_lines()
            product_stock_info()
            add_quantity()
            set_quantity()
            remove_item()
            clear()
        }
    }

    namespace Adaptadores {
        class SqlAlchemyCartRepository
        class cart_router {
            <<FastAPI>>
        }
        class get_session_id {
            <<dependencia>>
            X-Session-Id
        }
    }

    cart_router ..> get_session_id : exige la sesión
    cart_router ..> casos_de_uso : invoca
    casos_de_uso ..> CartRepository : usa
    casos_de_uso ..> reglas : aplica
    reglas ..> excepciones : lanza
    CartRepository <|.. SqlAlchemyCartRepository : implementa
    CartRepository ..> CartLine : devuelve
    CartRepository ..> ProductStockInfo : devuelve
    Cart o-- CartLine
```

`Cart` y `CartLine` calculan el subtotal, el total y la cantidad de unidades. No guardan nada: el precio llega del repositorio en cada lectura.
