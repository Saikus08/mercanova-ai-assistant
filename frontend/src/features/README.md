# features/

Contenedores y hooks por funcionalidad, por ejemplo `cart/useCart.ts` o `chat/useChat.ts`.

Acá vive el acceso a datos: llaman al cliente de `api/`, manejan los estados de carga, error (mensaje en español) y vacío, y le pasan los datos a los componentes presentacionales de `components/`.
