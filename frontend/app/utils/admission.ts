// Two-level check of a typed reading, shown live under each Capture field.
//   Level 1 - non-admissible: not a number, or outside what a person (or the instrument) can
//             read. Saving is blocked and the server would answer 422 anyway.
//   Level 2 - admissible but outside the normal range for the crew member's sex: the reading
//             is saved and the onboard alert engine raises a clinical advisory.

export type Sex = 'F' | 'M' | null | undefined

export interface RangeItem {
  unit: string
  nominal_min: number
  nominal_max: number
  plausible_min: number | null
  plausible_max: number | null
  by_sex?: Record<string, { nominal_min?: number | null, nominal_max?: number | null }> | null
}

export type Admission =
  | { level: 'empty' }
  | { level: 'invalid', text: string }
  | { level: 'non_admissible', text: string }
  | { level: 'abnormal', text: string }
  | { level: 'nominal' }

export const ABNORMAL_TEXT = 'Admissible reading · Outside nominal range — saving will log reading and trigger clinical advisory'
export const MIN_PULSE_PRESSURE = 10

function trim(value: number): string {
  return Number.isInteger(value) ? String(value) : String(Number(value.toFixed(3)))
}

export function admissibleText(item: RangeItem): string {
  return `Non-admissible reading · admissible ${trim(item.plausible_min ?? 0)}–${trim(item.plausible_max ?? 0)} ${item.unit}`.trim()
}

/** Normal range for this crew member: the female or male range when the metric has one. */
export function nominalFor(item: RangeItem, sex: Sex): [number, number] {
  const override = sex ? item.by_sex?.[sex] : undefined
  return [override?.nominal_min ?? item.nominal_min, override?.nominal_max ?? item.nominal_max]
}

/**
 * ``checkNominal`` is false for daily habits (water, energy, exercise): one entry is part
 * of the day's total, so only the admissible range applies to it.
 */
export function admissionOf(item: RangeItem | undefined, value: number | undefined, sex: Sex, checkNominal = true): Admission {
  if (value === undefined) return { level: 'empty' }
  if (Number.isNaN(value)) return { level: 'invalid', text: 'Non-admissible reading · enter a number' }
  if (!item) return { level: 'nominal' }
  if ((item.plausible_min != null && value < item.plausible_min) || (item.plausible_max != null && value > item.plausible_max)) {
    return { level: 'non_admissible', text: admissibleText(item) }
  }
  if (!checkNominal) return { level: 'nominal' }
  const [low, high] = nominalFor(item, sex)
  return value < low || value > high ? { level: 'abnormal', text: ABNORMAL_TEXT } : { level: 'nominal' }
}

/** Blood pressure typed as "118 / 76": both values in range and diastolic well below systolic. */
export function pressureAdmission(
  systolic: number | undefined, diastolic: number | undefined,
  sysItem: RangeItem | undefined, diaItem: RangeItem | undefined, sex: Sex,
): Admission {
  if (systolic === undefined && diastolic === undefined) return { level: 'empty' }
  if (systolic === undefined || diastolic === undefined || Number.isNaN(systolic) || Number.isNaN(diastolic)) {
    return { level: 'invalid', text: 'Non-admissible reading · enter as 118 / 76' }
  }
  const s = admissionOf(sysItem, systolic, sex)
  const d = admissionOf(diaItem, diastolic, sex)
  if (s.level === 'non_admissible') return { level: 'non_admissible', text: s.text.replace('· admissible', '· systolic admissible') }
  if (d.level === 'non_admissible') return { level: 'non_admissible', text: d.text.replace('· admissible', '· diastolic admissible') }
  if (systolic - diastolic < MIN_PULSE_PRESSURE) {
    return { level: 'non_admissible', text: `Non-admissible reading · diastolic must be at least ${MIN_PULSE_PRESSURE} mmHg below systolic` }
  }
  return s.level === 'abnormal' || d.level === 'abnormal' ? { level: 'abnormal', text: ABNORMAL_TEXT } : { level: 'nominal' }
}

/** Notice shown under a field, or null when there is nothing to say. */
export function noticeOf(admission: Admission): { tone: 'critical' | 'watch', text: string } | null {
  if (admission.level === 'invalid' || admission.level === 'non_admissible') return { tone: 'critical', text: admission.text }
  if (admission.level === 'abnormal') return { tone: 'watch', text: admission.text }
  return null
}
