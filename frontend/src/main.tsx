import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router'
import { App } from './App'
import { CartProvider } from './features/cart/CartProvider'
import { ChatProvider } from './features/chat/ChatProvider'
import { applyTokens } from './theme/tokens'
import './theme/global.css'

applyTokens()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <CartProvider>
        <ChatProvider>
          <App />
        </ChatProvider>
      </CartProvider>
    </BrowserRouter>
  </StrictMode>,
)
