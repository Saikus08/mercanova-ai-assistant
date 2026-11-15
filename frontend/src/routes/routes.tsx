import { Route, Routes } from 'react-router'
import { CatalogPage } from '../pages/CatalogPage'
import { ProductDetailPage } from '../pages/ProductDetailPage'
import { UiShowcasePage } from '../pages/UiShowcasePage'
import { paths } from './paths'

export function AppRoutes() {
  return (
    <Routes>
      <Route path={paths.catalog} element={<CatalogPage />} />
      <Route path={paths.productPattern} element={<ProductDetailPage />} />
      <Route path={paths.ui} element={<UiShowcasePage />} />
    </Routes>
  )
}
