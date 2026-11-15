# components/

Componentes **presentacionales compartidos**: reciben datos y callbacks por props, no hacen pedidos a la API ni tienen efectos secundarios.

- `ui/`: componentes base reutilizables (Button, Card, Input, Badge, Modal, Spinner). Se importan desde `components/ui`.

Los componentes propios de una funcionalidad no van acá: viven en `features/<feature>/components/`, por ejemplo `features/catalog/components/ProductCard.tsx`.

Los estilos usan CSS Modules y solo variables de los tokens (`var(--color-primary)`, `var(--space-4)`).
