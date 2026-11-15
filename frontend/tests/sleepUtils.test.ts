import { readFileSync } from 'node:fs'
import { join, resolve } from 'node:path'
import { describe, expect, it } from 'vitest'
import {
  buildSleepScoreGaugeOption,
  buildSleepStageRibbonOption,
  stageColorVar,
} from '../app/utils/sleepCharts'

const FRONTEND_ROOT = resolve(import.meta.dirname, '..')

describe('D2-04 Sleep Monitor Utilities & Read-Only Separation', () => {
  it('builds Sleep Score radial gauge option with animation disabled and clamped score', () => {
    const option = buildSleepScoreGaugeOption(84, 'of 100 · Optimal', 'reference')

    expect(option.animation).toBe(false)
    expect(option.series[0]?.type).toBe('gauge')
    expect(option.series[0]?.animation).toBe(false)
    expect(option.series[0]?.detail.valueAnimation).toBe(false)
    expect(option.series[0]?.data[0]).toEqual({
      value: 84,
      name: 'of 100 · Optimal',
    })
  })

  it('builds ECharts CustomChart sleep stage ribbon option and renders bout + barcode primitives', () => {
    const option = buildSleepStageRibbonOption(
      [
        {
          stage: 'AWAKE',
          lane_index: 4,
          prev_lane_index: null,
          start_offset_min: 0,
          end_offset_min: 8,
          duration_min: 8,
          start_hm: '22:18',
          end_hm: '22:26',
        },
        {
          stage: 'DEEP',
          lane_index: 1,
          prev_lane_index: 4,
          start_offset_min: 8,
          end_offset_min: 50,
          duration_min: 42,
          start_hm: '22:26',
          end_hm: '23:08',
        },
      ],
      480,
      [
        { offset_min: 0, label: '22:18' },
        { offset_min: 60, label: '23:18' },
      ],
    )

    expect(option.animation).toBe(false)
    expect(option.series[0]?.type).toBe('custom')
    expect(option.series[0]?.data).toHaveLength(2)
    expect(option.yAxis.data).toEqual(['RIBBON', 'DEEP', 'LIGHT', 'REM', 'AWAKE'])

    const secondTuple = option.series[0]!.data[1]!
    const rendered = option.series[0]!.renderItem(
      {
        dataIndex: 1,
        coordSys: { x: 56, y: 12, width: 700, height: 200 },
      },
      {
        value: (idx: number) => secondTuple[idx] ?? 0,
        coord: ([x, y]: [number, number]) => [56 + (x / 480) * 700, 200 - y * 36],
        size: ([w, h]: [number, number]) => [(w / 480) * 700, h * 36],
      },
    )

    expect(rendered.type).toBe('group')
    expect(rendered.children.some(c => c.type === 'line')).toBe(true)
    expect(rendered.children.filter(c => c.type === 'rect')).toHaveLength(2)
    expect(rendered.children.some(c => c.type === 'text')).toBe(true)
  })

  it('maps sleep stage keys to CSS variables without raw hex leakage', () => {
    expect(stageColorVar('DEEP')).toBe('var(--color-status-ok)')
    expect(stageColorVar('REM')).toBe('var(--color-rem-accent)')
    expect(stageColorVar('LIGHT')).toBe('var(--color-navy-edge)')
    expect(stageColorVar('AWAKE')).toBe('var(--color-status-critical)')
  })

  it('enforces 100% read-only separation on /sleep screen and filter bar', () => {
    const sleepPage = readFileSync(join(FRONTEND_ROOT, 'app/pages/sleep.vue'), 'utf-8')
    const filterBar = readFileSync(
      join(FRONTEND_ROOT, 'app/components/sleep/SleepTimeFilterBar.vue'),
      'utf-8',
    )

    for (const content of [sleepPage, filterBar]) {
      expect(content).not.toMatch(/<(input|select|textarea|form)\b/i)
      expect(content).not.toMatch(/\+\s*Log\b/i)
    }
  })
})
