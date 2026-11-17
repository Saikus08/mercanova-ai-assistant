import { useState, type FormEvent } from 'react'
import { Button, Input } from '../../../components/ui'
import styles from './ChatComposer.module.css'

/** Same limit as the backend (MAX_MESSAGE_CHARS). */
const MAX_MESSAGE_LENGTH = 2000

export interface ChatComposerProps {
  onSend: (text: string) => void
  /** An answer is being written: the message can be typed but not sent yet. */
  busy?: boolean
}

/** Text field and "Enviar" button of the chat. */
export function ChatComposer({ onSend, busy = false }: ChatComposerProps) {
  const [text, setText] = useState('')
  const canSend = !busy && text.trim() !== ''

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!canSend) return
    onSend(text)
    setText('')
  }

  return (
    <form className={styles.form} onSubmit={handleSubmit} aria-label="Enviar un mensaje al asistente">
      <Input
        className={styles.field}
        label="¿Qué estás buscando?"
        placeholder="Por ejemplo: auriculares para videollamadas, máximo USD 200"
        value={text}
        maxLength={MAX_MESSAGE_LENGTH}
        autoComplete="off"
        onChange={(event) => setText(event.target.value)}
      />
      <Button type="submit" disabled={!canSend}>
        Enviar
      </Button>
    </form>
  )
}
