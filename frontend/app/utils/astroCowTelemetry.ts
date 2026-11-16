import { token } from './charts'

export interface AstroCowMinuteSlice {
  minute: number
  accuracyPct: number
  targetsHit: number
  targetsTotal: number
}

export interface AstroCowSummary {
  score: number
  high_score: number
  difficulty_level: number
  duration_sec: number
  mean_reaction_ms: number
  rt_variability_ms: number
  recovery_time_sec: number
  errors_after_change: number
  omitted_responses: number
  precision_pct: number
  collisions: number
  reticle_hits: number
  reticle_total: number
  reaction_times_ms: number[]
  recovery_times_sec: number[]
  performance_by_minute: AstroCowMinuteSlice[]
}

export interface AstroCowComputeInput {
  score: number
  highScore: number
  difficultyLevel: number
  durationSec: number
  reticleHits: number
  reticleTotal: number
  collisions: number
  errorsAfterChange: number
  omittedResponses: number
  reactionTimesMs: number[]
  recoveryTimesSec: number[]
  targetTimelineEvents: { time: number, hit: boolean }[]
}

export function gameCanvasPalette() {
  return {
    bgBase: token('--color-bg-base'),
    bgTop: token('--color-bg-top'),
    bgInset: token('--color-inset-solid'),
    surfaceCard: token('--color-surface-card'),
    borderHi: token('--color-border-hi'),
    rem: token('--color-rem-accent'),
    navy: token('--color-navy-accent'),
    navyEdge: token('--color-navy-edge'),
    text: token('--color-text-primary'),
    ice: token('--color-text-secondary'),
    muted: token('--color-text-muted'),
    ok: token('--color-status-ok'),
    okSoft: token('--color-ok-soft'),
    crit: token('--color-status-critical'),
    critSoft: token('--color-crit-soft'),
    band: token('--color-band-fill'),
  }
}

export function computeAstroCowSummary(input: AstroCowComputeInput): AstroCowSummary {
  const durationSec = Math.max(1, Math.round(input.durationSec))
  const rts = input.reactionTimesMs
  const meanRt = rts.length
    ? Math.round(rts.reduce((acc, v) => acc + v, 0) / rts.length)
    : 280
  let rtVar = 0
  if (rts.length > 1) {
    const variance = rts.reduce((acc, val) => acc + (val - meanRt) ** 2, 0) / rts.length
    rtVar = Math.round(Math.sqrt(variance))
  }
  const avgRecovery = input.recoveryTimesSec.length
    ? Number((input.recoveryTimesSec.reduce((a, b) => a + b, 0) / input.recoveryTimesSec.length).toFixed(2))
    : Number((meanRt / 1000).toFixed(2))

  const precisionPct = input.reticleTotal > 0
    ? Math.round((input.reticleHits / input.reticleTotal) * 100)
    : (input.collisions === 0 ? 100 : Math.max(0, Math.round(100 - input.collisions * 12)))

  const totalMinutes = Math.max(1, Math.ceil(durationSec / 60))
  const performanceByMinute: AstroCowMinuteSlice[] = []
  for (let m = 1; m <= totalMinutes; m++) {
    const minStart = (m - 1) * 60
    const minEnd = m * 60
    const eventsInMin = input.targetTimelineEvents.filter(ev => ev.time >= minStart && ev.time <= minEnd)
    const hitsInMin = eventsInMin.filter(ev => ev.hit).length
    const pctInMin = eventsInMin.length > 0 ? Math.round((hitsInMin / eventsInMin.length) * 100) : precisionPct
    performanceByMinute.push({
      minute: m,
      accuracyPct: pctInMin,
      targetsHit: hitsInMin,
      targetsTotal: eventsInMin.length,
    })
  }

  return {
    score: input.score,
    high_score: Math.max(input.score, input.highScore),
    difficulty_level: input.difficultyLevel,
    duration_sec: durationSec,
    mean_reaction_ms: meanRt,
    rt_variability_ms: rtVar,
    recovery_time_sec: avgRecovery,
    errors_after_change: input.errorsAfterChange,
    omitted_responses: input.omittedResponses,
    precision_pct: precisionPct,
    collisions: input.collisions,
    reticle_hits: input.reticleHits,
    reticle_total: input.reticleTotal,
    reaction_times_ms: rts,
    recovery_times_sec: input.recoveryTimesSec,
    performance_by_minute: performanceByMinute,
  }
}
