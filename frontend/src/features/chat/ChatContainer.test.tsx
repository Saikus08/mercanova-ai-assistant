import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import type { CartApi } from '../../api/cart'
import type { ChatApi } from '../../api/chat'
import { ApiRequestError } from '../../api/http'
import type { ChatStreamEvent } from '../../api/types'
import { createFakeCartApi } from '../../test/fakeCartApi'
import { answerEvents, chatProduct, createFakeChatApi } from '../../test/fakeChatApi'
import { renderWithShop } from '../../test/renderWithShop'
import { ChatContainer } from './ChatContainer'

const recommendation = answerEvents('Te recomiendo estos auriculares.', {
  tools: [{ name: 'search_products', args: { query: 'headphones for video calls', max_price: 200 } }],
  blocks: [{ type: 'product_recommendations', items: [{ product: chatProduct(), reason: 'Buen micrófono.' }] }],
})

async function sendMessage(text: string) {
  const user = userEvent.setup()
  await user.type(screen.getByLabelText('¿Qué estás buscando?'), text)
  await user.click(screen.getByRole('button', { name: 'Enviar' }))
  return user
}

describe('ChatContainer', () => {
  it('shows examples when the conversation is empty and sends one when clicked', async () => {
    const user = userEvent.setup()
    const chatApi = createFakeChatApi()
    renderWithShop(<ChatContainer onCheckout={() => {}} />, { chatApi })

    await user.click(screen.getByRole('button', { name: 'Busco un monitor para programar' }))

    const log = screen.getByRole('log', { name: 'Conversación' })
    expect(within(log).getByText('Busco un monitor para programar')).toBeInTheDocument()
    expect(await within(log).findByText('Hola, ¿en qué te ayudo?')).toBeInTheDocument()
  })

  it('shows the answer, the recommended products and the tools used', async () => {
    const chatApi = createFakeChatApi([recommendation])
    renderWithShop(<ChatContainer onCheckout={() => {}} />, { chatApi })

    const user = await sendMessage('Necesito auriculares para videollamadas')

    expect(await screen.findByText('Te recomiendo estos auriculares.')).toBeInTheDocument()
    expect(screen.getByText('Buen micrófono.')).toBeInTheDocument()
    await user.click(screen.getByText('Cómo lo resolví'))
    expect(screen.getByText('Buscó productos en el catálogo')).toBeInTheDocument()
    expect(chatApi.requests[0]).toEqual({
      message: 'Necesito auriculares para videollamadas',
      conversation_id: null,
      input_mode: 'text',
    })
  })

  it('adds a recommended product to the cart', async () => {
    const cartApi = createFakeCartApi()
    const addItem = vi.fn(cartApi.addItem)
    renderWithShop(<ChatContainer onCheckout={() => {}} />, {
      chatApi: createFakeChatApi([recommendation]),
      cartApi: { ...cartApi, addItem },
    })

    const user = await sendMessage('auriculares')
    await user.click(await screen.findByRole('button', { name: 'Agregar al carrito: Echo Calm ANC' }))

    expect(addItem).toHaveBeenCalledWith('MN-HEA-0001', 1)
    expect(await screen.findByText('Agregado al carrito')).toBeInTheDocument()
  })

  it('sends the conversation id after the first answer and a quick reply as the next message', async () => {
    const chatApi = createFakeChatApi([
      answerEvents('Necesito un dato más.', {
        conversationId: 'c42',
        blocks: [{ type: 'clarification', question: '¿Para qué lo vas a usar?', options: ['Trabajo', 'Gaming'] }],
      }),
    ])
    renderWithShop(<ChatContainer onCheckout={() => {}} />, { chatApi })

    const user = await sendMessage('Quiero un monitor')
    await user.click(await screen.findByRole('button', { name: 'Gaming' }))

    expect(await screen.findByText('Hola, ¿en qué te ayudo?')).toBeInTheDocument()
    expect(chatApi.requests[1]).toEqual({ message: 'Gaming', conversation_id: 'c42', input_mode: 'text' })
    // The old question cannot be answered twice.
    expect(screen.getByRole('button', { name: 'Gaming' })).toBeDisabled()
  })

  it('reloads the cart when the assistant changes it', async () => {
    const cartApi = createFakeCartApi()
    const getCart = vi.fn<CartApi['getCart']>(cartApi.getCart)
    const cart = { items: [], item_count: 0, total: 0, currency: 'USD' as const }
    renderWithShop(<ChatContainer onCheckout={() => {}} />, {
      cartApi: { ...cartApi, getCart },
      chatApi: createFakeChatApi([answerEvents('Listo, lo agregué.', { blocks: [{ type: 'cart_updated', cart }] })]),
    })
    await vi.waitFor(() => expect(getCart).toHaveBeenCalledTimes(1))

    await sendMessage('Agregalo al carrito')

    expect(await screen.findByText(/Carrito actualizado/)).toBeInTheDocument()
    await vi.waitFor(() => expect(getCart).toHaveBeenCalledTimes(2))
  })

  it('opens the checkout from the checkout draft, never confirming by itself', async () => {
    const onCheckout = vi.fn()
    const cart = { items: [], item_count: 0, total: 0, currency: 'USD' as const }
    renderWithShop(<ChatContainer onCheckout={onCheckout} />, {
      chatApi: createFakeChatApi([answerEvents('Tu compra está lista.', { blocks: [{ type: 'checkout_draft', cart }] })]),
    })

    const user = await sendMessage('Quiero comprar')
    await user.click(await screen.findByRole('button', { name: 'Revisar y confirmar la compra' }))

    expect(onCheckout).toHaveBeenCalledTimes(1)
  })

  it('starts a new conversation that the server does not link to the previous one', async () => {
    const chatApi = createFakeChatApi([answerEvents('Primera respuesta.', { conversationId: 'c1' })])
    renderWithShop(<ChatContainer onCheckout={() => {}} />, { chatApi })
    expect(screen.queryByRole('button', { name: 'Nueva conversación' })).not.toBeInTheDocument()

    const user = await sendMessage('Hola')
    expect(await screen.findByText('Primera respuesta.')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Nueva conversación' }))

    expect(screen.queryByRole('log', { name: 'Conversación' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Busco un monitor para programar' })).toBeInTheDocument()

    await sendMessage('Otra consulta')
    expect(await screen.findByText('Hola, ¿en qué te ayudo?')).toBeInTheDocument()
    expect(chatApi.requests[1]).toEqual({ message: 'Otra consulta', conversation_id: null, input_mode: 'text' })
    expect(screen.queryByText('Primera respuesta.')).not.toBeInTheDocument()
  })

  it('shows the error event message and lets the user write again', async () => {
    const failure: ChatStreamEvent[] = [
      { event: 'meta', data: { conversation_id: 'c1' } },
      {
        event: 'error',
        data: { error: { code: 'LLM_UNAVAILABLE', message: 'El asistente no está disponible por ahora.' } },
      },
    ]
    renderWithShop(<ChatContainer onCheckout={() => {}} />, { chatApi: createFakeChatApi([failure]) })

    await sendMessage('Hola')

    expect(await screen.findByRole('alert')).toHaveTextContent('El asistente no está disponible por ahora.')
    await userEvent.type(screen.getByLabelText('¿Qué estás buscando?'), 'Otra vez')
    expect(screen.getByRole('button', { name: 'Enviar' })).toBeEnabled()
  })

  it('shows what the assistant is doing while a tool runs', async () => {
    let finish: () => void = () => {}
    const chatApi: ChatApi = {
      stream: (_request, onEvent) =>
        new Promise<void>((resolve) => {
          onEvent({ event: 'tool_call', data: { name: 'get_stock', args: {} } })
          finish = () => {
            onEvent({ event: 'done', data: { reply: 'Hay stock.', tools_used: [] } })
            resolve()
          }
        }),
      send: vi.fn(),
    }
    renderWithShop(<ChatContainer onCheckout={() => {}} />, { chatApi })

    await sendMessage('¿Hay stock?')

    expect(await screen.findByText('Consultando el stock…', { selector: '.visually-hidden' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Enviar' })).toBeDisabled()
    finish()
    expect(await screen.findByText('Hay stock.')).toBeInTheDocument()
  })

  it('asks for the complete answer when the stream connection fails', async () => {
    const fallback = createFakeChatApi([recommendation])
    const chatApi: ChatApi = {
      stream: vi.fn().mockRejectedValue(new ApiRequestError('NETWORK_ERROR', 'Sin conexión.', null)),
      send: vi.fn(fallback.send),
    }
    renderWithShop(<ChatContainer onCheckout={() => {}} />, { chatApi })

    await sendMessage('auriculares')

    expect(await screen.findByText('Te recomiendo estos auriculares.')).toBeInTheDocument()
    expect(chatApi.send).toHaveBeenCalledTimes(1)
  })

  it('shows the API error when the stream is rejected and does not retry', async () => {
    const chatApi: ChatApi = {
      stream: vi.fn().mockRejectedValue(new ApiRequestError('VALIDATION_ERROR', 'El mensaje es demasiado largo.', 400)),
      send: vi.fn(),
    }
    renderWithShop(<ChatContainer onCheckout={() => {}} />, { chatApi })

    await sendMessage('Hola')

    expect(await screen.findByRole('alert')).toHaveTextContent('El mensaje es demasiado largo.')
    expect(chatApi.send).not.toHaveBeenCalled()
  })
})
