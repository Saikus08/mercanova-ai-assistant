import { describe, expect, it } from 'vitest'
import type { ChatStreamEvent } from '../../api/types'
import { chatReducer, initialChatState, type AssistantTurn, type ChatState } from './chatState'

const started = chatReducer(initialChatState, { type: 'sent', userId: 'u0', assistantId: 'a0', text: 'Hola' })

const apply = (state: ChatState, ...events: ChatStreamEvent[]) =>
  events.reduce((current, event) => chatReducer(current, { type: 'event', assistantId: 'a0', event }), state)

const assistant = (state: ChatState) => state.turns[1] as AssistantTurn

describe('chatReducer', () => {
  it('adds the user message and an empty answer in progress', () => {
    expect(started.turns).toHaveLength(2)
    expect(started.turns[0]).toEqual({ id: 'u0', role: 'user', text: 'Hola' })
    expect(assistant(started)).toMatchObject({ status: 'streaming', text: '', blocks: [] })
  })

  it('keeps the conversation id, the running tool and the text written so far', () => {
    let state = apply(
      started,
      { event: 'meta', data: { conversation_id: 'c1' } },
      { event: 'tool_call', data: { name: 'search_products', args: { query: 'headphones' } } },
    )
    expect(state.conversationId).toBe('c1')
    expect(assistant(state).activeTool).toBe('search_products')

    state = apply(state, { event: 'token', data: { text: 'Te ' } }, { event: 'token', data: { text: 'recomiendo' } })
    expect(assistant(state).text).toBe('Te recomiendo')
    expect(assistant(state).activeTool).toBeNull()
  })

  it('adds blocks and closes the turn with the full reply and tools of done', () => {
    const tools = [{ name: 'get_stock', args: { product_id: 'MN-1' } }]
    const state = apply(
      started,
      { event: 'token', data: { text: 'Parcial' } },
      { event: 'block', data: { type: 'not_found', query: 'PS9' } },
      { event: 'done', data: { reply: 'Respuesta completa', tools_used: tools } },
    )

    expect(assistant(state)).toMatchObject({
      status: 'done',
      text: 'Respuesta completa',
      toolsUsed: tools,
      blocks: [{ type: 'not_found', query: 'PS9' }],
    })
  })

  it('shows the error event message', () => {
    const state = apply(started, {
      event: 'error',
      data: { error: { code: 'LLM_UNAVAILABLE', message: 'El asistente no está disponible por ahora.' } },
    })

    expect(assistant(state)).toMatchObject({ status: 'error', errorMessage: 'El asistente no está disponible por ahora.' })
  })

  it('marks a failure only while the turn is still in progress', () => {
    const done = apply(started, { event: 'done', data: { reply: 'Ok', tools_used: [] } })

    expect(assistant(chatReducer(done, { type: 'failed', assistantId: 'a0', message: 'x' })).status).toBe('done')
    expect(assistant(chatReducer(started, { type: 'failed', assistantId: 'a0', message: 'x' })).status).toBe('error')
  })
})
