import { describe, expect, it } from 'vitest'
import { ocularCaptureSchema, physicalCaptureSchema } from '../app/schemas/capture'

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
      leftOpticSheathMm: 4.5,
      rightOpticSheathMm: 4.7,
      leftIopMmhg: 15,
      rightIopMmhg: 16,
      retinalThicknessUm: 108,
      visualAcuity: '20/20',
    })
    expect(ocular.success).toBe(true)
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
