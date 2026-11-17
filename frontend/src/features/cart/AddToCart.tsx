import { useState } from 'react'
import type { ButtonSize } from '../../components/ui'
import { AddToCartButton } from './components/AddToCartButton'
import { useCart } from './useCart'
import styles from './AddToCart.module.css'

export interface AddToCartProps {
  productId: string
  productName: string
  availableQty: number
  size?: ButtonSize
}

/** Adds one unit of a product to the cart (RF-09) and shows the outcome next to the button. */
export function AddToCart({ productId, productName, availableQty, size }: AddToCartProps) {
  const cart = useCart()
  const [feedback, setFeedback] = useState<'idle' | 'added' | 'failed'>('idle')

  const handleAdd = async () => {
    setFeedback('idle')
    const added = await cart.add(productId, 1)
    setFeedback(added ? 'added' : 'failed')
  }

  return (
    <div className={styles.wrapper}>
      <AddToCartButton
        size={size}
        outOfStock={availableQty <= 0}
        pending={cart.pendingProductId === productId}
        ariaLabel={`Agregar al carrito: ${productName}`}
        onAdd={() => void handleAdd()}
      />
      {feedback === 'added' && (
        <p role="status" className={styles.success}>
          Agregado al carrito
        </p>
      )}
      {feedback === 'failed' && cart.actionError && (
        <p role="alert" className={styles.error}>
          {cart.actionError}
        </p>
      )}
    </div>
  )
}
