import { render } from '@testing-library/react'
import type { ReactElement } from 'react'
import { MemoryRouter, Route, Routes } from 'react-router'
import type { CatalogApi } from '../api/catalog'
import { createMockCatalogApi } from '../api/mocks/mockCatalogApi'
import { CatalogApiProvider } from '../features/catalog/CatalogApiProvider'
import { LocationProbe } from './LocationProbe'

export function renderWithCatalog(
  ui: ReactElement,
  { api = createMockCatalogApi(), path = '/', route = '/' }: { api?: CatalogApi; path?: string; route?: string } = {},
) {
  return render(
    <CatalogApiProvider api={api}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path={route} element={ui} />
          <Route path="*" element={null} />
        </Routes>
        <LocationProbe />
      </MemoryRouter>
    </CatalogApiProvider>,
  )
}
