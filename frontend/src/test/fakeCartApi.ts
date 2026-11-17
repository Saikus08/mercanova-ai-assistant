import type { CartApi } from '../api/cart'
import { ApiRequestError } from '../api/http'
import type { Cart, CartItem } from '../api/types'

export interface FakeProduct {
  product_id: string
  name: string
  unit_price: number
  available_qty: number
  image_url?: string | null
}

export const fakeProducts: FakeProduct[] = [
  { product_id: 'MN-MON-0001', name: 'Flux Vision 24 QHD IPS', unit_price: 100, available_qty: 5, image_url: '/m1.jpg' },
  { product_id: 'MN-HEA-0001', name: 'Echo Calm ANC', unit_price: 50, available_qty: 2, image_url: null },
  { product_id: 'MN-MON-0003', name: 'Flux Sin Stock', unit_price: 80, available_qty: 0, image_url: null },
]

function toCart(items: CartItem[]): Cart {
  return {
    items,
    item_count: items.reduce((sum, item) => sum + item.quantity, 0),
    total: items.reduce((sum, item) => sum + item.line_total, 0),
    currency: 'USD',
  }
}

/** In-memory CartApi that enforces stock like the backend does. Quantities are `{ productId: quantity }`. */
export function createFakeCartApi(initial: Record<string, number> = {}, catalog: FakeProduct[] = fakeProducts): CartApi {
  const quantities = new Map(Object.entries(initial))

  const snapshot = (): Cart =>
    toCart(
      [...quantities.entries()].map(([productId, quantity]) => {
        const product = catalog.find((p) => p.product_id === productId)!
        return {
          product_id: productId,
          name: product.name,
          image_url: product.image_url ?? null,
          unit_price: product.unit_price,
          quantity,
          line_total: product.unit_price * quantity,
          available_qty: product.available_qty,
        }
      }),
    )

  const set = (productId: string, quantity: number): Cart => {
    const product = catalog.find((p) => p.product_id === productId)
    if (!product) throw new ApiRequestError('PRODUCT_NOT_FOUND', 'No encontramos ese producto.', 404)
    if (quantity > product.available_qty) {
      throw new ApiRequestError('INSUFFICIENT_STOCK', `Solo hay ${product.available_qty} unidades disponibles.`, 409)
    }
    quantities.set(productId, quantity)
    return snapshot()
  }

  return {
    getCart: async () => snapshot(),
    addItem: async (productId, quantity) => set(productId, (quantities.get(productId) ?? 0) + quantity),
    updateQuantity: async (productId, quantity) => set(productId, quantity),
    removeItem: async (productId) => {
      quantities.delete(productId)
      return snapshot()
    },
    clear: async () => {
      quantities.clear()
      return snapshot()
    },
  }
}
