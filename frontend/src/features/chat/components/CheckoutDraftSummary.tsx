import type { CheckoutDraftBlock } from '../../../api/types'
import { Button, Card } from '../../../components/ui'
import { formatPrice } from '../../../lib/format'
import styles from './CheckoutDraftSummary.module.css'

export interface CheckoutDraftSummaryProps {
  block: CheckoutDraftBlock
  /** Opens the checkout screen, where the user enters their data and confirms the purchase. */
  onCheckout: () => void
}

/**
 * Block `checkout_draft`: the cart is ready to pay. The assistant never confirms the purchase:
 * only the "Confirmar compra" button of the checkout screen registers the order (RF-12).
 */
export function CheckoutDraftSummary({ block, onCheckout }: CheckoutDraftSummaryProps) {
  const { cart } = block
  return (
    <Card className={styles.card}>
      <h3 className={styles.title}>Tu compra está lista para revisar</h3>
      <ul className={styles.items} aria-label="Resumen de la compra">
        {cart.items.map((item) => (
          <li key={item.product_id} className={styles.item}>
            <span>
              {item.quantity} × {item.name}
            </span>
            <span>{formatPrice(item.line_total, cart.currency)}</span>
          </li>
        ))}
      </ul>
      <p className={styles.total}>
        <span>Total</span>
        <span>{formatPrice(cart.total, cart.currency)}</span>
      </p>
      <p className={styles.hint}>La compra solo se registra cuando la confirmás vos.</p>
      <Button onClick={onCheckout}>Revisar y confirmar la compra</Button>
    </Card>
  )
}
