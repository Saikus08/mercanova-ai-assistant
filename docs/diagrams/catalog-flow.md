# Flujo de un pedido a la API de catálogo

Estos diagramas muestran cómo viaja un pedido por las capas del backend, tal como está implementado. Cada capa solo conoce a la de abajo a través de un puerto (interfaz): el dominio no importa FastAPI ni SQLAlchemy.

## Detalle de un producto

`GET /api/products/{product_id}`

```mermaid
sequenceDiagram
    participant C as Cliente (frontend)
    participant R as Router (adapters/api)
    participant U as Caso de uso (application)
    participant A as Repositorio SQLAlchemy (adapters/persistence)
    participant DB as PostgreSQL

    C->>R: GET /api/products/MN-HDP-0001
    R->>R: Depends: abre la sesión y arma el repositorio
    R->>U: get_product(product_id)
    U->>A: get_detail(product_id) por el puerto CatalogRepository
    A->>DB: producto + precio + stock total (joins)
    A->>DB: stock por depósito, relacionados, especificaciones
    DB-->>A: filas
    A-->>U: ProductDetail (tipo del dominio)
    alt el producto no existe
        U-->>R: ProductNotFound
        R-->>C: 404 {"error": {"code": "PRODUCT_NOT_FOUND", ...}}
    else existe
        U-->>R: ProductDetail
        R-->>C: 200 JSON validado con response_model
    end
```

## Listado con filtros

`GET /api/products?q=headphone&max_price=200&sort=rating&page=1`

```mermaid
sequenceDiagram
    participant C as Cliente
    participant R as Router
    participant U as Caso de uso
    participant A as Repositorio
    participant DB as PostgreSQL

    C->>R: GET /api/products?q=headphone&max_price=200&sort=rating
    R->>R: FastAPI valida los parámetros
    alt parámetro inválido
        R-->>C: 400 {"error": {"code": "VALIDATION_ERROR", ...}}
    else válidos
        R->>U: list_products(filtros, sort, page, page_size)
        U->>A: list_products(...)
        A->>DB: SELECT count(*) con los mismos filtros
        A->>DB: SELECT con joins, ORDER BY sort + product_id, LIMIT, OFFSET
        DB-->>A: total y filas
        A-->>U: ProductPage
        U-->>R: ProductPage
        R-->>C: 200 {"items", "page", "page_size", "total"}
    end
```

## Comparación

`GET /api/products/compare?ids=A,B`

El caso de uso pide al repositorio los productos y sus especificaciones, y arma la tabla de atributos con datos del dominio, no con SQL:

```mermaid
sequenceDiagram
    participant C as Cliente
    participant R as Router
    participant U as Caso de uso
    participant A as Repositorio

    C->>R: GET /api/products/compare?ids=A,B
    R->>U: compare_products([A, B])
    U->>U: descarta ids repetidos y exige de 2 a 4
    U->>A: get_summaries([A, B]) y get_specifications([A, B])
    A-->>U: resúmenes y especificaciones
    alt falta algún id
        U-->>R: ProductNotFound
        R-->>C: 404 PRODUCT_NOT_FOUND
    else todos existen
        U->>U: une los atributos por (grupo, nombre); el faltante vale null
        U-->>R: Comparison
        R-->>C: 200 {"products": [...], "attributes": [...]}
    end
```

El router de `compare` se declara antes que el de `/{product_id}`. Si no, FastAPI tomaría `compare` como un identificador de producto.
