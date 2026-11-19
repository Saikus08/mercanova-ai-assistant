import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiRequestError } from '../../api/http'
import { useSpeechApi } from './speechApiContext'

export type VoiceStatus = 'idle' | 'requesting' | 'recording' | 'transcribing'

/**
 * The backend accepts up to 60 seconds (docs/api-contract.md). Recording stops a bit earlier
 * because the encoded file can last slightly longer than the time shown on screen.
 */
export const MAX_RECORDING_SECONDS = 55

export const VOICE_MESSAGES = {
  unsupported: 'Tu navegador no permite grabar audio. Probá con Chrome o escribí tu consulta.',
  permissionDenied:
    'No tenemos permiso para usar el micrófono. Habilitalo desde el ícono junto a la dirección de la página e intentá de nuevo.',
  noMicrophone: 'No encontramos un micrófono conectado.',
  microphoneBusy: 'El micrófono está siendo usado por otra aplicación. Cerrala e intentá de nuevo.',
  microphoneFailed: 'No pudimos acceder al micrófono. Intentá de nuevo.',
  recordingFailed: 'La grabación se interrumpió. Intentá de nuevo.',
  emptyRecording: 'No se grabó ningún sonido. Intentá de nuevo.',
  unexpected: 'Ocurrió un error inesperado. Intentá de nuevo en unos minutos.',
} as const

function microphoneError(error: unknown): string {
  const name = error instanceof DOMException ? error.name : ''
  if (name === 'NotAllowedError' || name === 'SecurityError') return VOICE_MESSAGES.permissionDenied
  if (name === 'NotFoundError' || name === 'OverconstrainedError') return VOICE_MESSAGES.noMicrophone
  if (name === 'NotReadableError') return VOICE_MESSAGES.microphoneBusy
  return VOICE_MESSAGES.microphoneFailed
}

const canRecord = () => typeof MediaRecorder !== 'undefined' && Boolean(navigator.mediaDevices?.getUserMedia)

export interface VoiceRecorder {
  status: VoiceStatus
  /** Whole seconds since the recording started. */
  elapsedSeconds: number
  /** Spanish message of the last failure; cleared when a new recording starts. */
  error: string | null
  start: () => void
  /** Stops the recording and sends it to be transcribed. */
  stop: () => void
}

/**
 * Records the microphone, sends the audio to POST /api/transcribe and gives the text to
 * `onTranscript`. Nothing is recorded until the user starts it, and the microphone is released
 * as soon as the recording stops.
 */
export function useVoiceRecorder(onTranscript: (text: string) => void): VoiceRecorder {
  const api = useSpeechApi()
  const [status, setStatus] = useState<VoiceStatus>('idle')
  const [elapsedSeconds, setElapsedSeconds] = useState(0)
  const [error, setError] = useState<string | null>(null)

  const recorder = useRef<MediaRecorder | null>(null)
  const timer = useRef<ReturnType<typeof setInterval> | null>(null)
  const transcription = useRef<AbortController | null>(null)
  const mounted = useRef(true)
  const busy = useRef(false)
  const onTranscriptRef = useRef(onTranscript)

  useEffect(() => {
    onTranscriptRef.current = onTranscript
  }, [onTranscript])

  const stopTimer = () => {
    if (timer.current) clearInterval(timer.current)
    timer.current = null
  }

  const stop = useCallback(() => {
    stopTimer()
    const current = recorder.current
    recorder.current = null
    if (current && current.state !== 'inactive') current.stop()
  }, [])

  const fail = (message: string) => {
    busy.current = false
    if (!mounted.current) return
    setError(message)
    setStatus('idle')
  }

  const transcribe = useCallback(
    async (audio: Blob) => {
      if (audio.size === 0) return fail(VOICE_MESSAGES.emptyRecording)
      setStatus('transcribing')
      const controller = new AbortController()
      transcription.current = controller
      try {
        const { text } = await api.transcribe(audio, controller.signal)
        busy.current = false
        if (!mounted.current) return
        setStatus('idle')
        onTranscriptRef.current(text)
      } catch (cause) {
        if (controller.signal.aborted) return
        fail(cause instanceof ApiRequestError ? cause.message : VOICE_MESSAGES.unexpected)
      } finally {
        if (transcription.current === controller) transcription.current = null
      }
    },
    [api],
  )

  const start = useCallback(async () => {
    if (busy.current) return
    setError(null)
    if (!canRecord()) return fail(VOICE_MESSAGES.unsupported)

    busy.current = true
    setStatus('requesting')
    let stream: MediaStream
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    } catch (cause) {
      return fail(microphoneError(cause))
    }
    const release = () => stream.getTracks().forEach((track) => track.stop())
    if (!mounted.current) return release()

    let media: MediaRecorder
    try {
      media = new MediaRecorder(stream)
    } catch {
      release()
      return fail(VOICE_MESSAGES.unsupported)
    }

    const chunks: Blob[] = []
    let failed = false
    media.ondataavailable = (event) => {
      if (event.data.size > 0) chunks.push(event.data)
    }
    media.onerror = () => {
      failed = true
      stop()
    }
    media.onstop = () => {
      release()
      if (!mounted.current) return
      if (failed) return fail(VOICE_MESSAGES.recordingFailed)
      void transcribe(new Blob(chunks, { type: media.mimeType || 'audio/webm' }))
    }

    recorder.current = media
    media.start()
    setElapsedSeconds(0)
    setStatus('recording')
    let seconds = 0
    timer.current = setInterval(() => {
      seconds += 1
      setElapsedSeconds(seconds)
      if (seconds >= MAX_RECORDING_SECONDS) stop()
    }, 1000)
  }, [stop, transcribe])

  // Leaving the screen stops the microphone and drops any pending transcription.
  useEffect(() => {
    mounted.current = true
    return () => {
      mounted.current = false
      stop()
      transcription.current?.abort()
    }
  }, [stop])

  return { status, elapsedSeconds, error, start: () => void start(), stop }
}
