import { useEffect, useRef } from 'react'
import { Button } from '../../../components/ui'
import type { ChatTurn } from '../chatState'
import { AssistantMessage } from './AssistantMessage'
import type { BlockActions } from './ChatBlockView'
import { ChatComposer } from './ChatComposer'
import { UserMessage } from './UserMessage'
import styles from './ChatView.module.css'

const EXAMPLE_PROMPTS = [
  'Necesito auriculares para videollamadas, máximo USD 200',
  'Busco un monitor para programar',
  'Quiero una notebook liviana para la facultad',
]

export interface ChatViewProps extends Omit<BlockActions, 'onSelectOption'> {
  turns: ChatTurn[]
  busy: boolean
  onSend: (text: string) => void
}

/** Chat screen: the conversation, examples when it is empty and the message field. */
export function ChatView({ turns, busy, onSend, ...actions }: ChatViewProps) {
  const endRef = useRef<HTMLDivElement>(null)
  const lastTurn = turns.at(-1)

  // Keep the newest content in view while the answer is written.
  useEffect(() => {
    endRef.current?.scrollIntoView?.({ block: 'end' })
  }, [turns])

  return (
    <section className={styles.chat} aria-labelledby="chat-title">
      <header className={styles.header}>
        <h1 id="chat-title" className={styles.title}>
          Asistente de compras
        </h1>
        <p className={styles.subtitle}>
          Contame qué necesitás y te recomiendo productos del catálogo con su precio y stock actuales.
        </p>
      </header>

      {turns.length === 0 ? (
        <div className={styles.examples}>
          <p className={styles.examplesTitle}>Podés empezar con:</p>
          <div className={styles.exampleButtons}>
            {EXAMPLE_PROMPTS.map((prompt) => (
              <Button key={prompt} variant="secondary" size="sm" onClick={() => onSend(prompt)}>
                {prompt}
              </Button>
            ))}
          </div>
        </div>
      ) : (
        <div role="log" aria-label="Conversación" className={styles.log}>
          {turns.map((turn) =>
            turn.role === 'user' ? (
              <UserMessage key={turn.id} text={turn.text} />
            ) : (
              <AssistantMessage
                key={turn.id}
                turn={turn}
                isLatest={turn === lastTurn}
                onSelectOption={onSend}
                {...actions}
              />
            ),
          )}
          <div ref={endRef} />
        </div>
      )}

      <div className={styles.composer}>
        <ChatComposer onSend={onSend} busy={busy} />
      </div>
    </section>
  )
}
