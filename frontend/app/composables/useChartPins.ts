// Points the crew member pins on a chart by clicking them (up to three), to compare their
// exact value, UTC time, mission stage, difference from the reference and clinical status.
// Clicking a pinned point again removes it. Each screen describes its own points.
import type { PinMark } from '~/utils/chartDecor'

export interface ChartPin {
  key: string
  series: string
  value: number
  unit: string
  digits: number
  time_utc: string | null
  stage: string | null
  delta: number | null
  reference_label: string | null
  status: 'NOMINAL' | 'WATCH' | 'CRITICAL' | 'NO_DATA'
  coord: [number | string, number]
}

/** What ECharts passes to a click handler (the fields the screens use). */
export interface ChartClick {
  componentType?: string
  seriesName?: string
  seriesIndex?: number
  dataIndex: number
  value?: unknown
  data?: unknown
  name?: string
}

export const MAX_PINS = 3

/** Pure toggle used by the composable (kept separate so it can be tested). */
export function togglePin(pins: ChartPin[], pin: ChartPin | null, max = MAX_PINS): ChartPin[] {
  if (!pin) return pins
  if (pins.some(p => p.key === pin.key)) return pins.filter(p => p.key !== pin.key)
  return [...pins, pin].slice(-max)
}

export function pinLabel(pin: ChartPin): string {
  return `${Number(pin.value.toFixed(pin.digits))}`
}

export function useChartPins(describe: (click: ChartClick) => ChartPin | null) {
  const pins = ref<ChartPin[]>([])

  function onClick(click: ChartClick) {
    if (click.componentType && click.componentType !== 'series') return
    pins.value = togglePin(pins.value, describe(click))
  }
  function remove(key: string) {
    pins.value = pins.value.filter(p => p.key !== key)
  }
  function clear() {
    pins.value = []
  }
  /** Pins of one series, as chart marks. */
  function marks(series?: string): PinMark[] {
    return pins.value.filter(p => !series || p.series === series).map(p => ({ coord: p.coord, label: pinLabel(p) }))
  }

  return { pins, onClick, remove, clear, marks }
}
