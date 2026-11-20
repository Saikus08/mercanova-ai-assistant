# Decisión 0013: Guardrail de entrada con una marca en la respuesta final, y guardrail de salida para stock e ids

- **Estado:** propuesta
- **Fecha:** 20/11/2026
- **Autores:** Agustín Vignolo y Florencia Mendoza (Grupo 8, N8B)

## Problema

El asistente tiene que cumplir dos protecciones que pide el curso (clase 7, p.11-13):

1. **Guardrail de entrada.** Un pedido fuera del dominio de la tienda, como una receta o quién ganó un mundial, se rechaza con amabilidad. Hasta ahora solo lo pedía el prompt. Ningún control del software lo hacía cumplir: si el modelo contestaba la receta, la receta llegaba al cliente.
2. **Guardrail de salida.** Todo precio, cifra de stock e identificador de producto de la respuesta tiene que salir de una herramienta del turno. Es la forma verificable de cumplir la información actual de precio y stock (RF-07) y no presentar datos que no están en el sistema (RF-18). El ciclo del agente (decisión 0009) ya verificaba los montos de dinero y descartaba las tarjetas con ids desconocidos. No verificaba las cifras de stock ("quedan 7 unidades") ni los ids de producto escritos en el texto.

## Alternativas

Para el guardrail de entrada:

| Opción | A favor | En contra |
|---|---|---|
| **Campo `out_of_scope` en el esquema de la respuesta final. Si el modelo lo marca, el software reemplaza el texto por un mensaje fijo (elegida)** | No suma llamadas al modelo: la respuesta final ya es un JSON con esquema. El texto que llega al cliente lo escribe el software, así que una receta nunca se filtra aunque el modelo la haya escrito. | La clasificación la sigue haciendo el modelo. Si el modelo no marca el campo, el pedido pasa. Si ya llamó a herramientas antes de la respuesta final, esas llamadas se gastan. |
| Una llamada extra al modelo, antes del ciclo, que solo clasifica el mensaje | Corta antes de llamar a herramientas. La clasificación queda aislada en su propio prompt. | Suma una llamada en **todos** los turnos. Con un modelo local de 8B en CPU, cada llamada agrega segundos, y el turno ya tiene un tope de 90 s (decisión 0009). |
| Lista de palabras prohibidas o permitidas | No usa el modelo. Es determinística. | Es frágil: "receta" puede ser "una balanza para recetas" y no hay una lista que cubra todo lo que no es de la tienda. Rechazaría pedidos válidos. |
| Solo la regla del prompt (lo que había) | Sin código. | No es un control del software. La skill `backend-feature` pide hacer cumplir las reglas en el software, no en el prompt. |

Para el guardrail de salida, la única opción razonable es extender el control que ya existe para los montos. Se compara contra los mismos datos: los resultados de las herramientas del turno y lo que escribió el cliente.

## Decisión

**Entrada.**
- La respuesta final tiene un campo nuevo `out_of_scope` (falso por defecto). El prompt del sistema y la instrucción final le piden al modelo que lo marque solo cuando el pedido no tiene nada que ver con comprar en la tienda. Un saludo o una pregunta sobre productos, el carrito, las órdenes o la entrega no cuentan.
- Si el modelo lo marca, el software descarta su texto y responde: "Solo puedo ayudarte con compras en MercaNova: buscar productos, compararlos, consultar precios y stock, y armar tu carrito. ¿Qué estás buscando?". No se arman bloques y el objetivo de compra del estado no cambia.
- Si la misma respuesta también recomienda productos o hace una pregunta de aclaración, la marca se ignora. Es una respuesta contradictoria, y un error del modelo no debe ocultar productos que el cliente sí pidió.
- El resultado del turno lleva `out_of_scope=true` para que la evaluación y los registros lo vean.

**Salida.**
- Además de los montos, el texto de la respuesta y las razones de cada recomendación se revisan buscando:
  - **cifras de stock**: un número seguido de "unidad", "unidades", "disponible(s)" o "en stock", o precedido de "quedan", "queda" o "stock";
  - **ids de producto**: palabras con la forma `MN-...`.
- Una cifra de stock se acepta si apareció en un resultado de herramienta del turno o en un mensaje del cliente (por ejemplo, "quiero 3 unidades").
- Un id se acepta si lo devolvió una herramienta del turno (también `get_price` o `get_stock`, que no devuelven tarjetas), si se le mostró al cliente en un turno anterior y está en el estado, o si lo escribió el cliente.
- Si algo no cumple, el modelo recibe un reintento con el problema concreto. Si sigue mal, el turno termina con la respuesta degradada de siempre, ahora con el texto "No pude verificar los precios, el stock o los productos en este turno…".

## Justificación

- **Hacer cumplir la regla en el software (clase 7, p.12).** En los dos guardrails, lo que llega al cliente lo controla el código. El modelo solo propone.
- **Costo y latencia.** La marca va en la respuesta final, que ya existe. No suma llamadas. En la comparación de modelos (`docs/model-comparison.md`, casos C15 y C16), `qwen3:8b`, el modelo elegido en la decisión 0011, ya rechazó los dos pedidos fuera de dominio en 3 de 3 corridas sin llamar a herramientas. Lo que faltaba no era que el modelo los reconociera, sino que el software garantizara el mensaje.
- **Ids de turnos anteriores.** Un id es un dato fijo del catálogo, no un dato que cambia como el precio o el stock. Ya está en el estado porque una herramienta lo devolvió antes. Exigir una herramienta nueva solo para nombrarlo obligaría a llamadas innecesarias. La misma regla ya se usaba para los argumentos de las herramientas.

## Costos y riesgos (trade-offs)

- **Si el modelo no marca `out_of_scope`, el pedido pasa.** Contra eso quedan la regla del prompt y los casos C15 y C16 de la evaluación, que miden el comportamiento. Un clasificador aparte sería más robusto, pero cuesta una llamada por turno.
- **Llamadas gastadas.** Un modelo que primero busca "milanesa" y después marca `out_of_scope` gasta esas llamadas. El cliente no ve el resultado.
- **Las expresiones de stock no cubren todas las formas de decirlo.** "Te quedan tres" (con el número en letras) o "hay 7" (sin la palabra "unidades") no se detectan. Se eligió no revisar "hay N" porque marcaría cosas que no son stock ("hay 2 modelos"). Los montos y las cifras con "unidades" son las formas que usa el modelo en las pruebas.
- **Falsos positivos.** Una característica escrita como "4 unidades de almacenamiento" que no esté en el resultado de la herramienta dispararía un reintento. El costo es una llamada más, no una respuesta incorrecta.

## Fuentes

1. Clases del curso: clase 7 (p.11-12, guardrails de entrada y de salida; p.13, *prompt injection*).
2. `AGENTS.md`, regla 7 del asistente (guardrails) y `docs/agent-practices.md`.
3. Decisión 0009 (ciclo del agente y controles de la respuesta final) y decisión 0011 (modelo de chat), con los resultados de C15 y C16 en `docs/model-comparison.md`.
4. Pydantic, *JSON Schema*: el esquema de la respuesta final se genera con `model_json_schema()` desde el modelo `FinalAnswer`: https://docs.pydantic.dev/latest/concepts/json_schema/
