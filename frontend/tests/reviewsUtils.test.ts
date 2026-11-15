import { describe, expect, it } from 'vitest'
import { metricLine, sourceLabel, strengthLabel } from '../app/utils/reviews'

describe('Physician review helpers', () => {
  it('describes readings against the usual value', () => {
    expect(metricLine({
      metric_key: 'iop_right_mmhg',
      display_name_en: 'Right Intraocular Pressure',
      unit: 'mmHg',
      value: 17.5,
      baseline: 14.5,
      z: 5.2,
    })).toBe('Right Intraocular Pressure 17.5 mmHg · usual 14.5 mmHg')
    expect(metricLine({
      metric_key: 'spo2_pct', display_name_en: 'Blood Oxygen', unit: '%', value: 94, baseline: 98, z: -3,
    })).toBe('Blood Oxygen 94% · usual 98%')
  })

  it('uses plain words for strength and source', () => {
    expect(strengthLabel(1.05)).toBe('MILD')
    expect(strengthLabel(1.5)).toBe('CLEAR')
    expect(strengthLabel(2.6)).toBe('STRONG')
    expect(sourceLabel('assistant')).toBe('SUGGESTED BY ONBOARD ASSISTANT')
    expect(sourceLabel('fallback')).toBe('STANDARD CARE STEPS')
  })
})
