import type { ReactNode } from 'react'
import type { ChatApi } from '../../api/chat'
import { ChatApiContext } from './chatApiContext'

/** Lets tests (or a page) swap the chat API implementation. */
export function ChatApiProvider({ api, children }: { api: ChatApi; children: ReactNode }) {
  return <ChatApiContext.Provider value={api}>{children}</ChatApiContext.Provider>
}
