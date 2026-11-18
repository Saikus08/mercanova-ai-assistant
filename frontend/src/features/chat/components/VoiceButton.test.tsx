import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { VoiceButton } from './VoiceButton'

describe('VoiceButton', () => {
  it('starts a recording when idle', async () => {
    const onStart = vi.fn()
    render(<VoiceButton status="idle" onStart={onStart} onStop={vi.fn()} />)

    await userEvent.click(screen.getByRole('button', { name: 'Hablar: grabar una consulta por voz' }))

    expect(onStart).toHaveBeenCalledOnce()
  })

  it('stops the recording on the second click, even while an answer is being written', async () => {
    const onStop = vi.fn()
    render(<VoiceButton status="recording" disabled onStart={vi.fn()} onStop={onStop} />)

    await userEvent.click(screen.getByRole('button', { name: 'Detener la grabación y enviar' }))

    expect(onStop).toHaveBeenCalledOnce()
  })

  it('is blocked while waiting for permission and while transcribing', () => {
    const { rerender } = render(<VoiceButton status="requesting" onStart={vi.fn()} onStop={vi.fn()} />)
    expect(screen.getByRole('button', { name: 'Esperando permiso para usar el micrófono' })).toBeDisabled()

    rerender(<VoiceButton status="transcribing" onStart={vi.fn()} onStop={vi.fn()} />)
    expect(screen.getByRole('button', { name: 'Transcribiendo la consulta' })).toBeDisabled()
  })
})
