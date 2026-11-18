import type { SpeechApi } from '../api/speech'
import type { TranscribeResponse } from '../api/types'

/** Voice-to-text API that answers with `text`, or fails with `error`. `audios` records what was sent. */
export function createFakeSpeechApi({ text = 'Necesito auriculares', error }: { text?: string; error?: Error } = {}) {
  const audios: Blob[] = []
  const api: SpeechApi & { audios: Blob[] } = {
    audios,
    async transcribe(audio): Promise<TranscribeResponse> {
      audios.push(audio)
      await Promise.resolve()
      if (error) throw error
      return { text, language: 'es', duration_s: 2 }
    },
  }
  return api
}
