import { act, renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { describe, expect, it, vi } from 'vitest'
import type { CartApi } from '../../api/cart'
import { ApiRequestError } from '../../api/http'
import type { Cart } from '../../api/types'
import { createFakeCartApi } from '../../test/fakeCartApi'
import { CartApiProvider } from './CartApiProvider'
import { CartProvider } from './CartProvider'
import { useCart } from './useCart'

function setup(api: CartApi) {
  const wrapper = ({ children }: { children: ReactNode }) => (
    <CartApiProvider api={api}>
      <CartProvider>{children}</CartProvider>
    </CartApiProvider>
  )
  return renderHook(() => useCart(), { wrapper })
}

const emptyCart: Cart = { items: [], item_count: 0, total: 0, currency: 'USD' }

describe('CartProvider', () => {
  it('loads the cart on mount', async () => {
    const { result } = setup(createFakeCartApi({ 'MN-MON-0001': 2 }))

    expect(result.current.status).toBe('loading')
    await waitFor(() => expect(result.current.status).toBe('ready'))
    expect(result.current.cart?.item_count).toBe(2)
  })

  it('exposes a Spanish error when loading fails and reloads', async () => {
    const getCart = vi
      .fn<CartApi['getCart']>()
      .mockRejectedValueOnce(new ApiRequestError('NETWORK_ERROR', 'Sin conexión.', null))
      .mockResolvedValue(emptyCart)
    const { result } = setup({ ...createFakeCartApi(), getCart })

    await waitFor(() => expect(result.current.status).toBe('error'))
    expect(result.current.errorMessage).toBe('Sin conexión.')

    act(() => result.current.reload())
    await waitFor(() => expect(result.current.status).toBe('ready'))
  })

  it('replaces the cart with the server response after each mutation', async () => {
    const { result } = setup(createFakeCartApi({ 'MN-MON-0001': 1 }))
    await waitFor(() => expect(result.current.status).toBe('ready'))

    await act(() => result.current.add('MN-HEA-0001', 1))
    expect(result.current.cart?.item_count).toBe(2)

    await act(() => result.current.setQuantity('MN-MON-0001', 3))
    expect(result.current.cart?.item_count).toBe(4)

    await act(() => result.current.remove('MN-HEA-0001'))
    expect(result.current.cart?.items.map((i) => i.product_id)).toEqual(['MN-MON-0001'])

    await act(() => result.current.clear())
    expect(result.current.cart?.items).toEqual([])
  })

  it('keeps the cart and sets a clearable actionError when a mutation fails', async () => {
    const { result } = setup(createFakeCartApi({ 'MN-HEA-0001': 2 }))
    await waitFor(() => expect(result.current.status).toBe('ready'))

    let ok = true
    await act(async () => {
      ok = await result.current.add('MN-HEA-0001', 1)
    })

    expect(ok).toBe(false)
    expect(result.current.status).toBe('ready')
    expect(result.current.cart?.item_count).toBe(2)
    expect(result.current.actionError).toBe('Solo hay 2 unidades disponibles.')

    act(() => result.current.clearActionError())
    expect(result.current.actionError).toBeNull()
  })

  it('applies rapid mutations in order and ends with the last server response', async () => {
    const resolvers: Array<() => void> = []
    const base = createFakeCartApi({ 'MN-MON-0001': 1 })
    const api: CartApi = {
      ...base,
      updateQuantity: (id, qty) =>
        new Promise<Cart>((resolve) => {
          resolvers.push(() => resolve(base.updateQuantity(id, qty)))
        }),
    }
    const { result } = setup(api)
    await waitFor(() => expect(result.current.status).toBe('ready'))

    let first!: Promise<boolean>
    let second!: Promise<boolean>
    act(() => {
      first = result.current.setQuantity('MN-MON-0001', 2)
      second = result.current.setQuantity('MN-MON-0001', 3)
    })
    expect(result.current.pendingProductId).toBe('MN-MON-0001')
    await waitFor(() => expect(resolvers).toHaveLength(1))

    await act(async () => {
      resolvers[0]()
      await first
    })
    await waitFor(() => expect(resolvers).toHaveLength(2))
    await act(async () => {
      resolvers[1]()
      await second
    })

    expect(result.current.cart?.items[0].quantity).toBe(3)
    expect(result.current.pendingProductId).toBeNull()
  })
})
