import { describe, expect, it } from 'vitest'
import type { Order } from '../../api/types'
import { fieldErrorsFromValidation, priceChangedMessage, stockMessage } from './checkoutMessages'

const order = {
  currency: 'USD',
  items: [{ product_id: 'P1', name: 'Flux Vision 24', unit_price: 100, quantity: 2, line_total: 200 }],
} as Order

describe('stockMessage', () => {
  it('names the product and the units left', () => {
    expect(stockMessage(order, { product_id: 'P1', available_qty: 3 })).toBe('Solo quedan 3 unidades de Flux Vision 24.')
    expect(stockMessage(order, { product_id: 'P1', available_qty: 1 })).toBe('Solo queda 1 unidad de Flux Vision 24.')
    expect(stockMessage(order, { product_id: 'P1', available_qty: 0 })).toBe('Flux Vision 24 se quedó sin stock.')
  })

  it('does not invent data when the details are missing', () => {
    expect(stockMessage(order, undefined)).toBe('No hay stock suficiente de uno de los productos.')
  })
})

describe('priceChangedMessage', () => {
  it('shows old and new price', () => {
    const message = priceChangedMessage(order, { product_id: 'P1', old_price: 100, new_price: 120 })

    expect(message).toMatch(/^El precio de Flux Vision 24 cambió de .*100,00.* a .*120,00.*\.$/)
  })

  it('returns null without usable prices', () => {
    expect(priceChangedMessage(order, { product_id: 'P1' })).toBeNull()
  })
})

describe('fieldErrorsFromValidation', () => {
  it('maps API fields to form fields with a Spanish message', () => {
    expect(
      fieldErrorsFromValidation({
        errors: [
          { field: 'customer.name', message: 'must not be blank' },
          { field: 'delivery.warehouse_id', message: 'required' },
          { field: 'other', message: 'x' },
        ],
      }),
    ).toEqual({ name: 'Revisá este dato', warehouse: 'Revisá este dato' })
  })

  it('returns nothing without details', () => {
    expect(fieldErrorsFromValidation(undefined)).toEqual({})
  })
})
