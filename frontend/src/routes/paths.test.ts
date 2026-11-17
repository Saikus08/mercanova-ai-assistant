import { describe, expect, it } from 'vitest'
import { paths } from './paths'

describe('order paths', () => {
  it('builds the list and detail paths and encodes the id', () => {
    expect(paths.orders).toBe('/orders')
    expect(paths.order('ORD-1')).toBe('/orders/ORD-1')
    expect(paths.order('A/B C')).toBe('/orders/A%2FB%20C')
    expect(paths.orderPattern).toBe('/orders/:orderId')
  })
})
