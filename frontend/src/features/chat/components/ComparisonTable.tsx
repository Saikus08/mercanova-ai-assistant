import { Link } from 'react-router'
import type { ComparisonAttribute, ComparisonBlock } from '../../../api/types'
import { productPath } from '../../../routes/paths'
import { PriceTag } from '../../catalog/components/PriceTag'
import { StockBadge } from '../../catalog/components/StockBadge'
import styles from './ComparisonTable.module.css'

const MISSING_VALUE = '—'

const formatValue = (attribute: ComparisonAttribute, productId: string): string => {
  const value = attribute.values[productId]
  if (value === null || value === undefined || value === '') return MISSING_VALUE
  return attribute.unit ? `${value} ${attribute.unit}` : value
}

/** Block `comparison`: price, stock and specifications side by side (RF-06). */
export function ComparisonTable({ block }: { block: ComparisonBlock }) {
  const { products, attributes } = block
  return (
    <div className={styles.wrapper}>
      <table className={styles.table}>
        <caption className={styles.caption}>Comparación de productos</caption>
        <thead>
          <tr>
            <td className={styles.corner} />
            {products.map((product) => (
              <th key={product.product_id} scope="col" className={styles.product}>
                <Link to={productPath(product.product_id)} className={styles.link}>
                  {product.name}
                </Link>
                <span className={styles.brand}>{product.brand}</span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          <tr>
            <th scope="row" className={styles.attribute}>
              Precio
            </th>
            {products.map((product) => (
              <td key={product.product_id}>
                <PriceTag price={product.price} />
              </td>
            ))}
          </tr>
          <tr>
            <th scope="row" className={styles.attribute}>
              Stock
            </th>
            {products.map((product) => (
              <td key={product.product_id}>
                <StockBadge availableQty={product.available_qty} />
              </td>
            ))}
          </tr>
          {attributes.map((attribute) => (
            <tr key={`${attribute.group}-${attribute.name}`}>
              <th scope="row" className={styles.attribute}>
                {attribute.name}
                <span className={styles.group}>{attribute.group}</span>
              </th>
              {products.map((product) => (
                <td key={product.product_id}>{formatValue(attribute, product.product_id)}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
