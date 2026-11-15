// Two-level admission of a typed reading: impossible values are blocked, abnormal ones are
// saved with a clinical advisory, and normal ranges follow the crew member's sex.
import { describe, expect, it } from 'vitest'
import { ABNORMAL_TEXT, admissionOf, nominalFor, noticeOf, pressureAdmission, type RangeItem } from '../app/utils/admission'

const spo2: RangeItem = { unit: '%', nominal_min: 95, nominal_max: 100, plausible_min: 50, plausible_max: 100 }
const temp: RangeItem = { unit: '°C', nominal_min: 36.5, nominal_max: 37.3, plausible_min: 32, plausible_max: 43 }
const hemoglobin: RangeItem = {
  unit: 'g/dL', nominal_min: 12, nominal_max: 17.5, plausible_min: 4, plausible_max: 24,
  by_sex: { F: { nominal_min: 12, nominal_max: 16 }, M: { nominal_min: 13.5, nominal_max: 17.5 } },
}
const hydration: RangeItem = { unit: 'mL', nominal_min: 2000, nominal_max: 3700, plausible_min: 10, plausible_max: 5000 }
const systolic: RangeItem = { unit: 'mmHg', nominal_min: 90, nominal_max: 119, plausible_min: 50, plausible_max: 260 }
const diastolic: RangeItem = { unit: 'mmHg', nominal_min: 55, nominal_max: 79, plausible_min: 30, plausible_max: 160 }

describe('admission levels', () => {
  it('blocks impossible and non-numeric values', () => {
    expect(admissionOf(spo2, 105, 'F')).toEqual({ level: 'non_admissible', text: 'Non-admissible reading · admissible 50–100 %' })
    expect(admissionOf(temp, 52, 'M').level).toBe('non_admissible')
    expect(admissionOf(temp, -1, 'M').level).toBe('non_admissible')
    expect(admissionOf(temp, Number.NaN, 'M').level).toBe('invalid')
    expect(noticeOf(admissionOf(spo2, 105, 'F'))?.tone).toBe('critical')
  })

  it('admits abnormal but possible values with a clinical pre-warning', () => {
    expect(admissionOf(spo2, 89, 'F')).toEqual({ level: 'abnormal', text: ABNORMAL_TEXT })
    expect(admissionOf(temp, 38.6, 'M').level).toBe('abnormal')
    expect(noticeOf(admissionOf(spo2, 89, 'F'))?.tone).toBe('watch')
    expect(admissionOf(spo2, 98, 'F').level).toBe('nominal')
    expect(admissionOf(spo2, undefined, 'F').level).toBe('empty')
  })

  it('uses the female or male normal range', () => {
    expect(nominalFor(hemoglobin, 'F')).toEqual([12, 16])
    expect(nominalFor(hemoglobin, 'M')).toEqual([13.5, 17.5])
    expect(admissionOf(hemoglobin, 12.6, 'F').level).toBe('nominal')
    expect(admissionOf(hemoglobin, 12.6, 'M').level).toBe('abnormal')
    expect(admissionOf(hemoglobin, 16.8, 'F').level).toBe('abnormal')
  })

  it('checks a single habit entry for being possible only', () => {
    expect(admissionOf(hydration, 400, 'F', false).level).toBe('nominal')
    expect(admissionOf(hydration, 9000, 'F', false).level).toBe('non_admissible')
  })
})

describe('blood pressure pair', () => {
  const check = (s?: number, d?: number) => pressureAdmission(s, d, systolic, diastolic, 'F')
  it('needs both values and diastolic at least 10 mmHg below systolic', () => {
    expect(check(90, 110).level).toBe('non_admissible')
    expect(check(118, 112).level).toBe('non_admissible')
    expect(check(118, undefined).level).toBe('invalid')
    expect(check(300, 80).text).toContain('systolic admissible')
  })

  it('flags abnormal pressure and passes normal pressure', () => {
    expect(check(165, 102).level).toBe('abnormal')
    expect(check(182, 114).level).toBe('abnormal')
    expect(check(118, 76).level).toBe('nominal')
    expect(check().level).toBe('empty')
  })
})
