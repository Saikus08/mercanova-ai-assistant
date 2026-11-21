import { createContext, useContext } from 'react'
import type { Cart } from '../../api/types'

/** Outcome of one mutation, with its own message so each caller shows its own error. */
export type MutationResult = { ok: true } | { ok: false; message: string }

export interface CartState {
  /** Last cart returned by the server. It is kept when a mutation fails. */
  cart: Cart | null
  status: 'loading' | 'ready' | 'error'
  /** Spanish message of the last failed load. */
  errorMessage: string | null
  /** Products with a mutation queued or running, so each one stays pending until its own finishes. */
  pendingProductIds: readonly string[]
  /** Spanish message of the last failed mutation (for example INSUFFICIENT_STOCK), for the cart screen. */
  actionError: string | null
  add: (productId: string, quantity: number) => Promise<MutationResult>
  setQuantity: (productId: string, quantity: number) => Promise<MutationResult>
  remove: (productId: string) => Promise<MutationResult>
  clear: () => Promise<MutationResult>
  clearActionError: () => void
  reload: () => void
}

export const CartContext = createContext<CartState | null>(null)

export function useCart(): CartState {
  const state = useContext(CartContext)
  if (!state) throw new Error('useCart must be used inside a CartProvider')
  return state
}
