import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { describe, expect, it } from 'vitest'
import { createMockCatalogApi } from './api/mocks/mockCatalogApi'
import { App } from './App'
import { CatalogApiProvider } from './features/catalog/CatalogApiProvider'

function renderAt(path: string) {
  return render(
    <CatalogApiProvider api={createMockCatalogApi()}>
      <MemoryRouter initialEntries={[path]}>
        <App />
      </MemoryRouter>
    </CatalogApiProvider>,
  )
}

describe('App routes', () => {
  it('shows the catalog on /', async () => {
    renderAt('/')

    expect(screen.getByRole('heading', { name: 'Catálogo' })).toBeInTheDocument()
    expect(await screen.findByRole('list', { name: 'Productos' })).toBeInTheDocument()
  })

  it('shows a product detail on /productos/:productId', async () => {
    renderAt('/productos/MN-HEA-0001')

    expect(await screen.findByRole('heading', { level: 1, name: 'Echo Calm ANC' })).toBeInTheDocument()
  })

  it('shows the UI showcase on /ui', () => {
    renderAt('/ui')

    expect(screen.getByRole('heading', { name: 'Componentes de interfaz' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Abrir modal' })).toBeInTheDocument()
  })
})
