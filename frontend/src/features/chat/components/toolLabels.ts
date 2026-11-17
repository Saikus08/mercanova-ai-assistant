/** What the assistant is doing while a tool runs, and how the tool is named in "Cómo lo resolví". */
const TOOL_LABELS: Record<string, { activity: string; summary: string }> = {
  search_products: { activity: 'Buscando productos…', summary: 'Buscó productos en el catálogo' },
  get_product_details: { activity: 'Consultando el detalle del producto…', summary: 'Consultó el detalle de un producto' },
  get_price: { activity: 'Consultando el precio…', summary: 'Consultó el precio actual' },
  get_stock: { activity: 'Consultando el stock…', summary: 'Consultó el stock actual' },
  compare_products: { activity: 'Comparando productos…', summary: 'Comparó productos' },
  get_alternatives: { activity: 'Buscando alternativas…', summary: 'Buscó alternativas' },
  view_cart: { activity: 'Revisando el carrito…', summary: 'Revisó el carrito' },
  add_to_cart: { activity: 'Agregando al carrito…', summary: 'Agregó un producto al carrito' },
  start_checkout: { activity: 'Preparando la compra…', summary: 'Preparó la compra' },
}

export const toolActivity = (name: string): string => TOOL_LABELS[name]?.activity ?? 'Pensando…'

export const toolSummary = (name: string): string => TOOL_LABELS[name]?.summary ?? name
