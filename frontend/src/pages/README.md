# pages/

Un componente por ruta. Solo compone contenedores de `features/` y componentes de `components/`; no tiene lógica de datos propia.

Rutas actuales:

- `/`: `CatalogPage`, catálogo de productos con filtros (consultar y ver los productos, RF-01). Los filtros quedan en la dirección de la página, así una búsqueda se puede recargar o compartir.
- `/productos/:productId`: `ProductDetailPage`, detalle de un producto con precio, stock por depósito y especificaciones.
- `/ui`: `UiShowcasePage`, muestra todos los componentes base y sus variantes para revisarlos.
