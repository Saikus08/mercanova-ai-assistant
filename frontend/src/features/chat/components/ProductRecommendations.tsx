import type { ReactNode } from 'react'
import type { ChatProduct, ProductRecommendationsBlock } from '../../../api/types'
import { RecommendationCard } from './RecommendationCard'
import styles from './ProductRecommendations.module.css'

export interface ProductRecommendationsProps {
  block: ProductRecommendationsBlock
  /** Purchase actions for one product (add to cart), supplied by the container. */
  renderActions?: (product: ChatProduct) => ReactNode
}

/** Block `product_recommendations`: one card per recommended product. */
export function ProductRecommendations({ block, renderActions }: ProductRecommendationsProps) {
  return (
    <ul className={styles.grid} aria-label="Productos recomendados">
      {block.items.map((item) => (
        <li key={item.product.product_id}>
          <RecommendationCard recommendation={item} actions={renderActions?.(item.product)} />
        </li>
      ))}
    </ul>
  )
}
