import { apiPost } from './http'
import type { CheckoutRequest, Order } from './types'

/** Purchase endpoints (docs/api-contract.md, "Compra"). The purchase has two steps: checkout and confirm. */
export interface OrdersApi {
  /** Step 1: creates a pending order from the session cart. It does not touch stock. */
  checkout(request: CheckoutRequest): Promise<Order>
  /** Step 2: confirms a pending order. Only the user triggers it, from the confirmation dialog. */
  confirm(orderId: string): Promise<Order>
  cancel(orderId: string): Promise<Order>
}

const orderPath = (orderId: string, action: 'confirm' | 'cancel') =>
  `/orders/${encodeURIComponent(orderId)}/${action}`

export const httpOrdersApi: OrdersApi = {
  checkout: (request) => apiPost<Order>('/checkout', request),
  confirm: (orderId) => apiPost<Order>(orderPath(orderId, 'confirm'), undefined),
  cancel: (orderId) => apiPost<Order>(orderPath(orderId, 'cancel'), undefined),
}
