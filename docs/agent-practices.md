# Prácticas para el asistente y para el coding agent

Este documento explica qué reglas seguimos al construir el asistente de compras y al trabajar con coding agents, y de dónde sale cada una: la letra del obligatorio, su rúbrica o las clases del curso. Las reglas operativas están en `AGENTS.md`. Acá está el porqué.

Cada cita de clase indica la presentación y la página (por ejemplo "clase 6, p.9"). Las presentaciones son las del curso: 1 LLMs en aplicaciones, 2 RAG, 3 tools y function calling, 4 coding agents y skills, 5 agents, 6 agents robustos y MCP, 7 evals, observabilidad, guardrails y seguridad.

## 1. El asistente (el agente del producto)

| Regla | Por qué | Fuente |
|---|---|---|
| El modelo propone llamar a una herramienta y el software valida que exista, sus argumentos y su permiso antes de ejecutarla | El modelo puede equivocarse de herramienta o de formato. La aplicación es la que controla qué se ejecuta | Clase 3, p.6 y p.12 |
| Errores de herramientas útiles y accionables, devueltos al modelo | Así el modelo puede corregir el pedido en el siguiente paso en lugar de fallar | Clase 3, p.18 |
| Tabla de permisos por herramienta y mínimo privilegio. Confirmar una compra no es una herramienta | Las acciones que cambian el estado de la compra se tratan de forma controlada, y la compra final requiere confirmación explícita | Clase 6, p.9-10. Letra: sección 8 y confirmación de compra (RF-12) |
| La herramienta de checkout solo crea una orden pendiente, sin efectos | La clase 6 pone "crear una orden" entre las acciones con confirmación humana. Nuestra orden pendiente no descuenta stock ni registra la compra: es un borrador hasta que el usuario confirma | Clase 6, p.10 |
| Estado explícito y separado del historial (objetivo, productos mostrados, herramientas usadas, paso) | Sin estado, "compará el primero con el segundo" no sabe a qué productos se refiere | Clase 5, p.9. Clase 6, p.3-6. Letra: comparación (RF-06) |
| Contexto mínimo, no todo el historial | "Buen contexto no es mucho contexto": más texto agrega costo, demora y ruido | Clase 6, p.4. Clase 2, p.6 |
| Memoria entre sesiones fuera de alcance | La clase la presenta como opcional y la letra no la pide | Clase 6, p.6 |
| Condiciones de corte: respuesta lista, máximo de pasos, error no recuperable o falta de confirmación | Un agente sin condición de fin puede quedar en loop | Clase 5, p.8. Clase 6, p.8 |
| Timeout, un reintento y respuesta degradada | Cubre los fallos típicos: llamada inválida, datos incompletos, timeout, demasiados pasos, respuesta inventada | Clase 6, p.7-8. Letra: robustez (RNF-04) |
| Guardrail de entrada: rechazar pedidos fuera del dominio | Mantiene al asistente en su tarea | Clase 7, p.11-12 |
| El texto recuperado por RAG se trata como datos, no como instrucciones | Previene *prompt injection* desde descripciones de producto | Clase 7, p.13 |
| Guardrail de salida: precio, stock e identificadores solo si salieron de una herramienta del turno | Es la forma verificable de no inventar información | Clase 2, p.17. Clase 7, p.12. Letra: información actual (RF-07) y no invención (RF-18) |
| Los datos personales del checkout no pasan por el modelo ni por los logs | Evita fugas de datos personales | Clase 7, p.12-13 |
| Temperatura baja, prompt con rol, criterios y restricciones, y ejemplos | Da respuestas más consistentes y estructuradas | Clase 1, p.9 y p.17-18 |
| Traza por respuesta y log por paso | Una demo no garantiza confiabilidad: hay que poder ver qué hizo el agente y cuánto tardó | Clase 7, p.3 y p.9-10 |
| Evaluación con casos fijos y puntaje por métrica (éxito de la tarea, herramienta correcta, grounding, costo y latencia), en tres niveles: componente, trayectoria y resultado | La clase usa MercaNova como ejemplo de evaluación | Clase 7, p.4-8. Rúbrica: asistente inteligente (4 puntos) y testing y robustez (2 puntos) |
| Un solo agente, sin MCP | La letra los deja fuera de alcance. La clase 6 presenta MCP solo como concepto | Letra: sección 13. Clase 6, p.11-14 |

## 2. Trabajo con coding agents

| Práctica | Por qué | Fuente |
|---|---|---|
| `AGENTS.md` con las reglas del proyecto, versionado | Le da al coding agent el contexto del proyecto en cada tarea | Letra: sección 10. Clase 4, p.8-10 |
| Al menos dos skills reutilizables (tenemos cuatro: backend, testing, frontend y revisión de código) | Las skills son procedimientos que el agente sigue. Son distintas del contexto general | Letra: sección 10. Clase 4, p.9-11 |
| Cada tarea es un ticket con contexto, objetivo, alcance, qué no tocar, restricciones y criterios de aceptación | Un pedido acotado reduce los cambios inventados o innecesarios | Clase 4, p.6-7 |
| Ciclo de trabajo: tarea, contexto, inspeccionar, implementar, tests y revisar el diff | Separa lo que propone el agente de lo que aceptamos | Clase 4, p.12 |
| Revisión por la otra persona del equipo, con preguntas explícitas: ¿inventó arquitectura o datos?, ¿hay complejidad innecesaria?, ¿el diff es revisable? | El código generado es responsabilidad del equipo | Clase 4, p.14. Letra: sección 10 y criterios generales |
| Hooks que bloquean escribir archivos con secretos, commitear en `main`, hacer *force push* y commitear el dataset | Son reglas que no dependen de que el agente "se acuerde": las hace cumplir la herramienta | Clase 7, p.13 (secretos y auditoría). Letra: configuración (RNF-03) |
| Revisión automática con cuatro enfoques (riesgo, resiliencia, legibilidad y confiabilidad) antes de dar por terminado un cambio grande | Da una segunda mirada sistemática sobre el código generado | Clase 4, p.14 |

## 3. Cómo se verifica

- **Hooks:** `.claude/hooks/guard.py` se probó con eventos de ejemplo. Bloquea escribir `.env`, el *force push* y agregar el dataset, y permite `.env.example` y los commits en ramas.
- **Reglas del asistente:** cada una tiene un criterio de aceptación en las issues de IA, con la cita de la clase. Se verifican con los tests del asistente y la evaluación de modelos.
