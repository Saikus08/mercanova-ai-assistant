# Estrategia de testing

Este documento explica qué se prueba, con qué herramienta y qué no se cubre. Las cifras son de la ejecución del 20/11/2026: **962 tests de backend** y **241 de frontend**, todos en verde en el CI de cada pull request.

## Niveles

| Nivel | Qué prueba | Herramienta | Dónde |
|---|---|---|---|
| Dominio | Reglas de negocio sin base ni modelo: carrito, stock, estado de la orden | pytest | `backend/tests/unit/` |
| Integración | La API contra PostgreSQL real, con una transacción que se revierte por test: catálogo, carrito, checkout en dos pasos, historial, concurrencia al confirmar, restricciones y migraciones | pytest + httpx | `backend/tests/integration/` |
| Agente, determinista | El ciclo del asistente con un modelo simulado que devuelve llamadas a herramientas preparadas; se comprueban las herramientas que se ejecutan y que la respuesta use solo datos de ellas | pytest | `backend/tests/unit/test_agent_loop.py` y afines |
| Agente, evaluación | 20 casos fijos contra un modelo real de Ollama, con puntaje por métrica. No bloquea el CI porque el modelo no es determinista | `python -m tests.eval.runner` | `backend/tests/eval/` |
| Frontend | Componentes y recorridos críticos con APIs falsas, por ejemplo del chat a la compra confirmada | Vitest + Testing Library | `frontend/src/**/*.test.tsx` |

## Cómo se evalúa al asistente

Un asistente basado en un modelo no se puede probar solo con aserciones exactas sobre el texto. Se evalúa en tres niveles (clase 7, p.5):

1. **Componente: cada herramienta por separado.** Tests de `search_products`, `get_price`, `get_stock`, `compare_products`, `add_to_cart` y las demás, con repositorios falsos y con la base real. También el dispatcher: argumentos inválidos, herramientas prohibidas y permisos.
2. **Trayectoria: la secuencia de herramientas.** Con el modelo simulado se comprueba qué herramientas se llaman, en qué orden y con qué argumentos (por ejemplo, que una consulta vaga no ejecute una búsqueda, o que un id inventado se rechace). En la evaluación real, la métrica de herramientas puntúa si eligió la herramienta correcta y si mandó llamadas inválidas.
3. **Resultado: la respuesta final.** Se comprueba que la respuesta sea válida, que cada precio y cada identificador salgan de una herramienta del turno (grounding), que no mencione nombres internos y que cumpla lo que pedía el caso (la métrica de tarea).

Los 20 casos están en `backend/tests/eval/golden_cases.py` y cubren los casos de uso del producto ([use-cases.md](use-cases.md)) y otros de ambigüedad, adversarios (inyección de instrucciones, datos personales), bordes y varios turnos. Cada corrida se guarda en `backend/tests/eval/results/` y la comparación entre modelos, con la decisión del modelo elegido, está en [model-comparison.md](model-comparison.md).

## Evidencia

- **CI:** cada pull request corre backend (ruff y pytest) y frontend (lint, tipos y Vitest).
- **Evaluación con `qwen3:8b` sin razonamiento.** Barrido de los 20 casos con 2 corridas cada uno (19/11/2026): todos pasan en tarea. Los casos C04, C07, C13 y C18 se repitieron el 20/11/2026 después de los últimos cambios del asistente, con el mismo resultado. En herramientas, C10 y C13 sacan menos (el modelo intenta un `max_price` inventado, que el software bloquea, y en C13 manda el nombre del producto como id en la primera llamada). En grounding, C18 saca 0,67 porque la respuesta cita el id de un producto mostrado en un turno anterior.

## Qué no se cubre, y límites

- **El modelo no es determinista.** Los casos de evaluación se corren varias veces y las conclusiones valen por la tendencia, no por un caso suelto. Un caso que pasó en una corrida puede fallar en otra.
- **No hay una guarda de entrada fuera de dominio.** El caso C16 (una pregunta ajena a la tienda) puede pasar o fallar según el modelo.
- **Pruebas manuales.** La voz se probó a mano en Chrome con micrófono real. No se probó en otros navegadores ni con otras voces.
- **El frontend se prueba con APIs falsas.** El recorrido del chat a la compra confirmada se comprobó además a mano contra el backend y el modelo reales, pero no hay una prueba automática de punta a punta con navegador.
