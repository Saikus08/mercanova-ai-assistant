import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import type { Cart } from '../../api/types'
import { ApiRequestError } from '../../api/http'
import { useCartApi } from './cartApiContext'
import { CartContext, type CartState, type MutationResult } from './useCart'

const FALLBACK_ERROR = 'Ocurrió un error inesperado. Intentá de nuevo en unos minutos.'

const messageOf = (error: unknown) => (error instanceof ApiRequestError ? error.message : FALLBACK_ERROR)

/**
 * Holds the cart for the whole app. The server is the source of truth: every mutation replaces
 * the cart with its response. Mutations run one at a time, in order, so a slow response can never
 * overwrite a newer one; a load that was overtaken by a mutation is ignored.
 */
export function CartProvider({ children }: { children: ReactNode }) {
  const api = useCartApi()
  const [cart, setCart] = useState<Cart | null>(null)
  const [status, setStatus] = useState<CartState['status']>('loading')
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [pendingProductIds, setPendingProductIds] = useState<readonly string[]>([])
  const [actionError, setActionError] = useState<string | null>(null)
  const [attempt, setAttempt] = useState(0)

  const queue = useRef<Promise<unknown>>(Promise.resolve())
  // Mutations queued or running per product: a product stays pending until its last one ends.
  const pendingCounts = useRef(new Map<string, number>())
  const version = useRef(0)

  const trackPending = useCallback((productId: string | null, delta: 1 | -1) => {
    if (productId === null) return
    const counts = pendingCounts.current
    const next = (counts.get(productId) ?? 0) + delta
    if (next > 0) counts.set(productId, next)
    else counts.delete(productId)
    setPendingProductIds([...counts.keys()])
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    const startedAt = version.current
    api.getCart(controller.signal).then(
      (next) => {
        if (controller.signal.aborted || version.current !== startedAt) return
        setCart(next)
        setStatus('ready')
      },
      (error: unknown) => {
        if (controller.signal.aborted || version.current !== startedAt) return
        setErrorMessage(messageOf(error))
        setStatus('error')
      },
    )
    return () => controller.abort()
  }, [api, attempt])

  const mutate = useCallback(
    (productId: string | null, run: () => Promise<Cart>): Promise<MutationResult> => {
      trackPending(productId, 1)
      setActionError(null)
      const task = queue.current.then(async (): Promise<MutationResult> => {
        try {
          const next = await run()
          version.current += 1
          setCart(next)
          setStatus('ready')
          return { ok: true }
        } catch (error) {
          const message = messageOf(error)
          setActionError(message)
          return { ok: false, message }
        } finally {
          trackPending(productId, -1)
        }
      })
      queue.current = task
      return task
    },
    [trackPending],
  )

  const value = useMemo<CartState>(
    () => ({
      cart,
      status,
      errorMessage,
      pendingProductIds,
      actionError,
      add: (productId, quantity) => mutate(productId, () => api.addItem(productId, quantity)),
      setQuantity: (productId, quantity) => mutate(productId, () => api.updateQuantity(productId, quantity)),
      remove: (productId) => mutate(productId, () => api.removeItem(productId)),
      clear: () => mutate(null, () => api.clear()),
      clearActionError: () => setActionError(null),
      reload: () => {
        setStatus('loading')
        setAttempt((n) => n + 1)
      },
    }),
    [api, mutate, cart, status, errorMessage, pendingProductIds, actionError],
  )

  return <CartContext.Provider value={value}>{children}</CartContext.Provider>
}
