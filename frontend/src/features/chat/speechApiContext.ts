import { createContext, useContext } from 'react'
import { httpSpeechApi, type SpeechApi } from '../../api/speech'

export const SpeechApiContext = createContext<SpeechApi>(httpSpeechApi)

export function useSpeechApi(): SpeechApi {
  return useContext(SpeechApiContext)
}
