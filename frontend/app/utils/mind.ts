// Psychological profile (screen 05) and reaction test (screen 13) helpers.
// Scoring rules mirror backend/app/services/mind.py (vigilance task rules).

export const ARENA_DURATION_MS = 120_000
export const ARENA_MIN_DELAY_MS = 3_000
export const ARENA_MAX_DELAY_MS = 7_000
export const ARENA_RESPONSE_WINDOW_MS = 1_500
export const ARENA_PLANNED_TRIALS = Math.round(
  ARENA_DURATION_MS / ((ARENA_MIN_DELAY_MS + ARENA_MAX_DELAY_MS) / 2),
)
export const FALSE_START_MS = 100
export const LAPSE_MS = 500
export const REACTION_TARGET_MS = 300

/** Random wait before the next green target, in [min, max). */
export function nextDelayMs(random: () => number = Math.random): number {
  return ARENA_MIN_DELAY_MS + Math.floor(random() * (ARENA_MAX_DELAY_MS - ARENA_MIN_DELAY_MS))
}

export interface ArenaSummary {
  trials: number
  valid: number
  falseStarts: number
  lapses: number
  meanMs: number
  precisionPct: number
}

/** Live summary of a session; ``null`` entries are targets with no tap. */
export function summarizeArena(times: (number | null)[], falseStarts: number): ArenaSummary {
  const early = times.filter((t): t is number => t !== null && t < FALSE_START_MS)
  const answered = times.filter((t): t is number => t !== null && t >= FALSE_START_MS)
  const valid = answered.filter(t => t < LAPSE_MS)
  const lapses = times.filter(t => t === null).length + answered.length - valid.length
  const attempts = times.length + falseStarts
  return {
    trials: times.length,
    valid: valid.length,
    falseStarts: falseStarts + early.length,
    lapses,
    meanMs: answered.length ? Math.round(answered.reduce((a, b) => a + b, 0) / answered.length) : 0,
    precisionPct: attempts ? Math.round((1000 * valid.length) / attempts) / 10 : 0,
  }
}

/** "01:28" from milliseconds. */
export function formatClock(ms: number): string {
  const total = Math.max(0, Math.floor(ms / 1000))
  const m = String(Math.floor(total / 60)).padStart(2, '0')
  const s = String(total % 60).padStart(2, '0')
  return `${m}:${s}`
}

/** Hours and minutes between sleep onset and wake time, crossing midnight. */
export function sleepDuration(onset: string, wake: string): string | null {
  const parse = (v: string) => {
    const match = /^(\d{2}):(\d{2})$/.exec(v)
    return match ? Number(match[1]) * 60 + Number(match[2]) : null
  }
  const a = parse(onset)
  const b = parse(wake)
  if (a === null || b === null) return null
  const minutes = (b - a + 1440) % 1440
  return `${Math.floor(minutes / 60)}h ${String(minutes % 60).padStart(2, '0')}m asleep`
}

// ------------------------------------------------------------- profile ---

export interface PsychProfile {
  crew_id: string
  latest_state: { mood_state: string | null, recorded_at_utc: string, wellbeing_index: number } | null
  scales: {
    mood: { value: number, range: [number, number], label: string }
    stress_index: { value: number, target_below: number, label: string }
    isolation: { value: number, target_below: number, label: string }
    motivation: { value: number, range: [number, number], label: string }
  } | null
  trend: { day: string, mood: number, calmness: number }[]
  optimal_zone: [number, number]
  stability_pct: number
  reaction: {
    reaction_ms: number | null
    reaction_target_ms: number
    accuracy_pct: number
    accuracy_target_pct: number
    attention_score: number
    lapses: number
    false_starts: number
    trials_total: number
    valid_responses: number
    recorded_at_utc: string
  } | null
}

const STATE_TEXT: Record<string, { title: string, detail: string }> = {
  CALM: { title: 'CALM', detail: 'Emotional stability within your personal baseline.' },
  FOCUSED: { title: 'FOCUSED', detail: 'Clear focus and steady energy for the shift.' },
  TIRED: { title: 'TIRED', detail: 'Low energy today. Protect your next rest period.' },
  STRESSED: { title: 'STRESSED', detail: 'Pressure is high today. Short breaks and a talk with the crew help.' },
}

export function stateText(state: string | null | undefined): { title: string, detail: string } {
  return STATE_TEXT[state ?? ''] ?? { title: 'NO CHECK-IN YET', detail: 'Log a daily check-in in Data Capture.' }
}

/** Position (0-100%) of a 1-5 value on a slider track. */
export function scalePercent(value: number): number {
  return Math.min(100, Math.max(0, ((value - 1) / 4) * 100))
}

function token(name: string, fallback: string): string {
  if (typeof window === 'undefined') return fallback
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback
}

/** "D34"-style mission day labels, counted from launch. */
export function missionDay(dayIso: string, launchIso: string): string {
  const day = Date.parse(`${dayIso}T00:00:00Z`)
  const launch = Date.parse(launchIso.slice(0, 10) + 'T00:00:00Z')
  return `D${Math.floor((day - launch) / 86400000) + 1}`
}

export function buildMoodTrendOption(profile: PsychProfile, launchIso: string) {
  const ok = token('--color-status-ok', '#2AEF4B')
  const rem = token('--color-rem-accent', '#2994A6')
  const navyEdge = token('--color-navy-edge', '#263BB0')
  const [low, high] = profile.optimal_zone
  return {
    backgroundColor: 'transparent',
    grid: { left: 36, right: 16, top: 24, bottom: 28 },
    tooltip: { trigger: 'axis' },
    xAxis: {
      type: 'category',
      data: profile.trend.map(t => missionDay(t.day, launchIso)),
      boundaryGap: false,
    },
    yAxis: { type: 'value', min: 1, max: 5, interval: 1 },
    series: [
      {
        name: 'Mood',
        type: 'line',
        data: profile.trend.map(t => t.mood),
        symbolSize: 7,
        lineStyle: { color: ok, width: 2.4 },
        itemStyle: { color: ok },
        markArea: {
          silent: true,
          itemStyle: { color: navyEdge, opacity: 0.18 },
          data: [[{ yAxis: low }, { yAxis: high }]],
        },
      },
      {
        name: 'Calmness',
        type: 'line',
        data: profile.trend.map(t => t.calmness),
        symbol: 'none',
        lineStyle: { color: rem, width: 1.8 },
      },
    ],
  }
}
