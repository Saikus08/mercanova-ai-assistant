# Decisión 0004: Búsqueda por significado (RAG) sobre los datos estáticos

- **Estado:** propuesta
- **Fecha:** 15/11/2026
- **Autores:** Agustín Vignolo y Florencia Mendoza (Grupo 8, N8B)

## Problema

La letra pide buscar productos a partir de lo que el usuario necesita, dicho en lenguaje natural (RF-02). Un pedido como "auriculares cómodos para videollamadas, máximo USD 200" no se resuelve con un filtro por palabra: hay que entender la intención.

Esa búsqueda tiene que respetar una regla de arquitectura del proyecto. El contenido estático del producto (descripción, características, para qué se recomienda) puede recuperarse por significado. El **precio y el stock no**: se leen de la base en cada consulta (información actual, RF-07). Si estuvieran dentro del índice quedarían desactualizados y el asistente podría decir un precio que ya no es real.

Hay que decidir cuatro cosas: qué texto se indexa, cómo se parte, cuántos resultados se recuperan y cómo se combinan la búsqueda por significado con los filtros de precio y categoría.

## Alternativas

**1. Unidad de fragmento (*chunk*)**

| Opción | A favor | En contra |
|---|---|---|
| **1 producto = 1 fragmento (elegida)** | Las fichas son cortas: 594 caracteres en promedio y 712 como máximo en los 360 productos. Un solo vector conserva la relación entre la descripción, las características y el "para qué sirve". Cada resultado ya es un producto, sin reconstruir nada. | Una ficha muy larga mezclaría temas en un solo vector. No pasa con este catálogo. |
| Un fragmento por campo (descripción, características, recomendado para) | Vectores más específicos. | Cada producto tendría 3 o 4 vectores. Hay que agrupar los resultados por producto. Se separa lo que en el texto va junto. |
| Fragmentos de tamaño fijo con solapamiento | Estándar para documentos largos. | Las fichas ya caben enteras. Partirlas corta frases por la mitad sin aportar nada. |

**2. Cómo se combina la búsqueda por significado con los filtros**

| Opción | A favor | En contra |
|---|---|---|
| **Filtrar y ordenar en la misma consulta SQL (elegida)** | Los filtros (categoría, marca, precio, stock) se aplican antes de elegir los K mejores, así que siempre salen K resultados que cumplen. El precio y el stock se leen de sus tablas en esa misma consulta. | El filtro y el orden dependen de PostgreSQL. |
| Buscar los K más cercanos y filtrar después | Más simple de escribir. | Si los K más cercanos no cumplen el filtro, devuelve menos resultados o ninguno. Con "máximo USD 200" puede dejar la lista vacía. |

**3. Índice vectorial**

| Opción | A favor | En contra |
|---|---|---|
| **Sin índice, búsqueda exacta (elegida)** | Sin un índice aproximado, pgvector compara contra todas las filas y devuelve el resultado exacto [1]. Con 360 productos tarda milisegundos. | No escala a millones de filas. |
| Índice HNSW o IVFFlat | Rinde con muchos datos. | Es una búsqueda aproximada: puede omitir el mejor resultado. No aporta nada con 360 filas [1]. |

**4. Cuántos resultados recuperar (Top-K)**

| Opción | A favor | En contra |
|---|---|---|
| **Máximo 5, por defecto 5 (elegida)** | La clase 2 pide recuperar pocos resultados (de 3 a 5) y no todo el catálogo (clase 2, p.6). Menos texto en el contexto del modelo es menos costo y menos ruido. | Si el usuario pide "mostrame todos", no los ve. Para eso está el listado con filtros del catálogo. |
| 10 o más | Más cobertura. | Más contexto para el modelo y más productos para elegir mal. |

## Decisión

- **Qué se indexa.** Por cada producto, un texto con nombre, marca, categoría, subcategoría, descripción corta, descripción, características, "recomendado para", "no recomendado para" y etiquetas. **Nunca** precio, stock ni puntaje. Lo arma una función pura del dominio, siempre en el mismo orden.
- **Cuándo se generan los vectores.** Una sola vez al cargar el catálogo, con `make embed`. No se generan en cada consulta (clase 2, p.13). El comando solo recalcula los productos nuevos o cuyo texto cambió, así que correrlo dos veces seguidas no hace nada.
- **Modelo de embeddings.** `nomic-embed-text` en Ollama, de 768 dimensiones (decisión 0001). El cliente habla directo con la API de Ollama [2], sin LangChain.
- **Prefijos de tarea.** El modelo exige un prefijo: `search_document: ` para los textos que se indexan y `search_query: ` para la consulta del usuario [3]. Lo agrega el adaptador de Ollama, porque es un detalle de este modelo. El texto guardado en la base no lleva prefijo. La columna `model` guarda el nombre del modelo con la versión del esquema de prefijos (`nomic-embed-text+task-prefix-v1`), así que cambiar cualquiera de los dos obliga a reindexar.
- **Búsqueda.** Una sola consulta SQL: une productos, vectores, marcas, precios y la suma del stock; aplica los filtros; ordena por distancia coseno y devuelve los K mejores. Solo entran los productos activos [1].
- **Qué devuelve.** El identificador, el nombre, la descripción corta y el puntaje de similitud (de 0 a 1). **No** devuelve precio ni stock: los lee después la herramienta correspondiente.
- **Argumentos de la búsqueda.** El modelo de lenguaje extrae la consulta, la categoría y el precio máximo como argumentos tipados (clase 1, p.20; clase 2, p.15-16). La consulta va en inglés (decisión 0001).
- **Sin endpoint HTTP.** Esta tarea entrega el caso de uso y el adaptador. La herramienta `search_products` que los expone al asistente es otra tarea.

## Justificación

- **Información actual (RF-07).** Precio y stock nunca están en el índice. Los filtros por precio y stock leen las tablas `prices` e `inventory` en la misma consulta. Un test cambia un precio en la base entre dos búsquedas y comprueba que el resultado cambia.
- **Filtros que no vacían la lista.** Filtrar dentro de la consulta garantiza que "máximo USD 200" devuelva productos de ese rango.
- **Defecto encontrado y corregido.** La primera versión mandaba el texto sin prefijo. La ficha del modelo indica que el prefijo es obligatorio [3]. Al corregirlo, el mejor resultado del caso de uso 1 subió de 0.649 a 0.668 de similitud y cambió el orden de los productos.
- **Resultado sobre datos reales.** Con los 360 productos indexados, la consulta "comfortable headphones for work and video calls" con tope de USD 200 devuelve 5 auriculares, todos de menos de USD 200 (entre USD 85,32 y USD 182,94).

## Costos y riesgos (trade-offs)

- **La búsqueda siempre devuelve K resultados, aunque nada sea relevante.** La consulta "PlayStation 9 console", que no existe en el catálogo, devolvió 5 productos con similitud entre 0.537 y 0.563. Los productos relevantes del caso 1 estuvieron entre 0.659 y 0.668. Hay un hueco, pero con una sola muestra no alcanza para fijar un umbral. **Esto no alcanza para cumplir "decir que no está en el catálogo" (RF-18).** Hay que combinar un puntaje mínimo con la decisión del asistente, y fijar el umbral midiendo con los casos de evaluación. Queda como trabajo del agente y de las evaluaciones.
- **Los puntajes son parecidos entre sí.** Los cinco mejores auriculares difieren en menos de 0.01. El catálogo es homogéneo: todos los auriculares dicen ser buenos para "calls", y ninguno menciona "videollamadas". El modelo no puede separar lo que el texto no distingue.
- **Un modelo en inglés.** `nomic-embed-text` se publicó para inglés (decisión 0001). Por eso la consulta la escribe el asistente en inglés.
- **Indexar es lento en CPU.** Embeber los 360 productos tardó unos 3 minutos. Es un costo de una sola vez, no de cada consulta.
- **Escala.** La búsqueda exacta sin índice sirve para cientos de productos. En producción habría que sumar un índice aproximado [1].
- **Los productos inactivos se indexan pero no se devuelven.** Así, si se reactivan, no hay que reindexar.

## Fuentes

1. pgvector, *README* (distancia coseno, búsqueda exacta sin índice, índices HNSW e IVFFlat aproximados): https://github.com/pgvector/pgvector
2. Ollama, *API: Generate embeddings* (`/api/embed`): https://github.com/ollama/ollama/blob/main/docs/api.md
3. Nomic AI, *nomic-embed-text-v1.5* (prefijos de tarea `search_document` y `search_query`, obligatorios): https://huggingface.co/nomic-ai/nomic-embed-text-v1.5
4. Clases del curso: clase 1 (p.20, salidas estructuradas) y clase 2 (p.6, Top-K; p.11-16, fragmentos, embeddings y búsqueda híbrida).
