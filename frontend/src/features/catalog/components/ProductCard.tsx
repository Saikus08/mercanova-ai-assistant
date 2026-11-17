import type { ReactNode } from 'react'
import { Link } from 'react-router'
import type { ProductSummary } from '../../../api/types'
import { Card } from '../../../components/ui'
import { formatNumber } from '../../../lib/format'
import { productPath } from '../../../routes/paths'
import { PriceTag } from './PriceTag'
import { StockBadge } from './StockBadge'
import styles from './ProductCard.module.css'

export interface ProductCardProps {
  product: ProductSummary
  /** Slot for the purchase actions (add to cart), supplied by the container. */
  actions?: ReactNode
}

export function ProductCard({ product, actions }: ProductCardProps) {
  return (
    <Card padding="none" className={styles.card}>
      <img src={product.image_url} alt="" className={styles.image} loading="lazy" />
      <div className={styles.body}>
        <p className={styles.brand}>
          {product.brand} · {product.subcategory}
        </p>
        <h3 className={styles.name}>
          <Link to={productPath(product.product_id)} className={styles.link}>
            {product.name}
          </Link>
        </h3>
        <p className={styles.description}>{product.short_description}</p>
        <p className={styles.rating}>
          <span aria-hidden="true">★ </span>
          {formatNumber(product.rating, 1)}
          <span className={styles.reviews}> ({formatNumber(product.review_count)} opiniones)</span>
        </p>
        <div className={styles.footer}>
          <PriceTag price={product.price} />
          <StockBadge availableQty={product.available_qty} />
        </div>
        {actions && <div className={styles.actions}>{actions}</div>}
      </div>
    </Card>
  )
}
