import { afterEach, describe, expect, it, vi } from 'vitest'
import { createSseParser, httpChatApi, responseToEvents, toChatEvent } from './chat'
import { ApiRequestError } from './http'
import type { ChatStreamEvent } from './types'

const request = { message: 'Hola', conversation_id: null, input_mode: 'text' as const }

function streamResponse(chunks: string[]): Response {
  const encoder = new TextEncoder()
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      chunks.forEach((chunk) => controller.enqueue(encoder.encode(chunk)))
      controller.close()
    },
  })
  return new Response(body, { status: 200, headers: { 'Content-Type': 'text/event-stream' } })
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('createSseParser', () => {
  it('returns complete frames and keeps a frame split across chunks', () => {
    const parser = createSseParser()

    expect(parser.push('event: meta\ndata: {"conversation_id":"c1"}\n\nevent: tok')).toEqual([
      { event: 'meta', data: '{"conversation_id":"c1"}' },
    ])
    expect(parser.push('en\ndata: {"text":"Hola "}\n')).toEqual([])
    expect(parser.push('\n')).toEqual([{ event: 'token', data: '{"text":"Hola "}' }])
  })

  it('accepts CRLF line endings, comments and multi-line data', () => {
    const parser = createSseParser()

    expect(parser.push(': ping\r\n\r\nevent: token\r\ndata: a\r\ndata: b\r\n\r\n')).toEqual([
      { event: 'token', data: 'a\nb' },
    ])
  })

  it('flushes a last frame without the final blank line', () => {
    const parser = createSseParser()
    parser.push('event: done\ndata: {}')

    expect(parser.flush()).toEqual([{ event: 'done', data: '{}' }])
  })
})

describe('toChatEvent', () => {
  it('parses known events and ignores unknown names or broken JSON', () => {
    expect(toChatEvent({ event: 'token', data: '{"text":"Hi"}' })).toEqual({ event: 'token', data: { text: 'Hi' } })
    expect(toChatEvent({ event: 'other', data: '{}' })).toBeNull()
    expect(toChatEvent({ event: 'token', data: '{broken' })).toBeNull()
  })
})

describe('responseToEvents', () => {
  it('replays a complete answer in the stream order', () => {
    const events = responseToEvents({
      conversation_id: 'c9',
      reply: 'Listo',
      blocks: [{ type: 'not_found', query: 'PlayStation 9' }],
      tools_used: [{ name: 'search_products', args: {} }],
    })

    expect(events.map((e) => e.event)).toEqual(['meta', 'token', 'block', 'done'])
  })
})

describe('httpChatApi.stream', () => {
  it('posts with the session header and emits the events in order', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      streamResponse([
        'event: meta\ndata: {"conversation_id":"c1"}\n\n',
        'event: token\ndata: {"text":"Te reco',
        'miendo"}\n\nevent: done\ndata: {"reply":"Te recomiendo","tools_used":[]}\n\n',
      ]),
    )
    vi.stubGlobal('fetch', fetchMock)
    const events: ChatStreamEvent[] = []

    await httpChatApi.stream(request, (event) => events.push(event))

    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/chat/stream')
    expect(init.headers['X-Session-Id']).toBeTruthy()
    expect(JSON.parse(init.body)).toEqual(request)
    expect(events).toEqual([
      { event: 'meta', data: { conversation_id: 'c1' } },
      { event: 'token', data: { text: 'Te recomiendo' } },
      { event: 'done', data: { reply: 'Te recomiendo', tools_used: [] } },
    ])
  })

  it('throws the contract error when the request is rejected', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ error: { code: 'MISSING_SESSION', message: 'Falta la sesión.' } }), { status: 400 }),
      ),
    )

    await expect(httpChatApi.stream(request, () => {})).rejects.toMatchObject({
      code: 'MISSING_SESSION',
      message: 'Falta la sesión.',
    })
  })

  it('throws a Spanish network error when the connection fails', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))

    const error = await httpChatApi.stream(request, () => {}).catch((e: unknown) => e)

    expect(error).toBeInstanceOf(ApiRequestError)
    expect(error).toMatchObject({ code: 'NETWORK_ERROR' })
  })
})
