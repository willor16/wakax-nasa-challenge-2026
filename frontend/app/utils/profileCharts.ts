export type StatusTone = 'nominal' | 'warn' | 'critical'
export type HudTagTone = 'reference' | 'warn' | 'critical'

function readCssToken(name: string, fallback: string): string {
  if (typeof window === 'undefined') return fallback
  const val = getComputedStyle(document.documentElement).getPropertyValue(name).trim()
  return val || fallback
}

export function buildLeadIiEcgOption(
  samplesMv: number[],
  sampleRateHz = 100,
  rhythmTone: HudTagTone = 'reference',
) {
  const okColor = readCssToken('--color-status-ok', '#2AEF4B')
  const critColor = readCssToken('--color-status-critical', '#D5110B')
  const remColor = readCssToken('--color-rem-accent', '#2994A6')
  const mutedColor = readCssToken('--color-text-muted', '#C8B69C')
  const cardColor = readCssToken('--color-surface-card', '#15616D')

  const traceColor = rhythmTone === 'critical'
    ? critColor
    : rhythmTone === 'warn'
      ? remColor
      : okColor

  const safeRate = Math.max(10, sampleRateHz)
  const xLabels = samplesMv.map((_, idx) => `${(idx / safeRate).toFixed(2)}s`)

  return {
    backgroundColor: 'transparent',
    animation: false,
    grid: {
      top: 10,
      right: 12,
      bottom: 20,
      left: 34,
    },
    tooltip: {
      trigger: 'axis',
      confine: true,
      valueFormatter: (value: number) => `${Number(value).toFixed(2)} mV`,
    },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: xLabels,
      axisLine: { lineStyle: { color: cardColor } },
      axisTick: { show: false },
      axisLabel: {
        color: mutedColor,
        fontSize: 9,
        interval: Math.max(1, Math.floor(samplesMv.length / 5) - 1),
      },
      splitLine: {
        show: true,
        lineStyle: {
          color: 'rgba(38, 59, 176, 0.34)',
          width: 1,
        },
      },
    },
    yAxis: {
      type: 'value',
      min: -0.5,
      max: 1.45,
      interval: 0.5,
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: {
        color: mutedColor,
        fontSize: 9,
        formatter: (val: number) => `${val.toFixed(1)}`,
      },
      splitLine: {
        show: true,
        lineStyle: {
          color: 'rgba(38, 59, 176, 0.34)',
          width: 1,
        },
      },
    },
    series: [
      {
        name: 'Lead II',
        type: 'line',
        data: samplesMv,
        showSymbol: false,
        smooth: false,
        sampling: 'lttb',
        animation: false,
        lineStyle: {
          color: traceColor,
          width: 2.1,
        },
        areaStyle: {
          color: rhythmTone === 'critical'
            ? 'rgba(213, 17, 11, 0.10)'
            : 'rgba(42, 239, 75, 0.09)',
        },
      },
    ],
  }
}

export function shiftEcgSweepWindow(
  source: number[],
  cursor: number,
  windowSize = 200,
  step = 4,
): { window: number[], nextCursor: number } {
  if (source.length === 0) {
    return { window: [], nextCursor: 0 }
  }
  const size = Math.min(windowSize, source.length)
  const start = ((cursor % source.length) + source.length) % source.length
  const window: number[] = []
  for (let i = 0; i < size; i += 1) {
    const sample = source[(start + i) % source.length]
    window.push(sample ?? 0)
  }
  const nextCursor = (start + step) % source.length
  return { window, nextCursor }
}

export function computeGaugeArcStroke(percent: number, radius = 38): {
  circumference: number
  arcSpan: number
  dashArray: string
  dashOffset: number
} {
  const clamped = Math.max(0, Math.min(100, percent))
  const circumference = 2 * Math.PI * radius
  const arcSpan = circumference * 0.72
  const filled = (clamped / 100) * arcSpan
  return {
    circumference: Number(circumference.toFixed(2)),
    arcSpan: Number(arcSpan.toFixed(2)),
    dashArray: `${filled.toFixed(2)} ${circumference.toFixed(2)}`,
    dashOffset: 0,
  }
}

export function formatZScoreLabel(zScore: number | null | undefined): string {
  if (zScore === null || zScore === undefined || Number.isNaN(zScore)) {
    return 'z 0.0σ'
  }
  const sign = zScore > 0 ? '+' : ''
  return `z ${sign}${zScore.toFixed(1)}σ`
}
