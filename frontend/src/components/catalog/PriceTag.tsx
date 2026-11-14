import type { Price } from '../../api/types'
import { Badge } from '../ui'
import { cx } from '../ui/cx'
import { formatPrice } from './format'
import styles from './PriceTag.module.css'

export interface PriceTagProps {
  price: Price
  size?: 'md' | 'lg'
}

/** Current price, plus the list price and discount when there is one. */
export function PriceTag({ price, size = 'md' }: PriceTagProps) {
  const discounted = price.discount_percent > 0 && price.list > price.current
  return (
    <div className={styles.price}>
      <span className={cx(styles.current, styles[size])}>{formatPrice(price.current, price.currency)}</span>
      {discounted && (
        <>
          <s className={styles.list}>
            <span className="visually-hidden">Antes </span>
            {formatPrice(price.list, price.currency)}
          </s>
          <Badge variant="success">-{price.discount_percent}%</Badge>
        </>
      )}
    </div>
  )
}
