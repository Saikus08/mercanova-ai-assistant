import { afterEach, describe, expect, it, vi } from 'vitest'
import type { Warehouse } from './types'
import { httpWarehousesApi } from './warehouses'

const warehouses: Warehouse[] = [
  {
    warehouse_id: 'WH-MVD-CEN',
    warehouse_name: 'Depósito Centro',
    city: 'Montevideo',
    department: 'Montevideo',
    country: 'UY',
    pickup_enabled: true,
    shipping_enabled: true,
  },
]

describe('httpWarehousesApi', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('lists warehouses with GET /warehouses', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 200, json: () => Promise.resolve(warehouses) })
    vi.stubGlobal('fetch', fetchMock)
    const controller = new AbortController()

    await expect(httpWarehousesApi.listWarehouses(controller.signal)).resolves.toEqual(warehouses)

    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/warehouses')
    expect(init.method).toBe('GET')
    expect(init.signal).toBe(controller.signal)
  })
})
