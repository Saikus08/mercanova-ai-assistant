import { apiPostForm } from './http'
import type { TranscribeResponse } from './types'

/** Voice to text (docs/api-contract.md, "POST /api/transcribe"). */
export interface SpeechApi {
  /** Sends the recorded audio and returns its Spanish transcript. */
  transcribe(audio: Blob, signal?: AbortSignal): Promise<TranscribeResponse>
}

/** File name sent with the audio; the backend reads the format from the Blob type. */
const fileName = (audio: Blob) => (audio.type.includes('ogg') ? 'voice.ogg' : audio.type.includes('wav') ? 'voice.wav' : 'voice.webm')

export const httpSpeechApi: SpeechApi = {
  transcribe(audio, signal) {
    const form = new FormData()
    form.append('audio', audio, fileName(audio))
    return apiPostForm<TranscribeResponse>('/transcribe', form, signal)
  },
}
