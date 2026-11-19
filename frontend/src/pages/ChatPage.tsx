import { useNavigate } from 'react-router'
import { ChatContainer } from '../features/chat/ChatContainer'
import { paths } from '../routes/paths'

export function ChatPage() {
  const navigate = useNavigate()
  return <ChatContainer onCheckout={() => navigate(paths.checkout)} />
}
