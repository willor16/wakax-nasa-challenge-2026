import { readFileSync } from 'node:fs'
import { join, resolve } from 'node:path'
import { describe, expect, it } from 'vitest'
import {
  buildLeadIiEcgOption,
  computeGaugeArcStroke,
  formatZScoreLabel,
  shiftEcgSweepWindow,
} from '../app/utils/profileCharts'

const FRONTEND_ROOT = resolve(import.meta.dirname, '..')

describe('D2-03 Crew Profile Utilities & Read-Only Separation', () => {
  it('builds Lead II ECG chart option with animation disabled and LTTB sampling', () => {
    const samples = Array.from({ length: 120 }, (_, idx) => Math.sin(idx / 10) * 0.6)
    const option = buildLeadIiEcgOption(samples, 100, 'reference')

    expect(option.animation).toBe(false)
    expect(option.series[0]?.type).toBe('line')
    expect(option.series[0]?.showSymbol).toBe(false)
    expect(option.series[0]?.sampling).toBe('lttb')
    expect(option.series[0]?.animation).toBe(false)
    expect(option.series[0]?.data).toHaveLength(120)
  })

  it('advances ECG sweep window circularly without losing samples', () => {
    const source = [0.1, 0.2, 0.9, -0.2, 0.3, 0.0]
    const step1 = shiftEcgSweepWindow(source, 4, 4, 2)
    expect(step1.window).toEqual([0.3, 0.0, 0.1, 0.2])
    expect(step1.nextCursor).toBe(0)
  })

  it('computes clamped gauge arc stroke and z-score labels', () => {
    const full = computeGaugeArcStroke(120, 38)
    const zero = computeGaugeArcStroke(-15, 38)
    expect(full.dashArray.startsWith(full.arcSpan.toFixed(2))).toBe(true)
    expect(zero.dashArray.startsWith('0.00 ')).toBe(true)

    expect(formatZScoreLabel(1.24)).toBe('z +1.2σ')
    expect(formatZScoreLabel(-0.8)).toBe('z -0.8σ')
    expect(formatZScoreLabel(null)).toBe('z 0.0σ')
  })

  it('enforces 100% read-only separation on personal and physical profile screens', () => {
    const personalVue = readFileSync(
      join(FRONTEND_ROOT, 'app/pages/profile/personal.vue'),
      'utf-8',
    )
    const physicalVue = readFileSync(
      join(FRONTEND_ROOT, 'app/pages/profile/physical.vue'),
      'utf-8',
    )

    for (const content of [personalVue, physicalVue]) {
      expect(content).not.toMatch(/<(input|select|textarea|form)\b/i)
      expect(content).not.toMatch(/\+\s*Log\b/i)
    }
  })
})
