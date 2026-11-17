import type { Currency, Order } from '../../api/types'
import { formatPrice } from '../../lib/format'
import type { CheckoutFormErrors } from './checkoutForm'

export const FIELD_ERROR_MESSAGE = 'Revisá este dato'
export const GENERIC_VALIDATION_MESSAGE = 'Revisá los datos ingresados e intentá de nuevo.'
export const UNEXPECTED_MESSAGE = 'Ocurrió un error inesperado. Intentá de nuevo en unos minutos.'

const productName = (order: Order, productId: unknown): string =>
  order.items.find((item) => item.product_id === productId)?.name ?? 'uno de los productos'

/** Message for INSUFFICIENT_STOCK on confirm: names the product and says how many units are left. */
export function stockMessage(order: Order, details: Record<string, unknown> | undefined): string {
  const name = productName(order, details?.product_id)
  const available = Number(details?.available_qty)
  if (!Number.isFinite(available)) return `No hay stock suficiente de ${name}.`
  if (available <= 0) return `${name} se quedó sin stock.`
  if (available === 1) return `Solo queda 1 unidad de ${name}.`
  return `Solo quedan ${available} unidades de ${name}.`
}

/** Message for PRICE_CHANGED on confirm, or null when the details are not usable. */
export function priceChangedMessage(order: Order, details: Record<string, unknown> | undefined): string | null {
  const oldPrice = Number(details?.old_price)
  const newPrice = Number(details?.new_price)
  if (!Number.isFinite(oldPrice) || !Number.isFinite(newPrice)) return null
  const currency: Currency = order.currency
  return `El precio de ${productName(order, details?.product_id)} cambió de ${formatPrice(oldPrice, currency)} a ${formatPrice(newPrice, currency)}.`
}

const FIELD_BY_API_FIELD: Record<string, keyof CheckoutFormErrors> = {
  'customer.name': 'name',
  'customer.email': 'email',
  'customer.address': 'address',
}

/**
 * Maps the `details.errors` of a VALIDATION_ERROR to form fields. The backend messages are in
 * English, so they are replaced by a generic Spanish one.
 */
export function fieldErrorsFromValidation(details: Record<string, unknown> | undefined): CheckoutFormErrors {
  const entries = Array.isArray(details?.errors) ? (details.errors as unknown[]) : []
  const errors: CheckoutFormErrors = {}
  for (const entry of entries) {
    const field = (entry as { field?: unknown } | null)?.field
    if (typeof field !== 'string') continue
    const key = FIELD_BY_API_FIELD[field] ?? (field.startsWith('delivery') ? 'warehouse' : undefined)
    if (key) errors[key] = FIELD_ERROR_MESSAGE
  }
  return errors
}
