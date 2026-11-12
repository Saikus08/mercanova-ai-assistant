import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { Modal } from './Modal'

function ModalHarness({ onClose }: { onClose?: () => void }) {
  const [open, setOpen] = useState(false)
  const close = () => {
    onClose?.()
    setOpen(false)
  }
  return (
    <>
      <button type="button" onClick={() => setOpen(true)}>
        Abrir
      </button>
      <Modal open={open} title="Confirmar compra" onClose={close}>
        <p>Total: USD 937,24</p>
      </Modal>
    </>
  )
}

describe('Modal', () => {
  it('renders nothing while closed', () => {
    render(<Modal open={false} title="Confirmar compra" onClose={() => {}}>Contenido</Modal>)

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('opens as an accessible dialog labelled by its title, with focus inside', async () => {
    render(<ModalHarness />)

    await userEvent.click(screen.getByRole('button', { name: 'Abrir' }))

    const dialog = screen.getByRole('dialog', { name: 'Confirmar compra' })
    expect(dialog).toHaveAttribute('aria-modal', 'true')
    expect(dialog).toContainElement(document.activeElement as HTMLElement)
    expect(screen.getByText('Total: USD 937,24')).toBeInTheDocument()
  })

  it('closes on Escape and returns focus to the trigger', async () => {
    const onClose = vi.fn()
    render(<ModalHarness onClose={onClose} />)
    const trigger = screen.getByRole('button', { name: 'Abrir' })

    await userEvent.click(trigger)
    await userEvent.keyboard('{Escape}')

    expect(onClose).toHaveBeenCalledTimes(1)
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(trigger).toHaveFocus()
  })

  it('closes with the close button', async () => {
    const onClose = vi.fn()
    render(<ModalHarness onClose={onClose} />)

    await userEvent.click(screen.getByRole('button', { name: 'Abrir' }))
    await userEvent.click(screen.getByRole('button', { name: 'Cerrar' }))

    expect(onClose).toHaveBeenCalledTimes(1)
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })
})
