import { createContext, useContext } from 'react'
import type { ChatState } from './chatState'

export interface ChatContextValue extends ChatState {
  /** An answer is being written: the composer waits until it ends. */
  busy: boolean
  send: (text: string) => void
}

export const ChatContext = createContext<ChatContextValue | null>(null)

export function useChat(): ChatContextValue {
  const value = useContext(ChatContext)
  if (!value) throw new Error('useChat must be used inside a ChatProvider')
  return value
}
