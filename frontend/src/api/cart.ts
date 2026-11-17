import { apiDelete, apiGet, apiPatch, apiPost } from './http'
import type { AddCartItemRequest, Cart, UpdateCartItemRequest } from './types'

/** Cart endpoints (docs/api-contract.md, "Carrito"). Every call returns the cart as the server holds it. */
export interface CartApi {
  getCart(signal?: AbortSignal): Promise<Cart>
  addItem(productId: string, quantity: number): Promise<Cart>
  updateQuantity(productId: string, quantity: number): Promise<Cart>
  removeItem(productId: string): Promise<Cart>
  clear(): Promise<Cart>
}

const itemPath = (productId: string) => `/cart/items/${encodeURIComponent(productId)}`

export const httpCartApi: CartApi = {
  getCart: (signal) => apiGet<Cart>('/cart', signal),
  addItem: (productId, quantity) =>
    apiPost<Cart>('/cart/items', { product_id: productId, quantity } satisfies AddCartItemRequest),
  updateQuantity: (productId, quantity) =>
    apiPatch<Cart>(itemPath(productId), { quantity } satisfies UpdateCartItemRequest),
  removeItem: (productId) => apiDelete<Cart>(itemPath(productId)),
  clear: () => apiDelete<Cart>('/cart'),
}
