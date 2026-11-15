import { describe, expect, it } from 'vitest'
import { createMockCatalogApi } from './mockCatalogApi'

describe('mock catalog API', () => {
  const api = createMockCatalogApi()

  it('filters by category, price and stock like the contract', async () => {
    const result = await api.listProducts({ category: 'Monitors', max_price: 500, in_stock: true })

    expect(result.items.map((p) => p.product_id)).toEqual(['MN-MON-0001', 'MN-MON-0002'])
    expect(result.items.every((p) => p.in_stock)).toBe(true)
  })

  it('sorts and paginates', async () => {
    const result = await api.listProducts({ sort: 'price_asc', page: 2, page_size: 2 })

    expect(result.page).toBe(2)
    expect(result.total).toBe(7)
    expect(result.items[0].price.current).toBeLessThanOrEqual(result.items[1].price.current)
  })

  it('returns only summary fields in listings', async () => {
    const result = await api.listProducts({})

    expect(result.items[0]).not.toHaveProperty('specifications')
  })

  it('rejects unknown products with PRODUCT_NOT_FOUND', async () => {
    await expect(api.getProduct('MN-NOPE')).rejects.toMatchObject({ code: 'PRODUCT_NOT_FOUND' })
  })
})
