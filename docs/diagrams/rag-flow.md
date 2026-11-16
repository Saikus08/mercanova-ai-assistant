# Flujo de la búsqueda por significado

Estos diagramas muestran lo que está implementado en la búsqueda semántica (decisión 0004). La herramienta que la expone al asistente todavía no existe: hoy se usa el caso de uso `search_products` directamente.

## 1. Indexar los productos (una sola vez al cargar el catálogo)

`make embed`

```mermaid
sequenceDiagram
    participant S as Script embed
    participant I as Indexador (adapters/persistence)
    participant DB as PostgreSQL
    participant O as Ollama (nomic-embed-text)

    S->>I: run()
    I->>DB: lee productos y marcas
    I->>I: arma el texto de cada producto (sin precio, stock ni puntaje)
    I->>DB: lee los textos y el modelo ya guardados
    I->>I: separa los productos nuevos o cambiados
    loop de a 32 productos
        I->>O: POST /api/embed con "search_document: <texto>"
        O-->>I: vectores de 768 dimensiones
        I->>DB: upsert en product_embeddings y commit
    end
    I-->>S: total, embebidos y salteados
```

Si se corre otra vez sin cambios, la lista de productos nuevos o cambiados queda vacía y no llama a Ollama.

## 2. Buscar (cada consulta del asistente)

```mermaid
sequenceDiagram
    participant A as Asistente (tool, próxima tarea)
    participant U as Caso de uso search_products
    participant O as Ollama
    participant R as Repositorio (pgvector)
    participant DB as PostgreSQL

    A->>U: consulta en inglés + filtros (categoría, precio máximo)
    alt consulta vacía
        U-->>A: error de validación
    else consulta válida
        U->>O: POST /api/embed con "search_query: <consulta>"
        alt Ollama no responde
            O--xU: error
            U-->>A: SearchUnavailable
        else responde
            O-->>U: vector de 768 dimensiones
            U->>R: search(vector, filtros, K)
            R->>DB: una consulta: productos activos + filtros, precio e inventario leídos de sus tablas, orden por distancia coseno, LIMIT K
            DB-->>R: los K más cercanos
            R-->>U: id, nombre, descripción corta, similitud
            U-->>A: hasta 5 resultados, sin precio ni stock
        end
    end
```

El precio y el stock del resultado los consulta después la herramienta de precio y stock, siempre en el mismo turno.
