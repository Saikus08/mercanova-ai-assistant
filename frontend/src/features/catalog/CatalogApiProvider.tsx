import type { ReactNode } from 'react'
import type { CatalogApi } from '../../api/catalog'
import { CatalogApiContext } from './catalogApiContext'

/** Lets tests (or a page) swap the catalog API implementation. */
export function CatalogApiProvider({ api, children }: { api: CatalogApi; children: ReactNode }) {
  return <CatalogApiContext.Provider value={api}>{children}</CatalogApiContext.Provider>
}
