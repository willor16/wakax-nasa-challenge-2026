// 2-minute reaction test (screen 13), following the Psychomotor Vigilance Task: a target
// appears after a random 2-10 s wait and must be tapped as fast as possible. A tap with no
// target is a false start; a target left for 1.5 s counts as a lapse (no response). The
// server scores the session (responses under 100 ms are false starts, 500 ms or more lapses).

export const ARENA_DURATION_MS = 120_000
const RESPONSE_WINDOW_MS = 1_500
const MIN_WAIT_MS = 2_000
const MAX_WAIT_MS = 10_000
const LAPSE_MS = 500

export type ArenaPhase = 'idle' | 'waiting' | 'target' | 'done'

export function useReactionArena(random: () => number = Math.random) {
  const phase = ref<ArenaPhase>('idle')
  const times = ref<(number | null)[]>([])
  const falseStarts = ref(0)
  const elapsedMs = ref(0)
  const lastLatencyMs = ref<number | null>(null)
  let startedAt = 0
  let shownAt = 0
  let waitTimer: ReturnType<typeof setTimeout> | null = null
  let missTimer: ReturnType<typeof setTimeout> | null = null
  let clock: ReturnType<typeof setInterval> | null = null

  const answered = computed(() => times.value.filter((t): t is number => t !== null && t >= 100))
  const summary = computed(() => {
    const valid = answered.value.filter(t => t < LAPSE_MS)
    const attempts = times.value.length + falseStarts.value
    return {
      trials: times.value.length,
      meanMs: answered.value.length ? Math.round(answered.value.reduce((a, b) => a + b, 0) / answered.value.length) : null,
      valid: valid.length,
      precisionPct: attempts ? Math.round((valid.length / attempts) * 1000) / 10 : null,
      lapses: times.value.filter(t => t === null || t >= LAPSE_MS).length,
    }
  })

  function clearTimers() {
    if (waitTimer) clearTimeout(waitTimer)
    if (missTimer) clearTimeout(missTimer)
    if (clock) clearInterval(clock)
    waitTimer = missTimer = clock = null
  }

  function finish() {
    clearTimers()
    elapsedMs.value = ARENA_DURATION_MS
    phase.value = 'done'
  }

  function scheduleTarget() {
    phase.value = 'waiting'
    const wait = MIN_WAIT_MS + random() * (MAX_WAIT_MS - MIN_WAIT_MS)
    const left = ARENA_DURATION_MS - (performance.now() - startedAt)
    if (wait + RESPONSE_WINDOW_MS > left) {
      waitTimer = setTimeout(finish, Math.max(0, left))
      return
    }
    waitTimer = setTimeout(() => {
      phase.value = 'target'
      shownAt = performance.now()
      missTimer = setTimeout(() => {
        times.value = [...times.value, null]
        lastLatencyMs.value = null
        scheduleTarget()
      }, RESPONSE_WINDOW_MS)
    }, wait)
  }

  function start() {
    clearTimers()
    times.value = []
    falseStarts.value = 0
    lastLatencyMs.value = null
    elapsedMs.value = 0
    startedAt = performance.now()
    clock = setInterval(() => {
      elapsedMs.value = Math.min(ARENA_DURATION_MS, performance.now() - startedAt)
    }, 250)
    scheduleTarget()
  }

  function tap() {
    if (phase.value === 'waiting') {
      falseStarts.value += 1
      return
    }
    if (phase.value !== 'target') return
    if (missTimer) clearTimeout(missTimer)
    const latency = Math.round(performance.now() - shownAt)
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

  onBeforeUnmount(clearTimers)
  return { phase, times, falseStarts, elapsedMs, lastLatencyMs, summary, start, tap, reset }
}
