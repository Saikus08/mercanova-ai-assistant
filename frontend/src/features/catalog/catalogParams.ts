import type { ProductListParams, ProductSort } from '../../api/types'

export const CATALOG_PAGE_SIZE = 12

const SORTS: readonly ProductSort[] = ['price_asc', 'price_desc', 'rating']

function positiveNumber(value: string | null): number | undefined {
  if (value === null || value.trim() === '') return undefined
  const parsed = Number(value)
  return Number.isFinite(parsed) && parsed >= 0 ? parsed : undefined
}

function text(value: string | null): string | undefined {
  const trimmed = value?.trim()
  return trimmed ? trimmed : undefined
}

/** Reads catalog filters from the URL, ignoring values the API would reject. */
export function parseCatalogParams(search: URLSearchParams): ProductListParams {
  const sort = search.get('sort')
  const page = positiveNumber(search.get('page'))
  return {
    q: text(search.get('q')),
    category: text(search.get('category')),
    subcategory: text(search.get('subcategory')),
    min_price: positiveNumber(search.get('min_price')),
    max_price: positiveNumber(search.get('max_price')),
    in_stock: search.get('in_stock') === 'true' ? true : undefined,
    sort: SORTS.includes(sort as ProductSort) ? (sort as ProductSort) : undefined,
    page: page && Number.isInteger(page) && page >= 1 ? page : undefined,
  }
}

/** Writes filters back to the URL, so a filtered view can be shared or restored with "Atrás". */
export function toCatalogSearch(params: ProductListParams): URLSearchParams {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === '' || value === false) continue
    if (key === 'page' && value === 1) continue
    search.set(key, String(value))
  }
  return search
}
