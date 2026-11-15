export type VisionHudTone = 'reference' | 'warn' | 'critical'
export type VisionMetricTone = 'nominal' | 'warn' | 'critical'

export interface VisionEyeArcInput {
  side: 'LEFT' | 'RIGHT'
  label: string
  sheath_mm: number
  display_value: string
  status_label: string
  tone: VisionHudTone
}

export interface VisionTrendPointInput {
  label: string
  left_mm: number
  right_mm: number
  is_projected?: boolean
}

export interface OnsdTrendChartInput {
  points: VisionTrendPointInput[]
  baselineBandMinMm: number
  baselineBandMaxMm: number
  alertThresholdMm: number
  rightEyeTone: VisionHudTone
  leftEyeTone: VisionHudTone
}

function readCssToken(name: string, fallback: string): string {
  if (typeof window === 'undefined') return fallback
  const val = getComputedStyle(document.documentElement).getPropertyValue(name).trim()
  return val || fallback
}

export function visionToneColorVar(tone: VisionHudTone): string {
  if (tone === 'critical') return 'var(--color-status-critical)'
  if (tone === 'warn') return 'var(--color-rem-accent)'
  return 'var(--color-status-ok)'
}

export function visionMetricColorVar(tone: VisionMetricTone): string {
  if (tone === 'critical') return 'var(--color-status-critical)'
  if (tone === 'warn') return 'var(--color-rem-accent)'
  return 'var(--color-status-ok)'
}

export function eyeSeriesColorVar(side: 'LEFT' | 'RIGHT', tone: VisionHudTone): string {
  if (tone === 'critical') return 'var(--color-status-critical)'
  if (tone === 'warn') return 'var(--color-rem-accent)'
  return side === 'LEFT' ? 'var(--color-status-ok)' : 'var(--color-border-hi)'
}

function resolveToneCanvasColor(side: 'LEFT' | 'RIGHT', tone: VisionHudTone): string {
  if (tone === 'critical') return readCssToken('--color-status-critical', '#D5110B')
  if (tone === 'warn') return readCssToken('--color-rem-accent', '#2994A6')
  if (side === 'RIGHT') return readCssToken('--color-border-hi', '#25899B')
  return readCssToken('--color-status-ok', '#2AEF4B')
}

export function buildOcularSheathGaugeOption(eye: VisionEyeArcInput) {
  const clampedVal = Math.max(3.6, Math.min(6.6, eye.sheath_mm))
  const textColor = readCssToken('--color-text-primary', '#FFECD1')
  const mutedColor = readCssToken('--color-text-muted', '#C8B69C')
  const arcColor = eye.tone === 'critical'
    ? readCssToken('--color-status-critical', '#D5110B')
    : eye.tone === 'warn'
      ? readCssToken('--color-rem-accent', '#2994A6')
      : readCssToken('--color-status-ok', '#2AEF4B')

  return {
    backgroundColor: 'transparent',
    animation: false,
    series: [
      {
        name: eye.label,
        type: 'gauge',
        startAngle: 215,
        endAngle: -35,
        min: 3.6,
        max: 6.6,
        radius: '94%',
        center: ['50%', '57%'],
        animation: false,
        progress: {
          show: true,
          width: 7.5,
          roundCap: true,
          itemStyle: {
            color: arcColor,
          },
        },
        axisLine: {
          roundCap: true,
          lineStyle: {
            width: 7.5,
            color: [[1, 'rgba(38, 59, 176, 0.36)']],
          },
        },
        pointer: { show: false },
        axisTick: { show: false },
        splitLine: { show: false },
        axisLabel: { show: false },
        anchor: { show: false },
        title: {
          show: true,
          offsetCenter: [0, '36%'],
          fontSize: 9.5,
          fontWeight: 600,
          color: mutedColor,
        },
        detail: {
          valueAnimation: false,
          offsetCenter: [0, '-6%'],
          fontSize: 23,
          fontWeight: 800,
          color: textColor,
          formatter: (val: number) => Number(val).toFixed(1),
        },
        data: [
          {
            value: Number(clampedVal.toFixed(1)),
            name: eye.status_label,
          },
        ],
      },
    ],
  }
}

export function buildOnsdBilateralTrendOption(input: OnsdTrendChartInput) {
  const okColor = readCssToken('--color-status-ok', '#2AEF4B')
  const critColor = readCssToken('--color-status-critical', '#D5110B')
  const textColor = readCssToken('--color-text-primary', '#FFECD1')
  const mutedColor = readCssToken('--color-text-muted', '#C8B69C')
  const cardColor = readCssToken('--color-surface-card', '#15616D')

  const rightColor = resolveToneCanvasColor('RIGHT', input.rightEyeTone)
  const leftColor = resolveToneCanvasColor('LEFT', input.leftEyeTone)

  const xLabels = input.points.map(p => p.label)
  const firstProjectedIdx = input.points.findIndex(p => Boolean(p.is_projected))
  const lastMeasuredIdx = firstProjectedIdx > 0
    ? firstProjectedIdx - 1
    : input.points.length - 1

  const rightMeasured = input.points.map((p, idx) =>
    p.is_projected && idx > lastMeasuredIdx ? null : p.right_mm,
  )
  const leftMeasured = input.points.map((p, idx) =>
    p.is_projected && idx > lastMeasuredIdx ? null : p.left_mm,
  )

  const rightProjected = input.points.map((p, idx) =>
    idx >= lastMeasuredIdx && firstProjectedIdx > 0 ? p.right_mm : null,
  )
  const leftProjected = input.points.map((p, idx) =>
    idx >= lastMeasuredIdx && firstProjectedIdx > 0 ? p.left_mm : null,
  )

  return {
    backgroundColor: 'transparent',
    animation: false,
    grid: {
      top: 22,
      right: 26,
      bottom: 28,
      left: 42,
    },
    tooltip: {
      trigger: 'axis',
      confine: true,
      valueFormatter: (val: number | null) =>
        val === null || val === undefined ? '—' : `${Number(val).toFixed(2)} mm`,
    },
    xAxis: {
      type: 'category',
      boundaryGap: true,
      data: xLabels,
      axisLine: { lineStyle: { color: cardColor } },
      axisTick: { show: false },
      axisLabel: {
        color: mutedColor,
        fontSize: 10,
      },
      splitLine: {
        show: true,
        lineStyle: {
          color: 'rgba(38, 59, 176, 0.28)',
          width: 1,
        },
      },
    },
    yAxis: {
      type: 'value',
      min: 4.0,
      max: 6.5,
      interval: 0.5,
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: {
        color: mutedColor,
        fontSize: 10,
        formatter: (val: number) => val.toFixed(1),
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
        name: 'Right Eye',
        type: 'line',
        data: rightMeasured,
        symbol: 'circle',
        symbolSize: 8,
        smooth: false,
        animation: false,
        itemStyle: {
          color: rightColor,
        },
        lineStyle: {
          color: rightColor,
          width: 2.6,
        },
        label: {
          show: true,
          position: 'top',
          color: textColor,
          fontSize: 9.5,
          fontWeight: 700,
          formatter: (params: { dataIndex: number, value: number | null }) => {
            if (params.value === null) return ''
            if (params.dataIndex === 0 || params.dataIndex === lastMeasuredIdx) {
              return `${Number(params.value).toFixed(1)} mm`
            }
            return ''
          },
        },
        markArea: {
          silent: true,
          itemStyle: {
            color: 'rgba(21, 97, 109, 0.20)',
          },
          data: [
            [
              { yAxis: input.baselineBandMinMm },
              { yAxis: input.baselineBandMaxMm },
            ],
          ],
        },
        markLine: {
          silent: true,
          symbol: 'none',
          animation: false,
          data: [
            {
              yAxis: input.alertThresholdMm,
              lineStyle: {
                color: critColor,
                width: 1.6,
                type: 'dashed',
              },
              label: {
                show: true,
                position: 'insideStartTop',
                color: textColor,
                fontSize: 9.5,
                fontWeight: 700,
                formatter: `ALERT THRESHOLD (${input.alertThresholdMm.toFixed(1)} mm)`,
              },
            },
            {
              yAxis: input.baselineBandMaxMm,
              lineStyle: {
                color: 'rgba(42, 239, 75, 0.48)',
                width: 1.2,
                type: 'solid',
              },
              label: {
                show: true,
                position: 'insideStartBottom',
                color: mutedColor,
                fontSize: 9,
                fontWeight: 600,
                formatter: `PERSONAL BASELINE (${input.baselineBandMinMm.toFixed(1)} – ${input.baselineBandMaxMm.toFixed(1)} mm)`,
              },
            },
          ],
        },
      },
      {
        name: 'Left Eye',
        type: 'line',
        data: leftMeasured,
        symbol: 'circle',
        symbolSize: 7.5,
        smooth: false,
        animation: false,
        itemStyle: {
          color: leftColor,
        },
        lineStyle: {
          color: leftColor,
          width: 2.3,
        },
      },
      {
        name: 'Right Eye Recovery Target',
        type: 'line',
        data: rightProjected,
        symbol: 'circle',
        symbolSize: 7.5,
        smooth: false,
        animation: false,
        itemStyle: {
          color: okColor,
        },
        lineStyle: {
          color: okColor,
          width: 2.1,
          type: 'dashed',
        },
        label: {
          show: true,
          position: 'top',
          color: okColor,
          fontSize: 9.5,
          fontWeight: 700,
          formatter: (params: { dataIndex: number, value: number | null }) => {
            if (params.value === null || params.dataIndex !== firstProjectedIdx) return ''
            return `${Number(params.value).toFixed(1)} mm`
          },
        },
      },
      {
        name: 'Left Eye Recovery Target',
        type: 'line',
        data: leftProjected,
        symbol: 'circle',
        symbolSize: 7,
        smooth: false,
        animation: false,
        itemStyle: {
          color: okColor,
        },
        lineStyle: {
          color: okColor,
          width: 1.9,
          type: 'dashed',
        },
      },
    ],
  }
}
