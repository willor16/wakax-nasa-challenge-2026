import { readFileSync } from 'node:fs'
import { join, resolve } from 'node:path'
import { describe, expect, it } from 'vitest'
import {
  buildOcularSheathGaugeOption,
  buildOnsdBilateralTrendOption,
  eyeSeriesColorVar,
  visionToneColorVar,
} from '../app/utils/visionCharts'

const FRONTEND_ROOT = resolve(import.meta.dirname, '..')

describe('D2-05 Vision Exam Utilities & Read-Only Separation', () => {
  it('builds bilateral ocular sheath radial gauge option with animation disabled', () => {
    const option = buildOcularSheathGaugeOption({
      side: 'RIGHT',
      label: 'RIGHT EYE',
      sheath_mm: 5.9,
      display_value: '5.9',
      status_label: 'mm (Elevated)',
      tone: 'critical',
    })

    expect(option.animation).toBe(false)
    expect(option.series[0]?.type).toBe('gauge')
    expect(option.series[0]?.animation).toBe(false)
    expect(option.series[0]?.detail.valueAnimation).toBe(false)
    expect(option.series[0]?.data[0]).toEqual({
      value: 5.9,
      name: 'mm (Elevated)',
    })
  })

  it('builds bilateral ONSD trend option with baseline markArea, 5.8 mm markLine, and recovery projection', () => {
    const option = buildOnsdBilateralTrendOption({
      points: [
        { label: 'Baseline', left_mm: 4.6, right_mm: 4.7, is_projected: false },
        { label: 'Day 15', left_mm: 5.0, right_mm: 5.2, is_projected: false },
        { label: 'Day 45', left_mm: 5.5, right_mm: 5.9, is_projected: false },
        { label: 'Target D60', left_mm: 5.3, right_mm: 5.5, is_projected: true },
      ],
      baselineBandMinMm: 4.2,
      baselineBandMaxMm: 5.5,
      alertThresholdMm: 5.8,
      rightEyeTone: 'critical',
      leftEyeTone: 'warn',
    })

    expect(option.animation).toBe(false)
    expect(option.xAxis.data).toEqual(['Baseline', 'Day 15', 'Day 45', 'Target D60'])
    expect(option.series).toHaveLength(4)
    expect(option.series[0]?.data).toEqual([4.7, 5.2, 5.9, null])
    expect(option.series[1]?.data).toEqual([4.6, 5.0, 5.5, null])
    expect(option.series[2]?.data).toEqual([null, null, 5.9, 5.5])
    expect(option.series[2]?.lineStyle?.type).toBe('dashed')
    expect(option.series[0]?.markLine?.data?.[0]?.yAxis).toBe(5.8)
  })

  it('maps ocular tones to CSS variables without raw hex literals', () => {
    expect(visionToneColorVar('critical')).toBe('var(--color-status-critical)')
    expect(visionToneColorVar('warn')).toBe('var(--color-rem-accent)')
    expect(visionToneColorVar('reference')).toBe('var(--color-status-ok)')
    expect(eyeSeriesColorVar('LEFT', 'reference')).toBe('var(--color-status-ok)')
    expect(eyeSeriesColorVar('RIGHT', 'critical')).toBe('var(--color-status-critical)')
  })

  it('enforces 100% read-only separation on /vision screen', () => {
    const visionPage = readFileSync(join(FRONTEND_ROOT, 'app/pages/vision.vue'), 'utf-8')
    expect(visionPage).not.toMatch(/<(input|select|textarea|form)\b/i)
    expect(visionPage).not.toMatch(/\+\s*Log\b/i)
  })
})
