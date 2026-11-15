export type ClinicalBand = 'Optimal' | 'Nominal' | 'Attention' | 'Critical'

export function computeZScore(value: number, mean: number, stdDev: number): number {
  if (!Number.isFinite(stdDev) || stdDev <= 0) {
    return 0
  }
  return Number(((value - mean) / stdDev).toFixed(2))
}

export function evaluateMetricStatus(
  value: number,
  nominalMin: number,
  nominalMax: number,
  criticalMin?: number | null,
  criticalThreshold?: number | null,
): ClinicalBand {
  if ((criticalThreshold !== undefined && criticalThreshold !== null && value >= criticalThreshold)
    || (criticalMin !== undefined && criticalMin !== null && value <= criticalMin)) {
    return 'Critical'
  }
  if (value < nominalMin || value > nominalMax) {
    return 'Attention'
  }
  const margin = (nominalMax - nominalMin) * 0.15
  if (value >= nominalMin + margin && value <= nominalMax - margin) {
    return 'Optimal'
  }
  return 'Nominal'
}

export function readinessBandFromScore(score: number, hasCriticalAlert = false): ClinicalBand {
  if (hasCriticalAlert || score < 60) return 'Critical'
  if (score < 78) return 'Attention'
  if (score < 88) return 'Nominal'
  return 'Optimal'
}

export function statusPillClasses(status: ClinicalBand): string {
  if (status === 'Critical') {
    return 'bg-cabin-crit/25 border-cabin-crit text-cabin-text'
  }
  if (status === 'Attention') {
    return 'bg-cabin-navy/55 border-cabin-navy-edge text-cabin-text'
  }
  if (status === 'Nominal') {
    return 'bg-cabin-navy/35 border-cabin-navy-edge/70 text-cabin-text'
  }
  return 'bg-cabin-navy/42 border-cabin-ok/75 text-cabin-ok'
}
