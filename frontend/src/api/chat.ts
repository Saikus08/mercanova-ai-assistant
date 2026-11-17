import { ApiRequestError, apiPost } from './http'
import { getSessionId } from './session'
import type { ApiError, ChatRequest, ChatResponse, ChatStreamEvent, ChatStreamEventName } from './types'

const NETWORK_ERROR_MESSAGE = 'No pudimos conectarnos con el asistente. Revisá tu conexión e intentá de nuevo.'
const UNEXPECTED_ERROR_MESSAGE = 'Ocurrió un error inesperado. Intentá de nuevo en unos minutos.'

const EVENT_NAMES: readonly ChatStreamEventName[] = ['meta', 'tool_call', 'token', 'block', 'done', 'error']

/** Chat endpoints (docs/api-contract.md, "Asistente"). */
export interface ChatApi {
  /** POST /api/chat/stream: calls `onEvent` for every Server-Sent Event, in order. */
  stream(request: ChatRequest, onEvent: (event: ChatStreamEvent) => void, signal?: AbortSignal): Promise<void>
  /** POST /api/chat: the same answer at once. Used when the stream cannot be read. */
  send(request: ChatRequest, signal?: AbortSignal): Promise<ChatResponse>
}

export interface SseFrame {
  event: string
  data: string
}

/**
 * Incremental Server-Sent Events parser. `push` receives text as it arrives (frames can be split
 * across chunks) and returns the frames completed so far. Frames end with a blank line.
 */
export function createSseParser() {
  let buffer = ''

  const parseFrame = (raw: string): SseFrame | null => {
    let event = 'message'
    const data: string[] = []
    for (const line of raw.split('\n')) {
      if (line === '' || line.startsWith(':')) continue
      const colon = line.indexOf(':')
      const field = colon === -1 ? line : line.slice(0, colon)
      let value = colon === -1 ? '' : line.slice(colon + 1)
      if (value.startsWith(' ')) value = value.slice(1)
      if (field === 'event') event = value
      else if (field === 'data') data.push(value)
    }
    return data.length > 0 ? { event, data: data.join('\n') } : null
  }

  return {
    push(chunk: string): SseFrame[] {
      buffer += chunk.replace(/\r\n?/g, '\n')
      const frames: SseFrame[] = []
      let end = buffer.indexOf('\n\n')
      while (end !== -1) {
        const frame = parseFrame(buffer.slice(0, end))
        if (frame) frames.push(frame)
        buffer = buffer.slice(end + 2)
        end = buffer.indexOf('\n\n')
      }
      return frames
    },
    /** Frame left without the final blank line when the stream closed. */
    flush(): SseFrame[] {
      const frame = parseFrame(buffer)
      buffer = ''
      return frame ? [frame] : []
    },
  }
}

/** Turns a frame into a typed event. Unknown events and unreadable data are ignored. */
export function toChatEvent(frame: SseFrame): ChatStreamEvent | null {
  if (!EVENT_NAMES.includes(frame.event as ChatStreamEventName)) return null
  try {
    return { event: frame.event, data: JSON.parse(frame.data) } as ChatStreamEvent
  } catch {
    return null
  }
}

/** Replays a complete answer as the events the stream would have sent. */
export function responseToEvents(response: ChatResponse): ChatStreamEvent[] {
  return [
    { event: 'meta', data: { conversation_id: response.conversation_id } },
    { event: 'token', data: { text: response.reply } },
    ...response.blocks.map((block): ChatStreamEvent => ({ event: 'block', data: block })),
    { event: 'done', data: { reply: response.reply, tools_used: response.tools_used } },
  ]
}

function isApiError(body: unknown): body is ApiError {
  return (
    typeof body === 'object' &&
    body !== null &&
    'error' in body &&
    typeof (body as ApiError).error?.code === 'string' &&
    typeof (body as ApiError).error?.message === 'string'
  )
}

async function openStream(request: ChatRequest, signal?: AbortSignal): Promise<Response> {
  let response: Response
  try {
    response = await fetch('/api/chat/stream', {
      method: 'POST',
      headers: {
        Accept: 'text/event-stream',
        'Content-Type': 'application/json',
        'X-Session-Id': getSessionId(),
      },
      body: JSON.stringify(request),
      signal,
    })
  } catch (cause) {
    if (cause instanceof DOMException && cause.name === 'AbortError') throw cause
    throw new ApiRequestError('NETWORK_ERROR', NETWORK_ERROR_MESSAGE, null)
  }
  if (!response.ok) {
    const payload: unknown = await response.json().catch(() => null)
    if (isApiError(payload)) {
      const { code, message, details } = payload.error
      throw new ApiRequestError(code, message, response.status, details)
    }
    throw new ApiRequestError('INTERNAL_ERROR', UNEXPECTED_ERROR_MESSAGE, response.status)
  }
  return response
}

export const httpChatApi: ChatApi = {
  async stream(request, onEvent, signal) {
    const response = await openStream(request, signal)
    if (!response.body) {
      // The browser cannot read the body as a stream: ask for the complete answer instead.
      responseToEvents(await httpChatApi.send(request, signal)).forEach(onEvent)
      return
    }

    const parser = createSseParser()
    const reader = response.body.pipeThrough(new TextDecoderStream()).getReader()
    const emit = (frames: SseFrame[]) => {
      for (const frame of frames) {
        const event = toChatEvent(frame)
        if (event) onEvent(event)
      }
    }
    try {
      for (;;) {
        const { done, value } = await reader.read()
        if (done) break
        emit(parser.push(value))
      }
    } catch (cause) {
      if (cause instanceof DOMException && cause.name === 'AbortError') throw cause
      throw new ApiRequestError('NETWORK_ERROR', NETWORK_ERROR_MESSAGE, null)
    }
    emit(parser.flush())
  },
  send: (request, signal) => apiPost<ChatResponse>('/chat', request, signal),
}
