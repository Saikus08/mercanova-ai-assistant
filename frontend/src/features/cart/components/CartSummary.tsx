import type { Currency } from '../../../api/types'
import { Button, Card } from '../../../components/ui'
import { formatPrice } from '../../../lib/format'
import styles from './CartSummary.module.css'

export interface CartSummaryProps {
  itemCount: number
  total: number
  currency: Currency
  /** The button stays disabled without a handler (the checkout screen does not exist yet). */
  onCheckout?: () => void
}

export function CartSummary({ itemCount, total, currency, onCheckout }: CartSummaryProps) {
  return (
    <Card padding="lg" className={styles.summary} aria-labelledby="cart-summary-title">
      <h2 id="cart-summary-title" className={styles.title}>
        Resumen
      </h2>
      <p className={styles.count}>{itemCount === 1 ? '1 producto' : `${itemCount} productos`}</p>
      <p className={styles.total}>
        <span>Total</span>
        <strong>{formatPrice(total, currency)}</strong>
      </p>
      <Button disabled={itemCount === 0 || !onCheckout} onClick={onCheckout}>
        Continuar con la compra
      </Button>
    </Card>
  )
}
