import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiRequestError } from './http'
import { httpOrdersApi } from './orders'
import type { CheckoutRequest, Order } from './types'

const order: Order = {
  order_id: 'ORD-1',
  status: 'pending_confirmation',
  created_at: '2026-11-12T22:00:00Z',
  confirmed_at: null,
  customer: { name: 'Ana', email: 'ana@example.com', address: 'Calle 1' },
  delivery: { method: 'shipping' },
  items: [],
  total: 0,
  currency: 'USD',
}

function mockFetch(response: { ok: boolean; status: number; body: unknown } = { ok: true, status: 200, body: order }) {
  const fetchMock = vi
    .fn()
    .mockResolvedValue({ ok: response.ok, status: response.status, json: () => Promise.resolve(response.body) })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

describe('httpOrdersApi', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('creates the pending order with POST /checkout', async () => {
    const fetchMock = mockFetch({ ok: true, status: 201, body: order })
    const request: CheckoutRequest = { customer: order.customer, delivery: { method: 'pickup', warehouse_id: 'WH-1' } }

    await expect(httpOrdersApi.checkout(request)).resolves.toEqual(order)

    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/checkout')
    expect(init.method).toBe('POST')
    expect(JSON.parse(init.body)).toEqual(request)
  })

  it('confirms an order and encodes the id', async () => {
    const fetchMock = mockFetch()

    await httpOrdersApi.confirm('ORD/1 A')

    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/orders/ORD%2F1%20A/confirm')
    expect(init.method).toBe('POST')
    expect(init.body).toBeUndefined()
  })

  it('cancels an order and encodes the id', async () => {
    const fetchMock = mockFetch()

    await httpOrdersApi.cancel('ORD/1 A')

    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/orders/ORD%2F1%20A/cancel')
    expect(init.method).toBe('POST')
  })

  it('maps contract errors to ApiRequestError with their details', async () => {
    mockFetch({
      ok: false,
      status: 409,
      body: { error: { code: 'PRICE_CHANGED', message: 'El precio cambió.', details: { product_id: 'P1' } } },
    })

    await expect(httpOrdersApi.confirm('ORD-1')).rejects.toMatchObject({
      code: 'PRICE_CHANGED',
      status: 409,
      details: { product_id: 'P1' },
    })
    await expect(httpOrdersApi.confirm('ORD-1')).rejects.toBeInstanceOf(ApiRequestError)
  })
})
