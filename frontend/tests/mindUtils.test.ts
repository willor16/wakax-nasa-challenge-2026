import { describe, expect, it } from 'vitest'
import { psychCheckinSchema } from '../app/schemas/mind'
import {
  ARENA_MAX_DELAY_MS,
  ARENA_MIN_DELAY_MS,
  ARENA_PLANNED_TRIALS,
  formatClock,
  missionDay,
  nextDelayMs,
  scalePercent,
  sleepDuration,
  stateText,
  summarizeArena,
} from '../app/utils/mind'

describe('Reaction test helpers', () => {
  it('plans about 24 targets in 2 minutes with random waits', () => {
    expect(ARENA_PLANNED_TRIALS).toBe(24)
    expect(nextDelayMs(() => 0)).toBe(ARENA_MIN_DELAY_MS)
    expect(nextDelayMs(() => 0.999999)).toBeLessThan(ARENA_MAX_DELAY_MS)
  })

  it('summarizes like the server scoring rules', () => {
    const summary = summarizeArena([250, 300, 620, null, 80], 1)
    expect(summary).toEqual({
      trials: 5,
      valid: 2,
      falseStarts: 2,
      lapses: 2,
      meanMs: 390,
      precisionPct: 33.3,
    })
    expect(summarizeArena([], 0).precisionPct).toBe(0)
  })

  it('formats the session clock and sleep window', () => {
    expect(formatClock(88_000)).toBe('01:28')
    expect(formatClock(120_000)).toBe('02:00')
    expect(sleepDuration('22:18', '05:54')).toBe('7h 36m asleep')
    expect(sleepDuration('bad', '05:54')).toBeNull()
  })
})

describe('Check-in validation', () => {
  const valid = {
    moodState: 'CALM', mood: 5, stress: 2, isolation: 1, motivation: 5,
    sleepOnsetUtc: '22:18', wakeUtc: '05:54',
  }

  it('accepts a complete check-in', () => {
    expect(psychCheckinSchema.safeParse(valid).success).toBe(true)
  })

  it('rejects out-of-range scales and bad times with plain messages', () => {
    const result = psychCheckinSchema.safeParse({ ...valid, mood: 6, wakeUtc: '25:00' })
    expect(result.success).toBe(false)
    const messages = result.success ? [] : result.error.issues.map(i => i.message)
    expect(messages).toContain('Choose a value from 1 to 5.')
    expect(messages).toContain('Use a time like 22:18.')
  })
})

describe('Profile helpers', () => {
  it('maps values and days for screen 05', () => {
    expect(scalePercent(1)).toBe(0)
    expect(scalePercent(5)).toBe(100)
    expect(scalePercent(4.5)).toBe(87.5)
    expect(missionDay('2026-11-16', '2026-10-01T08:00:00Z')).toBe('D47')
    expect(stateText('CALM').title).toBe('CALM')
    expect(stateText(null).title).toBe('NO CHECK-IN YET')
  })
})
