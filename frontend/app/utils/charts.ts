// ECharts options for every chart in the cockpit. Colors are read from the CSS
// tokens at render time (never written here), so charts follow the palette and
// the cabin alert mode exactly like the rest of the interface.
import type { EChartsOption } from 'echarts'
import type { PinMark, Thresholds } from './chartDecor'
import {
  GRID_BOTTOM_WITH_ZOOM,
  alertColoured,
  dataZoomFor,
  markPointsFor,
  thresholdMarks,
} from './chartDecor'

export function token(name: string): string {
  if (typeof document === 'undefined') return ''
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim()
}

export function palette() {
  return {
    ok: token('--color-status-ok'),
    crit: token('--color-status-critical'),
    navy: token('--color-navy-accent'),
    navyEdge: token('--color-navy-edge'),
    rem: token('--color-rem-accent'),
    text: token('--color-text-primary'),
    ice: token('--color-text-secondary'),
    muted: token('--color-text-muted'),
    card: token('--color-surface-card'),
    track: token('--color-track'),
    guide: token('--color-guide-line'),
    band: token('--color-band-fill'),
    okSoft: token('--color-ok-soft'),
    okGlow: token('--color-ok-glow'),
    envelope: token('--color-envelope-fill'),
    inset: token('--color-inset-solid'),
    edge: token('--color-border-hi'),
  }
}

const MONO = '\'JetBrains Mono\', monospace'

// -- Medical-monitor motion -------------------------------------------------------------
/** False when the crew member asked the system for reduced motion. */
export function motionAllowed(): boolean {
  if (typeof window === 'undefined' || !window.matchMedia) return true
  return !window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

/** Entrance animation for trend charts: lines draw left to right, bars grow from the axis. */
export function trendMotion() {
  const on = motionAllowed()
  return {
    animation: on,
    animationDuration: 1100,
    animationEasing: 'cubicOut' as const,
    animationDurationUpdate: 350,
    animationEasingUpdate: 'cubicOut' as const,
  }
}

/** Glowing "head" of a trace with a pulsing ring, like the bright point of a bedside monitor. */
export function headDot(point: [number, number] | null, color: string) {
  const on = motionAllowed()
  return {
    type: on ? 'effectScatter' as const : 'scatter' as const,
    data: point ? [point] : [],
    symbolSize: 7,
    showEffectOn: 'render' as const,
    rippleEffect: { scale: 3.2, brushType: 'stroke' as const, period: 1.4, number: on ? 2 : 0 },
    itemStyle: { color, shadowBlur: 14, shadowColor: color },
    silent: true,
    animation: false,
    z: 6,
    tooltip: { show: false },
  }
}

/** Horizontal fade: faint where the trace is oldest (left), full colour at the newest point. */
function fadeToward(colorFaint: string, color: string) {
  return { type: 'linear' as const, x: 0, y: 0, x2: 1, y2: 0,
    colorStops: [{ offset: 0, color: colorFaint }, { offset: 0.55, color }, { offset: 1, color }] }
}

export type GaugeTone = 'ok' | 'watch' | 'critical' | 'neutral'

/** 270-degree arc used for every score, streak and environment dial. */
export function arcGaugeOption(fraction: number, tone: GaugeTone = 'ok'): EChartsOption {
  const c = palette()
  const color = tone === 'critical' ? c.crit : tone === 'watch' ? c.navyEdge : tone === 'neutral' ? c.muted : c.ok
  const share = Math.min(1, Math.max(0, fraction))
  return {
    backgroundColor: 'transparent',
    animation: false,
    series: [{
      type: 'gauge',
      startAngle: 225,
      endAngle: -45,
      min: 0,
      max: 1,
      radius: '96%',
      center: ['50%', '54%'],
      progress: { show: true, width: 4, roundCap: true, itemStyle: { color } },
      axisLine: { roundCap: true, lineStyle: { width: 4, color: [[1, c.track]] } },
      pointer: { show: false },
      axisTick: { show: false },
      splitLine: { show: false },
      axisLabel: { show: false },
      detail: { show: false },
      title: { show: false },
      data: [{ value: share }],
    }],
  }
}

function baseGrid(left = 46, right = 18, top = 16, bottom = 30) {
  return { left, right, top, bottom, containLabel: false }
}

function axisStyle() {
  const c = palette()
  return {
    axisLine: { show: false },
    axisTick: { show: false },
    axisLabel: { color: c.muted, fontSize: 9.5, fontFamily: MONO },
    splitLine: { show: true, lineStyle: { color: c.guide, width: 1 } },
  }
}

export interface TrendPoint { label: string, values: (number | null)[] }

/** Mood and calmness lines over the optimal wellbeing zone (screen 05), interactive. */
export function moodTrendOption(points: { day_label: string, mood: number, calmness: number }[],
  thresholds: Thresholds, pins: Record<string, PinMark[]> = {}): EChartsOption {
  const c = palette()
  const decor = thresholdMarks(thresholds, '/ 5', 1)
  return {
    backgroundColor: 'transparent',
    ...trendMotion(),
    grid: baseGrid(40, 20, 46, GRID_BOTTOM_WITH_ZOOM),
    dataZoom: dataZoomFor(),
    tooltip: { trigger: 'axis', valueFormatter: value => `${Number(value).toFixed(1)} / 5` },
    xAxis: { type: 'category', data: points.map(p => p.day_label), boundaryGap: false, ...axisStyle() },
    yAxis: { type: 'value', min: 1, max: 5, interval: 1, ...axisStyle(),
      axisLabel: { color: c.muted, fontSize: 9.5, fontFamily: MONO, formatter: (v: number) => v.toFixed(1) } },
    series: [
      {
        name: 'Mood',
        type: 'line',
        data: alertColoured(points.map(p => p.mood), thresholds),
        symbol: 'circle',
        symbolSize: 6,
        lineStyle: { color: c.ok, width: 2.4, shadowBlur: 6, shadowColor: c.okGlow },
        itemStyle: { color: c.ok },
        markArea: decor.markArea,
        markLine: decor.markLine,
        markPoint: markPointsFor('', 1, pins.Mood),
      },
      {
        name: 'Calmness',
        type: 'line',
        data: alertColoured(points.map(p => p.calmness), thresholds),
        symbol: 'circle',
        symbolSize: 4,
        lineStyle: { color: c.rem, width: 1.8 },
        itemStyle: { color: c.rem },
        markPoint: markPointsFor('', 1, pins.Calmness, false),
      },
    ],
  }
}

/** Stored Lead II strip (screen 06): zoom, max / min in mV and pinned samples. */
export function ecgOption(samples: number[], sampleRateHz: number, pins: PinMark[] = []): EChartsOption {
  const c = palette()
  return {
    backgroundColor: 'transparent',
    animation: false,
    grid: { left: 34, right: 34, top: 34, bottom: GRID_BOTTOM_WITH_ZOOM - 14 },
    dataZoom: dataZoomFor('none'),
    tooltip: { trigger: 'axis', valueFormatter: value => `${Number(value).toFixed(2)} mV` },
    xAxis: { type: 'value', min: 0, max: samples.length / sampleRateHz, show: false },
    yAxis: { type: 'value', min: -0.8, max: 1.6, interval: 0.6, axisLabel: { show: false },
      axisLine: { show: false }, axisTick: { show: false },
      splitLine: { show: true, lineStyle: { color: c.guide, width: 1 } } },
    series: [{
      name: 'ECG',
      type: 'line',
      data: samples.map((value, index) => [index / sampleRateHz, value]),
      showSymbol: false,
      sampling: 'lttb',
      lineStyle: { color: c.ok, width: 2 },
      areaStyle: { color: c.okSoft, origin: -0.8 },
      markPoint: markPointsFor('mV', 2, pins),
    }],
  }
}

/**
 * Live ECG: a fixed 6-second window that slides as new samples arrive (newest on the right),
 * drawn without animation so four updates a second stay smooth. Wheel zoom stays where the
 * crew member left it; max / min marks follow the visible beats.
 */
export function ecgLiveOption(samples: number[], sampleRateHz: number, windowSeconds = 6,
  totalSamples?: number): EChartsOption {
  if (totalSamples !== undefined) return ecgSweepOption(samples, sampleRateHz, windowSeconds, totalSamples)
  const c = palette()
  const offset = windowSeconds - samples.length / sampleRateHz
  return {
    backgroundColor: 'transparent',
    animation: false,
    grid: { left: 34, right: 34, top: 34, bottom: GRID_BOTTOM_WITH_ZOOM - 14 },
    dataZoom: dataZoomFor('none'),
    tooltip: { trigger: 'axis', valueFormatter: value => `${Number(value).toFixed(2)} mV` },
    xAxis: { type: 'value', min: 0, max: windowSeconds, show: false },
    yAxis: { type: 'value', min: -0.8, max: 1.6, interval: 0.6, axisLabel: { show: false },
      axisLine: { show: false }, axisTick: { show: false },
      splitLine: { show: true, lineStyle: { color: c.guide, width: 1 } } },
    series: [{
      name: 'ECG',
      type: 'line',
      data: samples.map((value, index) => [offset + index / sampleRateHz, value]),
      showSymbol: false,
      sampling: 'lttb',
      silent: false,
      lineStyle: { color: c.ok, width: 2 },
      areaStyle: { color: c.okSoft, origin: -0.8 },
      markPoint: markPointsFor('mV', 2),
    }],
  }
}

/** Gap (seconds) the sweep erases ahead of the newest sample, as on a bedside monitor. */
export const SWEEP_GAP_S = 0.25

/**
 * Bedside-monitor sweep: each sample has a fixed place in the window (its index modulo the
 * window), the trace is redrawn left to right over the previous pass, and a short gap ahead
 * of the newest sample erases the old one. Returns the current pass, the fading previous
 * pass and the head point.
 */
export function sweepSegments(samples: number[], rate: number, windowSeconds: number, total: number) {
  const width = Math.round(rate * windowSeconds)
  const gap = Math.round(rate * SWEEP_GAP_S)
  const head = total % width
  const firstIndex = total - samples.length
  const current: [number, number][] = []
  const previous: [number, number][] = []
  samples.forEach((value, i) => {
    const absolute = firstIndex + i
    const slot = absolute % width
    const point: [number, number] = [slot / rate, value]
    if (absolute >= total - head) current.push(point)
    else if (slot >= head + gap) previous.push(point)
  })
  return { current, previous, head: current.at(-1) ?? null }
}

function ecgSweepOption(samples: number[], rate: number, windowSeconds: number, total: number): EChartsOption {
  const c = palette()
  const { current, previous, head } = sweepSegments(samples, rate, windowSeconds, total)
  return {
    backgroundColor: 'transparent',
    animation: false,
    grid: { left: 34, right: 34, top: 34, bottom: GRID_BOTTOM_WITH_ZOOM - 14 },
    dataZoom: dataZoomFor('none'),
    tooltip: { trigger: 'axis', valueFormatter: value => `${Number(value).toFixed(2)} mV` },
    xAxis: { type: 'value', min: 0, max: windowSeconds, show: false },
    yAxis: { type: 'value', min: -0.8, max: 1.6, interval: 0.6, axisLabel: { show: false },
      axisLine: { show: false }, axisTick: { show: false },
      splitLine: { show: true, lineStyle: { color: c.guide, width: 1 } } },
    series: [
      {
        name: 'ECG previous pass',
        type: 'line',
        data: previous,
        showSymbol: false,
        silent: true,
        lineStyle: { color: c.ok, width: 1.6, opacity: 0.28 },
        tooltip: { show: false },
      },
      {
        name: 'ECG',
        type: 'line',
        data: current,
        showSymbol: false,
        lineStyle: { color: fadeToward(c.okSoft, c.ok), width: 2.2, shadowBlur: 8, shadowColor: c.okGlow },
        areaStyle: { color: c.okSoft, origin: -0.8, opacity: 0.6 },
        markPoint: markPointsFor('mV', 2),
      },
      headDot(head, c.ok),
    ],
  }
}

/** Sound envelope of a recording: heart bursts (green) or breathing (cream fill), interactive. */
export function envelopeOption(envelope: number[], kind: 'cardiac' | 'pulmonary', pins: PinMark[] = [],
  pointsPerSecond = 20, cursorSeconds: number | null = null): EChartsOption {
  const c = palette()
  const cardiac = kind === 'cardiac'
  // Heart sounds are drawn as a mirrored trace around the centre line, like a phonocardiogram.
  const data: [number, number][] = cardiac
    ? envelope.map((value, index) => [index / pointsPerSecond, index % 2 === 0 ? value : -value * 0.8])
    : envelope.map((value, index) => [index / pointsPerSecond, value])
  const color = cardiac ? c.ok : c.text
  const listening = cursorSeconds !== null
  // While listening, the part already heard lights up, the rest stays faint and a pulsing
  // point rides the trace at the current position (the monitor sweep of the recording).
  const heard = listening ? data.filter(([t]) => t <= cursorSeconds) : []
  const at = listening && heard.length ? heard[heard.length - 1]! : null
  return {
    backgroundColor: 'transparent',
    animation: false,
    grid: { left: 34, right: 34, top: 22, bottom: GRID_BOTTOM_WITH_ZOOM - 18 },
    dataZoom: dataZoomFor('none'),
    tooltip: { trigger: 'axis', valueFormatter: value => Number(value).toFixed(2),
      axisPointer: { type: 'line' } },
    xAxis: { type: 'value', min: 0, max: Math.max(1, envelope.length - 1) / pointsPerSecond, show: false },
    yAxis: { type: 'value', min: cardiac ? -1.1 : 0, max: 1.1, interval: cardiac ? 0.55 : 0.37,
      axisLabel: { show: false }, axisLine: { show: false }, axisTick: { show: false },
      splitLine: { show: true, lineStyle: { color: c.guide, width: 1 } } },
    series: [
      {
        name: cardiac ? 'Heart sound' : 'Breath sound',
        type: 'line',
        data,
        showSymbol: false,
        sampling: 'lttb',
        smooth: !cardiac,
        lineStyle: { color, width: cardiac ? 1.8 : 2, opacity: listening ? 0.3 : 1 },
        areaStyle: cardiac ? undefined : { color: c.envelope, opacity: listening ? 0.35 : 1 },
        markPoint: markPointsFor('', 2, pins),
      },
      ...(listening
        ? [
            {
              type: 'line' as const,
              data: heard,
              showSymbol: false,
              silent: true,
              smooth: !cardiac,
              lineStyle: { color, width: cardiac ? 2.2 : 2.4, shadowBlur: 10, shadowColor: cardiac ? c.okGlow : c.edge },
              areaStyle: cardiac ? undefined : { color: c.envelope },
              tooltip: { show: false },
              markPoint: at
                ? {
                    silent: true, animation: false, symbol: 'roundRect', symbolSize: [44, 16],
                    symbolOffset: [0, -16], itemStyle: { color: c.inset, borderColor: c.edge, borderWidth: 0.6 },
                    label: { color: c.text, fontSize: 9, fontFamily: MONO, formatter: `${cursorSeconds.toFixed(1)} s` },
                    data: [{ coord: at }],
                  }
                : undefined,
            },
            headDot(at, color),
          ]
        : []),
    ],
  }
}

/**
 * Sound trace while recording: a fixed window that fills from the right, fading toward
 * the oldest sound, with a pulsing head on the newest point.
 */
export function captureTraceOption(envelope: number[], kind: 'cardiac' | 'pulmonary', capacity: number): EChartsOption {
  const c = palette()
  const cardiac = kind === 'cardiac'
  const color = cardiac ? c.ok : c.text
  const start = capacity - envelope.length
  const data: [number, number][] = envelope.map((value, i) => [start + i,
    cardiac ? (i % 2 === 0 ? value : -value * 0.8) : value])
  return {
    backgroundColor: 'transparent',
    animation: false,
    grid: { left: 10, right: 16, top: 12, bottom: 10 },
    xAxis: { type: 'value', min: 0, max: capacity - 1, show: false },
    yAxis: { type: 'value', min: cardiac ? -1.1 : 0, max: 1.1, show: false,
      splitLine: { show: true, lineStyle: { color: c.guide, width: 1 } } },
    series: [
      {
        type: 'line',
        data,
        showSymbol: false,
        silent: true,
        smooth: !cardiac,
        lineStyle: { color: fadeToward(cardiac ? c.okSoft : c.envelope, color), width: 2,
          shadowBlur: 8, shadowColor: cardiac ? c.okGlow : c.edge },
        areaStyle: cardiac ? undefined : { color: c.envelope },
      },
      headDot(data.at(-1) ?? null, color),
    ],
  }
}

/** Cabin CO2 with target band, watch (target) and alert lines (screen 09), interactive. */
export function co2TrendOption(points: { recorded_at_utc: string, co2_mmhg: number }[],
  thresholds: Thresholds, pins: PinMark[] = [], hourly = false): EChartsOption {
  const c = palette()
  const values = points.map(p => p.co2_mmhg)
  const alert = thresholds.critical?.[0] ?? 4
  const low = Math.floor(Math.min(2, ...values) - 0.2)
  const high = Math.max(alert + 0.5, Math.ceil(Math.max(...values, 0) + 0.3))
  const decor = thresholdMarks(thresholds, 'mmHg', 1)
  return {
    backgroundColor: 'transparent',
    ...trendMotion(),
    grid: baseGrid(40, 22, 14, GRID_BOTTOM_WITH_ZOOM),
    dataZoom: dataZoomFor(),
    tooltip: { trigger: 'axis', valueFormatter: value => `${Number(value).toFixed(2)} mmHg` },
    xAxis: { type: 'time', ...axisStyle(), splitLine: { show: false },
      axisLabel: { color: c.muted, fontSize: 9.5, fontFamily: MONO,
        formatter: (value: number) => {
          const d = new Date(value)
          return hourly ? `${d.toISOString().slice(5, 10)}` : `${String(d.getUTCHours()).padStart(2, '0')}:00`
        } } },
    yAxis: { type: 'value', min: low, max: high, interval: 1, ...axisStyle(),
      axisLabel: { color: c.muted, fontSize: 9.5, fontFamily: MONO, formatter: (v: number) => v.toFixed(1) } },
    series: [{
      name: 'Cabin CO₂',
      type: 'line',
      data: alertColoured(values, thresholds, (v, i) => [points[i]!.recorded_at_utc, v]),
      symbol: 'circle',
      symbolSize: 5,
      showAllSymbol: false,
      lineStyle: { color: c.ok, width: 2.2, shadowBlur: 6, shadowColor: c.okGlow },
      itemStyle: { color: c.ok },
      markArea: decor.markArea,
      markLine: decor.markLine,
      markPoint: markPointsFor('mmHg', 2, pins),
    },
    headDot(points.length ? [points[points.length - 1]!.recorded_at_utc as unknown as number, values[values.length - 1]!] : null, c.ok)],
  }
}

export interface OcularPoint { label: string, left: number | null, right: number | null, kind: string
  recorded_at_utc?: string | null, mission_stage?: string | null }

/** Bilateral optic nerve sheath trend: personal band, watch and alert lines (screen 08). */
export function ocularTrendOption(points: OcularPoint[], thresholds: Thresholds,
  target: { label: string, value: number } | null, pins: Record<string, PinMark[]> = {},
): EChartsOption {
  const c = palette()
  const labels = points.map(p => p.label)
  const measured = points.flatMap(p => [p.left, p.right]).filter((v): v is number => v !== null)
  const alert = thresholds.critical?.[0] ?? 5.8
  const low = Math.floor((Math.min(...measured, thresholds.band?.[0] ?? 4) - 0.3) * 2) / 2
  const high = Math.ceil((Math.max(...measured, alert) + 0.4) * 2) / 2
  const dashed = (side: 'left' | 'right') => {
    const last = points.at(-1)?.[side]
    if (!target || last === null || last === undefined || last <= target.value) return []
    return [...labels.slice(0, -1).map(() => null), last, target.value]
  }
  const decor = thresholdMarks(thresholds, 'mm', 1)
  const line = (name: string, side: 'left' | 'right', color: string) => ({
    name,
    type: 'line' as const,
    data: alertColoured(points.map(p => p[side]), thresholds),
    connectNulls: true,
    symbol: 'circle',
    symbolSize: 7,
    lineStyle: { color, width: 2.4 },
    itemStyle: { color },
    markPoint: markPointsFor('mm', 2, pins[name]),
  })
  const projection = (side: 'left' | 'right', color: string) => ({
    type: 'line' as const,
    data: dashed(side),
    symbol: 'circle',
    symbolSize: 6,
    silent: true,
    lineStyle: { color, width: 1.8, type: 'dashed' as const },
    itemStyle: { color },
  })
  return {
    backgroundColor: 'transparent',
    ...trendMotion(),
    grid: baseGrid(44, 36, 18, GRID_BOTTOM_WITH_ZOOM),
    dataZoom: dataZoomFor('none'),
    tooltip: { trigger: 'axis', valueFormatter: value => (value == null ? '—' : `${Number(value).toFixed(2)} mm`) },
    xAxis: { type: 'category', data: target ? [...labels, target.label] : labels, boundaryGap: true,
      ...axisStyle(), axisLabel: { color: c.muted, fontSize: 10.5 } },
    yAxis: { type: 'value', min: low, max: high, interval: 0.5, ...axisStyle(),
      axisLabel: { color: c.muted, fontSize: 9.5, fontFamily: MONO, formatter: (v: number) => v.toFixed(1) } },
    series: [
      { ...line('Right Eye', 'right', c.crit), markArea: decor.markArea, markLine: decor.markLine },
      line('Left Eye', 'left', c.ok),
      projection('right', c.crit),
      projection('left', c.ok),
    ],
  }
}

export interface SleepBout { stage: 'DEEP' | 'REM' | 'LIGHT' | 'AWAKE', start_utc: string, end_utc: string
  minutes: number }

const STAGE_ROWS = ['RIBBON', 'DEEP', 'LIGHT', 'REM', 'AWAKE'] as const

/** Sleep stage ribbon: one lane per stage plus the continuous ribbon (screen 07). */
export function sleepRibbonOption(bouts: SleepBout[], pins: PinMark[] = []): EChartsOption {
  const c = palette()
  const colors: Record<string, string> = { AWAKE: c.crit, REM: c.rem, LIGHT: c.navyEdge, DEEP: c.ok }
  const start = new Date(bouts[0]!.start_utc).getTime()
  const end = new Date(bouts.at(-1)!.end_utc).getTime()
  const hour = 3_600_000
  const min = Math.floor(start / hour) * hour
  const max = Math.ceil(end / hour) * hour
  const data = bouts.flatMap((bout) => {
    const from = new Date(bout.start_utc).getTime()
    const to = new Date(bout.end_utc).getTime()
    return [
      { value: [from, to, STAGE_ROWS.indexOf(bout.stage), bout.minutes, 0], itemStyle: { color: colors[bout.stage] } },
      { value: [from, to, 0, bout.minutes, 1], itemStyle: { color: colors[bout.stage] } },
    ]
  })
  return {
    backgroundColor: 'transparent',
    ...trendMotion(),
    grid: { left: 62, right: 24, top: 14, bottom: GRID_BOTTOM_WITH_ZOOM },
    dataZoom: dataZoomFor('weakFilter'),
    tooltip: {
      formatter: (params: unknown) => {
        const item = params as { value: [number, number, number, number, number] }
        const clock = (ms: number) => new Date(ms).toISOString().slice(11, 16)
        return `${STAGE_ROWS[item.value[2]] === 'RIBBON' ? 'Stage' : STAGE_ROWS[item.value[2]]} · `
          + `${clock(item.value[0])}–${clock(item.value[1])} UTC · ${item.value[3]} min`
      },
    },
    xAxis: { type: 'time', min, max, interval: hour, ...axisStyle(),
      axisLabel: { color: c.text, fontSize: 10, fontFamily: MONO,
        formatter: (value: number) => new Date(value).toISOString().slice(11, 16) } },
    yAxis: { type: 'category', data: [...STAGE_ROWS], ...axisStyle(),
      axisLabel: { color: c.ice, fontSize: 9.5, fontFamily: MONO } },
    series: [{
      name: 'Sleep stage',
      type: 'custom',
      encode: { x: [0, 1], y: 2 },
      data,
      markPoint: markPointsFor('min', 0, pins, false),
      renderItem: (_params, api) => {
        const ribbon = api.value(4) === 1
        const from = api.coord([api.value(0), api.value(2)])
        const to = api.coord([api.value(1), api.value(2)])
        const band = (api.size!([0, 1]) as number[])[1]!
        const height = ribbon ? band * 0.34 : band * 0.42
        const width = Math.max(2, to[0]! - from[0]!)
        const minutes = api.value(3) as number
        return {
          type: 'group',
          children: [
            { type: 'rect',
              shape: { x: from[0]!, y: from[1]! - height / 2, width, height, r: ribbon ? 0 : 3 },
              style: api.style() },
            ...(!ribbon && width > 30
              ? [{ type: 'text' as const,
                  style: { text: `${minutes}m`, x: from[0]! + width / 2, y: from[1]!, fill: c.text,
                    font: `600 9.5px ${MONO}`, textAlign: 'center' as const,
                    textVerticalAlign: 'middle' as const } }]
              : []),
          ],
        }
      },
    }],
  }
}

/**
 * Nightly stage totals as stacked bars for the 7 / 14 / 30 day views (screen 07), with the
 * total-sleep line carrying max / min, the 7 h target (watch) and the 6 h alert line.
 */
export function sleepHistoryOption(nights: { day_label: string, deep_min: number, rem_min: number
  light_min: number, awake_min: number }[], thresholds: Thresholds, pins: PinMark[] = []): EChartsOption {
  const c = palette()
  const bar = (name: string, key: 'deep_min' | 'rem_min' | 'light_min' | 'awake_min', color: string) => ({
    name,
    type: 'bar' as const,
    stack: 'night',
    barMaxWidth: 26,
    animationDelay: (index: number) => index * 35,
    itemStyle: { color },
    data: nights.map(n => +(n[key] / 60).toFixed(2)),
  })
  const totals = nights.map(n => +((n.deep_min + n.rem_min + n.light_min) / 60).toFixed(2))
  const decor = thresholdMarks(thresholds, 'h', 1)
  return {
    backgroundColor: 'transparent',
    ...trendMotion(),
    grid: baseGrid(40, 22, 16, GRID_BOTTOM_WITH_ZOOM),
    dataZoom: dataZoomFor(),
    tooltip: { trigger: 'axis', valueFormatter: value => `${Number(value).toFixed(1)} h` },
    xAxis: { type: 'category', data: nights.map(n => n.day_label), ...axisStyle(), splitLine: { show: false } },
    yAxis: { type: 'value', min: 0, max: 10, interval: 2, ...axisStyle(),
      axisLabel: { color: c.muted, fontSize: 9.5, fontFamily: MONO, formatter: '{value}h' } },
    series: [
      bar('Deep', 'deep_min', c.ok),
      bar('REM', 'rem_min', c.rem),
      bar('Light', 'light_min', c.navyEdge),
      bar('Awake', 'awake_min', c.crit),
      {
        name: 'Total sleep',
        type: 'line',
        data: alertColoured(totals, thresholds),
        symbol: 'circle',
        symbolSize: 6,
        lineStyle: { color: c.text, width: 1.6 },
        itemStyle: { color: c.text },
        markArea: decor.markArea,
        markLine: decor.markLine,
        markPoint: markPointsFor('h', 1, pins),
      },
    ],
  }
}
