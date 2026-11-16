# Decisión 0005: Herramientas del asistente y el dispatcher que las controla

- **Estado:** propuesta
- **Fecha:** 15/11/2026
- **Autores:** Agustín Vignolo y Florencia Mendoza (Grupo 8, N8B)

## Problema

El asistente es un modelo de lenguaje que puede pedir ejecutar herramientas: buscar productos, consultar precio y stock, comparar. Un modelo local de 8 mil millones de parámetros se equivoca: inventa nombres de herramientas, manda argumentos con el tipo incorrecto o pide cosas que no debería poder hacer.

La letra pide un asistente que ayude durante la compra (RF-03), que compare alternativas con información del sistema (RF-06) y que lea precio y disponibilidad siempre del estado actual (RF-07). Además, ninguna compra se registra sin confirmación explícita del usuario (RF-12).

Hay que decidir cuatro cosas:

1. Quién valida lo que pide el modelo antes de ejecutarlo.
2. Cómo se garantiza que el modelo no confirme una compra ni use la sesión de otra persona.
3. Qué devuelve la herramienta de búsqueda y de dónde salen el precio y el stock.
4. Qué pasa cuando la búsqueda por significado no encuentra nada realmente parecido.

## Qué es el dispatcher

Es el código que está entre el modelo y las herramientas. El modelo no ejecuta nada: escribe un pedido (`{"name": "get_price", "arguments": {...}}`) y el dispatcher decide si se ejecuta. Es la forma concreta de "el modelo propone, el software ejecuta" (clase 3, p.6 y p.12; clase 6, p.9).

## Alternativas

**1. Cómo se validan los argumentos**

| Opción | A favor | En contra |
|---|---|---|
| **Modelos de Pydantic con `extra="forbid"` (elegida)** | El mismo modelo valida los datos y genera el esquema JSON que se le da al modelo de lenguaje, así que se escribe una sola vez. Rechaza campos de más, tipos incorrectos y campos faltantes [2]. Ya es una dependencia del proyecto. | Los mensajes de error de Pydantic hay que reformularlos para que el modelo los entienda. |
| Librería `jsonschema` | Valida directamente contra un esquema JSON. | Hay que mantener el esquema y el código por separado. Una dependencia más. |
| Comprobaciones a mano en cada herramienta | Control total. | Se repite en cada herramienta y es fácil olvidarse de una. |

**2. Cómo se impide que el modelo confirme una compra**

| Opción | A favor | En contra |
|---|---|---|
| **Tabla de permisos en código, y las acciones prohibidas no se registran nunca (elegida)** | La tabla nombra cada herramienta y su permiso: libre, requiere confirmación o prohibida. `confirm_order` y `cancel_order` están marcadas como prohibidas, y el registro se niega a aceptarlas. Si el modelo las pide, recibe un error que le indica que solo el usuario puede hacerlo desde la interfaz. | Hay que mantener la tabla al día cuando se agrega una herramienta. Un test comprueba que cada herramienta registrada figure en ella. |
| Pedirle al modelo en el prompt que no lo haga | Cero código. | Un modelo puede ignorar una instrucción. No es una garantía (clase 6, p.9). |
| Dejar la herramienta pero pedir confirmación dentro del chat | Flujo corto. | La confirmación pasaría por el mismo modelo que se quiere controlar. Contradice la regla de que confirmar es una acción del usuario fuera del modelo (clase 6, p.10). |

**3. Qué devuelve la búsqueda**

| Opción | A favor | En contra |
|---|---|---|
| **Devuelve los productos con precio y stock leídos de la base en esa misma llamada (elegida)** | El modelo recibe todo lo necesario en un solo paso. Para un modelo chico, menos pasos son menos errores y menos demora. El índice sigue sin guardar precio ni stock: se leen de sus tablas en cada llamada. | La herramienta de búsqueda hace dos lecturas (el índice y las tablas de precio y stock). |
| Devuelve solo los identificadores y el modelo pide precio y stock por separado | Cada herramienta hace una sola cosa. | Un caso como "auriculares hasta USD 200" necesitaría una búsqueda y hasta cinco consultas de precio. Más pasos, más costo y más chances de que el modelo se equivoque o no las haga. |

**4. Qué hacer cuando nada se parece**

La búsqueda por significado siempre devuelve resultados, aunque ninguno sea relevante (decisión 0004). Para saber si conviene fijar un mínimo medimos el mejor puntaje de 16 consultas contra el índice real:

| Consultas | Mejor puntaje |
|---|---|
| 8 que sí están en el catálogo (auriculares, monitor gamer, teclado ergonómico, webcam, parlante, dock, etc.) | de 0.661 a 0.776 |
| 8 que no están (bananas, "PlayStation 9", entradas de un concierto, pasta, etc.) | de 0.494 a 0.588 |

Hay un hueco entre 0.588 y 0.661.

| Opción | A favor | En contra |
|---|---|---|
| **Puntaje mínimo de 0.62, configurable (elegida)** | Separa las dos muestras medidas. Si ningún producto lo supera, la herramienta devuelve una lista vacía con una nota que le indica al modelo que diga que el producto no está. Es la base del aviso de producto inexistente (RF-18). | Es un valor provisional (ver trade-offs). |
| Sin mínimo: que el modelo decida mirando los resultados | Cero código. | Un modelo chico tiende a recomendar lo que tiene delante, aunque sea irrelevante. Es justo el caso que RF-18 pide evitar. |
| Comparar contra la diferencia entre el primero y el último | No depende de un valor fijo. | En las muestras medidas el primero y el quinto difieren en menos de 0.04, tanto cuando hay coincidencia como cuando no, así que no distingue. |

## Decisión

- **Dispatcher.** Antes de ejecutar cualquier pedido del modelo comprueba, en este orden: que los argumentos sean un objeto, que la herramienta no esté prohibida, que exista, que no traiga `session_id`, y que los argumentos cumplan el esquema. Si algo falla, devuelve `{"error": ..., "hint": ...}` con una pista para corregir. Nunca lanza una excepción hacia el usuario (clase 3, p.18).
- **Mensajes de error útiles.** Para un nombre mal escrito, lista las herramientas disponibles y sugiere la parecida (`get_prize` devuelve "¿quisiste decir `get_price`?"). Para argumentos inválidos, indica el campo, el problema y el esquema esperado, sin repetir los valores enviados, que podrían contener datos personales.
- **Sesión.** El identificador de sesión lo agrega el sistema al ejecutar la herramienta. Si el modelo intenta mandarlo, el pedido se rechaza.
- **Permisos.** La tabla está en `application/agent/permissions.py`. Las herramientas de lectura son libres. Confirmar o cancelar una orden están prohibidas y no existen como herramientas. Un test comprueba que no se puedan registrar.
- **Seis herramientas de lectura.** `search_products`, `get_product_details`, `get_price`, `get_stock`, `compare_products` y `get_alternatives`. Cada descripción dice para qué sirve, cuándo usarla y qué devuelve (clase 3, p.18). Esquema en el formato que Ollama espera para las herramientas [3].
- **Precio y stock en cada llamada.** Las seis leen de la base en cada ejecución. Un test cambia el precio con SQL directo entre dos llamadas y comprueba que la segunda devuelve el valor nuevo.
- **Mínimo de similitud.** `SEARCH_MIN_SIMILARITY=0.62`. Lo aplica el caso de uso de búsqueda.
- **Qué falta.** `add_to_cart`, `view_cart` y `start_checkout` figuran en la tabla de permisos pero todavía no existen como herramientas, porque dependen del carrito y de la compra, que son otras tareas.

## Justificación

- **El modelo propone, el software ejecuta.** Un modelo local falla, así que la aplicación es la que controla qué se ejecuta, con qué argumentos y con qué permiso (clase 3, p.6 y p.12).
- **Confirmar una compra no puede depender del modelo (RF-12).** La garantía no es una instrucción en el prompt: la herramienta no existe y el registro rechaza registrarla. En la ejecución real, `confirm_order` devolvió el error con la indicación de usar los botones de la interfaz.
- **Información actual (RF-07).** Precio y stock se leen en cada llamada, y el índice no los contiene.
- **Producto inexistente (RF-18).** Con el mínimo, "fresh organic bananas" devolvió una lista vacía con la nota para el modelo en lugar de cinco productos sin relación.
- **Errores que el modelo puede corregir.** En la ejecución real, un nombre mal escrito, un `session_id` inventado y un precio máximo con texto devolvieron un error con la acción correctiva.

## Costos y riesgos (trade-offs)

- **El mínimo de 0.62 es provisional.** Se midió con 16 consultas elegidas por nosotros, todas en inglés. El margen es angosto: "electric guitar amplifier", que no está, llegó a 0.588 porque hay auriculares parecidos en significado. Se va a ajustar con la evaluación del asistente.
- **El puntaje mide parecido, no acierto.** "laptop for video editing" devolvió una webcam con 0.661. El umbral descarta lo claramente irrelevante, pero el asistente todavía tiene que decidir si lo que recibió responde al pedido.
- **El mínimo puede esconder un producto válido.** Si alguien pide algo con palabras muy distintas a las del catálogo, el puntaje baja y el asistente dirá que no lo tiene. Es el costo de evitar el caso contrario.
- **Las herramientas de consulta responden también para productos inactivos.** La búsqueda los excluye, pero `get_price`, `get_stock` y `get_product_details` no, porque una orden o un carrito viejo pueden referirse a ellos. La regla de que un producto activo siempre tiene precio, y el estado del producto (borrador o activo), quedan para una decisión aparte.
- **Los mensajes de error están en inglés.** Los lee el modelo, no el usuario. El usuario recibe la respuesta final del asistente, en español.
- **Un solo conjunto de herramientas por ahora.** Hasta que existan el carrito y la compra, el asistente puede buscar, comparar y consultar, pero no armar un pedido.

## Fuentes

1. Clases del curso: clase 3 (p.3-4 y p.16-17, precio y stock por herramientas; p.6 y p.12, el software valida antes de ejecutar; p.18, nombres claros, parámetros tipados y errores accionables) y clase 6 (p.9, permisos y mínimo privilegio, identificador de sesión puesto por el sistema; p.10, acciones que requieren confirmación humana).
2. Pydantic, *Configuration: extra* (`extra='forbid'` rechaza los campos que no están en el modelo): https://pydantic.dev/docs/validation/latest/api/pydantic/config
3. Ollama, *Tool calling* (cada herramienta se declara con nombre, descripción y un esquema de parámetros): https://docs.ollama.com/capabilities/tool-calling
