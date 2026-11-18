import { act, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiRequestError } from '../../api/http'
import { answerEvents, createFakeChatApi } from '../../test/fakeChatApi'
import { FakeMediaRecorder, installFakeMicrophone, uninstallFakeMicrophone } from '../../test/fakeMicrophone'
import { createFakeSpeechApi } from '../../test/fakeSpeechApi'
import { renderWithShop } from '../../test/renderWithShop'
import { ChatContainer } from './ChatContainer'
import { MAX_RECORDING_SECONDS, VOICE_MESSAGES } from './useVoiceRecorder'

const startButton = () => screen.getByRole('button', { name: 'Hablar: grabar una consulta por voz' })
const stopButton = () => screen.findByRole('button', { name: 'Detener la grabación y enviar' })

describe('ChatContainer voice input', () => {
  afterEach(() => {
    uninstallFakeMicrophone()
    vi.useRealTimers()
  })

  it('records, transcribes and sends the text as a voice message', async () => {
    const user = userEvent.setup()
    const { track } = installFakeMicrophone()
    const chatApi = createFakeChatApi([answerEvents('Te recomiendo estos auriculares.')])
    const speechApi = createFakeSpeechApi({ text: 'Necesito auriculares para videollamadas' })
    renderWithShop(<ChatContainer onCheckout={() => {}} />, { chatApi, speechApi })

    await user.click(startButton())
    expect(await screen.findByText(/Grabando 0:00 de 0:55/)).toBeInTheDocument()
    await user.click(await stopButton())

    const log = await screen.findByRole('log', { name: 'Conversación' })
    expect(within(log).getByText('Necesito auriculares para videollamadas')).toBeInTheDocument()
    expect(await within(log).findByText('Te recomiendo estos auriculares.')).toBeInTheDocument()
    expect(chatApi.requests[0]).toEqual({
      message: 'Necesito auriculares para videollamadas',
      conversation_id: null,
      input_mode: 'voice',
    })
    expect(speechApi.audios[0].type).toBe('audio/webm;codecs=opus')
    // The microphone is released as soon as the recording ends.
    expect(track.stop).toHaveBeenCalled()
    expect(startButton()).toBeEnabled()
  })

  it('shows a clear message when the microphone permission is denied', async () => {
    const user = userEvent.setup()
    installFakeMicrophone({ denied: 'NotAllowedError' })
    const chatApi = createFakeChatApi()
    renderWithShop(<ChatContainer onCheckout={() => {}} />, { chatApi })

    await user.click(startButton())

    expect(await screen.findByRole('alert')).toHaveTextContent(VOICE_MESSAGES.permissionDenied)
    expect(chatApi.requests).toHaveLength(0)
    expect(startButton()).toBeEnabled()
  })

  it('shows a clear message when there is no microphone', async () => {
    const user = userEvent.setup()
    installFakeMicrophone({ denied: 'NotFoundError' })
    renderWithShop(<ChatContainer onCheckout={() => {}} />)

    await user.click(startButton())

    expect(await screen.findByRole('alert')).toHaveTextContent(VOICE_MESSAGES.noMicrophone)
  })

  it('explains that the browser cannot record when MediaRecorder is missing', async () => {
    const user = userEvent.setup()
    renderWithShop(<ChatContainer onCheckout={() => {}} />)

    await user.click(startButton())

    expect(await screen.findByRole('alert')).toHaveTextContent(VOICE_MESSAGES.unsupported)
  })

  it('shows the message of the backend when the audio cannot be understood', async () => {
    const user = userEvent.setup()
    installFakeMicrophone()
    const message = 'No pudimos entender el audio. Probá grabarlo de nuevo o escribí tu consulta.'
    const chatApi = createFakeChatApi()
    const speechApi = createFakeSpeechApi({ error: new ApiRequestError('AUDIO_UNREADABLE', message, 422) })
    renderWithShop(<ChatContainer onCheckout={() => {}} />, { chatApi, speechApi })

    await user.click(startButton())
    await user.click(await stopButton())

    expect(await screen.findByRole('alert')).toHaveTextContent(message)
    expect(chatApi.requests).toHaveLength(0)
  })

  it('does not send a recording without sound', async () => {
    const user = userEvent.setup()
    installFakeMicrophone()
    FakeMediaRecorder.nextAudio = ''
    const speechApi = createFakeSpeechApi()
    renderWithShop(<ChatContainer onCheckout={() => {}} />, { speechApi })

    await user.click(startButton())
    await user.click(await stopButton())

    expect(await screen.findByRole('alert')).toHaveTextContent(VOICE_MESSAGES.emptyRecording)
    expect(speechApi.audios).toHaveLength(0)
  })

  it('stops by itself at the time limit and sends what was recorded', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    installFakeMicrophone()
    const chatApi = createFakeChatApi()
    renderWithShop(<ChatContainer onCheckout={() => {}} />, { chatApi })

    await user.click(startButton())
    await stopButton()
    await act(async () => {
      vi.advanceTimersByTime(MAX_RECORDING_SECONDS * 1000)
    })

    expect(FakeMediaRecorder.instances[0].state).toBe('inactive')
    const log = await screen.findByRole('log', { name: 'Conversación' })
    expect(within(log).getByText('Necesito auriculares')).toBeInTheDocument()
    expect(chatApi.requests[0].input_mode).toBe('voice')
  })

  it('cannot start a recording while an answer is being written', async () => {
    const user = userEvent.setup()
    installFakeMicrophone()
    const chatApi = createFakeChatApi()
    chatApi.stream = () => new Promise(() => {})
    renderWithShop(<ChatContainer onCheckout={() => {}} />, { chatApi })

    await user.type(screen.getByLabelText('¿Qué estás buscando?'), 'Hola')
    await user.click(screen.getByRole('button', { name: 'Enviar' }))

    expect(startButton()).toBeDisabled()
  })
})
