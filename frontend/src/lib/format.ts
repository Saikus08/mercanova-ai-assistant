import type { Currency } from '../api/types'

const LOCALE = 'es-UY'

export function formatPrice(amount: number, currency: Currency): string {
  return new Intl.NumberFormat(LOCALE, { style: 'currency', currency }).format(amount)
}

export function formatNumber(value: number, maximumFractionDigits = 0): string {
  return new Intl.NumberFormat(LOCALE, { maximumFractionDigits }).format(value)
}

/** The store operates in Montevideo, so dates are shown in that time zone whatever the browser's. */
const STORE_TIME_ZONE = 'America/Montevideo'

export function formatDateTime(iso: string): string {
  return new Intl.DateTimeFormat(LOCALE, {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    timeZone: STORE_TIME_ZONE,
    hourCycle: 'h23',
  }).format(new Date(iso))
}
