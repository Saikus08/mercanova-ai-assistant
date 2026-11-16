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

## 3. Clases y capas

Cada capa solo conoce a la de adentro a través de una interfaz (puerto). El dominio no importa FastAPI, SQLAlchemy ni Ollama. Los adaptadores implementan los puertos.

```mermaid
classDiagram
    direction LR

    namespace Dominio {
        class SearchFilters {
            category
            subcategory
            brand
            min_price
            max_price
            in_stock
        }
        class SearchHit {
            product_id
            name
            score
            short_description
        }
        class ProductDocumentSource {
            name
            brand
            category
            description
            key_features
            recommended_for
            tags
        }
        class SearchUnavailable
    }

    namespace Aplicacion {
        class search_products {
            <<caso de uso>>
            query, filters, top_k
        }
        class EmbeddingModel {
            <<puerto>>
            index_id
            embed_documents(texts)
            embed_query(text)
        }
        class SemanticSearch {
            <<puerto>>
            search(vector, filters, top_k, index_id)
        }
    }

    namespace Adaptadores {
        class OllamaEmbeddings {
            DOCUMENT_PREFIX
            QUERY_PREFIX
        }
        class SqlAlchemySemanticSearch
        class EmbeddingIndexer {
            run()
        }
    }

    search_products ..> EmbeddingModel : usa
    search_products ..> SemanticSearch : usa
    search_products ..> SearchFilters
    search_products ..> SearchHit : devuelve
    EmbeddingModel <|.. OllamaEmbeddings : implementa
    SemanticSearch <|.. SqlAlchemySemanticSearch : implementa
    EmbeddingIndexer ..> EmbeddingModel : usa
    EmbeddingIndexer ..> ProductDocumentSource : arma el texto
    OllamaEmbeddings ..> SearchUnavailable : lanza
```

`ProductDocumentSource` no tiene precio, stock ni puntaje: es lo que garantiza que esos datos nunca entren al índice. El prefijo del modelo (`search_document:` y `search_query:`) vive solo en `OllamaEmbeddings`.
