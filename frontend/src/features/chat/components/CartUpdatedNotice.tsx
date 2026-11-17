import { Link } from 'react-router'
import type { CartUpdatedBlock } from '../../../api/types'
import { cx } from '../../../components/ui/cx'
import { formatPrice } from '../../../lib/format'
import { paths } from '../../../routes/paths'
import styles from './Notice.module.css'

const units = (count: number) => (count === 1 ? '1 producto' : `${count} productos`)

/** Block `cart_updated`: short notice with the cart as the server returned it. */
export function CartUpdatedNotice({ block }: { block: CartUpdatedBlock }) {
  const { cart } = block
  return (
    <p className={cx(styles.notice, styles.success)}>
      Carrito actualizado: {units(cart.item_count)}, total {formatPrice(cart.total, cart.currency)}.{' '}
      <Link to={paths.cart} className={styles.link}>
        Ver carrito
      </Link>
    </p>
  )
}
