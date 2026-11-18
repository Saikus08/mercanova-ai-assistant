import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiRequestError } from './http'
import { httpSpeechApi } from './speech'

const jsonResponse = (status: number, body: unknown) => ({
  ok: status >= 200 && status < 300,
  status,
  json: () => Promise.resolve(body),
})

describe('httpSpeechApi', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('posts the audio as multipart form data and returns the transcript', async () => {
    const transcript = { text: 'necesito auriculares', language: 'es', duration_s: 3.1 }
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, transcript))
    vi.stubGlobal('fetch', fetchMock)
    const audio = new Blob(['sound'], { type: 'audio/webm;codecs=opus' })

    await expect(httpSpeechApi.transcribe(audio)).resolves.toEqual(transcript)

    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/transcribe')
    expect(init.method).toBe('POST')
    // The browser sets the multipart Content-Type with its boundary.
    expect(init.headers['Content-Type']).toBeUndefined()
    expect(init.headers['X-Session-Id']).toEqual(expect.any(String))
    const sent = (init.body as FormData).get('audio') as File
    expect(sent.name).toBe('voice.webm')
    expect(sent.type).toBe('audio/webm;codecs=opus')
  })

  it('turns AUDIO_UNREADABLE into an error with the Spanish message', async () => {
    const message = 'No pudimos entender el audio. Probá grabarlo de nuevo o escribí tu consulta.'
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse(422, { error: { code: 'AUDIO_UNREADABLE', message } })))

    const error = await httpSpeechApi.transcribe(new Blob(['x'], { type: 'audio/webm' })).catch((e: unknown) => e)

    expect(error).toBeInstanceOf(ApiRequestError)
    expect(error).toMatchObject({ code: 'AUDIO_UNREADABLE', status: 422, message })
  })
})
