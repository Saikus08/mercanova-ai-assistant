import { afterEach, describe, expect, it, vi } from 'vitest'
import { apiGet, ApiRequestError, buildQuery } from './http'

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

describe('buildQuery', () => {
  it('skips empty values', () => {
    expect(buildQuery({ q: 'mouse', category: undefined, in_stock: true, brand: '' })).toBe('?q=mouse&in_stock=true')
    expect(buildQuery({})).toBe('')
  })
})
