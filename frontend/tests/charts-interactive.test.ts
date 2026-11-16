// M4: every clinical chart zooms, marks its extremes, shows its thresholds, paints alert
// points red and lets the crew member pin points for comparison.
import { readFileSync } from 'node:fs'
import { join, resolve } from 'node:path'
import { describe, expect, it } from 'vitest'
import { togglePin, type ChartPin } from '../app/composables/useChartPins'
import {
  alertColoured, dataZoomFor, interpretation, isAlert, markPointsFor, statusFor, thresholdMarks, SLIDER_HEIGHT,
  type Thresholds,
} from '../app/utils/chartDecor'
import { co2TrendOption, moodTrendOption, ocularTrendOption, sleepHistoryOption } from '../app/utils/charts'

const APP = join(resolve(import.meta.dirname, '..'), 'app')
const co2: Thresholds = { band: [0, 3], watch: [3], critical: [4], alertWhen: 'above' }
const mood: Thresholds = { band: [3.8, 5], watch: [3], critical: [2], alertWhen: 'below' }

function pin(key: string): ChartPin {
  return { key, series: 'Mood', value: 4, unit: '/ 5', digits: 1, time_utc: null, stage: null, delta: null,
    reference_label: null, status: 'NOMINAL', coord: ['D01', 4] }
}

describe('clinical decorations', () => {
  it('zooms with the wheel and a 16px slider', () => {
    const zoom = dataZoomFor()
    expect(zoom.map(z => z.type)).toEqual(['inside', 'slider'])
    expect(zoom[1]).toMatchObject({ height: SLIDER_HEIGHT })
    expect(SLIDER_HEIGHT).toBe(16)
  })

  it('marks max and min with the clinical unit, plus pins', () => {
    const marks = markPointsFor('mmHg', 2, [{ coord: ['2026-11-15T10:00:00Z', 3.1], label: '3.1' }])
    expect(marks.data.map(d => ('type' in d ? d.type : d.name))).toEqual(['max', 'min', 'Pin'])
    const label = (marks.data[0] as { label: { formatter: (p: { value: number }) => string } }).label
    expect(label.formatter({ value: 4.256 })).toBe('MAX 4.26 mmHg')
  })

  it('draws the nominal band, a dashed watch line and a red alert line', () => {
    const decor = thresholdMarks(co2, 'mmHg')
    expect(decor.markArea?.data).toEqual([[{ yAxis: 0 }, { yAxis: 3 }]])
    const lines = decor.markLine.data
    expect(lines.map(l => l.yAxis)).toEqual([3, 4])
    expect(lines[0]!.lineStyle.type).toBe('dashed')
    expect(lines[1]!.lineStyle.type).toBe('solid')
  })

  it('paints points beyond the alert line red and classifies them', () => {
    expect(isAlert(4.4, co2)).toBe(true)
    expect(isAlert(1.8, mood)).toBe(true)
    expect(isAlert(3.5, mood)).toBe(false)
    const data = alertColoured([2.5, 4.5], co2) as unknown[]
    expect(data[0]).toBe(2.5)
    expect(data[1]).toMatchObject({ value: 4.5, itemStyle: {} })
    expect(statusFor(2.5, co2)).toBe('NOMINAL')
    expect(statusFor(3.5, co2)).toBe('WATCH')
    expect(statusFor(4.5, co2)).toBe('CRITICAL')
    expect(interpretation(co2, 'mmHg')).toContain('red line: alert')
  })
})

describe('pins', () => {
  it('toggles a point and keeps at most three', () => {
    let pins = togglePin([], pin('a'))
    pins = togglePin(pins, pin('b'))
    pins = togglePin(pins, pin('a'))
    expect(pins.map(p => p.key)).toEqual(['b'])
    for (const key of ['c', 'd', 'e']) pins = togglePin(pins, pin(key))
    expect(pins.map(p => p.key)).toEqual(['c', 'd', 'e'])
    expect(togglePin(pins, null)).toBe(pins)
  })
})

describe('every trend chart carries the five capabilities', () => {
  const charts = {
    mood: moodTrendOption([{ day_label: 'D01', mood: 4, calmness: 1.5 }], mood),
    co2: co2TrendOption([{ recorded_at_utc: '2026-11-15T10:00:00Z', co2_mmhg: 4.5 }], co2),
    ocular: ocularTrendOption([{ label: 'Day 10', left: 5.2, right: 6.0, kind: 'EXAM' }],
      { band: [4.6, 5.5], watch: [5.5], critical: [5.8], alertWhen: 'above' }, null),
    sleep: sleepHistoryOption([{ day_label: 'D01', deep_min: 60, rem_min: 60, light_min: 180, awake_min: 20 }],
      { band: [7, 9], watch: [7], critical: [6], alertWhen: 'below' }),
  }
  for (const [name, option] of Object.entries(charts)) {
    it(name, () => {
      expect(option.dataZoom).toHaveLength(2)
      const series = option.series as { markPoint?: { data: unknown[] }, markLine?: { data: unknown[] }, markArea?: unknown, data: unknown[] }[]
      const withLines = series.find(s => s.markLine)!
      expect(withLines.markLine!.data.length).toBeGreaterThanOrEqual(2)
      expect(withLines.markArea).toBeTruthy()
      expect(series.some(s => (s.markPoint?.data ?? []).length >= 2)).toBe(true)
      expect(series.some(s => s.data.some(d => typeof d === 'object' && d !== null && 'itemStyle' in d))).toBe(true)
    })
  }
})

describe('results screens use the interactive frame', () => {
  it('wraps every chart in the frame with clickable points', () => {
    for (const page of ['pages/profile/psychological.vue', 'pages/profile/physical.vue', 'pages/sleep.vue',
      'pages/vision.vue', 'pages/auscultation.vue']) {
      const source = readFileSync(join(APP, page), 'utf-8')
      expect(source, page).toContain('<UiInteractiveChartFrame')
      expect(source, page).toMatch(/@point="/)
    }
  })

  it('registers zoom, mark point and legend in the chart plugin', () => {
    const plugin = readFileSync(join(APP, 'plugins/echarts.client.ts'), 'utf-8')
    for (const name of ['DataZoomInsideComponent', 'DataZoomSliderComponent', 'MarkPointComponent', 'LegendComponent']) {
      expect(plugin, name).toContain(name)
    }
  })
})
