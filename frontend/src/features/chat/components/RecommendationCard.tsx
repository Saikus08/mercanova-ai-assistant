import type { ReactNode } from 'react'
import { Link } from 'react-router'
import type { ProductRecommendation } from '../../../api/types'
import { Card } from '../../../components/ui'
import { formatNumber } from '../../../lib/format'
import { productPath } from '../../../routes/paths'
import { PriceTag } from '../../catalog/components/PriceTag'
import { StockBadge } from '../../catalog/components/StockBadge'
import styles from './RecommendationCard.module.css'

export interface RecommendationCardProps {
  recommendation: ProductRecommendation
  /** Slot for the add to cart action, supplied by the container. */
  actions?: ReactNode
}

/** A recommended product with the reason the assistant gives for it (RF-04). */
export function RecommendationCard({ recommendation, actions }: RecommendationCardProps) {
  const { product, reason } = recommendation
  return (
    <Card padding="none" className={styles.card}>
      {product.image_url && <img src={product.image_url} alt="" className={styles.image} loading="lazy" />}
      <div className={styles.body}>
        <p className={styles.brand}>
          {product.brand} · {product.subcategory}
        </p>
        <h3 className={styles.name}>
          <Link to={productPath(product.product_id)} className={styles.link}>
            {product.name}
          </Link>
        </h3>
        {product.rating !== null && (
          <p className={styles.rating}>
            <span aria-hidden="true">★ </span>
            {formatNumber(product.rating, 1)}
            {product.review_count !== null && (
              <span className={styles.reviews}> ({formatNumber(product.review_count)} opiniones)</span>
            )}
          </p>
        )}
        <p className={styles.reason}>
          <span className={styles.reasonLabel}>Por qué te lo recomiendo: </span>
          {reason}
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
