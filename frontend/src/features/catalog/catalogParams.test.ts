import { describe, expect, it } from 'vitest'
import { parseCatalogParams, toCatalogSearch } from './catalogParams'

describe('catalog URL params', () => {
  it('reads valid filters from the URL', () => {
    const params = parseCatalogParams(
      new URLSearchParams('q=monitor&category=Monitors&min_price=100&max_price=500&in_stock=true&sort=price_asc&page=2'),
    )

    expect(params).toEqual({
      q: 'monitor',
      category: 'Monitors',
      subcategory: undefined,
      min_price: 100,
      max_price: 500,
      in_stock: true,
      sort: 'price_asc',
      page: 2,
    })
  })

  it('ignores values the API would reject', () => {
    const params = parseCatalogParams(
      new URLSearchParams('q=%20%20&min_price=abc&max_price=-5&sort=cheapest&page=0&in_stock=yes'),
    )

    expect(params.q).toBeUndefined()
    expect(params.min_price).toBeUndefined()
    expect(params.max_price).toBeUndefined()
    expect(params.sort).toBeUndefined()
    expect(params.page).toBeUndefined()
    expect(params.in_stock).toBeUndefined()
  })

  it('writes only the filters that are set, without page 1', () => {
    const search = toCatalogSearch({ q: 'auriculares', category: undefined, in_stock: true, page: 1 })

    expect(search.toString()).toBe('q=auriculares&in_stock=true')
  })
})
