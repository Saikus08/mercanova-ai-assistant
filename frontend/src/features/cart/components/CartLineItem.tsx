import { Link } from 'react-router'
import type { CartItem, Currency } from '../../../api/types'
import { Button } from '../../../components/ui'
import { formatPrice } from '../../../lib/format'
import { paths } from '../../../routes/paths'
import styles from './CartLineItem.module.css'

export interface CartLineItemProps {
  item: CartItem
  currency: Currency
  /** Blocks the controls while this line is being updated. */
  disabled?: boolean
  onChangeQuantity: (quantity: number) => void
  onRemove: () => void
}

/** The stock went down after the product was added: the line cannot be bought as it is. */
function stockProblemOf(item: CartItem): string | null {
  if (item.available_qty <= 0) return 'Este producto se quedó sin stock. Quitalo para poder comprar.'
  if (item.quantity > item.available_qty) {
    const units = item.available_qty === 1 ? '1 unidad' : `${item.available_qty} unidades`
    return `Ahora solo hay ${units}. Bajá la cantidad para poder comprar.`
  }
  return null
}

export function CartLineItem({ item, currency, disabled = false, onChangeQuantity, onRemove }: CartLineItemProps) {
  const atMinimum = item.quantity <= 1
  const atMaximum = item.quantity >= item.available_qty
  const stockProblem = stockProblemOf(item)

  return (
    <article className={styles.line} aria-label={item.name}>
      {item.image_url ? (
        <img src={item.image_url} alt="" className={styles.image} loading="lazy" />
      ) : (
        <span aria-hidden="true" className={styles.placeholder} />
      )}

      <div className={styles.info}>
        <Link to={paths.product(item.product_id)} className={styles.name}>
          {item.name}
        </Link>
        <p className={styles.unitPrice}>{formatPrice(item.unit_price, currency)} c/u</p>
        {stockProblem && <p className={styles.stockProblem}>{stockProblem}</p>}
      </div>

      <div className={styles.quantity}>
        <div className={styles.stepper}>
          <Button
            variant="secondary"
            size="sm"
            aria-label={`Quitar una unidad de ${item.name}`}
            disabled={disabled || atMinimum}
            onClick={() => onChangeQuantity(item.quantity - 1)}
          >
            −
          </Button>
          <span className={styles.value} aria-live="polite">
            <span className="visually-hidden">Cantidad: </span>
            {item.quantity}
          </span>
          <Button
            variant="secondary"
            size="sm"
            aria-label={`Agregar una unidad de ${item.name}`}
            disabled={disabled || atMaximum}
            onClick={() => onChangeQuantity(item.quantity + 1)}
          >
            +
          </Button>
        </div>
        {atMaximum && !stockProblem && <p className={styles.hint}>Máximo disponible</p>}
      </div>

      <p className={styles.total}>{formatPrice(item.line_total, currency)}</p>

      <Button variant="ghost" size="sm" aria-label={`Quitar ${item.name} del carrito`} disabled={disabled} onClick={onRemove}>
        Quitar
      </Button>
    </article>
  )
}
