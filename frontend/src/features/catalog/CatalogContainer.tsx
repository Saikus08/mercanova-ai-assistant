import { useSearchParams } from 'react-router'
import type { ProductListParams } from '../../api/types'
import { CatalogFilters } from '../../components/catalog/CatalogFilters'
import { Pagination } from '../../components/catalog/Pagination'
import { ProductGrid } from '../../components/catalog/ProductGrid'
import { StatusMessage } from '../../components/catalog/StatusMessage'
import { Spinner } from '../../components/ui'
import { useCatalogApi } from './catalogApiContext'
import { CATALOG_PAGE_SIZE, parseCatalogParams, toCatalogSearch } from './catalogParams'
import { useAsyncResource } from './useAsyncResource'
import styles from './CatalogContainer.module.css'

/** Catalog screen (RF-01): filters in the URL, product list with loading, error and empty states. */
export function CatalogContainer() {
  const api = useCatalogApi()
  const [searchParams, setSearchParams] = useSearchParams()
  const params = parseCatalogParams(searchParams)
  const query = { ...params, page_size: CATALOG_PAGE_SIZE }
  const queryKey = JSON.stringify(query)

  const products = useAsyncResource(queryKey, (signal) => api.listProducts(query, signal))
  const categories = useAsyncResource('categories', (signal) => api.listCategories(signal))

  const updateParams = (next: ProductListParams) => setSearchParams(toCatalogSearch(next))
  const changeFilters = (next: ProductListParams) => updateParams({ ...next, page: undefined })
  const clearFilters = () => updateParams({})

  return (
    <div className={styles.layout}>
      <aside className={styles.sidebar}>
        <CatalogFilters
          key={searchParams.toString()}
          value={params}
          categories={categories.status === 'success' ? categories.data : []}
          onChange={changeFilters}
          onClear={clearFilters}
        />
      </aside>

      <section className={styles.results} aria-labelledby="catalog-title">
        <h1 id="catalog-title" className={styles.title}>
          Catálogo
        </h1>

        {products.status === 'loading' && (
          <div className={styles.loading}>
            <Spinner size="lg" label="Cargando productos…" />
          </div>
        )}

        {products.status === 'error' && (
          <StatusMessage
            tone="error"
            title="No pudimos cargar los productos"
            message={products.message}
            actionLabel="Reintentar"
            onAction={products.retry}
          />
        )}

        {products.status === 'success' && products.data.items.length === 0 && (
          <StatusMessage
            title="No encontramos productos"
            message="Probá con otra búsqueda o quitá algunos filtros."
            actionLabel="Quitar filtros"
            onAction={clearFilters}
          />
        )}

        {products.status === 'success' && products.data.items.length > 0 && (
          <>
            <p className={styles.count}>
              {products.data.total === 1 ? '1 producto' : `${products.data.total} productos`}
            </p>
            <ProductGrid products={products.data.items} />
            <Pagination
              page={products.data.page}
              pageSize={products.data.page_size}
              total={products.data.total}
              onPageChange={(page) => updateParams({ ...params, page })}
            />
          </>
        )}
      </section>
    </div>
  )
}
