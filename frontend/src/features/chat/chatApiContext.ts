import { createContext, useContext } from 'react'
import { httpChatApi, type ChatApi } from '../../api/chat'

export const ChatApiContext = createContext<ChatApi>(httpChatApi)

export function useChatApi(): ChatApi {
  return useContext(ChatApiContext)
}
