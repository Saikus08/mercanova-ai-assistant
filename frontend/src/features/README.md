# features/

Una carpeta por funcionalidad, por ejemplo `catalog/`, `cart/` o `chat/`. Cada una agrupa todo lo que necesita:

- Contenedores y hooks (`CatalogContainer.tsx`, `useAsyncResource.ts`): acá vive el acceso a datos. Llaman al cliente de `api/`, manejan los estados de carga, error (mensaje en español) y vacío, y le pasan los datos a los componentes presentacionales.
- `components/`: componentes presentacionales de esa funcionalidad (por ejemplo `catalog/components/ProductCard.tsx`). Reciben props y no hacen pedidos a la API.

Los componentes compartidos entre funcionalidades están en `components/ui/`. Las funciones puras compartidas (formato de precios y números) están en `lib/`, y las rutas y sus URL en `routes/`.
