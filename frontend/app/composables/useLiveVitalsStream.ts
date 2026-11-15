// Live wearable sensor for the signed-in crew member: a continuous Lead II ECG (4 frames per
// second, 125 Hz) with heart rate, heart-rate variability and core temperature.
//
// The stream opens with a one-minute stream pass (browsers cannot send headers on streams),
// always through the relative /api URL so every device on the cabin network uses the same
// path. When the stream drops or reaches its lifetime it reconnects with a fresh pass.
// It stays open only while the screen using it is mounted.
import { RingBuffer } from '~/utils/ringBuffer'

export interface EcgFrame {
  t0_s: number
  sample_rate_hz: number
  paper_speed_mm_s: number
  lead: string
  samples: number[]
  heart_rate_bpm: number
  hrv_ms: number
  body_temp_c: number
  rhythm_text: string
  override_en: string | null
}

export type LiveState = 'connecting' | 'live' | 'reconnecting'

export const LIVE_WINDOW_SECONDS = 6
const RECONNECT_MS = 1000
const STALE_MS = 3000

export function useLiveVitalsStream() {
  const { api } = useApi()
  const base = useRuntimeConfig().public.apiBase

  const state = ref<LiveState>('connecting')
  const samples = shallowRef<number[]>([])
  const latest = shallowRef<EcgFrame | null>(null)
  const sampleRate = ref(125)
  const frames = ref(0)

  let buffer = new RingBuffer(sampleRate.value * LIVE_WINDOW_SECONDS)
  let source: EventSource | null = null
  let retry: ReturnType<typeof setTimeout> | null = null
  let watchdog: ReturnType<typeof setInterval> | null = null
  let lastFrameAt = 0
  let alive = true

  function onFrame(event: MessageEvent<string>) {
    try {
      const frame = JSON.parse(event.data) as EcgFrame
      if (frame.sample_rate_hz !== sampleRate.value) {
        sampleRate.value = frame.sample_rate_hz
        buffer = new RingBuffer(frame.sample_rate_hz * LIVE_WINDOW_SECONDS)
      }
      buffer.push(frame.samples)
      samples.value = buffer.toArray()
      latest.value = frame
      frames.value += 1
      lastFrameAt = Date.now()
      state.value = 'live'
    }
    catch {
      // A damaged frame is skipped; the next one arrives in a quarter of a second.
    }
  }

  function scheduleReconnect() {
    source?.close()
    source = null
    if (!alive || retry) return
    state.value = 'reconnecting'
    retry = setTimeout(() => {
      retry = null
      void connect()
    }, RECONNECT_MS)
  }

  async function connect() {
    if (!alive) return
    try {
      const { stream_token: token } = await api<{ stream_token: string }>('/auth/stream-token', { method: 'POST' })
      if (!alive) return
      source = new EventSource(`${base}/api/v1/stream/live-ecg?token=${encodeURIComponent(token)}`)
      source.addEventListener('ecg', onFrame as EventListener)
      // The pass is valid for one minute, so the browser's own retry would fail: reconnect here.
      source.onerror = scheduleReconnect
    }
    catch {
      scheduleReconnect()
    }
  }

  onMounted(() => {
    void connect()
    watchdog = setInterval(() => {
      if (state.value === 'live' && Date.now() - lastFrameAt > STALE_MS) scheduleReconnect()
    }, 1000)
  })
  onBeforeUnmount(() => {
    alive = false
    source?.close()
    if (retry) clearTimeout(retry)
    if (watchdog) clearInterval(watchdog)
  })

  return { state, samples, latest, sampleRate, frames }
}
