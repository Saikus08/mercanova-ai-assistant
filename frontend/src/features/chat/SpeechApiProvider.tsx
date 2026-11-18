import type { ReactNode } from 'react'
import type { SpeechApi } from '../../api/speech'
import { SpeechApiContext } from './speechApiContext'

/** Lets tests swap the voice-to-text API implementation. */
export function SpeechApiProvider({ api, children }: { api: SpeechApi; children: ReactNode }) {
  return <SpeechApiContext.Provider value={api}>{children}</SpeechApiContext.Provider>
}
