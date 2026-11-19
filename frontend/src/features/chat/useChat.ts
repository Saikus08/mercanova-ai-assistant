import { createContext, useContext } from 'react'
import type { InputMode } from '../../api/types'
import type { ChatState } from './chatState'

export interface ChatContextValue extends ChatState {
  /** An answer is being written: the composer waits until it ends. */
  busy: boolean
  /** `inputMode` tells the backend whether the text was typed or transcribed from voice. */
  send: (text: string, inputMode?: InputMode) => void
}

export const ChatContext = createContext<ChatContextValue | null>(null)

export function useChat(): ChatContextValue {
  const value = useContext(ChatContext)
  if (!value) throw new Error('useChat must be used inside a ChatProvider')
  return value
}
