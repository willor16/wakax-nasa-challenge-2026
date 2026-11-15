// ECharts options for every chart in the cockpit. Colors are read from the CSS
// tokens at render time (never written here), so charts follow the palette and
// the cabin alert mode exactly like the rest of the interface.
import type { EChartsOption } from 'echarts'

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
    envelope: token('--color-envelope-fill'),
    inset: token('--color-inset-solid'),
    edge: token('--color-border-hi'),
  }
}

const MONO = '\'JetBrains Mono\', monospace'

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

/** 14-day mood and calmness lines over the optimal wellbeing zone (screen 05). */
export function moodTrendOption(points: { day_label: string, mood: number, calmness: number }[],
  zone: [number, number]): EChartsOption {
  const c = palette()
  return {
    backgroundColor: 'transparent',
    animation: false,
    grid: baseGrid(40, 20, 46, 30),
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: points.map(p => p.day_label), boundaryGap: false, ...axisStyle() },
    yAxis: { type: 'value', min: 1, max: 5, interval: 1, ...axisStyle(),
      axisLabel: { color: c.muted, fontSize: 9.5, fontFamily: MONO, formatter: (v: number) => v.toFixed(1) } },
    series: [
      {
        name: 'Mood',
        type: 'line',
        data: points.map(p => p.mood),
        symbol: 'circle',
        symbolSize: 6,
        lineStyle: { color: c.ok, width: 2.4 },
        itemStyle: { color: c.ok },
        markArea: { silent: true, itemStyle: { color: c.band },
          data: [[{ yAxis: zone[0] }, { yAxis: zone[1] }]] },
        markLine: { silent: true, symbol: 'none', label: { show: false },
          lineStyle: { color: c.navyEdge, type: 'solid', width: 1.2 }, data: [{ yAxis: zone[0] }] },
      },
      {
        name: 'Calmness',
        type: 'line',
        data: points.map(p => p.calmness),
        showSymbol: false,
        lineStyle: { color: c.rem, width: 1.8 },
        itemStyle: { color: c.rem },
      },
    ],
  }
}

/** Live Lead II strip (screen 06). */
export function ecgOption(samples: number[], sampleRateHz: number): EChartsOption {
  const c = palette()
  return {
    backgroundColor: 'transparent',
    animation: false,
    grid: { left: 10, right: 10, top: 34, bottom: 12 },
    xAxis: { type: 'value', min: 0, max: samples.length / sampleRateHz, show: false },
    yAxis: { type: 'value', min: -0.8, max: 1.6, interval: 0.6, axisLabel: { show: false },
      axisLine: { show: false }, axisTick: { show: false },
      splitLine: { show: true, lineStyle: { color: c.guide, width: 1 } } },
    series: [{
      type: 'line',
      data: samples.map((value, index) => [index / sampleRateHz, value]),
      showSymbol: false,
      sampling: 'lttb',
      lineStyle: { color: c.ok, width: 2 },
      areaStyle: { color: c.okSoft, origin: -0.8 },
    }],
  }
}

/** Sound envelope of a recording: heart bursts (green) or breathing (cream fill). */
export function envelopeOption(envelope: number[], kind: 'cardiac' | 'pulmonary'): EChartsOption {
  const c = palette()
  const cardiac = kind === 'cardiac'
  // Heart sounds are drawn as a mirrored trace around the centre line, like a phonocardiogram.
  const data = cardiac
    ? envelope.map((value, index) => [index, index % 2 === 0 ? value : -value * 0.8])
    : envelope.map((value, index) => [index, value])
  return {
    backgroundColor: 'transparent',
    animation: false,
    grid: { left: 10, right: 10, top: 12, bottom: 10 },
    xAxis: { type: 'value', min: 0, max: Math.max(1, envelope.length - 1), show: false },
    yAxis: { type: 'value', min: cardiac ? -1.1 : 0, max: 1.1, interval: cardiac ? 0.55 : 0.37,
      axisLabel: { show: false }, axisLine: { show: false }, axisTick: { show: false },
      splitLine: { show: true, lineStyle: { color: c.guide, width: 1 } } },
    series: [{
      type: 'line',
      data,
      showSymbol: false,
      sampling: 'lttb',
      smooth: !cardiac,
      lineStyle: { color: cardiac ? c.ok : c.text, width: cardiac ? 1.8 : 2 },
      areaStyle: cardiac ? undefined : { color: c.envelope },
    }],
  }
}

/** 24-hour cabin CO2 with target zone and alert limit (screen 09). */
export function co2TrendOption(points: { recorded_at_utc: string, co2_mmhg: number }[],
  limits: { target: number, alert: number }): EChartsOption {
  const c = palette()
  const values = points.map(p => p.co2_mmhg)
  const low = Math.floor(Math.min(2, ...values) - 0.2)
  const high = Math.max(limits.alert + 0.5, Math.ceil(Math.max(...values, 0) + 0.3))
  return {
    backgroundColor: 'transparent',
    animation: false,
    grid: baseGrid(40, 22, 14, 28),
    tooltip: { trigger: 'axis', valueFormatter: value => `${Number(value).toFixed(2)} mmHg` },
    xAxis: { type: 'time', ...axisStyle(), splitLine: { show: false },
      axisLabel: { color: c.muted, fontSize: 9.5, fontFamily: MONO,
        formatter: (value: number) => `${String(new Date(value).getUTCHours()).padStart(2, '0')}:00` } },
    yAxis: { type: 'value', min: low, max: high, interval: 1, ...axisStyle(),
      axisLabel: { color: c.muted, fontSize: 9.5, fontFamily: MONO, formatter: (v: number) => v.toFixed(1) } },
    series: [{
      type: 'line',
      data: points.map(p => [p.recorded_at_utc, p.co2_mmhg]),
      symbol: 'circle',
      symbolSize: 5,
      showAllSymbol: false,
      lineStyle: { color: c.ok, width: 2.2 },
      itemStyle: { color: c.ok },
      markArea: { silent: true, itemStyle: { color: c.band }, data: [[{ yAxis: low }, { yAxis: limits.target }]] },
      markLine: { silent: true, symbol: 'none', label: { show: false },
        data: [
          { yAxis: limits.alert, lineStyle: { color: c.crit, type: 'dashed', width: 1.4 } },
          { yAxis: limits.target, lineStyle: { color: c.navyEdge, type: 'solid', width: 1.2 } },
        ] },
    }],
  }
}

export interface OcularPoint { label: string, left: number | null, right: number | null, kind: string }

/** Bilateral optic nerve sheath trend against baseline band and alert threshold (screen 08). */
export function ocularTrendOption(points: OcularPoint[], limits: { alert: number | null
  nominalMax: number | null, baselineLow: number | null }, target: { label: string, value: number } | null,
): EChartsOption {
  const c = palette()
  const labels = points.map(p => p.label)
  const measured = points.flatMap(p => [p.left, p.right]).filter((v): v is number => v !== null)
  const low = Math.floor((Math.min(...measured, limits.baselineLow ?? 4) - 0.3) * 2) / 2
  const high = Math.ceil((Math.max(...measured, limits.alert ?? 5.8) + 0.4) * 2) / 2
  const dashed = (side: 'left' | 'right') => {
    const last = points.at(-1)?.[side]
    if (!target || last === null || last === undefined || last <= target.value) return []
    return [...labels.slice(0, -1).map(() => null), last, target.value]
  }
  const line = (name: string, side: 'left' | 'right', color: string) => ({
    name,
    type: 'line' as const,
    data: points.map(p => p[side]),
    connectNulls: true,
    symbol: 'circle',
    symbolSize: 7,
    lineStyle: { color, width: 2.4 },
    itemStyle: { color },
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
  const marks = []
  if (limits.alert !== null) {
    marks.push({ yAxis: limits.alert, lineStyle: { color: c.crit, type: 'dashed' as const, width: 1.4 } })
  }
  if (limits.nominalMax !== null) {
    marks.push({ yAxis: limits.nominalMax, lineStyle: { color: c.navyEdge, type: 'solid' as const, width: 1.2 } })
  }
  return {
    backgroundColor: 'transparent',
    animation: false,
    grid: baseGrid(44, 36, 18, 34),
    tooltip: { trigger: 'axis', valueFormatter: value => (value == null ? '—' : `${Number(value).toFixed(2)} mm`) },
    xAxis: { type: 'category', data: target ? [...labels, target.label] : labels, boundaryGap: true,
      ...axisStyle(), axisLabel: { color: c.muted, fontSize: 10.5 } },
    yAxis: { type: 'value', min: low, max: high, interval: 0.5, ...axisStyle(),
      axisLabel: { color: c.muted, fontSize: 9.5, fontFamily: MONO, formatter: (v: number) => v.toFixed(1) } },
    series: [
      {
        ...line('Right Eye', 'right', c.crit),
        markArea: limits.nominalMax !== null && limits.baselineLow !== null
          ? { silent: true, itemStyle: { color: c.band },
              data: [[{ yAxis: limits.baselineLow }, { yAxis: limits.nominalMax }]] }
          : undefined,
        markLine: { silent: true, symbol: 'none', label: { show: false }, data: marks },
      },
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
export function sleepRibbonOption(bouts: SleepBout[]): EChartsOption {
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
    animation: false,
    grid: { left: 62, right: 24, top: 14, bottom: 30 },
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
      type: 'custom',
      encode: { x: [0, 1], y: 2 },
      data,
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

/** Nightly stage totals as stacked bars for the 7 / 14 / 30 day views (screen 07). */
export function sleepHistoryOption(nights: { day_label: string, deep_min: number, rem_min: number
  light_min: number, awake_min: number }[], targetMin: number): EChartsOption {
  const c = palette()
  const bar = (name: string, key: 'deep_min' | 'rem_min' | 'light_min' | 'awake_min', color: string) => ({
    name,
    type: 'bar' as const,
    stack: 'night',
    barMaxWidth: 26,
    itemStyle: { color },
    data: nights.map(n => +(n[key] / 60).toFixed(2)),
  })
  return {
    backgroundColor: 'transparent',
    animation: false,
    grid: baseGrid(40, 22, 16, 30),
    tooltip: { trigger: 'axis', valueFormatter: value => `${Number(value).toFixed(1)} h` },
    xAxis: { type: 'category', data: nights.map(n => n.day_label), ...axisStyle(), splitLine: { show: false } },
    yAxis: { type: 'value', min: 0, max: 10, interval: 2, ...axisStyle(),
      axisLabel: { color: c.muted, fontSize: 9.5, fontFamily: MONO, formatter: '{value}h' } },
    series: [
      { ...bar('Deep', 'deep_min', c.ok),
        markLine: { silent: true, symbol: 'none', label: { show: false },
          lineStyle: { color: c.text, type: 'dashed', width: 1 }, data: [{ yAxis: targetMin / 60 }] } },
      bar('REM', 'rem_min', c.rem),
      bar('Light', 'light_min', c.navyEdge),
      bar('Awake', 'awake_min', c.crit),
    ],
  }
}
