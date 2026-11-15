import { describe, expect, it } from 'vitest'
import {
  buildClinicalLabsItems,
  buildDailyVitalsItems,
  buildOcularExamItems,
} from '../app/composables/useMeasurements'
import {
  clinicalLabsSchema,
  dailyVitalsHabitsSchema,
  ocularCaptureSchema,
  parseWorkShiftMinutes,
  physicalCaptureSchema,
  snellenToLogMar,
} from '../app/schemas/capture'

describe('Capture Zod Schemas', () => {
  it('accepts valid physical and ocular capture payloads', () => {
    const physical = physicalCaptureSchema.safeParse({
      missionStage: 'MISSION',
      restingHrBpm: 64,
      spo2Pct: 98,
      bpSystolicMmhg: 118,
      bodyTempC: 36.7,
      bodyWeightKg: 63.0,
      hydrationMl: 2500,
      exerciseMin: 85,
      caloriesKcal: 2400,
      bloodGlucoseMgDl: 92,
    })
    expect(physical.success).toBe(true)

    const ocular = ocularCaptureSchema.safeParse({
      missionStage: 'MISSION',
      leftOpticSheathMm: 5.5,
      rightOpticSheathMm: 5.9,
      leftIopMmhg: 15.8,
      rightIopMmhg: 16.2,
      retinalThicknessUm: 104,
      visualAcuity: '20 / 20',
    })
    expect(ocular.success).toBe(true)
  })

  it('validates split Frame 11 vitals/habits and clinical lab strip panels', () => {
    const vitals = dailyVitalsHabitsSchema.safeParse({
      missionStage: 'MISSION',
      bodyWeightKg: 63.8,
      bpSystolicMmhg: 118,
      bpDiastolicMmhg: 76,
      restingHrBpm: 64,
      bodyTempC: 36.8,
      hydrationAddMl: 400,
      caloriesKcal: 2420,
      exerciseMin: 85,
      workShiftText: '5h 20m',
      workShiftMode: 'IVA',
    })
    expect(vitals.success).toBe(true)
    if (vitals.success) {
      const items = buildDailyVitalsItems(vitals.data, 2400)
      expect(items).toHaveLength(9)
      expect(items.find(i => i.metric_key === 'hydration_ml')?.value_num).toBe(2800)
      expect(items.find(i => i.metric_key === 'work_shift_min')?.value_num).toBe(320)
    }

    const labs = clinicalLabsSchema.safeParse({
      missionStage: 'MISSION',
      bloodGlucoseMgDl: 89,
      hemoglobinGDl: 13.8,
      urineSpecificGravity: 1.018,
      spo2Pct: 98,
    })
    expect(labs.success).toBe(true)
    if (labs.success) {
      expect(buildClinicalLabsItems(labs.data)).toHaveLength(4)
    }
  })

  it('parses work shift durations and converts Snellen acuity to LogMAR', () => {
    expect(parseWorkShiftMinutes('5h 20m')).toBe(320)
    expect(parseWorkShiftMinutes('90m')).toBe(90)
    expect(parseWorkShiftMinutes('5h 75m')).toBeNull()
    expect(snellenToLogMar('20 / 20')).toBe(0)
    expect(snellenToLogMar('20/40')).toBeCloseTo(0.301, 3)

    const ocularItems = buildOcularExamItems({
      missionStage: 'MISSION',
      leftOpticSheathMm: 5.5,
      rightOpticSheathMm: 5.9,
      leftIopMmhg: 15.8,
      rightIopMmhg: 16.2,
      retinalThicknessUm: 104,
      visualAcuity: '20 / 20',
    })
    expect(ocularItems).toHaveLength(4)
    expect(ocularItems[0]?.payload_json).toEqual({
      retinal_thickness_um: 104,
      visual_acuity: '20/20',
      visual_acuity_logmar: 0,
    })
  })

  it('rejects out-of-range optic nerve sheath and invalid acuity format', () => {
    const invalid = ocularCaptureSchema.safeParse({
      missionStage: 'MISSION',
      leftOpticSheathMm: 2.1,
      rightOpticSheathMm: 4.7,
      leftIopMmhg: 15,
      rightIopMmhg: 16,
      retinalThicknessUm: 108,
      visualAcuity: '10/10',
    })
    expect(invalid.success).toBe(false)
  })
})
