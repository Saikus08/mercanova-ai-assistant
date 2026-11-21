import { afterEach, describe, expect, it, vi } from 'vitest'
import { apiDelete, apiGet, apiPatch, apiPost, ApiRequestError, buildQuery } from './http'

function mockFetch(response: Partial<Response> | Error) {
  const fetchMock =
    response instanceof Error ? vi.fn().mockRejectedValue(response) : vi.fn().mockResolvedValue(response)
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

const jsonResponse = (status: number, body: unknown): Partial<Response> => ({
  ok: status >= 200 && status < 300,
  status,
  json: () => Promise.resolve(body),
})

describe('apiGet', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('sends the session header and returns the JSON body', async () => {
    const fetchMock = mockFetch(jsonResponse(200, { ok: true }))

    await expect(apiGet('/products')).resolves.toEqual({ ok: true })

    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/products')
    expect(init.headers['X-Session-Id']).toEqual(expect.any(String))
  })

  it('turns a contract error into ApiRequestError with the Spanish message', async () => {
    mockFetch(
      jsonResponse(404, {
        error: { code: 'PRODUCT_NOT_FOUND', message: 'No encontramos ese producto.', details: { product_id: 'X' } },
      }),
    )

    const error = await apiGet('/products/X').catch((e: unknown) => e)

    expect(error).toBeInstanceOf(ApiRequestError)
    expect(error).toMatchObject({ code: 'PRODUCT_NOT_FOUND', status: 404, message: 'No encontramos ese producto.' })
  })

  it('never shows technical details when the error body is not in the contract shape', async () => {
    mockFetch(jsonResponse(502, '<html>Bad gateway</html>'))

    await expect(apiGet('/products')).rejects.toMatchObject({
      code: 'INTERNAL_ERROR',
      message: 'Ocurrió un error inesperado. Intentá de nuevo en unos minutos.',
    })
  })

  it('reports a readable message when the backend cannot be reached', async () => {
    mockFetch(new TypeError('Failed to fetch'))

    await expect(apiGet('/products')).rejects.toMatchObject({ code: 'NETWORK_ERROR', status: null })
  })
})

describe.each([
  ['apiPost', 'POST', apiPost],
  ['apiPatch', 'PATCH', apiPatch],
] as const)('%s', (_name, method, call) => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('sends the method, the JSON body and the session header', async () => {
    const fetchMock = mockFetch(jsonResponse(200, { ok: true }))

    await expect(call('/cart/items', { quantity: 2 })).resolves.toEqual({ ok: true })

    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/cart/items')
    expect(init.method).toBe(method)
    expect(init.body).toBe(JSON.stringify({ quantity: 2 }))
    expect(init.headers['Content-Type']).toBe('application/json')
    expect(init.headers['X-Session-Id']).toEqual(expect.any(String))
  })

  it('turns a contract error into ApiRequestError with the Spanish message', async () => {
    mockFetch(
      jsonResponse(409, {
        error: { code: 'INSUFFICIENT_STOCK', message: 'Solo hay 7 unidades disponibles.', details: { available_qty: 7 } },
      }),
    )

    const error = await call('/cart/items', { quantity: 9 }).catch((e: unknown) => e)

    expect(error).toBeInstanceOf(ApiRequestError)
    expect(error).toMatchObject({
      code: 'INSUFFICIENT_STOCK',
      status: 409,
      message: 'Solo hay 7 unidades disponibles.',
      details: { available_qty: 7 },
    })
  })

  it('reports a readable message when the backend cannot be reached', async () => {
    mockFetch(new TypeError('Failed to fetch'))

    await expect(call('/cart/items', {})).rejects.toMatchObject({ code: 'NETWORK_ERROR', status: null })
  })
})

describe('apiDelete', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('sends DELETE with the session header and no body', async () => {
    const fetchMock = mockFetch(jsonResponse(200, { items: [] }))

    await expect(apiDelete('/cart')).resolves.toEqual({ items: [] })

    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/cart')
    expect(init.method).toBe('DELETE')
    expect(init.body).toBeUndefined()
    expect(init.headers['X-Session-Id']).toEqual(expect.any(String))
  })

  it('turns a contract error into ApiRequestError', async () => {
    mockFetch(jsonResponse(404, { error: { code: 'NOT_FOUND', message: 'No existe.' } }))

    await expect(apiDelete('/cart/items/X')).rejects.toMatchObject({ code: 'NOT_FOUND', status: 404, message: 'No existe.' })
  })

  it('falls back to an unexpected-error message for non-contract bodies', async () => {
    mockFetch(jsonResponse(500, null))

    await expect(apiDelete('/cart')).rejects.toMatchObject({ code: 'INTERNAL_ERROR' })
  })

  it.each([204, 200])('resolves to null without failing when a %s answer has no body', async (status) => {
    // fetch rejects `json()` on an empty body; the backend always sends JSON today.
    mockFetch({ ok: true, status, json: () => Promise.reject(new SyntaxError('Unexpected end of JSON input')) })

    await expect(apiDelete('/cart')).resolves.toBeNull()
  })
})

describe('buildQuery', () => {
  it('skips empty values', () => {
    expect(buildQuery({ q: 'mouse', category: undefined, in_stock: true, brand: '' })).toBe('?q=mouse&in_stock=true')
    expect(buildQuery({})).toBe('')
  })
})
