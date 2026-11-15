import { z } from 'zod'

export const missionStageSchema = z.enum(['LAUNCH', 'MISSION', 'RETURN'])

export const physicalCaptureSchema = z.object({
  missionStage: missionStageSchema,
  restingHrBpm: z.number().min(30, 'Minimum 30 bpm').max(200, 'Maximum 200 bpm'),
  spo2Pct: z.number().min(70, 'Minimum 70%').max(100, 'Maximum 100%'),
  bpSystolicMmhg: z.number().min(60, 'Minimum 60 mmHg').max(220, 'Maximum 220 mmHg'),
  bodyTempC: z.number().min(33.0, 'Minimum 33.0 C').max(42.0, 'Maximum 42.0 C'),
  bodyWeightKg: z.number().min(35.0, 'Minimum 35.0 kg').max(150.0, 'Maximum 150.0 kg'),
  hydrationMl: z.number().min(0, 'Minimum 0 mL').max(8000, 'Maximum 8000 mL'),
  exerciseMin: z.number().min(0, 'Minimum 0 min').max(360, 'Maximum 360 min'),
  caloriesKcal: z.number().min(0, 'Minimum 0 kcal').max(6500, 'Maximum 6500 kcal'),
  bloodGlucoseMgDl: z.number().min(30, 'Minimum 30 mg/dL').max(450, 'Maximum 450 mg/dL'),
})

export const ocularCaptureSchema = z.object({
  missionStage: missionStageSchema,
  leftOpticSheathMm: z.number().min(3.0, 'Minimum 3.0 mm').max(9.0, 'Maximum 9.0 mm'),
  rightOpticSheathMm: z.number().min(3.0, 'Minimum 3.0 mm').max(9.0, 'Maximum 9.0 mm'),
  leftIopMmhg: z.number().min(6, 'Minimum 6 mmHg').max(40, 'Maximum 40 mmHg'),
  rightIopMmhg: z.number().min(6, 'Minimum 6 mmHg').max(40, 'Maximum 40 mmHg'),
  retinalThicknessUm: z.number().min(70, 'Minimum 70 um').max(160, 'Maximum 160 um'),
  visualAcuity: z.string().regex(/^20\/\d{2}$/, 'Use Snellen format, e.g. 20/20'),
})
