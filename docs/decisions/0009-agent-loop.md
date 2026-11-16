# Decisión 0009: El asistente es un agente con herramientas, y el software controla lo que el modelo propone

- **Estado:** propuesta
- **Fecha:** 16/11/2026
- **Autores:** Agustín Vignolo y Florencia Mendoza (Grupo 8, N8B)

## Problema

La letra pide un asistente que entienda pedidos en lenguaje natural y ayude durante la compra (RF-03), que recomiende y explique por qué (RF-04), que pida aclaraciones cuando el pedido es ambiguo (RF-05) y que nunca presente información que no esté en el sistema (RF-18).

Hay que decidir cuatro cosas:

1. Si el asistente es un agente que decide qué herramienta usar o un flujo fijo.
2. Qué recuerda el asistente entre un mensaje y el siguiente, y qué le mandamos al modelo.
3. Cómo se corta el ciclo para que nunca quede dando vueltas.
4. Cómo se controla un modelo local de 8 mil millones de parámetros que se equivoca.

La cuarta pregunta salió de probar el modelo real y no de la teoría. Con `llama3.1:8b`, sin ningún control del software, vimos todos estos fallos:

- escribió la búsqueda en español, cuando el catálogo está en inglés;
- ante "Quiero un monitor" no preguntó nada: inventó un precio máximo de USD 1000 y buscó;
- recomendó productos antes de aclarar;
- le dijo al cliente que usara `start_checkout`, el nombre de una herramienta interna;
- marcó "no encontré nada" en una respuesta que sí traía productos.

## Alternativas

**1. Agente con herramientas o flujo fijo**

| Opción | A favor | En contra |
|---|---|---|
| **Agente con herramientas, con reglas fijas que el software hace cumplir (elegida)** | El modelo elige entre buscar, comparar, consultar precio y stock o preparar la compra según lo que dice el usuario, sin que haya que programar cada frase. Las reglas que no pueden fallar (precios, confirmaciones, datos personales) las hace cumplir el software, no el modelo. | Más lento y menos predecible que un flujo fijo. Un modelo chico se equivoca, y por eso hace falta el control del software. |
| Flujo fijo: clasificar la intención y ejecutar siempre los mismos pasos | Predecible, rápido y barato. | Hay que anticipar cada forma de pedir algo: buscar con filtros, comparar "el primero con el segundo", agregar al carrito, "comprámelo". Necesita igual un modelo para clasificar la intención y se vuelve una lista de reglas que crece. La clase 5 plantea que no todo problema necesita un agente (p.7 y p.11), y acá los pedidos son abiertos. |
| Varios agentes que se reparten el trabajo | Separa responsabilidades. | La letra lo deja fuera de alcance, y para este problema no aporta: un solo agente con las herramientas alcanza. |

**2. Qué recuerda el asistente y qué ve el modelo**

| Opción | A favor | En contra |
|---|---|---|
| **Estado explícito, separado del historial (elegida)** | El estado guarda el objetivo, los productos ya mostrados en orden, las herramientas usadas y el paso actual (clase 5, p.9; clase 6, p.3-5). Así "compará el primero con el segundo" sabe qué productos son, sin releer toda la conversación. | Hay que mantener el estado al día después de cada herramienta. |
| Mandar todo el historial al modelo | Cero código de estado. | Cada turno cuesta más contexto, más tiempo y más ruido ("buen contexto no es mucho contexto", clase 6, p.4). |
| Memoria entre sesiones | El asistente "te conoce". | La letra no la pide y la clase 6 (p.6) la presenta como opcional. Queda fuera de alcance. |

**3. Cómo obtener una respuesta estructurada**

| Opción | A favor | En contra |
|---|---|---|
| **Dos fases: primero el modelo usa herramientas, y después una llamada final con un esquema JSON (elegida)** | La fase de herramientas no obliga a responder en JSON. La fase final sí, con el esquema que Ollama acepta en el parámetro `format` [1]. Se puede validar la respuesta y reintentar. | Una llamada más al modelo por turno (unos 2 o 3 segundos con GPU). |
| Una sola llamada con herramientas y esquema a la vez | Una llamada menos. | No lo probamos y no hay garantía de que un modelo chico combine las dos cosas. |
| Pedir JSON en el prompt y leerlo a mano | Sin dependencia del esquema. | Falla más seguido y hay que parsear respuestas sueltas. |

**4. Cómo se controla un modelo que se equivoca**

| Opción | A favor | En contra |
|---|---|---|
| **El software verifica antes de ejecutar y antes de responder (elegida)** | "El modelo propone, el software ejecuta" (clase 3, p.6 y p.12; clase 6, p.9). Las reglas son código con tests y no dependen de que el modelo obedezca. | Más código en el ciclo. Algunas reglas son heurísticas (ver trade-offs). |
| Solo un prompt más detallado | Cero código. | Es lo que se probó primero, y el modelo seguía fallando. Un prompt es una sugerencia, no una garantía. |

## Decisión

- **Ciclo.** El modelo recibe el prompt del sistema, el estado y los últimos mensajes, y puede pedir herramientas. El dispatcher (decisión 0005) valida y ejecuta cada pedido, y el resultado vuelve al modelo. Se repite hasta que el modelo deja de pedir herramientas.
- **Cortes.** Termina cuando hay respuesta, al llegar a `AGENT_MAX_STEPS` (6 llamadas por defecto), si el modelo no está disponible, o si manda dos llamadas inválidas seguidas. En los tres últimos casos responde un mensaje fijo, degradado pero honesto, en español. La clase 5 (p.8) y la clase 6 (p.7-8) piden una condición de corte.
- **Estado.** Objetivo, productos mostrados (con su orden), herramientas usadas y paso. Se arma de nuevo para cada turno con lo que ya sabe la conversación. Al modelo se le mandan solo los últimos 8 mensajes de usuario y asistente, y los resultados de herramientas de turnos anteriores no se arrastran.
- **Respuesta final estructurada.** Texto para el cliente, hasta 3 recomendaciones (id y motivo), una aclaración opcional con 2 a 4 opciones y un "no encontrado" opcional.
- **Controles del software**, cada uno con tests:
  - **Búsqueda demasiado vaga.** Si todo lo que dijo el cliente son 3 palabras o menos, sin números, y la búsqueda no trae filtros, no se ejecuta. El modelo recibe la indicación de hacer una pregunta primero. Si después de esto la respuesta no trae aclaración, el software agrega una pregunta fija ("¿Para qué lo vas a usar y cuál es tu presupuesto máximo?") y elimina las recomendaciones.
  - **Filtros de precio inventados.** Un `max_price` o `min_price` que el cliente no dijo no se ejecuta.
  - **Una llamada inválida se puede corregir una vez.** La segunda seguida corta el turno.
  - **Montos en la respuesta.** Todo monto con USD, US$ o $ en el texto o en los motivos tiene que figurar en un resultado de herramienta de ese turno, o en lo que dijo el cliente. Si no, hay un reintento. Si persiste, respuesta degradada.
  - **Nombres de herramientas.** El texto no puede mencionarlas. Hay un reintento.
  - **Tarjetas de producto.** Las arma el software con lo que devolvió la herramienta. El modelo solo aporta el motivo. Un id que ninguna herramienta devolvió se descarta.
  - **"No encontrado".** Se descarta si hay productos. Si la búsqueda no encontró nada y el modelo no lo marcó, lo completa el software con la consulta buscada.
  - **Productos encontrados pero sin recomendación.** Un reintento. Si el modelo sigue sin recomendar, el software muestra los 3 primeros resultados, con la descripción corta del catálogo como motivo, y marca el resultado con `fallback_used`. Así el producto no depende de que el modelo acierte siempre, y la debilidad del modelo queda medible.
- **Modelo y temperatura.** Temperatura 0,1, contexto de 8 mil tokens y un límite de espera de 120 segundos por llamada. Para desarrollo y pruebas usamos `llama3.1:8b` (el valor por defecto sigue siendo el de la decisión 0001 hasta la comparación de modelos).
- **Registro.** Cada llamada al modelo y a una herramienta deja una línea con identificador de traza, paso, duración y tokens, sin el contenido de los mensajes (regla del asistente sobre observabilidad; clase 7, p.9-10).

## Justificación

- **Medición con el modelo real.** Se corrieron 10 veces los casos más difíciles, con `llama3.1:8b` y el catálogo cargado:

| Caso | Resultado en 10 corridas |
|---|---|
| 1. Auriculares para videollamadas, máximo USD 200 | Siempre buscó con `max_price = 200`. 8 veces recomendó el modelo y 2 veces el respaldo. Los precios de las tarjetas fueron de menos de USD 200 en las 10. Unos 11 segundos por turno. |
| 2. "Quiero un monitor" | Las 10 veces pidió una aclaración, con 0 búsquedas ejecutadas y 0 recomendaciones. |
| "¿Cuánto sale una PlayStation 9?" | Las 10 veces respondió que no está, sin recomendaciones ni precios. |

- **Sin los controles el resultado era peor.** En las pruebas previas a agregarlos, el caso 2 recomendaba productos en lugar de preguntar, y en una corrida del caso 1 el texto mencionaba una herramienta interna.
- **Los precios no pueden ser inventados (RF-18).** El precio de una tarjeta es el de la herramienta. El texto no puede nombrar un monto que no vino de una herramienta ni del cliente.
- **Caso de uso 3 (comparar).** El estado le dice al modelo qué productos mostró y en qué orden. En todas las corridas de evaluación del caso 3 que hicimos (sin una tasa medida aparte, a diferencia de los otros casos), el modelo llamó a `compare_products` con los dos ids en el orden mostrado.

## Costos y riesgos (trade-offs)

- **Las cifras son de una muestra chica.** Son 3 consultas, 10 corridas cada una, un modelo, un catálogo de 360 productos y temperatura baja. Muestran que los controles funcionan, no la tasa real de aciertos. La comparación entre modelos (tarea de evaluación) con casos difíciles y adversariales es la que mide eso.
- **El modelo no es determinista.** Dos corridas del mismo pedido pueden dar respuestas distintas. En una medición previa a agregar el respaldo, el caso 1 falló 2 de 3 veces. Por eso los tests del ciclo usan un modelo simulado y las pruebas con el modelo real son aparte, no corren en el CI y se miden con varias corridas.
- **El respaldo oculta un fallo del modelo si no se mira.** Por eso el resultado lo marca con `fallback_used` y las evaluaciones lo imprimen. Hay que contarlo al comparar modelos.
- **El texto de una comparación es flojo.** En las pruebas, el texto que acompañaba una comparación repetía la recomendación anterior en lugar de resumir diferencias. La tabla de la comparación sale de los datos de la herramienta y es correcta.
- **Las reglas son heurísticas.**
  - "3 palabras o menos y sin números" puede frenar un pedido corto pero claro. El costo es una pregunta de más. Un pedido vago de 4 palabras no se frena.
  - Un presupuesto escrito con letras ("doscientos dólares") no cuenta como dicho por el cliente, así que el filtro se rechaza.
  - La detección de montos mira solo números junto a una marca de moneda. Una cifra suelta ("cuesta 85") no se controla.
  - Un número decimal con exactamente tres decimales se lee como separador de miles.
- **Un turno son entre 3 mil y 6 mil tokens.** La mayor parte es el prompt con las herramientas. Con GPU son 8 a 11 segundos por turno. En CPU dentro de Docker medimos cerca de 1 token por segundo, que no sirve para una demo: por eso se corre Ollama directo en la Mac (README).
- **El estado vive en memoria durante el turno.** Guardarlo entre mensajes es parte del endpoint de chat.
- **Las tarjetas traen menos campos que el contrato.** Las tarjetas salen de las herramientas, que no devuelven SKU, imagen ni puntaje. El endpoint de chat las completa leyendo la base.
- **Los mensajes degradados están fijos en español**, no los genera el modelo.

## Fuentes

1. Ollama, *Structured outputs* (el parámetro `format` acepta un esquema JSON): https://docs.ollama.com/capabilities/structured-outputs
2. Ollama, *Tool calling*: https://docs.ollama.com/capabilities/tool-calling
3. Ollama, *API: chat* (parámetros `tools`, `format`, `options` y `think`): https://docs.ollama.com/api/chat
4. Clases del curso: clase 1 (p.9 y p.17-20, temperatura baja y salidas estructuradas), clase 3 (p.6, p.12 y p.18, el software valida y los errores son accionables), clase 5 (p.7-9 y p.11, agente o flujo fijo, estado y cortes), clase 6 (p.3-9, contexto, estado, memoria y reintentos) y clase 7 (p.9-13, observabilidad y guardrails).
5. Decisiones 0001 (modelo y búsqueda en inglés), 0004 (búsqueda), 0005 (dispatcher y herramientas) y 0008 (la compra desde el chat).
