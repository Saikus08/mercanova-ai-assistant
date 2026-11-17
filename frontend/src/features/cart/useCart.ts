import { createContext, useContext } from 'react'
import type { Cart } from '../../api/types'

export interface CartState {
  /** Last cart returned by the server. It is kept when a mutation fails. */
  cart: Cart | null
  status: 'loading' | 'ready' | 'error'
  /** Spanish message of the last failed load. */
  errorMessage: string | null
  /** Product of the mutation in progress, if any. */
  pendingProductId: string | null
  /** Spanish message of the last failed mutation (for example INSUFFICIENT_STOCK). */
  actionError: string | null
  /** Mutations resolve to `true` when the server accepted them. */
  add: (productId: string, quantity: number) => Promise<boolean>
  setQuantity: (productId: string, quantity: number) => Promise<boolean>
  remove: (productId: string) => Promise<boolean>
  clear: () => Promise<boolean>
  clearActionError: () => void
  reload: () => void
}

export const CartContext = createContext<CartState | null>(null)

export function useCart(): CartState {
  const state = useContext(CartContext)
  if (!state) throw new Error('useCart must be used inside a CartProvider')
  return state
}
