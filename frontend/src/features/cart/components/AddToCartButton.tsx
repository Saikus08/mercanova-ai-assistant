import { Button, type ButtonSize } from '../../../components/ui'

export interface AddToCartButtonProps {
  onAdd: () => void
  /** Shows "Sin stock" and blocks the button. */
  outOfStock?: boolean
  disabled?: boolean
  /** An add request is in progress. */
  pending?: boolean
  label?: string
  /** Accessible name when the visible label is not enough to tell products apart. */
  ariaLabel?: string
  size?: ButtonSize
}

export function AddToCartButton({
  onAdd,
  outOfStock = false,
  disabled = false,
  pending = false,
  label = 'Agregar al carrito',
  ariaLabel,
  size = 'md',
}: AddToCartButtonProps) {
  return (
    <Button
      size={size}
      loading={pending}
      disabled={disabled || outOfStock}
      aria-label={outOfStock ? undefined : ariaLabel}
      onClick={onAdd}
    >
      {outOfStock ? 'Sin stock' : label}
    </Button>
  )
}
