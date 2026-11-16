import { describe, expect, it } from 'vitest'
import { computeAstroCowSummary } from '../app/utils/astroCowTelemetry'
import { evaluateBehavioralMatrix } from '../app/utils/behavioralMatrix20'
import { buildNeuroFitReport, CAMPAIGN_STAGES } from '../app/utils/neuroFitEngine'

describe('M7 psychological, cognitive, and sensorimotor scoring', () => {
  it('computes real AstroCow RT variability, T_recovery, and precision', () => {
    const summary = computeAstroCowSummary({
      score: 18,
      highScore: 15,
      difficultyLevel: 3,
      durationSec: 65,
      reticleHits: 8,
      reticleTotal: 10,
      collisions: 1,
      errorsAfterChange: 2,
      omittedResponses: 2,
      reactionTimesMs: [300, 400, 500, 400],
      recoveryTimesSec: [1.2, 1.8],
      targetTimelineEvents: [
        { time: 12, hit: true },
        { time: 45, hit: false },
        { time: 62, hit: true },
      ],
    })
    expect(summary.high_score).toBe(18)
    expect(summary.mean_reaction_ms).toBe(400)
    expect(summary.rt_variability_ms).toBe(71)
    expect(summary.recovery_time_sec).toBe(1.5)
    expect(summary.precision_pct).toBe(80)
    expect(summary.performance_by_minute).toHaveLength(2)
    expect(summary.performance_by_minute[0]!.accuracyPct).toBe(50)
  })

  it('derives retention, sustained attention, and Focus Index across NeuroFit stages', () => {
    const report = buildNeuroFitReport(
      [
        {
          key: 'sequence',
          title: CAMPAIGN_STAGES[0]!.title,
          cabCode: 'CAB-ME',
          cabName: 'Working Memory',
          score: 150,
          accuracy: 90,
          correct_attempts: 9,
          error_attempts: 1,
          total_attempts: 10,
          avg_reaction_ms: 600,
          level_reached: 4,
          duration_sec: 30,
          leadCharId: 'tamalito',
          gains: { memory: 10 },
        },
        {
          key: 'bee',
          title: CAMPAIGN_STAGES[1]!.title,
          cabCode: 'CAB-AT',
          cabName: 'Attention',
          score: 140,
          accuracy: 80,
          correct_attempts: 8,
          error_attempts: 2,
          total_attempts: 10,
          avg_reaction_ms: 700,
          level_reached: 3,
          duration_sec: 30,
          leadCharId: 'chipilin',
          gains: { attention: 10 },
        },
        {
          key: 'explorer',
          title: CAMPAIGN_STAGES[2]!.title,
          cabCode: 'CAB-RS',
          cabName: 'Spatial Reasoning',
          score: 120,
          accuracy: 100,
          correct_attempts: 2,
          error_attempts: 0,
          total_attempts: 2,
          avg_reaction_ms: 1500,
          level_reached: 3,
          duration_sec: 20,
          leadCharId: 'wakax',
          gains: { spatial: 10 },
        },
        {
          key: 'scan',
          title: CAMPAIGN_STAGES[3]!.title,
          cabCode: 'CAB-PC',
          cabName: 'Perception',
          score: 130,
          accuracy: 90,
          correct_attempts: 9,
          error_attempts: 1,
          total_attempts: 10,
          avg_reaction_ms: 800,
          level_reached: 4,
          duration_sec: 30,
          leadCharId: 'misi',
          gains: { reaction: 10 },
        },
      ],
      'tamalito',
      {
        memory: { code: 'CAB-ME', label: 'Working Memory', score: 450 },
        attention: { code: 'CAB-AT', label: 'Attention & Inhibition', score: 460 },
      },
    )
    expect(report.retention_pct).toBe(90)
    expect(report.sustained_attention_pct).toBe(85)
    expect(report.focus_index_score).toBe(90)
    expect(report.overall_accuracy_pct).toBe(88)
  })

  it('classifies Behavioral Matrix 20 subscales and DSM-5-TR crosswalk triggers', () => {
    const nominal = evaluateBehavioralMatrix(Array.from({ length: 20 }, () => 0))
    expect(nominal.totalLoad).toBe(0)
    expect(nominal.readinessStatus).toBe('FIT FOR FLIGHT')
    expect(nominal.stage2Triggered).toBe(false)

    const critical = evaluateBehavioralMatrix([3, 3, 3, 3, 3, 3, 3, 3, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2])
    expect(critical.totalLoad).toBe(48)
    expect(critical.readinessStatus).toBe('RESTRICTED DUTY')
    expect(critical.stage2Triggered).toBe(true)
  })
})
