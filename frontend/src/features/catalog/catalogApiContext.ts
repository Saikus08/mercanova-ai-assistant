import { createContext, useContext } from 'react'
import { httpCatalogApi, type CatalogApi } from '../../api/catalog'

let mockApi: Promise<CatalogApi> | undefined

/** Loads the simulated catalog on first use, so it never ships in the main bundle. */
function loadMockApi(): Promise<CatalogApi> {
  mockApi ??= import('../../api/mocks/mockCatalogApi').then((m) => m.createMockCatalogApi())
  return mockApi
}

const lazyMockCatalogApi: CatalogApi = {
  listProducts: async (params, signal) => (await loadMockApi()).listProducts(params, signal),
  getProduct: async (productId, signal) => (await loadMockApi()).getProduct(productId, signal),
  listCategories: async (signal) => (await loadMockApi()).listCategories(signal),
}

/** `VITE_USE_MOCKS=true` serves the catalog from simulated data instead of the backend. */
const defaultCatalogApi: CatalogApi =
  import.meta.env.VITE_USE_MOCKS === 'true' ? lazyMockCatalogApi : httpCatalogApi

export const CatalogApiContext = createContext<CatalogApi>(defaultCatalogApi)

export function useCatalogApi(): CatalogApi {
  return useContext(CatalogApiContext)
}
