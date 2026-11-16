// 30-second heart or lung recording from the digital stethoscope (screen 10).
// Raw sound (no echo cancelling or noise suppression) is captured, kept at 4 kHz as a
// standard WAV file, checksummed and sent for analysis. Nothing is ever made up: without
// a working microphone the screen explains the problem instead of saving anything.
import { RECORD_SECONDS, downsample, encodeWav, levelDb, sha256Hex } from '~/utils/audio'

export type RecorderState = 'idle' | 'starting' | 'recording' | 'captured' | 'saving' | 'saved' | 'error'

export const ENVELOPE_POINTS = 150

const activeOrgan = ref<string | null>(null) // one stethoscope: one recording at a time

export function useAuscultationRecorder(organ: 'CARDIAC' | 'PULMONARY') {
  const state = ref<RecorderState>('idle')
  const seconds = ref(0)
  const inputDb = ref<number | null>(null)
  const envelope = shallowRef<number[]>([])
  const message = ref<string | null>(null)
  const captured = shallowRef<{ wav: Uint8Array<ArrayBuffer>, sha256: string } | null>(null)

  let stream: MediaStream | null = null
  let context: AudioContext | null = null
  let processor: ScriptProcessorNode | null = null
  let timer: ReturnType<typeof setInterval> | null = null
  let chunks: Float32Array[] = []
  let alive = true

  const busyElsewhere = computed(() => activeOrgan.value !== null && activeOrgan.value !== organ)

  async function release() {
    if (timer) clearInterval(timer)
    timer = null
    processor?.disconnect()
    processor = null
    stream?.getTracks().forEach(track => track.stop())
    stream = null
    if (context && context.state !== 'closed') await context.close().catch(() => undefined)
    context = null
    if (activeOrgan.value === organ) activeOrgan.value = null
  }

  async function finish() {
    const rate = context?.sampleRate ?? 48000
    await release()
    const total = chunks.reduce((n, c) => n + c.length, 0)
    const merged = new Float32Array(total)
    let offset = 0
    for (const chunk of chunks) {
      merged.set(chunk, offset)
      offset += chunk.length
    }
    chunks = []
    if (!alive) return
    const quiet = levelDb(merged) < -70
    if (total < rate * (RECORD_SECONDS - 1) || quiet) {
      state.value = 'error'
      message.value = quiet
        ? 'No sound reached the stethoscope. Check the connection and record again.'
        : 'The recording stopped early. Please record again.'
      return
    }
    const wav = encodeWav(downsample(merged, rate))
    captured.value = { wav, sha256: await sha256Hex(wav) }
    state.value = 'captured'
  }

  async function start() {
    if (state.value === 'starting' || state.value === 'recording' || busyElsewhere.value) return
    message.value = null
    captured.value = null
    envelope.value = []
    seconds.value = 0
    if (!navigator.mediaDevices?.getUserMedia) {
      state.value = 'error'
      message.value = 'This display cannot reach a stethoscope or microphone. Use a cabin tablet with audio input.'
      return
    }
    state.value = 'starting'
    activeOrgan.value = organ
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: false, noiseSuppression: false, autoGainControl: false, channelCount: 1 },
      })
      if (!alive || state.value !== 'starting') {
        await release()
        return
      }
      context = new AudioContext()
      const source = context.createMediaStreamSource(stream)
      processor = context.createScriptProcessor(4096, 1, 1)
      processor.onaudioprocess = (event) => {
        const block = new Float32Array(event.inputBuffer.getChannelData(0))
        chunks.push(block)
        inputDb.value = Math.round(levelDb(block))
        let peak = 0
        for (const value of block) peak = Math.max(peak, Math.abs(value))
        envelope.value = [...envelope.value.slice(-(ENVELOPE_POINTS - 1)), peak]
      }
      source.connect(processor)
      processor.connect(context.destination)
      state.value = 'recording'
      const startedAt = performance.now()
      timer = setInterval(() => {
        seconds.value = Math.min(RECORD_SECONDS, Math.floor((performance.now() - startedAt) / 1000))
        if (seconds.value >= RECORD_SECONDS) void finish()
      }, 200)
    }
    catch (error) {
      await release()
      state.value = 'error'
      message.value = (error as DOMException)?.name === 'NotAllowedError'
        ? 'Microphone access was refused. Allow audio input for this display and try again.'
        : 'The stethoscope could not be started. Check the connection and try again.'
    }
  }

  async function stop() {
    if (state.value === 'starting') {
      state.value = 'idle'
      await release()
      return
    }
    if (state.value !== 'recording') return
    await release()
    chunks = []
    state.value = 'idle'
    message.value = 'Recording stopped. A full 30 seconds is needed to save.'
  }

  onBeforeUnmount(() => {
    alive = false
    void release()
  })

  return { state, seconds, inputDb, envelope, message, captured, busyElsewhere, start, stop }
}
