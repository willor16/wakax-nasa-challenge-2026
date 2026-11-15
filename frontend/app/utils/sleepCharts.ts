export type SleepStageKey = 'DEEP' | 'REM' | 'LIGHT' | 'AWAKE'
export type SleepHudTone = 'reference' | 'warn' | 'critical'

export interface SleepAxisTickInput {
  offset_min: number
  label: string
}

export interface SleepRibbonBoutInput {
  stage: SleepStageKey
  lane_index: number
  prev_lane_index?: number | null
  start_offset_min: number
  end_offset_min: number
  duration_min: number
  start_hm: string
  end_hm: string
}

export interface CustomRenderApi {
  value: (idx: number) => number | string
  coord: (val: [number, number]) => [number, number]
  size: (val: [number, number]) => [number, number]
}

export interface CustomRenderParams {
  dataIndex: number
  coordSys: {
    x: number
    y: number
    width: number
    height: number
  }
}

function readCssToken(name: string, fallback: string): string {
  if (typeof window === 'undefined') return fallback
  const val = getComputedStyle(document.documentElement).getPropertyValue(name).trim()
  return val || fallback
}

export function stageColorVar(stage: SleepStageKey): string {
  if (stage === 'DEEP') return 'var(--color-status-ok)'
  if (stage === 'REM') return 'var(--color-rem-accent)'
  if (stage === 'LIGHT') return 'var(--color-navy-edge)'
  return 'var(--color-status-critical)'
}

export function resolveStageCanvasColor(stage: SleepStageKey): string {
  if (stage === 'DEEP') return readCssToken('--color-status-ok', '#2AEF4B')
  if (stage === 'REM') return readCssToken('--color-rem-accent', '#2994A6')
  if (stage === 'LIGHT') return readCssToken('--color-navy-edge', '#263BB0')
  return readCssToken('--color-status-critical', '#D5110B')
}

export function buildSleepScoreGaugeOption(
  score: number,
  subtitle: string,
  qualityTone: SleepHudTone = 'reference',
) {
  const clampedScore = Math.max(0, Math.min(100, Math.round(score)))
  const okColor = readCssToken('--color-status-ok', '#2AEF4B')
  const remColor = readCssToken('--color-rem-accent', '#2994A6')
  const critColor = readCssToken('--color-status-critical', '#D5110B')
  const textColor = readCssToken('--color-text-primary', '#FFECD1')
  const mutedColor = readCssToken('--color-text-muted', '#C8B69C')

  const arcColor = qualityTone === 'critical'
    ? critColor
    : qualityTone === 'warn'
      ? remColor
      : okColor

  return {
    backgroundColor: 'transparent',
    animation: false,
    series: [
      {
        name: 'Sleep Score',
        type: 'gauge',
        startAngle: 215,
        endAngle: -35,
        min: 0,
        max: 100,
        radius: '92%',
        center: ['50%', '56%'],
        animation: false,
        progress: {
          show: true,
          width: 9,
          roundCap: true,
          itemStyle: {
            color: arcColor,
          },
        },
        axisLine: {
          roundCap: true,
          lineStyle: {
            width: 9,
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
          offsetCenter: [0, '35%'],
          fontSize: 10,
          fontWeight: 600,
          color: mutedColor,
        },
        detail: {
          valueAnimation: false,
          offsetCenter: [0, '-6%'],
          fontSize: 28,
          fontWeight: 800,
          color: textColor,
          formatter: '{value}',
        },
        data: [
          {
            value: clampedScore,
            name: subtitle,
          },
        ],
      },
    ],
  }
}

export function buildSleepStageRibbonOption(
  bouts: SleepRibbonBoutInput[],
  windowTotalMin: number,
  axisTicks: SleepAxisTickInput[],
) {
  const safeTotalMin = Math.max(60, windowTotalMin)
  const textColor = readCssToken('--color-text-primary', '#FFECD1')
  const mutedColor = readCssToken('--color-text-muted', '#C8B69C')
  const cardColor = readCssToken('--color-surface-card', '#15616D')

  const stagePalette: Record<SleepStageKey, string> = {
    DEEP: resolveStageCanvasColor('DEEP'),
    REM: resolveStageCanvasColor('REM'),
    LIGHT: resolveStageCanvasColor('LIGHT'),
    AWAKE: resolveStageCanvasColor('AWAKE'),
  }

  const stageCodeToKey: Record<number, SleepStageKey> = {
    1: 'DEEP',
    2: 'LIGHT',
    3: 'REM',
    4: 'AWAKE',
  }

  const customData = bouts.map(b => [
    b.start_offset_min,
    b.end_offset_min,
    b.lane_index,
    b.prev_lane_index ?? -1,
    b.duration_min,
    b.stage,
    `${b.start_hm}–${b.end_hm}`,
  ])

  const renderRibbonItem = (params: CustomRenderParams, api: CustomRenderApi) => {
    const startMin = Number(api.value(0))
    const endMin = Number(api.value(1))
    const laneIdx = Number(api.value(2))
    const prevLaneIdx = Number(api.value(3))
    const durationMin = Number(api.value(4))
    const stageKey = stageCodeToKey[laneIdx] ?? 'LIGHT'
    const fillColor = stagePalette[stageKey]

    const startCoord = api.coord([startMin, laneIdx])
    const endCoord = api.coord([endMin, laneIdx])
    const ribbonCenter = api.coord([startMin, 0])
    const laneStep = Math.max(18, api.size([0, 1])[1])

    const rawX = startCoord[0]
    const rawW = Math.max(2, endCoord[0] - startCoord[0])
    const blockH = Math.min(24, laneStep * 0.64)
    const ribbonH = Math.min(14, laneStep * 0.42)

    const clipLeft = Math.max(rawX, params.coordSys.x)
    const clipRight = Math.min(rawX + rawW, params.coordSys.x + params.coordSys.width)
    const clippedW = Math.max(0, clipRight - clipLeft)

    const children: Array<Record<string, unknown>> = []

    if (prevLaneIdx >= 1 && prevLaneIdx !== laneIdx && rawX >= params.coordSys.x) {
      const prevCoord = api.coord([startMin, prevLaneIdx])
      children.push({
        type: 'line',
        shape: {
          x1: rawX,
          y1: prevCoord[1],
          x2: rawX,
          y2: startCoord[1],
        },
        style: {
          stroke: 'rgba(200, 182, 156, 0.48)',
          lineWidth: 1.15,
          lineDash: [3, 3],
        },
      })
    }

    if (clippedW > 0) {
      children.push({
        type: 'rect',
        shape: {
          x: clipLeft,
          y: startCoord[1] - blockH / 2,
          width: clippedW,
          height: blockH,
          r: 3,
        },
        style: {
          fill: fillColor,
          opacity: 0.92,
        },
      })

      children.push({
        type: 'rect',
        shape: {
          x: clipLeft,
          y: ribbonCenter[1] - ribbonH / 2,
          width: clippedW,
          height: ribbonH,
          r: 1.5,
        },
        style: {
          fill: fillColor,
          opacity: 0.96,
        },
      })

      if (clippedW >= 34) {
        children.push({
          type: 'text',
          style: {
            text: `${durationMin}m`,
            x: clipLeft + clippedW / 2,
            y: startCoord[1],
            textAlign: 'center',
            textVerticalAlign: 'middle',
            fill: stageKey === 'DEEP' ? '#001524' : textColor,
            fontSize: 9.5,
            fontWeight: 700,
            fontFamily: 'JetBrains Mono, monospace',
          },
          silent: true,
        })
      }
    }

    return {
      type: 'group',
      children,
    }
  }

  return {
    backgroundColor: 'transparent',
    animation: false,
    grid: {
      top: 12,
      right: 16,
      bottom: 26,
      left: 56,
    },
    tooltip: {
      trigger: 'item',
      confine: true,
      formatter: (item: { value?: Array<number | string> }) => {
        const v = item.value ?? []
        const stageName = String(v[5] ?? 'STAGE')
        const dur = Number(v[4] ?? 0)
        const windowStr = String(v[6] ?? '')
        return `${stageName} · ${windowStr} UTC (${dur}m)`
      },
    },
    xAxis: {
      type: 'value',
      min: 0,
      max: safeTotalMin,
      interval: 60,
      axisLine: { lineStyle: { color: cardColor } },
      axisTick: { show: false },
      axisLabel: {
        color: mutedColor,
        fontSize: 9.5,
        formatter: (val: number) => {
          const hit = axisTicks.find(t => Math.abs(t.offset_min - val) <= 2)
          if (hit) return hit.label
          const rounded = Math.round(val)
          return `${Math.floor(rounded / 60)}h`
        },
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
      type: 'category',
      data: ['RIBBON', 'DEEP', 'LIGHT', 'REM', 'AWAKE'],
      axisLine: { lineStyle: { color: cardColor } },
      axisTick: { show: false },
      axisLabel: {
        color: mutedColor,
        fontSize: 9.5,
        fontWeight: 700,
      },
      splitLine: {
        show: true,
        lineStyle: {
          color: 'rgba(38, 59, 176, 0.26)',
          width: 1,
        },
      },
    },
    series: [
      {
        name: 'Sleep Stage Ribbon',
        type: 'custom',
        renderItem: renderRibbonItem,
        encode: {
          x: [0, 1],
          y: 2,
        },
        animation: false,
        data: customData,
      },
    ],
  }
}
