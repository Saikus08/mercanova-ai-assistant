import { useState } from 'react'
import type { ButtonSize } from '../../components/ui'
import { AddToCartButton } from './components/AddToCartButton'
import { useCart } from './useCart'
import styles from './AddToCart.module.css'

type Feedback = { kind: 'idle' } | { kind: 'added' } | { kind: 'failed'; message: string }

export interface AddToCartProps {
  productId: string
  productName: string
  availableQty: number
  size?: ButtonSize
}

/** Adds one unit of a product to the cart (RF-09) and shows the outcome next to the button. */
export function AddToCart({ productId, productName, availableQty, size }: AddToCartProps) {
  const cart = useCart()
  // The message is this card's own: another card failing at the same time does not show here.
  const [feedback, setFeedback] = useState<Feedback>({ kind: 'idle' })

  const handleAdd = async () => {
    setFeedback({ kind: 'idle' })
    const result = await cart.add(productId, 1)
    setFeedback(result.ok ? { kind: 'added' } : { kind: 'failed', message: result.message })
  }

  return (
    <div className={styles.wrapper}>
      <AddToCartButton
        size={size}
        outOfStock={availableQty <= 0}
        pending={cart.pendingProductIds.includes(productId)}
        ariaLabel={`Agregar al carrito: ${productName}`}
        onAdd={() => void handleAdd()}
      />
      {feedback.kind === 'added' && (
        <p role="status" className={styles.success}>
          Agregado al carrito
        </p>
      )}
      {feedback.kind === 'failed' && (
        <p role="alert" className={styles.error}>
          {feedback.message}
        </p>
      )}
    </div>
  )
}
