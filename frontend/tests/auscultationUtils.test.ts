import { readFileSync } from 'node:fs'
import { join, resolve } from 'node:path'
import { describe, expect, it } from 'vitest'
import {
  auscultationMetricColorVar,
  auscultationToneColorVar,
  buildCabinCo2TrendOption,
  buildPhonocardiogramOption,
  buildPulmonaryEnvelopeOption,
  buildSyntheticStethoscopeBytes,
  computeRmsDba,
  computeSha256Hex,
  generateLivePreviewWave,
} from '../app/utils/auscultationCharts'

const FRONTEND_ROOT = resolve(import.meta.dirname, '..')

describe('D2-06 Auscultation Charts, Acoustic Gate & Read-Only Separation', () => {
  it('builds S1/S2 phonocardiogram and bilateral pulmonary envelope options with lttb and animation disabled', () => {
    const cardiacSamples = generateLivePreviewWave('CARDIAC', 1, 180)
    const pulmonarySamples = generateLivePreviewWave('PULMONARY', 1, 180)

    const phonoOpt = buildPhonocardiogramOption(cardiacSamples, 'reference')
    const pulmOpt = buildPulmonaryEnvelopeOption(pulmonarySamples, 'reference')

    expect(phonoOpt.animation).toBe(false)
    expect(phonoOpt.series[0]?.type).toBe('line')
    expect(phonoOpt.series[0]?.sampling).toBe('lttb')
    expect(phonoOpt.series[0]?.data).toHaveLength(180)

    expect(pulmOpt.animation).toBe(false)
    expect(pulmOpt.series[0]?.type).toBe('line')
    expect(pulmOpt.series[0]?.sampling).toBe('lttb')
    expect(pulmOpt.series[0]?.data).toHaveLength(180)
  })

  it('builds 24-hour cabin CO2 trend option with 3.2 mmHg target zone and 4.0 mmHg alert threshold', () => {
    const co2Opt = buildCabinCo2TrendOption({
      points: [
        { label: '00:00', co2_mmhg: 2.4 },
        { label: '04:00', co2_mmhg: 2.5 },
        { label: '08:00', co2_mmhg: 2.7 },
        { label: '12:00', co2_mmhg: 2.9 },
        { label: '16:00', co2_mmhg: 3.0 },
        { label: '20:00', co2_mmhg: 2.9 },
        { label: '24:00', co2_mmhg: 2.8 },
      ],
      targetMaxMmhg: 3.2,
      alertLimitMmhg: 4.0,
      tone: 'reference',
    })

    expect(co2Opt.animation).toBe(false)
    expect(co2Opt.xAxis.data).toEqual([
      '00:00',
      '04:00',
      '08:00',
      '12:00',
      '16:00',
      '20:00',
      '24:00',
    ])
    expect(co2Opt.series[0]?.markLine?.data?.[0]?.yAxis).toBe(4.0)
    expect(co2Opt.series[0]?.markLine?.data?.[0]?.lineStyle?.type).toBe('dashed')
    expect(co2Opt.series[0]?.markArea?.data?.[0]?.[1]?.yAxis).toBe(3.2)
  })

  it('computes calibrated RMS dBA and deterministic SHA-256 hex digest for stethoscope WebM payload', async () => {
    const quietDba = computeRmsDba(new Float32Array(512))
    const loudDba = computeRmsDba(Float32Array.from({ length: 512 }, () => 0.45))

    expect(quietDba).toBeLessThan(55.0)
    expect(loudDba).toBeGreaterThan(55.0)

    const webmBytes = buildSyntheticStethoscopeBytes('CARDIAC', 'mitral', 30)
    expect(webmBytes[0]).toBe(0x1A)
    expect(webmBytes[1]).toBe(0x45)
    expect(webmBytes[2]).toBe(0xDF)
    expect(webmBytes[3]).toBe(0xA3)

    const digest = await computeSha256Hex(webmBytes)
    expect(digest).toMatch(/^[0-9a-f]{64}$/)

    expect(auscultationToneColorVar('critical')).toBe('var(--color-status-critical)')
    expect(auscultationMetricColorVar('nominal')).toBe('var(--color-status-ok)')
  })

  it('enforces 100% read-only separation on /auscultation while keeping controls in /capture/auscultation', () => {
    const resultsPage = readFileSync(join(FRONTEND_ROOT, 'app/pages/auscultation.vue'), 'utf-8')
    expect(resultsPage).not.toMatch(/<(input|select|textarea|form)\b/i)
    expect(resultsPage).not.toMatch(/\+\s*Log\b/i)
    expect(resultsPage).not.toMatch(/Record Heart Audio|Save Cardiac Recording/i)

    const capturePage = readFileSync(
      join(FRONTEND_ROOT, 'app/pages/capture/auscultation.vue'),
      'utf-8',
    )
    expect(capturePage).toContain('Record Heart Audio')
    expect(capturePage).toContain('Save Cardiac Recording')
    expect(capturePage).toContain('Record Pulmonary Audio')
    expect(capturePage).toContain('Save Lung Recording')
  })
})
