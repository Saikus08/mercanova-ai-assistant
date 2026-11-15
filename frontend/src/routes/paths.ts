export const PRODUCT_ROUTE_PATTERN = '/products/:productId'

export function productPath(productId: string): string {
  return `/products/${encodeURIComponent(productId)}`
}

export const paths = {
  catalog: '/',
  ui: '/ui',
  product: productPath,
  productPattern: PRODUCT_ROUTE_PATTERN,
} as const
