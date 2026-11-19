import { vi } from 'vitest'

/** Minimal MediaRecorder: `stop` hands one chunk of audio and then fires `onstop`, like the browser. */
export class FakeMediaRecorder {
  static instances: FakeMediaRecorder[] = []
  /** Bytes of the next recording; an empty string simulates a recording without sound. */
  static nextAudio = 'voice'

  state: RecordingState = 'inactive'
  readonly mimeType = 'audio/webm;codecs=opus'
  ondataavailable: ((event: { data: Blob }) => void) | null = null
  onstop: (() => void) | null = null
  onerror: (() => void) | null = null

  readonly stream: MediaStream

  constructor(stream: MediaStream) {
    this.stream = stream
    FakeMediaRecorder.instances.push(this)
  }

  start() {
    this.state = 'recording'
  }

  stop() {
    if (this.state === 'inactive') return
    this.state = 'inactive'
    this.ondataavailable?.({ data: new Blob([FakeMediaRecorder.nextAudio], { type: this.mimeType }) })
    this.onstop?.()
  }
}

/**
 * Installs a fake microphone. `denied` makes getUserMedia fail with that DOMException name.
 * Call `uninstallFakeMicrophone` after each test.
 */
export function installFakeMicrophone({ denied }: { denied?: string } = {}) {
  const track = { stop: vi.fn() }
  const getUserMedia = denied
    ? vi.fn().mockRejectedValue(new DOMException('blocked', denied))
    : vi.fn().mockResolvedValue({ getTracks: () => [track] })
  FakeMediaRecorder.instances = []
  FakeMediaRecorder.nextAudio = 'voice'
  vi.stubGlobal('MediaRecorder', FakeMediaRecorder)
  Object.defineProperty(navigator, 'mediaDevices', { value: { getUserMedia }, configurable: true })
  return { track, getUserMedia }
}

export function uninstallFakeMicrophone() {
  vi.unstubAllGlobals()
  Reflect.deleteProperty(navigator, 'mediaDevices')
}
