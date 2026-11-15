import { z } from 'zod'

export const missionStageSchema = z.enum(['LAUNCH', 'MISSION', 'RETURN'])
export const workShiftModeSchema = z.enum(['IVA', 'EVA'])

export function parseWorkShiftMinutes(raw: string): number | null {
  const trimmed = raw.trim()
  const hmMatch = /^(\d{1,2})\s*h(?:\s*(\d{1,2})\s*m)?$/i.exec(trimmed)
  if (hmMatch) {
    const hours = Number(hmMatch[1])
    const mins = hmMatch[2] ? Number(hmMatch[2]) : 0
    if (mins >= 60) {
      return null
    }
    const total = hours * 60 + mins
    return total >= 0 && total <= 960 ? total : null
  }
  const minMatch = /^(\d{1,3})\s*m?$/i.exec(trimmed)
  if (minMatch) {
    const total = Number(minMatch[1])
    return total >= 0 && total <= 960 ? total : null
  }
  return null
}

export function normalizeSnellen(raw: string): string {
  const match = /^\s*20\s*\/\s*(\d{2,3})\s*$/.exec(raw)
  return match ? `20/${match[1]}` : raw.trim()
}

export function snellenToLogMar(raw: string): number {
  const match = /^\s*20\s*\/\s*(\d{2,3})\s*$/.exec(raw)
  if (!match) {
    return 0
  }
  const denominator = Number(match[1])
  if (!Number.isFinite(denominator) || denominator <= 0) {
    return 0
  }
  const value = Number(Math.log10(denominator / 20).toFixed(3))
  return value === 0 ? 0 : value
}

export const dailyVitalsHabitsSchema = z.object({
  missionStage: missionStageSchema,
  bodyWeightKg: z.number().min(35.0, 'Minimum 35.0 kg').max(150.0, 'Maximum 150.0 kg'),
  bpSystolicMmhg: z.number().min(60, 'Minimum 60 mmHg').max(220, 'Maximum 220 mmHg'),
  bpDiastolicMmhg: z.number().min(40, 'Minimum 40 mmHg').max(140, 'Maximum 140 mmHg'),
  restingHrBpm: z.number().min(30, 'Minimum 30 bpm').max(200, 'Maximum 200 bpm'),
  bodyTempC: z.number().min(33.0, 'Minimum 33.0 C').max(42.0, 'Maximum 42.0 C'),
  hydrationAddMl: z.number().min(0, 'Minimum 0 mL').max(5000, 'Maximum 5000 mL'),
  caloriesKcal: z.number().min(0, 'Minimum 0 kcal').max(6500, 'Maximum 6500 kcal'),
  exerciseMin: z.number().min(0, 'Minimum 0 min').max(360, 'Maximum 360 min'),
  workShiftText: z
    .string()
    .refine(value => parseWorkShiftMinutes(value) !== null, 'Use format like 5h 20m (max 16h)'),
  workShiftMode: workShiftModeSchema,
})

export const clinicalLabsSchema = z.object({
  missionStage: missionStageSchema,
  bloodGlucoseMgDl: z.number().min(30, 'Minimum 30 mg/dL').max(450, 'Maximum 450 mg/dL'),
  hemoglobinGDl: z.number().min(6.0, 'Minimum 6.0 g/dL').max(22.0, 'Maximum 22.0 g/dL'),
  urineSpecificGravity: z.number().min(1.001, 'Minimum 1.001 SG').max(1.04, 'Maximum 1.040 SG'),
  spo2Pct: z.number().min(70, 'Minimum 70%').max(100, 'Maximum 100%'),
})

export const physicalCaptureSchema = z.object({
  missionStage: missionStageSchema,
  restingHrBpm: z.number().min(30, 'Minimum 30 bpm').max(200, 'Maximum 200 bpm'),
  spo2Pct: z.number().min(70, 'Minimum 70%').max(100, 'Maximum 100%'),
  bpSystolicMmhg: z.number().min(60, 'Minimum 60 mmHg').max(220, 'Maximum 220 mmHg'),
  bpDiastolicMmhg: z.number().min(40, 'Minimum 40 mmHg').max(140, 'Maximum 140 mmHg').optional(),
  bodyTempC: z.number().min(33.0, 'Minimum 33.0 C').max(42.0, 'Maximum 42.0 C'),
  bodyWeightKg: z.number().min(35.0, 'Minimum 35.0 kg').max(150.0, 'Maximum 150.0 kg'),
  hydrationMl: z.number().min(0, 'Minimum 0 mL').max(8000, 'Maximum 8000 mL'),
  exerciseMin: z.number().min(0, 'Minimum 0 min').max(360, 'Maximum 360 min'),
  caloriesKcal: z.number().min(0, 'Minimum 0 kcal').max(6500, 'Maximum 6500 kcal'),
  bloodGlucoseMgDl: z.number().min(30, 'Minimum 30 mg/dL').max(450, 'Maximum 450 mg/dL'),
  hemoglobinGDl: z.number().min(6.0, 'Minimum 6.0 g/dL').max(22.0, 'Maximum 22.0 g/dL').optional(),
  urineSpecificGravity: z
    .number()
    .min(1.001, 'Minimum 1.001 SG')
    .max(1.04, 'Maximum 1.040 SG')
    .optional(),
  workShiftMin: z.number().min(0, 'Minimum 0 min').max(960, 'Maximum 960 min').optional(),
})

export const ocularCaptureSchema = z.object({
  missionStage: missionStageSchema,
  leftOpticSheathMm: z.number().min(3.0, 'Minimum 3.0 mm').max(9.0, 'Maximum 9.0 mm'),
  rightOpticSheathMm: z.number().min(3.0, 'Minimum 3.0 mm').max(9.0, 'Maximum 9.0 mm'),
  leftIopMmhg: z.number().min(8, 'Minimum 8 mmHg').max(35, 'Maximum 35 mmHg'),
  rightIopMmhg: z.number().min(8, 'Minimum 8 mmHg').max(35, 'Maximum 35 mmHg'),
  retinalThicknessUm: z.number().min(70, 'Minimum 70 um').max(160, 'Maximum 160 um'),
  visualAcuity: z.string().regex(/^\s*20\s*\/\s*\d{2,3}\s*$/, 'Use Snellen format, e.g. 20/20'),
})

export type DailyVitalsHabitsInput = z.infer<typeof dailyVitalsHabitsSchema>
export type ClinicalLabsInput = z.infer<typeof clinicalLabsSchema>
export type OcularCaptureInput = z.infer<typeof ocularCaptureSchema>
