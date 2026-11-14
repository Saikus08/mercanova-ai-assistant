import { apiGet, buildQuery } from './http'
import type { CategoryList, ProductDetail, ProductList, ProductListParams } from './types'

/** Catalog endpoints (docs/api-contract.md, "Catálogo"). Implemented over HTTP and with mock data. */
export interface CatalogApi {
  listProducts(params: ProductListParams, signal?: AbortSignal): Promise<ProductList>
  getProduct(productId: string, signal?: AbortSignal): Promise<ProductDetail>
  listCategories(signal?: AbortSignal): Promise<CategoryList>
}

export const httpCatalogApi: CatalogApi = {
  listProducts: (params, signal) => apiGet<ProductList>(`/products${buildQuery({ ...params })}`, signal),
  getProduct: (productId, signal) =>
    apiGet<ProductDetail>(`/products/${encodeURIComponent(productId)}`, signal),
  listCategories: (signal) => apiGet<CategoryList>('/categories', signal),
}
