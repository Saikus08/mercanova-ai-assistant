import type { CheckoutRequest, DeliveryMethod } from '../../api/types'

export interface CheckoutFormValues {
  name: string
  email: string
  address: string
  method: DeliveryMethod
  /** Warehouse chosen for pickup. Empty until the user picks one. */
  warehouseId: string
}

export type CheckoutFormField = 'name' | 'email' | 'address' | 'warehouse'

export type CheckoutFormErrors = Partial<Record<CheckoutFormField, string>>

/** Same limits as the backend (docs/api-contract.md, "Compra"). */
export const NAME_MAX_LENGTH = 120
export const EMAIL_MAX_LENGTH = 254
export const ADDRESS_MAX_LENGTH = 300

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

/** Client-side check that runs before calling the API. Messages are Spanish and ready to show. */
export function validateCheckout(values: CheckoutFormValues): CheckoutFormErrors {
  const errors: CheckoutFormErrors = {}
  const name = values.name.trim()
  const email = values.email.trim()
  const address = values.address.trim()

  if (!name) errors.name = 'Ingresá tu nombre.'
  else if (name.length > NAME_MAX_LENGTH) errors.name = `El nombre puede tener hasta ${NAME_MAX_LENGTH} caracteres.`

  if (!email) errors.email = 'Ingresá tu email.'
  else if (email.length > EMAIL_MAX_LENGTH) errors.email = `El email puede tener hasta ${EMAIL_MAX_LENGTH} caracteres.`
  else if (!EMAIL_PATTERN.test(email)) errors.email = 'Ingresá un email válido.'

  if (!address) errors.address = 'Ingresá tu dirección.'
  else if (address.length > ADDRESS_MAX_LENGTH) {
    errors.address = `La dirección puede tener hasta ${ADDRESS_MAX_LENGTH} caracteres.`
  }

  if (values.method === 'pickup' && !values.warehouseId) errors.warehouse = 'Elegí un depósito para retirar.'

  return errors
}

export function buildCheckoutRequest(values: CheckoutFormValues): CheckoutRequest {
  return {
    customer: { name: values.name.trim(), email: values.email.trim(), address: values.address.trim() },
    delivery:
      values.method === 'pickup' ? { method: 'pickup', warehouse_id: values.warehouseId } : { method: 'shipping' },
  }
}
