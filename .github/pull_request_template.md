## Issue
Closes #

## Qué cambió
<!-- Resumen corto. Qué requisito de la letra cubre (nombrarlo por su significado, no solo por su código). -->

## Cómo se construyó
- Coding agent usado: <!-- Claude Code / Codex / Cursor / ninguno -->
- Skill usada: <!-- backend-feature / frontend-component / testing -->
- Partes escritas o corregidas a mano:

## Cómo probarlo
```
make test
```
<!-- Pegar el resumen de la salida de los tests y esperar a que el CI esté en verde -->

## Checklist
- [ ] Se cumplen los criterios de aceptación del issue
- [ ] Tests agregados o actualizados y CI en verde
- [ ] Precio y stock solo salen de las tools o de la base de datos; la compra sigue requiriendo confirmación explícita
- [ ] No se subieron secretos y las variables de entorno nuevas están en `.env.example`
- [ ] Se agregó un ADR si hubo una decisión de arquitectura
- [ ] Si el cambio agrega o modifica un flujo (endpoint, caso de uso, paso del agente), el diagrama en `docs/diagrams/` está creado o actualizado, o no aplica
- [ ] Título y descripción del PR en español (solo el prefijo de Conventional Commits queda en inglés)
