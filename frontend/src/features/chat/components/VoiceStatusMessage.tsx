import type { VoiceStatus } from '../useVoiceRecorder'
import styles from './VoiceStatusMessage.module.css'

export interface VoiceStatusMessageProps {
  status: VoiceStatus
  elapsedSeconds: number
  maxSeconds: number
  error: string | null
}

const clock = (seconds: number) => `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`

/** Line under the message field: recording time, transcription in progress or the voice error. */
export function VoiceStatusMessage({ status, elapsedSeconds, maxSeconds, error }: VoiceStatusMessageProps) {
  if (error) {
    return (
      <p role="alert" className={`${styles.message} ${styles.error}`}>
        {error}
      </p>
    )
  }
  if (status === 'recording') {
    return (
      <p role="status" className={`${styles.message} ${styles.recording}`}>
        <span className={styles.dot} aria-hidden="true" />
        Grabando {clock(elapsedSeconds)} de {clock(maxSeconds)}. Tocá el botón de detener para enviar.
      </p>
    )
  }
  if (status === 'requesting') {
    return (
      <p role="status" className={styles.message}>
        Permití el uso del micrófono para grabar tu consulta.
      </p>
    )
  }
  if (status === 'transcribing') {
    return (
      <p role="status" className={styles.message}>
        Transcribiendo tu consulta…
      </p>
    )
  }
  return null
}
