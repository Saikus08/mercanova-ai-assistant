import { Button } from '../../../components/ui'
import type { VoiceStatus } from '../useVoiceRecorder'
import styles from './VoiceButton.module.css'

export interface VoiceButtonProps {
  status: VoiceStatus
  /** An answer is being written: a new recording cannot start. */
  disabled?: boolean
  onStart: () => void
  onStop: () => void
}

const LABELS: Record<VoiceStatus, string> = {
  idle: 'Hablar: grabar una consulta por voz',
  requesting: 'Esperando permiso para usar el micrófono',
  recording: 'Detener la grabación y enviar',
  transcribing: 'Transcribiendo la consulta',
}

const microphoneIcon = (
  <svg className={styles.icon} viewBox="0 0 24 24" aria-hidden="true" focusable="false">
    <path
      fill="currentColor"
      d="M12 15a3 3 0 0 0 3-3V6a3 3 0 0 0-6 0v6a3 3 0 0 0 3 3Zm5-3a5 5 0 0 1-10 0H5a7 7 0 0 0 6 6.92V21h2v-2.08A7 7 0 0 0 19 12h-2Z"
    />
  </svg>
)

const stopIcon = (
  <svg className={styles.icon} viewBox="0 0 24 24" aria-hidden="true" focusable="false">
    <rect fill="currentColor" x="6" y="6" width="12" height="12" rx="2" />
  </svg>
)

/** Microphone button of the chat: starts a recording, and the second click stops it and sends it. */
export function VoiceButton({ status, disabled = false, onStart, onStop }: VoiceButtonProps) {
  const recording = status === 'recording'
  const label = LABELS[status]
  return (
    <Button
      variant={recording ? 'danger' : 'secondary'}
      className={styles.button}
      aria-label={label}
      title={label}
      disabled={status === 'requesting' || (!recording && disabled)}
      loading={status === 'transcribing'}
      onClick={recording ? onStop : onStart}
    >
      {status !== 'transcribing' && (recording ? stopIcon : microphoneIcon)}
    </Button>
  )
}
