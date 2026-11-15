# Decisión 0003: Cómo la API de catálogo lee y devuelve los productos

- **Estado:** propuesta
- **Fecha:** 15/11/2026
- **Autores:** Agustín Vignolo y Florencia Mendoza (Grupo 8, N8B)

## Problema

La letra pide consultar y ver los productos del dataset (RF-01). El frontend y, más adelante, el asistente necesitan listar con filtros, ver el detalle y comparar productos. Hay que decidir cómo se construyen esas respuestas. Cuatro puntos no los fija el contrato de la API (`docs/api-contract.md`):

1. Cómo se filtra por texto libre.
2. Cómo se pagina y ordena sin repetir ni saltear productos.
3. Qué se hace con los productos inactivos o sin precio.
4. Qué forma tienen las categorías y los errores de validación.

Hay una restricción de arquitectura. El precio y el stock tienen que leerse de la base en cada pedido, sin copias guardadas (RF-07, información actual). El código del dominio no puede depender de FastAPI ni de SQLAlchemy (regla de arquitectura hexagonal de `AGENTS.md`).

## Alternativas

**1. Filtro por texto `q`**

| Opción | A favor | En contra |
|---|---|---|
| **`ILIKE` sobre nombre, marca y descripción corta (elegida)** | Una línea de SQL, sin índices ni columnas nuevas. Suficiente para 360 productos [1]. | No entiende sinónimos ni orden de palabras. |
| Búsqueda de texto completo de PostgreSQL (`tsvector`) [2] | Ranking y variantes de palabras. | Pide columna e índice nuevos y una configuración de idioma. El catálogo está en inglés y es chico. |
| Búsqueda semántica con embeddings | Entiende la intención del usuario. | Es otra tarea (búsqueda por significado, AI-01) y depende del modelo de embeddings. |

**2. Paginación y orden**

| Opción | A favor | En contra |
|---|---|---|
| **`LIMIT/OFFSET` con desempate por `product_id` (elegida)** | Simple. Permite saltar a cualquier página, como pide el contrato (`page`, `page_size`). Sin un orden total, PostgreSQL no garantiza qué filas devuelve cada página, por eso el desempate [3]. | `OFFSET` se vuelve lento con millones de filas. |
| Paginación por cursor (*keyset*) | Rinde parejo con tablas enormes. | No permite ir a la página N. Complica el contrato. Innecesario con 360 productos. |

**3. Productos inactivos o sin precio**

| Opción | A favor | En contra |
|---|---|---|
| **El listado oculta los inactivos. El detalle los devuelve (elegida)** | La tienda no ofrece lo que ya no se vende. Un carrito o una orden vieja siguen pudiendo mostrar el producto. | El detalle no marca si el producto está inactivo, porque el contrato no tiene ese campo. Agregar al carrito un producto inactivo lo rechazará la tarea del carrito con `PRODUCT_INACTIVE`. |
| Ocultarlos en todos lados | Más simple. | Una orden histórica no podría mostrar el producto. |

Si un producto no tiene fila de precio, devolvemos `price: null` y no un precio inventado. Queda fuera de los filtros de precio y al final de los ordenamientos por precio.

**4. Forma de las categorías y de los errores**

| Opción | A favor | En contra |
|---|---|---|
| **Categorías anidadas `[{category, subcategories[]}]` (elegida)** | Es la forma natural para un menú de filtros. Es la que usa el frontend de catálogo (PR #52). | Si el frontend quisiera una lista plana, la arma en una línea. |
| Lista plana (una fila por subcategoría) | Calca la tabla `categories`. | El frontend tiene que agrupar. |
| **Validación fallida como 400 `VALIDATION_ERROR` (elegida)** | Es lo que fija el contrato. Todos los errores comparten una sola forma. | Hay que reemplazar el 422 que FastAPI devuelve por defecto [4]. |
| Dejar el 422 por defecto | Cero código. | Contradice el contrato y el frontend tendría dos formatos de error. |

## Decisión

- **Arquitectura.** La API sigue la estructura hexagonal:
  - `domain/catalog.py`: tipos y excepciones puros.
  - `application/catalog.py`: casos de uso. La tabla de comparación se arma acá, con datos del dominio, no en SQL.
  - `application/ports.py`: el puerto `CatalogRepository`, que describe lo que el caso de uso necesita.
  - `adapters/persistence/catalog_repository.py`: la implementación con SQLAlchemy.
  - `adapters/api/`: routers y manejo de errores [5].
- **Precio y stock.** Se calculan con *joins* en cada pedido: precio desde `prices` y stock como la suma de `inventory.available_qty` de los cinco depósitos. No hay cache.
- **Texto, orden y páginas.** `q` es un `ILIKE` con los caracteres `%` y `_` escapados. Sin `sort`, el orden es por `product_id`. `page_size` mayor a 100 se recorta a 100. `page` o `page_size` menores a 1 dan error 400. `page` mayor a 10000 también da 400, para que el `OFFSET` no desborde en SQL.
- **Comparación.** Acepta de 2 a 4 productos distintos. Los ids repetidos se descartan. Los atributos son la unión de los de todos los productos y el que falta en alguno vale `null`. Las filas se identifican por grupo, nombre y unidad: si dos productos usan unidades distintas para el mismo atributo (por ejemplo `in` y `cm`), salen en filas separadas y ningún valor muestra una unidad ajena. Un id inexistente da 404 `PRODUCT_NOT_FOUND`.
- **Errores.** Un solo manejador convierte excepciones del dominio y errores de validación en `{"error": {"code", "message", "details"}}`. El error inesperado devuelve 500 `INTERNAL_ERROR` sin detalles técnicos. Los errores que lanza el framework usan códigos genéricos: 404 `NOT_FOUND`, 405 `METHOD_NOT_ALLOWED` y cualquier otro estado `HTTP_ERROR`, con el mismo cuerpo y el estado original. Estos códigos todavía no están en el contrato de la API.
- **Categorías.** Anidadas, ordenadas por categoría y orden de subcategoría. Pendiente de confirmación de Florencia en el PR #52.

## Justificación

- **Información actual (RF-07).** Leer precio y stock con *joins* en cada pedido evita que el catálogo muestre datos viejos. El asistente reutilizará los mismos casos de uso.
- **Un solo conjunto de consultas.** El listado y el detalle traen precio y stock en una sola consulta por pedido, así que no hay una consulta extra por producto.
- **Páginas estables.** El desempate por `product_id` hace que un producto no aparezca en dos páginas ni se pierda al cambiar de página [3].
- **Arquitectura evaluable.** Los casos de uso se prueban sin base de datos con un repositorio falso. Los endpoints se prueban contra PostgreSQL real, con cada test dentro de una transacción que se deshace.

## Costos y riesgos (trade-offs)

- **`ILIKE` no es búsqueda por significado.** "auriculares para videollamadas" no encuentra por intención. Eso lo resuelve la búsqueda semántica del asistente, no esta API.
- **`OFFSET` no escala a millones de filas.** Para el prototipo no importa. En producción se pasaría a paginación por cursor.
- **Mensajes de validación en inglés.** El `message` de cada campo con error viene de Pydantic y está en inglés. El mensaje general sí está en español. Si el frontend necesita mostrarlos, hay que traducirlos.
- **`price: null` es un caso nuevo para el frontend.** El contrato no lo prevé. Con el dataset actual no ocurre (los 360 productos tienen precio), pero un producto nuevo podría no tenerlo.
- **Error 500 con *stack trace* en el log.** Hoy no pasan datos personales por ahí. Cuando exista el checkout hay que revisar que el log no incluya nombre, email ni dirección.

## Fuentes

1. PostgreSQL 16, *Pattern Matching* (`LIKE` e `ILIKE`): https://www.postgresql.org/docs/16/functions-matching.html
2. PostgreSQL 16, *Full Text Search*: https://www.postgresql.org/docs/16/textsearch.html
3. PostgreSQL 16, *LIMIT and OFFSET* (sin `ORDER BY` el resultado no es predecible): https://www.postgresql.org/docs/16/queries-limit.html
4. FastAPI, *Handling Errors* (reemplazar el manejo de `RequestValidationError`): https://fastapi.tiangolo.com/tutorial/handling-errors/
5. Alistair Cockburn, *Hexagonal architecture*: https://alistair.cockburn.us/hexagonal-architecture/
