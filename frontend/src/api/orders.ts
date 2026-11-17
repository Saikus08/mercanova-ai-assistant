import { apiGet, apiPost } from './http'
import type { CheckoutRequest, Order } from './types'

/** Purchase endpoints (docs/api-contract.md, "Compra"). The purchase has two steps: checkout and confirm. */
export interface OrdersApi {
  /** Step 1: creates a pending order from the session cart. It does not touch stock. */
  checkout(request: CheckoutRequest): Promise<Order>
  /** Step 2: confirms a pending order. Only the user triggers it, from the confirmation dialog. */
  confirm(orderId: string): Promise<Order>
  cancel(orderId: string): Promise<Order>
  /** Orders of the session in any status, newest first, with the prices paid at purchase time. */
  list(signal?: AbortSignal): Promise<Order[]>
  /** One order of the session. Fails with ORDER_NOT_FOUND for an unknown id or another session's. */
  get(orderId: string, signal?: AbortSignal): Promise<Order>
}

const orderPath = (orderId: string, action?: 'confirm' | 'cancel') =>
  action ? `/orders/${encodeURIComponent(orderId)}/${action}` : `/orders/${encodeURIComponent(orderId)}`

export const httpOrdersApi: OrdersApi = {
  checkout: (request) => apiPost<Order>('/checkout', request),
  confirm: (orderId) => apiPost<Order>(orderPath(orderId, 'confirm'), undefined),
  cancel: (orderId) => apiPost<Order>(orderPath(orderId, 'cancel'), undefined),
  list: (signal) => apiGet<Order[]>('/orders', signal),
  get: (orderId, signal) => apiGet<Order>(orderPath(orderId), signal),
}
