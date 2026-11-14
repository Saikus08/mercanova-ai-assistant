import type { CatalogApi } from '../catalog'
import { ApiRequestError } from '../http'
import type { ProductDetail, ProductListParams, ProductSummary } from '../types'
import { mockCategories, mockProducts } from './catalogData'

const DEFAULT_PAGE_SIZE = 20
const MAX_PAGE_SIZE = 100

function toSummary(product: ProductDetail): ProductSummary {
  const {
    product_id, sku, name, brand, category, subcategory, short_description,
    image_url, rating, review_count, price, available_qty, in_stock,
  } = product
  return {
    product_id, sku, name, brand, category, subcategory, short_description,
    image_url, rating, review_count, price, available_qty, in_stock,
  }
}

function matches(product: ProductDetail, params: ProductListParams): boolean {
  const text = params.q?.trim().toLowerCase()
  if (text && ![product.name, product.brand, product.short_description].some((v) => v.toLowerCase().includes(text))) {
    return false
  }
  if (params.category && product.category !== params.category) return false
  if (params.subcategory && product.subcategory !== params.subcategory) return false
  if (params.brand && product.brand !== params.brand) return false
  if (params.min_price !== undefined && product.price.current < params.min_price) return false
  if (params.max_price !== undefined && product.price.current > params.max_price) return false
  if (params.in_stock && !product.in_stock) return false
  return true
}

const comparators = {
  price_asc: (a: ProductDetail, b: ProductDetail) => a.price.current - b.price.current,
  price_desc: (a: ProductDetail, b: ProductDetail) => b.price.current - a.price.current,
  rating: (a: ProductDetail, b: ProductDetail) => b.rating - a.rating,
} as const

/** In-memory implementation of the catalog endpoints, with the same filters as the contract. */
export function createMockCatalogApi(
  products: ProductDetail[] = mockProducts,
  categories = mockCategories,
): CatalogApi {
  return {
    async listProducts(params) {
      const pageSize = Math.min(params.page_size ?? DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE)
      const page = params.page ?? 1
      const filtered = products.filter((p) => matches(p, params))
      if (params.sort) filtered.sort(comparators[params.sort])
      const start = (page - 1) * pageSize
      return {
        items: filtered.slice(start, start + pageSize).map(toSummary),
        page,
        page_size: pageSize,
        total: filtered.length,
      }
    },
    async getProduct(productId) {
      const found = products.find((p) => p.product_id === productId)
      if (!found) {
        throw new ApiRequestError('PRODUCT_NOT_FOUND', 'No encontramos ese producto.', 404, {
          product_id: productId,
        })
      }
      return found
    },
    async listCategories() {
      return categories
    },
  }
}
