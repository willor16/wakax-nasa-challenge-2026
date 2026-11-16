import { describe, expect, it } from 'vitest'
import {
  buildSandraPayload,
  computeAmslerEyeSummary,
  computeConsolidatedSANS,
  createDefaultSandraSession,
  worstSnellenDenominator,
} from '../app/utils/sandraVisualBattery'

describe('Sandra Visual Battery scoring and payload', () => {
  it('computes nominal baseline when no alterations are present', () => {
    const session = createDefaultSandraSession()
    session.acuity.OD = {
      snellen: '20/20',
      decimal: '1.00',
      logMar: '0.00',
      avgResponseTime: '1.00',
      statusClass: 'ok',
      statusLabel: 'NOMINAL',
    }
    session.acuity.OS = { ...session.acuity.OD }
    expect(worstSnellenDenominator(session.acuity)).toBe(20)
    const overall = computeConsolidatedSANS(session)
    expect(overall.triageLevel).toBe('NOMINAL')
    expect(overall.score).toBe(0)
  })

  it('flags metamorphopsia distortion and worst-eye Snellen reduction', () => {
    const session = createDefaultSandraSession()
    session.milestone = 'Mission Day 30'
    session.acuity.OD = {
      snellen: '20/30',
      decimal: '0.67',
      logMar: '0.18',
      avgResponseTime: '1.40',
      statusClass: 'warn',
      statusLabel: 'OBSERVATION',
    }
    session.amslerGrid.OD['9_10'] = { row: 9, col: 10, type: 'metamorphopsia' }
    session.amslerAnswers.OD.hasWavyLines = true

    expect(worstSnellenDenominator(session.acuity)).toBe(30)
    const odAmsler = computeAmslerEyeSummary(session.amslerGrid.OD, session.amslerAnswers.OD)
    expect(odAmsler.hasMetamorphopsia).toBe(true)
    expect(odAmsler.totalCells).toBe(1)

    const payload = buildSandraPayload(session)
    expect(payload.sandra_test.milestone).toBe('Mission Day 30')
    expect(payload.sandra_test.amsler.OD.affectedCount).toBe(1)
    expect(payload.sandra_test.symptoms.triage_level).toBe('OBSERVATION')
  })

  it('escalates immediately to CRITICAL alert on scotoma or diplopia', () => {
    const session = createDefaultSandraSession()
    session.amslerGrid.OS['10_10'] = { row: 10, col: 10, type: 'scotoma' }
    session.symptoms.q3_1_diplopia = { experienced: true, type: 'Constant' }
    const overall = computeConsolidatedSANS(session)
    expect(overall.triageLevel).toBe('ALERT')
    expect(overall.statusClass).toBe('critica')
  })
})
