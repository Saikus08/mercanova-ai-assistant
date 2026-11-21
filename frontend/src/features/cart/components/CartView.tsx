import { Link } from 'react-router'
import type { Cart } from '../../../api/types'
import { Button, Card } from '../../../components/ui'
import { paths } from '../../../routes/paths'
import { CartLineItem } from './CartLineItem'
import { CartSummary } from './CartSummary'
import styles from './CartView.module.css'

export interface CartViewProps {
  cart: Cart
  /** Products whose lines are being updated. */
  pendingProductIds: readonly string[]
  /** Spanish message of the last failed action; the cart stays visible. */
  actionError: string | null
  onChangeQuantity: (productId: string, quantity: number) => void
  onRemove: (productId: string) => void
  onCheckout?: () => void
  onDismissError: () => void
}

export function CartView({
  cart,
  pendingProductIds,
  actionError,
  onChangeQuantity,
  onRemove,
  onCheckout,
  onDismissError,
}: CartViewProps) {
  return (
    <section className={styles.cart} aria-labelledby="cart-title">
      <h1 id="cart-title" className={styles.title}>
        Carrito
      </h1>

      {actionError && (
        <div role="alert" className={styles.error}>
          <span>{actionError}</span>
          <Button variant="ghost" size="sm" aria-label="Cerrar aviso" onClick={onDismissError}>
            Cerrar
          </Button>
        </div>
      )}

      {cart.items.length === 0 ? (
        <Card padding="lg" className={styles.empty} role="status">
          <h2 className={styles.emptyTitle}>Tu carrito está vacío</h2>
          <p className={styles.muted}>Sumá productos desde el catálogo y los vas a ver acá.</p>
          <Link to={paths.catalog}>Ver el catálogo</Link>
        </Card>
      ) : (
        <div className={styles.layout}>
          <Card padding="lg" className={styles.lines}>
            <ul className={styles.list} aria-label="Productos del carrito">
              {cart.items.map((item) => (
                <li key={item.product_id}>
                  <CartLineItem
                    item={item}
                    currency={cart.currency}
                    disabled={pendingProductIds.includes(item.product_id)}
                    onChangeQuantity={(quantity) => onChangeQuantity(item.product_id, quantity)}
                    onRemove={() => onRemove(item.product_id)}
                  />
                </li>
              ))}
            </ul>
          </Card>
          <CartSummary itemCount={cart.item_count} total={cart.total} currency={cart.currency} onCheckout={onCheckout} />
        </div>
      )}
    </section>
  )
}
