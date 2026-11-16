import { describe, expect, it } from 'vitest'
import { crewTone, dayText, formatClock, formatDuration, formatNumber, scalePct, toneOf } from '../app/utils/format'

describe('display helpers', () => {
  it('formats the mission clock and days', () => {
    expect(formatClock(47, Date.UTC(2026, 10, 15, 14, 32))).toBe('DAY 047 · 14:32 UTC')
    expect(formatClock(null, Date.UTC(2026, 10, 15, 9, 5))).toBe('09:05 UTC')
    expect(dayText('D47')).toBe('Day 047')
    expect(dayText(null)).toBe('—')
  })

  it('never shows a number for missing data', () => {
    expect(formatDuration(432)).toBe('7h 12m')
    expect(formatDuration(null)).toBe('—')
    expect(formatNumber(null)).toBe('—')
    expect(formatNumber(2420)).toBe('2,420')
  })

  it('maps statuses to the palette tones', () => {
    expect(toneOf('NOMINAL')).toBe('ok')
    expect(toneOf('WATCH')).toBe('watch')
    expect(toneOf('WARNING')).toBe('watch')
    expect(toneOf('CRITICAL')).toBe('critical')
    expect(toneOf('NO_DATA')).toBe('neutral')
    expect(crewTone('Attention')).toBe('critical')
  })

  it('clamps positions on a scale', () => {
    expect(scalePct(50, 0, 100)).toBe(50)
    expect(scalePct(150, 0, 100)).toBe(100)
    expect(scalePct(null, 0, 100)).toBe(0)
  })
})
