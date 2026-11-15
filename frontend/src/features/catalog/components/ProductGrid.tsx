import type { ProductSummary } from '../../../api/types'
import { ProductCard } from './ProductCard'
import styles from './ProductGrid.module.css'

export function ProductGrid({ products }: { products: ProductSummary[] }) {
  return (
    <ul className={styles.grid} aria-label="Productos">
      {products.map((product) => (
        <li key={product.product_id}>
          <ProductCard product={product} />
        </li>
      ))}
    </ul>
  )
}
