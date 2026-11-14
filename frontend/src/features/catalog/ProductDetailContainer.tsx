import { Link } from 'react-router'
import { ProductDetailView } from '../../components/catalog/ProductDetailView'
import { StatusMessage } from '../../components/catalog/StatusMessage'
import { Spinner } from '../../components/ui'
import { useCatalogApi } from './catalogApiContext'
import { useAsyncResource } from './useAsyncResource'
import styles from './ProductDetailContainer.module.css'

/** Product detail screen (RF-01). Price and stock come from the API on every visit. */
export function ProductDetailContainer({ productId }: { productId: string }) {
  const api = useCatalogApi()
  const product = useAsyncResource(productId, (signal) => api.getProduct(productId, signal))

  return (
    <div className={styles.page}>
      <Link to="/" className={styles.back}>
        ← Volver al catálogo
      </Link>

      {product.status === 'loading' && (
        <div className={styles.loading}>
          <Spinner size="lg" label="Cargando producto…" />
        </div>
      )}

      {product.status === 'error' &&
        (product.code === 'PRODUCT_NOT_FOUND' ? (
          <StatusMessage
            title="Este producto no existe"
            message="Puede que el enlace esté mal o que el producto ya no esté en el catálogo."
          />
        ) : (
          <StatusMessage
            tone="error"
            title="No pudimos cargar el producto"
            message={product.message}
            actionLabel="Reintentar"
            onAction={product.retry}
          />
        ))}

      {product.status === 'success' && <ProductDetailView product={product.data} />}
    </div>
  )
}
