import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { describe, expect, it } from 'vitest'
import { App } from './App'

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  )
}

describe('App routes', () => {
  it('shows the catalog placeholder on /', () => {
    renderAt('/')

    expect(screen.getByRole('heading', { name: 'Catálogo próximamente' })).toBeInTheDocument()
  })

  it('shows the UI showcase on /ui', () => {
    renderAt('/ui')

    expect(screen.getByRole('heading', { name: 'Componentes de interfaz' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Abrir modal' })).toBeInTheDocument()
  })
})
