import { afterEach, describe, expect, it, vi } from 'vitest'
import { httpCartApi } from './cart'
import type { Cart } from './types'

const cart: Cart = { items: [], item_count: 0, total: 0, currency: 'USD' }

function mockFetch() {
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 200, json: () => Promise.resolve(cart) })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

describe('httpCartApi', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('gets the cart', async () => {
    const fetchMock = mockFetch()

    await expect(httpCartApi.getCart()).resolves.toEqual(cart)

    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/cart')
    expect(init.method).toBe('GET')
  })

  it('adds an item with POST /cart/items', async () => {
    const fetchMock = mockFetch()

    await httpCartApi.addItem('MN-MON-0001', 2)

    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/cart/items')
    expect(init.method).toBe('POST')
    expect(JSON.parse(init.body)).toEqual({ product_id: 'MN-MON-0001', quantity: 2 })
  })

  it('updates a quantity with PATCH and encodes the product id', async () => {
    const fetchMock = mockFetch()

    await httpCartApi.updateQuantity('MN/A B', 3)

    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/cart/items/MN%2FA%20B')
    expect(init.method).toBe('PATCH')
    expect(JSON.parse(init.body)).toEqual({ quantity: 3 })
  })

  it('removes an item with DELETE and encodes the product id', async () => {
    const fetchMock = mockFetch()

    await httpCartApi.removeItem('MN/A B')

    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/cart/items/MN%2FA%20B')
    expect(init.method).toBe('DELETE')
  })

  it('clears the cart with DELETE /cart', async () => {
    const fetchMock = mockFetch()

    await httpCartApi.clear()

    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/cart')
    expect(init.method).toBe('DELETE')
  })
})
