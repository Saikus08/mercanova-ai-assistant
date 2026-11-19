import type { ChatApi } from '../api/chat'
import type { ChatBlock, ChatProduct, ChatRequest, ChatStreamEvent, ToolUsage } from '../api/types'

export const chatProduct = (overrides: Partial<ChatProduct> = {}): ChatProduct => ({
  product_id: 'MN-HEA-0001',
  sku: 'HEA-10000',
  name: 'Echo Calm ANC',
  brand: 'Echo',
  category: 'Headphones',
  subcategory: 'Wireless',
  short_description: 'Wireless headphones with noise cancelling.',
  image_url: null,
  rating: 4.5,
  review_count: 120,
  price: { current: 50, list: 50, discount_percent: 0, currency: 'USD' },
  available_qty: 2,
  in_stock: true,
  ...overrides,
})

/** The events of a complete, successful answer. */
export function answerEvents(
  reply: string,
  { blocks = [], tools = [], conversationId = 'c1' }: { blocks?: ChatBlock[]; tools?: ToolUsage[]; conversationId?: string } = {},
): ChatStreamEvent[] {
  return [
    { event: 'meta', data: { conversation_id: conversationId } },
    ...tools.map((tool): ChatStreamEvent => ({ event: 'tool_call', data: tool })),
    ...reply.split(/(?<= )/).map((text): ChatStreamEvent => ({ event: 'token', data: { text } })),
    ...blocks.map((block): ChatStreamEvent => ({ event: 'block', data: block })),
    { event: 'done', data: { reply, tools_used: tools } },
  ]
}

/**
 * Chat API that answers every message with the next scripted list of events.
 * `requests` records what the screen sent, to check the conversation id.
 */
export function createFakeChatApi(script: ChatStreamEvent[][] = []) {
  const requests: ChatRequest[] = []
  let turn = 0
  const next = () => script[turn++] ?? answerEvents('Hola, ¿en qué te ayudo?')

  const api: ChatApi & { requests: ChatRequest[] } = {
    requests,
    async stream(request, onEvent) {
      requests.push(request)
      for (const event of next()) {
        await Promise.resolve()
        onEvent(event)
      }
    },
    async send(request) {
      requests.push(request)
      const events = next()
      const meta = events.find((e) => e.event === 'meta')
      const done = events.find((e) => e.event === 'done')
      return {
        conversation_id: meta?.event === 'meta' ? meta.data.conversation_id : 'c1',
        reply: done?.event === 'done' ? done.data.reply : '',
        blocks: events.flatMap((e) => (e.event === 'block' ? [e.data] : [])),
        tools_used: done?.event === 'done' ? done.data.tools_used : [],
      }
    },
  }
  return api
}
