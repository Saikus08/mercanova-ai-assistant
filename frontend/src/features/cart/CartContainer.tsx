import { Button, Card, Spinner } from '../../components/ui'
import { CartView } from './components/CartView'
import { useCart } from './useCart'
import styles from './CartContainer.module.css'

/** Cart screen (RF-09, RF-10): the server cart with loading, error and empty states. */
export function CartContainer({ onCheckout }: { onCheckout?: () => void }) {
  const cart = useCart()

  if (cart.status === 'loading' && !cart.cart) {
    return (
      <div className={styles.loading}>
        <Spinner size="lg" label="Cargando carrito…" />
      </div>
    )
  }

  if (!cart.cart) {
    return (
      <Card padding="lg" className={styles.error} role="alert">
        <h2 className={styles.errorTitle}>No pudimos cargar tu carrito</h2>
        <p className={styles.muted}>{cart.errorMessage}</p>
        <Button variant="secondary" onClick={cart.reload}>
          Reintentar
        </Button>
      </Card>
    )
  }

  return (
    <CartView
      cart={cart.cart}
      pendingProductIds={cart.pendingProductIds}
      actionError={cart.actionError}
      onChangeQuantity={(productId, quantity) => void cart.setQuantity(productId, quantity)}
      onRemove={(productId) => void cart.remove(productId)}
      onCheckout={onCheckout}
      onDismissError={cart.clearActionError}
    />
  )
}
