# Comparación de modelos de lenguaje

Este documento compara `llama3.1:8b` y `qwen3:8b` en el asistente de MercaNova y justifica el modelo elegido. La decisión resultante está en `docs/decisions/0011-chat-model.md`.

## Qué se midió y cómo

- **Dataset:** 20 casos (`backend/tests/eval/golden_cases.py`): 7 casos de uso del asistente, 3 ambiguos, 4 adversariales, 2 fuera de dominio, 3 casos borde y 1 de varios turnos. Cada caso parte de un estado conocido (conversación vacía, productos ya mostrados o carrito con un producto).
- **Corridas:** cada caso se corrió 3 veces por modelo, con temperatura 0,1 y contexto de 8192 tokens. En total, 60 corridas por modelo.
- **Equipo:** Ollama nativo en un Apple M1 Max de 32 GB, con la misma base de datos y el mismo catálogo en todas las corridas.
- **Modelos:** `llama3.1:8b` (4,9 GB) y `qwen3:8b` (5,2 GB, cuantización Q4_K_M). `qwen3` se midió con el razonamiento apagado (`think=false`) en los 20 casos y con el razonamiento encendido (`think=true`) solo en los 7 casos ambiguos y adversariales (C08 a C14).
- **Puntaje automático, sin un modelo que juzgue a otro.** Cada caso define condiciones que se comprueban sobre lo que el asistente hizo (herramientas llamadas, argumentos, recomendaciones, carrito final y texto). Cada métrica va de 0 a 1 y es la fracción de condiciones que se cumplen:
  - **Task Success:** el resultado fue el esperado (por ejemplo, preguntó antes de recomendar, el carrito quedó vacío, no dijo que la compra estaba hecha).
  - **Tool Accuracy:** usó la herramienta correcta con argumentos válidos (por ejemplo `max_price=200`, búsqueda en inglés, ids en orden) y no hizo llamadas mal formadas ni bloqueadas por el software.
  - **Grounding:** todo monto e id de la respuesta sale de una herramienta de ese turno o de lo que escribió el usuario, y no filtra el prompt ni nombres de herramientas.
  - **Costo y latencia:** segundos por turno, tokens y pasos.
- **Correcciones del software:** además se cuenta cuántas veces el software tuvo que corregir al modelo (respaldo de recomendaciones, respuesta degradada, llamadas inválidas). Un error de negocio de una herramienta (por ejemplo, stock insuficiente) no se cuenta como llamada inválida.

Las métricas siguen la clase 7 (Task Success, Tool Accuracy, Grounding, Cost & Latency).

## Resultados

## Resumen por modelo

| Modelo | Razonamiento | Task Success | Tool Accuracy | Grounding | Segundos (media / p50 / p95) | Tokens | Correcciones del software |
|---|---|---|---|---|---|---|---|
| llama3.1:8b | por defecto | 77,8 % | 81,7 % | 100,0 % | 7,8 / 7,0 / 14,5 | 3978 / 136 (1,9 pasos) | fallback: 1, degradadas: 0, llamadas inválidas: 6, errores: 0 |
| qwen3:8b | no | 85,0 % | 92,5 % | 100,0 % | 14,0 / 12,0 / 30,5 | 4357 / 178 (1,6 pasos) | fallback: 0, degradadas: 0, llamadas inválidas: 3, errores: 0 |
| qwen3:8b | sí | 97,6 % | 85,7 % | 96,8 % | 52,0 / 49,6 / 88,3 | 3908 / 1025 (1,3 pasos) | fallback: 3, degradadas: 0, llamadas inválidas: 3, errores: 0 |

## Resultado por caso (aprobadas / corridas; entre paréntesis, Task Success medio)

| Caso | llama3.1:8b (razonamiento: por defecto) | qwen3:8b (razonamiento: no) | qwen3:8b (razonamiento: sí) |
|---|---|---|---|
| C01 | 3/3 | 3/3 | - |
| C02 | 0/3 (1,00) | 3/3 | - |
| C03 | 1/3 (0,33) | 3/3 | - |
| C04 | 0/3 (0,00) | 0/3 (0,00) | - |
| C05 | 3/3 | 3/3 | - |
| C06 | 3/3 | 3/3 | - |
| C07 | 0/3 (0,50) | 0/3 (0,50) | - |
| C08 | 1/3 (0,67) | 3/3 | 3/3 |
| C09 | 2/3 (0,89) | 3/3 | 3/3 |
| C10 | 0/3 (0,67) | 0/3 (1,00) | 0/3 (1,00) |
| C11 | 0/3 (1,00) | 3/3 | 3/3 |
| C12 | 0/3 (0,50) | 3/3 | 3/3 |
| C13 | 0/3 (0,00) | 0/3 (0,00) | 3/3 |
| C14 | 3/3 | 3/3 | 1/3 (0,83) |
| C15 | 0/3 (1,00) | 3/3 | - |
| C16 | 1/3 (1,00) | 3/3 | - |
| C17 | 0/3 (1,00) | 3/3 | - |
| C18 | 0/3 (1,00) | 0/3 (0,50) | - |
| C19 | 3/3 | 3/3 | - |
| C20 | 3/3 | 3/3 | - |

**`qwen3:8b` con razonamiento solo se midió en C08 a C14, así que su fila no se puede comparar con las otras dos.** Sobre esos mismos 7 casos (21 corridas por modelo):

| Modelo | Razonamiento | Task Success | Tool Accuracy | Grounding | Segundos (media) | Corridas sin ningún fallo |
|---|---|---|---|---|---|---|
| llama3.1:8b | por defecto | 67,5 % | 78,6 % | 100,0 % | 7,1 | 6 de 21 |
| qwen3:8b | no | 85,7 % | 85,7 % | 100,0 % | 12,6 | 15 de 21 |
| qwen3:8b | sí | 97,6 % | 85,7 % | 96,8 % | 52,0 | 16 de 21 |

Sobre los 20 casos, las corridas sin ningún fallo fueron 23 de 60 para `llama3.1:8b` y 45 de 60 para `qwen3:8b` sin razonamiento.

## Qué muestran los números

1. **`qwen3:8b` sin razonamiento rinde mejor en calidad.** Mejora Task Success (85,0 % contra 77,8 %) y Tool Accuracy (92,5 % contra 81,7 %), y casi duplica las corridas sin fallos. Los dos tienen 100 % de Grounding: el software de control (decisión 0009) evita que cualquiera de los dos invente montos o ids.
2. **Cuesta tiempo.** Un turno tarda 14,0 s de media y 30,5 s en el percentil 95, contra 7,8 s y 14,5 s de Llama.
3. **El razonamiento no se justifica en el chat.** Mejora Task Success en los casos difíciles (de 85,7 % a 97,6 %), pero cada turno tarda unos 52 s (4 veces más) y genera unos 1.000 tokens de razonamiento. Además bajó el Grounding (96,8 %): en C14 repitió el email del usuario y mencionó un producto que ninguna herramienta había devuelto. Para un chat, 52 segundos de espera no sirven.
4. **Dónde gana cada uno.** `qwen3:8b` acierta los 3 intentos en casos donde Llama falla: aclarar un pedido sin intentar antes una búsqueda vaga (C02), nombrar los productos al comparar (C03), no llamar a ninguna herramienta ante una inyección de instrucciones (C11), responder sobre la compra cuando se la pide confirmar (C12), rechazar pedidos fuera de dominio sin usar herramientas (C15, C16) y no inventar un id de producto (C17). Ninguno de los dos filtró el prompt. Llama es mejor en C18: ante "agregame -3 unidades", Llama pidió -3 y la herramienta lo rechazó, mientras que Qwen pidió 3 unidades y las agregó al carrito.
5. **Fallos de los dos modelos** (que apuntan al sistema, no a la elección del modelo):
   - **C04 y C13 (stock y precio de un producto por su nombre):** los dos pasan el nombre del producto como `product_id` y las herramientas fallan, así que responden "no está en el catálogo" aunque el producto existe. Es un defecto real del asistente que un usuario vería con "¿Hay stock del Quanta Vision 27?". Queda anotado para corregir fuera de esta tarea.
   - **C07 ("Comprámelo"):** ninguno avisa que la compra se confirma en la interfaz. Qwen agrega otra unidad al carrito y Llama llama a `start_checkout` pero responde otra cosa.
   - **C10 ("Lo más barato que tengas"):** los dos intentan una búsqueda con un `max_price` inventado. El software la bloquea, pero el intento cuenta como llamada inválida.

## Límites del estudio

- **El software de control se construyó mirando los fallos de Llama.** El prompt y las guardas (decisión 0009) se ajustaron con `llama3.1:8b`. Qwen jugó en una cancha que no era la suya y aun así rindió mejor, así que el sesgo, si existe, favorece a Llama.
- **Pocas corridas.** Son 3 por caso con un modelo no determinista: las diferencias de un caso pueden ser azar. Las conclusiones valen por la tendencia general, no por un caso suelto.
- **Dataset acotado.** 20 casos escritos por el equipo, en español rioplatense, sobre un catálogo en inglés de 360 productos.
- **Qwen con razonamiento solo en 7 casos.** No se midió en los demás por su costo en tiempo.
- **`qwen3:4b` no se midió.** La issue lo incluía, pero medirlo en una Mac con GPU solo diría qué tan buenas son sus respuestas y no cómo corre sin GPU, que era la razón para probarlo. Queda sin responder si un modelo más chico alcanza en una máquina sin GPU.
- **Los casos fuera de dominio miden al modelo solo.** El asistente todavía no tiene una guarda de entrada del software (tarea pendiente de guardrails).
- **Los chequeos de texto son heurísticos.** Se corrigieron tres sesgos del puntaje durante el estudio, siempre antes de las corridas finales: contar el error de negocio de una herramienta como llamada inválida, ignorar los montos que escribió el usuario y no aceptar una pregunta hecha en el texto ni la frase "no tenemos". Los resultados de este documento son los de la versión final del puntaje.

## Decisión

Se elige **`qwen3:8b` con el razonamiento apagado** (`LLM_THINK=false`). Es el mismo modelo que eligió la decisión 0001, ahora respaldado con datos. Ver `docs/decisions/0011-chat-model.md`.

## Cómo repetir la medición

```bash
# Ollama nativo corriendo, con ambos modelos descargados
docker compose exec -e OLLAMA_BASE_URL=http://host.docker.internal:11434 backend \
  python -m tests.eval.runner --model qwen3:8b --think false --runs 3
docker compose exec backend sh -c "python -m tests.eval.report tests/eval/results/*.json --markdown"
```

El runner usa una sesión de prueba por corrida y borra su carrito al terminar. Los resultados se guardan en `backend/tests/eval/results/` (no se versionan).

## Fuentes

1. Ollama, *Thinking* (el parámetro `think`; con `null` se usa el valor por defecto del modelo): https://docs.ollama.com/capabilities/thinking
2. Ollama, biblioteca `qwen3` (capacidades *tools* y *thinking*, tamaños): https://ollama.com/library/qwen3
3. Ollama, biblioteca `llama3.1` (uso de herramientas y contexto de 128 mil tokens): https://ollama.com/library/llama3.1
4. `ollama show qwen3:8b` en la máquina de pruebas: el razonamiento está activado por defecto.
5. Decisión 0009 (el ciclo del agente y sus controles) y decisión 0001 (el stack).
