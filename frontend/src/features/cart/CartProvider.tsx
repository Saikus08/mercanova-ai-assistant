import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import type { Cart } from '../../api/types'
import { ApiRequestError } from '../../api/http'
import { useCartApi } from './cartApiContext'
import { CartContext, type CartState } from './useCart'

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
  const [pendingProductId, setPendingProductId] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [attempt, setAttempt] = useState(0)

  const queue = useRef<Promise<unknown>>(Promise.resolve())
  const inFlight = useRef(0)
  const version = useRef(0)

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

  const mutate = useCallback((productId: string | null, run: () => Promise<Cart>): Promise<boolean> => {
    inFlight.current += 1
    setPendingProductId(productId)
    setActionError(null)
    const task = queue.current.then(async () => {
      try {
        const next = await run()
        version.current += 1
        setCart(next)
        setStatus('ready')
        return true
      } catch (error) {
        setActionError(messageOf(error))
        return false
      } finally {
        inFlight.current -= 1
        if (inFlight.current === 0) setPendingProductId(null)
      }
    })
    queue.current = task
    return task
  }, [])

  const value = useMemo<CartState>(
    () => ({
      cart,
      status,
      errorMessage,
      pendingProductId,
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
    [api, mutate, cart, status, errorMessage, pendingProductId, actionError],
  )

  return <CartContext.Provider value={value}>{children}</CartContext.Provider>
}
