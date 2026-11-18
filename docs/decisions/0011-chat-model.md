# Decisión 0011: El modelo del asistente es `qwen3:8b` con el razonamiento apagado

- **Estado:** propuesta
- **Fecha:** 18/11/2026
- **Autores:** Agustín Vignolo y Florencia Mendoza (Grupo 8, N8B)

## Problema

La decisión 0001 eligió `qwen3:8b` sin medirlo, y todo el desarrollo se hizo con `llama3.1:8b`, que era el modelo instalado. Hay que elegir el modelo con datos y decidir si se usa el modo de razonamiento de Qwen, que está activado por defecto.

## Alternativas

Los números salen de 60 corridas por modelo sobre 20 casos (`docs/model-comparison.md`).

| Opción | A favor | En contra |
|---|---|---|
| **`qwen3:8b` con `think=false` (elegida)** | Mejor calidad: Task Success 85,0 % y Tool Accuracy 92,5 %, con 45 de 60 corridas sin ningún fallo. No llama herramientas ante una inyección de instrucciones ni ante pedidos fuera de dominio. | Un turno tarda 14,0 s de media (30,5 s en el percentil 95), casi el doble que Llama. En un caso borde (cantidad negativa) agregó unidades al carrito. |
| `llama3.1:8b` | Más rápido: 7,8 s de media. Rechaza la cantidad negativa. | Task Success 77,8 % y Tool Accuracy 81,7 %, con 23 de 60 corridas sin fallos. Falló en aclarar un pedido sin una búsqueda vaga previa, en no llamar herramientas ante una inyección y en responder sobre la compra cuando se le pide confirmarla. |
| `qwen3:8b` con `think=true` | La mejor calidad en los casos difíciles: Task Success 97,6 % en C08 a C14. | Unos 52 s por turno y unos 1.000 tokens de razonamiento. Bajó el Grounding a 96,8 %. No sirve para un chat. |
| `qwen3:4b` | Más liviano (2,5 GB) [2]. | No se midió. |

## Decisión

- El modelo por defecto del asistente es `qwen3:8b`, con `LLM_THINK=false`. Qwen3 tiene el razonamiento activado por defecto [1][4], así que sin esta variable cada turno tarda cerca de 52 s.
- `llama3.1:8b` queda como alternativa documentada. Se puede usar con la variable `LLM_MODEL`.

## Justificación

- La calidad pesa más que la latencia en este producto: una respuesta equivocada sobre una compra cuesta más que unos segundos de espera. Con GPU, 14 s por turno es aceptable y los eventos de herramientas dan feedback mientras tanto.
- Los dos modelos tienen 100 % de Grounding: lo que impide que inventen precios es el software de control (decisión 0009), no el modelo. El modelo cambia cuánto trabajo extra tiene que hacer el software.
- El razonamiento activado no se justifica: mejora poco en los pocos casos donde ayuda y cuadruplica la espera.

## Costos y riesgos (trade-offs)

- **Más lento que Llama.** Sin GPU (por ejemplo, Ollama en Docker en una Mac) un modelo de 8B no es usable con ninguno de los dos. Esto no se midió con otro modelo más chico.
- **El estudio favorece a Llama sin querer:** el prompt y las guardas se ajustaron mirando sus fallos. Aun así Qwen rindió mejor.
- **Pocas corridas (3 por caso) y 20 casos.** Vale la tendencia, no un caso suelto.
- **Defectos compartidos que esta decisión no resuelve:** consultar el stock o el precio por el nombre del producto falla en los dos modelos, y ninguno responde bien a "Comprámelo" (avisar que se confirma en la interfaz). Se corrigen aparte.
- **Un cambio de configuración:** el valor por defecto de `LLM_THINK` hoy es "el del modelo" (activado en Qwen3). Implementar esta decisión exige que `config.py` y `.env.example` pasen a `false`.

## Fuentes

1. Ollama, *Thinking*: https://docs.ollama.com/capabilities/thinking
2. Ollama, biblioteca `qwen3`: https://ollama.com/library/qwen3
3. Ollama, biblioteca `llama3.1`: https://ollama.com/library/llama3.1
4. `ollama show qwen3:8b` (razonamiento activado por defecto) y los resultados completos en `docs/model-comparison.md`.
