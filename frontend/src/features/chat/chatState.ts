import type { ChatBlock, ChatStreamEvent, ToolUsage } from '../../api/types'

export type TurnStatus = 'streaming' | 'done' | 'error'

export interface UserTurn {
  id: string
  role: 'user'
  text: string
}

export interface AssistantTurn {
  id: string
  role: 'assistant'
  /** Text written so far; replaced by the full reply when the turn ends. */
  text: string
  blocks: ChatBlock[]
  /** Tools the assistant ran, shown in the "Cómo lo resolví" panel. */
  toolsUsed: ToolUsage[]
  /** Tool running right now, to show what the assistant is doing. */
  activeTool: string | null
  status: TurnStatus
  /** Spanish message shown when the turn failed. */
  errorMessage: string | null
}

export type ChatTurn = UserTurn | AssistantTurn

export interface ChatState {
  conversationId: string | null
  turns: ChatTurn[]
}

export type ChatAction =
  | { type: 'sent'; userId: string; assistantId: string; text: string }
  | { type: 'event'; assistantId: string; event: ChatStreamEvent }
  | { type: 'failed'; assistantId: string; message: string }

export const initialChatState: ChatState = { conversationId: null, turns: [] }

const updateAssistant = (state: ChatState, id: string, update: (turn: AssistantTurn) => AssistantTurn): ChatState => ({
  ...state,
  turns: state.turns.map((turn) => (turn.id === id && turn.role === 'assistant' ? update(turn) : turn)),
})

function applyEvent(state: ChatState, id: string, event: ChatStreamEvent): ChatState {
  switch (event.event) {
    case 'meta':
      return { ...state, conversationId: event.data.conversation_id }
    case 'tool_call':
      return updateAssistant(state, id, (turn) => ({
        ...turn,
        activeTool: event.data.name,
        toolsUsed: [...turn.toolsUsed, event.data],
      }))
    case 'token':
      return updateAssistant(state, id, (turn) => ({ ...turn, activeTool: null, text: turn.text + event.data.text }))
    case 'block':
      return updateAssistant(state, id, (turn) => ({ ...turn, blocks: [...turn.blocks, event.data] }))
    case 'done':
      return updateAssistant(state, id, (turn) => ({
        ...turn,
        text: event.data.reply,
        toolsUsed: event.data.tools_used,
        activeTool: null,
        status: 'done',
      }))
    case 'error':
      return updateAssistant(state, id, (turn) => ({
        ...turn,
        activeTool: null,
        status: 'error',
        errorMessage: event.data.error.message,
      }))
  }
}

export function chatReducer(state: ChatState, action: ChatAction): ChatState {
  switch (action.type) {
    case 'sent':
      return {
        ...state,
        turns: [
          ...state.turns,
          { id: action.userId, role: 'user', text: action.text },
          {
            id: action.assistantId,
            role: 'assistant',
            text: '',
            blocks: [],
            toolsUsed: [],
            activeTool: null,
            status: 'streaming',
            errorMessage: null,
          },
        ],
      }
    case 'event':
      return applyEvent(state, action.assistantId, action.event)
    case 'failed':
      return updateAssistant(state, action.assistantId, (turn) =>
        turn.status === 'streaming' ? { ...turn, activeTool: null, status: 'error', errorMessage: action.message } : turn,
      )
  }
}
