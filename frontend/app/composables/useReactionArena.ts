// 2-minute reaction test (screen 13): a green target appears after a random
// wait; the crew member taps it as fast as possible. Taps while waiting are
// false starts; a target left without a tap counts as a lapse.
import {
  ARENA_DURATION_MS,
  ARENA_RESPONSE_WINDOW_MS,
  nextDelayMs,
  summarizeArena,
} from '~/utils/mind'

export type ArenaPhase = 'idle' | 'waiting' | 'target' | 'done'

export function useReactionArena() {
  const phase = ref<ArenaPhase>('idle')
  const times = ref<(number | null)[]>([])
  const falseStarts = ref(0)
  const elapsedMs = ref(0)
  const lastLatencyMs = ref<number | null>(null)

  let startedAt = 0
  let targetShownAt = 0
  let targetTimer: ReturnType<typeof setTimeout> | null = null
  let missTimer: ReturnType<typeof setTimeout> | null = null
  let clockTimer: ReturnType<typeof setInterval> | null = null

  const summary = computed(() => summarizeArena(times.value, falseStarts.value))

  function clearTimers() {
    if (targetTimer) clearTimeout(targetTimer)
    if (missTimer) clearTimeout(missTimer)
    if (clockTimer) clearInterval(clockTimer)
    targetTimer = missTimer = clockTimer = null
  }

  function finish() {
    clearTimers()
    elapsedMs.value = ARENA_DURATION_MS
    phase.value = 'done'
  }

  function scheduleTarget() {
    phase.value = 'waiting'
    const wait = nextDelayMs()
    if (performance.now() - startedAt + wait >= ARENA_DURATION_MS) {
      targetTimer = setTimeout(finish, ARENA_DURATION_MS - (performance.now() - startedAt))
      return
    }
    targetTimer = setTimeout(() => {
      phase.value = 'target'
      targetShownAt = performance.now()
      missTimer = setTimeout(() => {
        times.value = [...times.value, null]
        lastLatencyMs.value = null
        scheduleTarget()
      }, ARENA_RESPONSE_WINDOW_MS)
    }, wait)
  }

  function start() {
    clearTimers()
    times.value = []
    falseStarts.value = 0
    lastLatencyMs.value = null
    elapsedMs.value = 0
    startedAt = performance.now()
    clockTimer = setInterval(() => {
      elapsedMs.value = Math.min(ARENA_DURATION_MS, performance.now() - startedAt)
    }, 200)
    scheduleTarget()
  }

  function tap() {
    if (phase.value === 'waiting') {
      falseStarts.value += 1
      return
    }
    if (phase.value !== 'target') return
    if (missTimer) clearTimeout(missTimer)
    const latency = Math.round(performance.now() - targetShownAt)
    lastLatencyMs.value = latency
    times.value = [...times.value, latency]
    scheduleTarget()
  }

  function reset() {
    clearTimers()
    phase.value = 'idle'
    times.value = []
    falseStarts.value = 0
    elapsedMs.value = 0
    lastLatencyMs.value = null
  }

  onUnmounted(clearTimers)

  return { phase, times, falseStarts, elapsedMs, lastLatencyMs, summary, start, tap, reset }
}
