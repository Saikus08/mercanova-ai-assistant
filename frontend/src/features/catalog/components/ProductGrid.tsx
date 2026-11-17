import type { ReactNode } from 'react'
import type { ProductSummary } from '../../../api/types'
import { ProductCard } from './ProductCard'
import styles from './ProductGrid.module.css'

export interface ProductGridProps {
  products: ProductSummary[]
  /** Builds the purchase actions of each card; supplied by the container. */
  renderActions?: (product: ProductSummary) => ReactNode
}

export function ProductGrid({ products, renderActions }: ProductGridProps) {
  return (
    <ul className={styles.grid} aria-label="Productos">
      {products.map((product) => (
        <li key={product.product_id}>
          <ProductCard product={product} actions={renderActions?.(product)} />
        </li>
      ))}
    </ul>
  )
}
