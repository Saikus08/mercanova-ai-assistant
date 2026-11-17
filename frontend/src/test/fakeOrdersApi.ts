import type { CartApi } from '../api/cart'
import { ApiRequestError } from '../api/http'
import type { OrdersApi } from '../api/orders'
import type { Order } from '../api/types'

/**
 * In-memory OrdersApi that builds orders from the given cart API, like the backend does:
 * checkout does not touch the cart, confirm empties it.
 */
export function createFakeOrdersApi(cartApi: CartApi): OrdersApi {
  const orders = new Map<string, Order>()
  let counter = 0

  const find = (orderId: string): Order => {
    const order = orders.get(orderId)
    if (!order) throw new ApiRequestError('ORDER_NOT_FOUND', 'No encontramos esa orden.', 404)
    return order
  }

  const move = (orderId: string, status: Order['status']): Order => {
    const order = find(orderId)
    if (order.status !== 'pending_confirmation') {
      throw new ApiRequestError('ORDER_NOT_PENDING', 'La orden ya no está pendiente.', 409)
    }
    const next: Order = { ...order, status, confirmed_at: status === 'confirmed' ? '2026-11-12T22:05:00Z' : null }
    orders.set(orderId, next)
    return next
  }

  return {
    checkout: async (request) => {
      const cart = await cartApi.getCart()
      if (cart.items.length === 0) throw new ApiRequestError('CART_EMPTY', 'Tu carrito está vacío.', 409)
      counter += 1
      const order: Order = {
        order_id: `ORD-TEST-${counter}`,
        status: 'pending_confirmation',
        created_at: '2026-11-12T22:00:00Z',
        confirmed_at: null,
        customer: request.customer,
        delivery: request.delivery,
        items: cart.items.map(({ product_id, name, unit_price, quantity, line_total }) => ({
          product_id,
          name,
          unit_price,
          quantity,
          line_total,
        })),
        total: cart.total,
        currency: cart.currency,
      }
      orders.set(order.order_id, order)
      return order
    },
    confirm: async (orderId) => {
      const confirmed = move(orderId, 'confirmed')
      await cartApi.clear()
      return confirmed
    },
    cancel: async (orderId) => move(orderId, 'cancelled'),
  }
}
