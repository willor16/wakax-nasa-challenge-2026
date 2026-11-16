// Shared clinical decorations for every interactive chart (M4 standard):
//   1. zoom and pan  - dataZoom "inside" (wheel / pinch) plus a 16px slider;
//   2. extremes      - automatic max / min marks with the clinical unit (visible window);
//   3. pins          - points the crew member clicked, drawn as marks for comparison;
//   4. thresholds    - translucent nominal band, dashed watch line, red alert line;
//   5. alert points  - any point beyond the alert threshold is drawn in red.
// Colours always come from the palette tokens (``palette()`` in charts.ts), never literals.
import { palette } from './charts'

export interface Thresholds {
  /** Translucent nominal band [low, high]. */
  band?: [number, number] | null
  /** Dashed watch / precaution lines. */
  watch?: number[]
  /** Red alert / critical lines. */
  critical?: number[]
  /** Which side of the critical line is out of range. */
  alertWhen?: 'above' | 'below'
}

export interface PinMark { coord: [number | string, number], label: string }

const MONO = '\'JetBrains Mono\', monospace'
export const SLIDER_HEIGHT = 16
/** Grid bottom that leaves room for the axis labels and the zoom slider. */
export const GRID_BOTTOM_WITH_ZOOM = 52

function trim(value: number, digits: number): string {
  return Number(value.toFixed(digits)).toString()
}

/** Wheel / pinch zoom plus a compact slider under the plot. */
export function dataZoomFor(filterMode: 'filter' | 'weakFilter' | 'none' = 'filter') {
  const c = palette()
  return [
    { type: 'inside' as const, xAxisIndex: 0, filterMode, zoomOnMouseWheel: true, moveOnMouseMove: true },
    {
      type: 'slider' as const,
      xAxisIndex: 0,
      filterMode,
      height: SLIDER_HEIGHT,
      bottom: 6,
      borderColor: c.edge,
      backgroundColor: c.inset,
      fillerColor: c.band,
      dataBackground: { lineStyle: { color: c.muted, opacity: 0.4 }, areaStyle: { color: c.track } },
      selectedDataBackground: { lineStyle: { color: c.ok, opacity: 0.6 }, areaStyle: { color: c.okSoft } },
      handleStyle: { color: c.text, borderColor: c.edge },
      moveHandleStyle: { color: c.edge },
      textStyle: { color: c.muted, fontSize: 9, fontFamily: MONO },
      showDetail: false,
      brushSelect: false,
    },
  ]
}

/** Max / min marks of the visible window with the clinical unit, plus the user's pins. */
export function markPointsFor(unit: string, digits: number, pins: PinMark[] = [], extremes = true) {
  const c = palette()
  const suffix = unit ? ` ${unit}` : ''
  const extreme = (type: 'max' | 'min', name: string) => ({
    type,
    name,
    // A small triangle on the point, with a one-line label outside it (above the maximum,
    // below the minimum) so the value stays readable over any trace.
    symbol: 'triangle',
    symbolSize: 9,
    symbolRotate: type === 'max' ? 180 : 0,
    symbolOffset: [0, type === 'max' ? -7 : 7],
    itemStyle: { color: type === 'max' ? c.text : c.ice, borderColor: c.inset, borderWidth: 0.6 },
    label: {
      position: type === 'max' ? 'top' as const : 'bottom' as const,
      distance: 3,
      color: c.text,
      backgroundColor: c.inset,
      borderColor: c.edge,
      borderWidth: 0.6,
      borderRadius: 2,
      padding: [2, 4],
      fontSize: 9,
      fontFamily: MONO,
      formatter: (p: { value?: number | string }) => `${type === 'max' ? 'MAX' : 'MIN'} ${trim(Number(p.value), digits)}${suffix}`,
    },
  })
  return {
    silent: false,
    animation: false,
    data: [
      ...(extremes ? [extreme('max', 'Max'), extreme('min', 'Min')] : []),
      ...pins.map(pin => ({
        name: 'Pin',
        coord: pin.coord,
        value: pin.label,
        symbol: 'diamond',
        symbolSize: 13,
        itemStyle: { color: c.text, borderColor: c.ok, borderWidth: 1.5 },
        label: { show: true, position: 'top' as const, color: c.text, fontSize: 9, fontFamily: MONO, formatter: pin.label },
      })),
    ],
  }
}

/** Nominal band (markArea) and watch / alert lines (markLine) for one series. */
export function thresholdMarks(thresholds: Thresholds, unit = '', digits = 1) {
  const c = palette()
  const suffix = unit ? ` ${unit}` : ''
  const line = (value: number, kind: 'watch' | 'critical') => ({
    yAxis: value,
    lineStyle: kind === 'critical'
      ? { color: c.crit, type: 'solid' as const, width: 1.5 }
      : { color: c.navyEdge, type: 'dashed' as const, width: 1.3 },
    label: {
      show: true,
      position: 'insideEndTop' as const,
      color: kind === 'critical' ? c.crit : c.ice,
      fontSize: 9,
      fontFamily: MONO,
      formatter: `${kind === 'critical' ? 'ALERT' : 'WATCH'} ${trim(value, digits)}${suffix}`,
    },
  })
  return {
    markArea: thresholds.band
      ? { silent: true, itemStyle: { color: c.band }, data: [[{ yAxis: thresholds.band[0] }, { yAxis: thresholds.band[1] }]] }
      : undefined,
    markLine: {
      silent: true,
      symbol: 'none',
      animation: false,
      data: [
        ...(thresholds.watch ?? []).map(v => line(v, 'watch')),
        ...(thresholds.critical ?? []).map(v => line(v, 'critical')),
      ],
    },
  }
}

/** True when a value is beyond the alert line (on the configured side). */
export function isAlert(value: number | null | undefined, thresholds: Thresholds): boolean {
  if (value == null || !thresholds.critical?.length) return false
  return thresholds.alertWhen === 'below'
    ? thresholds.critical.some(limit => value < limit)
    : thresholds.critical.some(limit => value > limit)
}

/** Clinical status of a value against the band and lines. */
export function statusFor(value: number | null | undefined, thresholds: Thresholds): 'NOMINAL' | 'WATCH' | 'CRITICAL' | 'NO_DATA' {
  if (value == null) return 'NO_DATA'
  if (isAlert(value, thresholds)) return 'CRITICAL'
  const band = thresholds.band
  const outsideBand = band ? value < band[0] || value > band[1] : false
  const pastWatch = (thresholds.watch ?? []).some(limit => (thresholds.alertWhen === 'below' ? value < limit : value > limit))
  return outsideBand || pastWatch ? 'WATCH' : 'NOMINAL'
}

/** Series data where points beyond the alert line are drawn in red. */
export function alertColoured<T extends number | null>(values: T[], thresholds: Thresholds, toPoint: (value: T, index: number) => unknown = v => v) {
  const c = palette()
  return values.map((value, index) => (isAlert(value, thresholds)
    ? { value: toPoint(value, index), itemStyle: { color: c.crit, borderColor: c.crit }, symbolSize: 9 }
    : toPoint(value, index)))
}

/** One-line reading of the band and lines, shown under every chart. */
export function interpretation(thresholds: Thresholds, unit: string): string {
  const parts = []
  if (thresholds.band) parts.push(`Inside the shaded band (${thresholds.band[0]}–${thresholds.band[1]} ${unit}): nominal`)
  if (thresholds.watch?.length) parts.push('past the dashed line: watch')
  if (thresholds.critical?.length) parts.push(`${thresholds.alertWhen === 'below' ? 'below' : 'past'} the red line: alert (red points)`)
  return parts.join(' · ')
}
