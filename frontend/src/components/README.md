# components/

Componentes **presentacionales**: reciben datos y callbacks por props, no hacen pedidos a la API ni tienen efectos secundarios.

- `ui/`: componentes base reutilizables (Button, Card, Input, Badge, Modal, Spinner). Se importan desde `components/ui`.
- `<feature>/`: componentes de una funcionalidad, por ejemplo `catalog/ProductCard.tsx` o `chat/ChatMessage.tsx`.

Los estilos usan CSS Modules y solo variables de los tokens (`var(--color-primary)`, `var(--space-4)`).
