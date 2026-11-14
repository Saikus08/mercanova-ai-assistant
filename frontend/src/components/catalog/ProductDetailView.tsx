import { Link } from 'react-router'
import type { ProductDetail, Specification } from '../../api/types'
import { Badge, Card } from '../ui'
import { formatNumber } from './format'
import { PriceTag } from './PriceTag'
import { productPath } from './paths'
import { StockBadge } from './StockBadge'
import styles from './ProductDetailView.module.css'

function groupSpecifications(specifications: Specification[]): [string, Specification[]][] {
  const groups = new Map<string, Specification[]>()
  for (const spec of specifications) {
    groups.set(spec.group, [...(groups.get(spec.group) ?? []), spec])
  }
  return [...groups.entries()]
}

function TagList({ title, items, variant }: { title: string; items: string[]; variant: 'success' | 'neutral' }) {
  if (items.length === 0) return null
  return (
    <div className={styles.tagGroup}>
      <h3 className={styles.subheading}>{title}</h3>
      <ul className={styles.tags}>
        {items.map((item) => (
          <li key={item}>
            <Badge variant={variant}>{item}</Badge>
          </li>
        ))}
      </ul>
    </div>
  )
}

export function ProductDetailView({ product }: { product: ProductDetail }) {
  const specGroups = groupSpecifications(product.specifications)

  return (
    <article className={styles.detail} aria-labelledby="product-name">
      <div className={styles.hero}>
        <img src={product.image_url} alt={product.name} className={styles.image} />

        <div className={styles.summary}>
          <p className={styles.meta}>
            {product.brand} · {product.category} · {product.subcategory}
          </p>
          <h1 id="product-name" className={styles.name}>
            {product.name}
          </h1>
          <p className={styles.rating}>
            <span aria-hidden="true">★ </span>
            {formatNumber(product.rating, 1)}
            <span className={styles.muted}> ({formatNumber(product.review_count)} opiniones)</span>
          </p>
          <PriceTag price={product.price} size="lg" />
          <div className={styles.stock}>
            <StockBadge availableQty={product.available_qty} />
            {product.in_stock && (
              <span className={styles.muted}>
                {product.available_qty === 1
                  ? '1 unidad disponible'
                  : `${formatNumber(product.available_qty)} unidades disponibles`}
              </span>
            )}
          </div>
          <p>{product.short_description}</p>
          <ul className={styles.policies}>
            <li>Garantía: {product.warranty_months} meses</li>
            <li>Devolución: hasta {product.return_days} días</li>
            <li>SKU: {product.sku}</li>
          </ul>
        </div>
      </div>

      <Card padding="lg" className={styles.section}>
        <h2 className={styles.heading}>Descripción</h2>
        <p>{product.description}</p>
        {product.key_features.length > 0 && (
          <ul className={styles.features}>
            {product.key_features.map((feature) => (
              <li key={feature}>{feature}</li>
            ))}
          </ul>
        )}
        <TagList title="Recomendado para" items={product.recommended_for} variant="success" />
        <TagList title="No recomendado para" items={product.not_recommended_for} variant="neutral" />
      </Card>

      <Card padding="lg" className={styles.section}>
        <h2 className={styles.heading}>Especificaciones</h2>
        {specGroups.map(([group, specs]) => (
          <table key={group} className={styles.table}>
            <caption className={styles.caption}>{group}</caption>
            <tbody>
              {specs.map((spec) => (
                <tr key={spec.name}>
                  <th scope="row">{spec.name}</th>
                  <td>{spec.unit ? `${spec.value} ${spec.unit}` : spec.value}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ))}
        <table className={styles.table}>
          <caption className={styles.caption}>Físicas</caption>
          <tbody>
            <tr>
              <th scope="row">Color</th>
              <td>{product.color}</td>
            </tr>
            <tr>
              <th scope="row">Dimensiones</th>
              <td>
                {formatNumber(product.dimensions_cm.width, 1)} × {formatNumber(product.dimensions_cm.height, 1)} ×{' '}
                {formatNumber(product.dimensions_cm.depth, 1)} cm
              </td>
            </tr>
            <tr>
              <th scope="row">Peso</th>
              <td>{formatNumber(product.weight_kg, 2)} kg</td>
            </tr>
          </tbody>
        </table>
      </Card>

      {product.availability.length > 0 && (
        <Card padding="lg" className={styles.section}>
          <h2 className={styles.heading}>Disponibilidad por depósito</h2>
          <table className={styles.table}>
            <thead>
              <tr>
                <th scope="col">Depósito</th>
                <th scope="col">Ciudad</th>
                <th scope="col">Unidades</th>
                <th scope="col">Retiro</th>
              </tr>
            </thead>
            <tbody>
              {product.availability.map((warehouse) => (
                <tr key={warehouse.warehouse_id}>
                  <th scope="row">{warehouse.warehouse_name}</th>
                  <td>{warehouse.city}</td>
                  <td>{formatNumber(warehouse.available_qty)}</td>
                  <td>{warehouse.pickup_enabled ? 'Sí' : 'No'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}

      {product.related.length > 0 && (
        <Card padding="lg" className={styles.section}>
          <h2 className={styles.heading}>Productos relacionados</h2>
          <ul className={styles.related}>
            {product.related.map((related) => (
              <li key={related.product_id}>
                <Link to={productPath(related.product_id)}>{related.name}</Link>
              </li>
            ))}
          </ul>
        </Card>
      )}
    </article>
  )
}
