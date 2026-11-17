import { describe, expect, it } from 'vitest'
import { buildCheckoutRequest, validateCheckout, type CheckoutFormValues } from './checkoutForm'

const valid: CheckoutFormValues = {
  name: 'Ana Pérez',
  email: 'ana@example.com',
  address: 'Av. 18 de Julio 1234',
  method: 'pickup',
  warehouseId: 'WH-1',
}

describe('validateCheckout', () => {
  it('accepts valid values', () => {
    expect(validateCheckout(valid)).toEqual({})
  })

  it('rejects blank fields with Spanish messages', () => {
    const errors = validateCheckout({ ...valid, name: '  ', email: '', address: '', warehouseId: '' })

    expect(errors).toEqual({
      name: 'Ingresá tu nombre.',
      email: 'Ingresá tu email.',
      address: 'Ingresá tu dirección.',
      warehouse: 'Elegí un depósito para retirar.',
    })
  })

  it('does not ask for a warehouse when shipping', () => {
    expect(validateCheckout({ ...valid, method: 'shipping', warehouseId: '' })).toEqual({})
  })

  it('rejects a malformed email', () => {
    expect(validateCheckout({ ...valid, email: 'ana@' }).email).toBe('Ingresá un email válido.')
    expect(validateCheckout({ ...valid, email: 'ana example@x.com' }).email).toBe('Ingresá un email válido.')
  })

  it('enforces the backend length limits', () => {
    expect(validateCheckout({ ...valid, name: 'a'.repeat(121) }).name).toBe('El nombre puede tener hasta 120 caracteres.')
    expect(validateCheckout({ ...valid, name: 'a'.repeat(120) }).name).toBeUndefined()
    expect(validateCheckout({ ...valid, email: `${'a'.repeat(250)}@x.com` }).email).toBe(
      'El email puede tener hasta 254 caracteres.',
    )
    expect(validateCheckout({ ...valid, address: 'a'.repeat(301) }).address).toBe(
      'La dirección puede tener hasta 300 caracteres.',
    )
  })
})

describe('buildCheckoutRequest', () => {
  it('trims the customer data and builds a pickup delivery', () => {
    expect(buildCheckoutRequest({ ...valid, name: ' Ana ', email: ' ana@example.com ' })).toEqual({
      customer: { name: 'Ana', email: 'ana@example.com', address: 'Av. 18 de Julio 1234' },
      delivery: { method: 'pickup', warehouse_id: 'WH-1' },
    })
  })

  it('builds a shipping delivery without warehouse', () => {
    expect(buildCheckoutRequest({ ...valid, method: 'shipping' }).delivery).toEqual({ method: 'shipping' })
  })
})
