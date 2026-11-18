import { useState, type FormEvent } from 'react'
import { Button, Input } from '../../../components/ui'
import type { VoiceStatus } from '../useVoiceRecorder'
import styles from './ChatComposer.module.css'
import { VoiceButton } from './VoiceButton'
import { VoiceStatusMessage } from './VoiceStatusMessage'

/** Same limit as the backend (MAX_MESSAGE_CHARS). */
const MAX_MESSAGE_LENGTH = 2000

/** State and actions of the voice recording, owned by the container. */
export interface VoiceControls {
  status: VoiceStatus
  elapsedSeconds: number
  maxSeconds: number
  error: string | null
  onStart: () => void
  onStop: () => void
}

export interface ChatComposerProps {
  onSend: (text: string) => void
  /** An answer is being written: the message can be typed but not sent yet. */
  busy?: boolean
  /** Without it, the microphone button is not shown. */
  voice?: VoiceControls
}

/** Text field, microphone button and "Enviar" button of the chat. */
export function ChatComposer({ onSend, busy = false, voice }: ChatComposerProps) {
  const [text, setText] = useState('')
  const canSend = !busy && text.trim() !== ''

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!canSend) return
    onSend(text)
    setText('')
  }

  return (
    <div>
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
        {voice && <VoiceButton status={voice.status} disabled={busy} onStart={voice.onStart} onStop={voice.onStop} />}
        <Button type="submit" disabled={!canSend}>
          Enviar
        </Button>
      </form>
      {voice && (
        <VoiceStatusMessage
          status={voice.status}
          elapsedSeconds={voice.elapsedSeconds}
          maxSeconds={voice.maxSeconds}
          error={voice.error}
        />
      )}
    </div>
  )
}
