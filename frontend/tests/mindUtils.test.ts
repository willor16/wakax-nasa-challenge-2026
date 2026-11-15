import { describe, expect, it } from 'vitest'
import { loadTranslate } from './helpers/locale'
import { psychCheckinSchema } from '../app/schemas/mind'
import {
  ARENA_MAX_DELAY_MS,
  ARENA_MIN_DELAY_MS,
  formatClock,
  missionDay,
  nextDelayMs,
  scalePercent,
  sleepDuration,
  rangeKey,
  stateKey,
  summarizeArena,
} from '../app/utils/mind'

describe('Reaction test helpers', () => {
  it('waits a random time before each target', () => {
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
    expect(sleepDuration('22:18', '05:54')).toEqual({ hours: 7, minutes: '36' })
    expect(sleepDuration('', '')).toBeNull()
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

  it('rejects out-of-range scales and bad times with plain messages', async () => {
    const t = await loadTranslate()
    const result = psychCheckinSchema.safeParse({ ...valid, mood: 6, wakeUtc: '25:00' })
    expect(result.success).toBe(false)
    const messages = result.success ? [] : result.error.issues.map(i => t(i.message))
    expect(messages).toContain('Choose a value from 1 to 5.')
    expect(messages).toContain('Use a time like 22:18.')
  })

  it('needs every scale chosen but not the mood chip or the sleep window', async () => {
    const t = await loadTranslate()
    const untouched = {
      moodState: null, mood: null, stress: null, isolation: null, motivation: null,
      sleepOnsetUtc: '', wakeUtc: '',
    }
    const empty = psychCheckinSchema.safeParse(untouched)
    expect(empty.success).toBe(false)
    const issues = empty.success ? [] : empty.error.issues
    expect(issues.map(i => i.path[0])).toEqual(['mood', 'stress', 'isolation', 'motivation'])
    expect(t(issues[0]!.message)).toBe('Choose a value from 1 to 5.')
    expect(psychCheckinSchema.safeParse({ ...untouched, mood: 3, stress: 3, isolation: 3, motivation: 3 }).success).toBe(true)
  })
})

describe('Profile helpers', () => {
  it('maps values and days for screen 05', () => {
    expect(scalePercent(1)).toBe(0)
    expect(scalePercent(5)).toBe(100)
    expect(scalePercent(4.5)).toBe(87.5)
    expect(missionDay('2026-11-16', '2026-10-01T08:00:00Z')).toBe('D47')
  })

  it('names the latest state and the source of each range', async () => {
    const t = await loadTranslate()
    expect(t(`mind.profile.states.${stateKey('CALM')}.title`)).toBe('CALM')
    expect(t(`mind.profile.states.${stateKey(null)}.title`)).toBe('NO CHECK-IN YET')
    expect(stateKey('UNKNOWN')).toBe('NONE')
    expect(t(`mind.profile.${rangeKey('BASELINE')}`, { low: 3, high: 5 })).toBe('Personal baseline: 3-5')
    expect(t(`mind.profile.${rangeKey('RECENT')}`, { low: 3, high: 4 })).toBe('Your recent range: 3-4')
    expect(t(`mind.profile.${rangeKey(undefined)}`, { low: 3.8, high: 5 })).toBe('Optimal zone: 3.8-5')
  })
})
