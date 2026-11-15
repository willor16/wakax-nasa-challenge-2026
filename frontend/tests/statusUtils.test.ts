import { describe, expect, it } from 'vitest'
import { computeZScore, evaluateMetricStatus, readinessBandFromScore } from '../app/utils/status'

describe('Clinical Status & Z-Score Utilities', () => {
  it('computes z-score safely including zero stdDev', () => {
    expect(computeZScore(70, 60, 5)).toBe(2)
    expect(computeZScore(70, 60, 0)).toBe(0)
  })

  it('evaluates metric status across nominal, attention, and critical thresholds', () => {
    expect(evaluateMetricStatus(64, 50, 85, 40, 110)).toBe('Optimal')
    expect(evaluateMetricStatus(52, 50, 85, 40, 110)).toBe('Nominal')
    expect(evaluateMetricStatus(92, 50, 85, 40, 110)).toBe('Attention')
    expect(evaluateMetricStatus(112, 50, 85, 40, 110)).toBe('Critical')
  })

  it('derives readiness bands from score and critical alert flag', () => {
    expect(readinessBandFromScore(92, false)).toBe('Optimal')
    expect(readinessBandFromScore(82, false)).toBe('Nominal')
    expect(readinessBandFromScore(70, false)).toBe('Attention')
    expect(readinessBandFromScore(95, true)).toBe('Critical')
  })
})
