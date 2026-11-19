import { useCallback, useEffect, useMemo, useReducer, useRef, type ReactNode } from 'react'
import { responseToEvents } from '../../api/chat'
import { ApiRequestError } from '../../api/http'
import type { ChatStreamEvent } from '../../api/types'
import { useCart } from '../cart/useCart'
import { useChatApi } from './chatApiContext'
import { chatReducer, initialChatState } from './chatState'
import { ChatContext, type ChatContextValue } from './useChat'

const FALLBACK_ERROR = 'Ocurrió un error inesperado. Intentá de nuevo en unos minutos.'
const CUT_OFF_ERROR = 'La respuesta se cortó antes de terminar. Intentá de nuevo.'

const isAbort = (error: unknown) => error instanceof DOMException && error.name === 'AbortError'
const messageOf = (error: unknown) => (error instanceof ApiRequestError ? error.message : FALLBACK_ERROR)

/**
 * Holds the conversation for the whole app, so it survives moving to the cart and back.
 * The conversation id and every message come from the server; nothing is kept in the browser.
 */
export function ChatProvider({ children }: { children: ReactNode }) {
  const api = useChatApi()
  const { reload: reloadCart } = useCart()
  const [state, dispatch] = useReducer(chatReducer, initialChatState)
  const conversationId = useRef<string | null>(null)
  const controller = useRef<AbortController | null>(null)
  const nextId = useRef(0)

  useEffect(() => {
    conversationId.current = state.conversationId
  }, [state.conversationId])

  useEffect(() => () => controller.current?.abort(), [])

  const busy = state.turns.some((turn) => turn.role === 'assistant' && turn.status === 'streaming')

  const send = useCallback(
    (raw: string) => {
      const text = raw.trim()
      if (!text || controller.current) return

      const assistantId = `a${nextId.current}`
      dispatch({ type: 'sent', userId: `u${nextId.current}`, assistantId, text })
      nextId.current += 1

      const current = new AbortController()
      controller.current = current
      const request = { message: text, conversation_id: conversationId.current, input_mode: 'text' as const }
      let received = 0
      let finished = false

      const onEvent = (event: ChatStreamEvent) => {
        if (current.signal.aborted) return
        received += 1
        if (event.event === 'meta') conversationId.current = event.data.conversation_id
        if (event.event === 'done' || event.event === 'error') finished = true
        // The assistant changed the cart: the header and the cart screen read it again from the server.
        if (event.event === 'block' && event.data.type === 'cart_updated') reloadCart()
        dispatch({ type: 'event', assistantId, event })
      }

      const run = async () => {
        try {
          await api.stream(request, onEvent, current.signal)
        } catch (error) {
          if (isAbort(error)) return
          const connectionFailed = error instanceof ApiRequestError && error.code === 'NETWORK_ERROR'
          if (received > 0 || !connectionFailed) throw error
          // The stream connection failed before any event: ask once for the complete answer (POST /api/chat).
          responseToEvents(await api.send(request, current.signal)).forEach(onEvent)
        }
      }

      run()
        .then(() => {
          if (!finished && !current.signal.aborted) dispatch({ type: 'failed', assistantId, message: CUT_OFF_ERROR })
        })
        .catch((error: unknown) => {
          if (!isAbort(error)) dispatch({ type: 'failed', assistantId, message: messageOf(error) })
        })
        .finally(() => {
          if (controller.current === current) controller.current = null
        })
    },
    [api, reloadCart],
  )

  const value = useMemo<ChatContextValue>(() => ({ ...state, busy, send }), [state, busy, send])

  return <ChatContext.Provider value={value}>{children}</ChatContext.Provider>
}
