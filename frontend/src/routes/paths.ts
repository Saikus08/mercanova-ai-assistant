export const PRODUCT_ROUTE_PATTERN = '/products/:productId'

export function productPath(productId: string): string {
  return `/products/${encodeURIComponent(productId)}`
}

export const ORDER_ROUTE_PATTERN = '/orders/:orderId'

export function orderPath(orderId: string): string {
  return `/orders/${encodeURIComponent(orderId)}`
}

export const paths = {
  catalog: '/',
  cart: '/cart',
  chat: '/chat',
  checkout: '/checkout',
  orders: '/orders',
  order: orderPath,
  orderPattern: ORDER_ROUTE_PATTERN,
  ui: '/ui',
  product: productPath,
  productPattern: PRODUCT_ROUTE_PATTERN,
} as const
