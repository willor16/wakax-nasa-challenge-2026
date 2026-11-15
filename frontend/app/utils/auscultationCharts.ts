export type AuscultationHudTone = 'reference' | 'warn' | 'critical'
export type AuscultationMetricTone = 'nominal' | 'warn' | 'critical'
export type AuscultationOrgan = 'CARDIAC' | 'PULMONARY'

export interface Co2TrendPointInput {
  label: string
  co2_mmhg: number
  co2_ppm?: number
}

export interface CabinCo2ChartInput {
  points: Co2TrendPointInput[]
  targetMaxMmhg: number
  alertLimitMmhg: number
  tone: AuscultationHudTone
}

function readCssToken(name: string, fallback: string): string {
  if (typeof window === 'undefined') return fallback
  const val = getComputedStyle(document.documentElement).getPropertyValue(name).trim()
  return val || fallback
}

export function auscultationToneColorVar(tone: AuscultationHudTone): string {
  if (tone === 'critical') return 'var(--color-status-critical)'
  if (tone === 'warn') return 'var(--color-rem-accent)'
  return 'var(--color-status-ok)'
}

export function auscultationMetricColorVar(tone: AuscultationMetricTone): string {
  if (tone === 'critical') return 'var(--color-status-critical)'
  if (tone === 'warn') return 'var(--color-rem-accent)'
  return 'var(--color-status-ok)'
}

export function buildPhonocardiogramOption(
  samples: number[],
  tone: AuscultationHudTone = 'reference',
) {
  const okColor = readCssToken('--color-status-ok', '#2AEF4B')
  const warnColor = readCssToken('--color-rem-accent', '#2994A6')
  const critColor = readCssToken('--color-status-critical', '#D5110B')
  const lineColor = tone === 'critical'
    ? critColor
    : tone === 'warn'
      ? warnColor
      : okColor

  return {
    backgroundColor: 'transparent',
    animation: false,
    grid: {
      top: 10,
      right: 10,
      bottom: 10,
      left: 10,
    },
    tooltip: {
      trigger: 'axis',
      confine: true,
      valueFormatter: (val: number) => `${Number(val).toFixed(3)} mV`,
    },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: samples.map((_, idx) => `${idx}`),
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { show: false },
      splitLine: {
        show: true,
        interval: 29,
        lineStyle: {
          color: 'rgba(38, 59, 176, 0.28)',
          width: 1,
        },
      },
    },
    yAxis: {
      type: 'value',
      min: -1.08,
      max: 1.08,
      interval: 0.5,
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { show: false },
      splitLine: {
        show: true,
        lineStyle: {
          color: 'rgba(21, 97, 109, 0.30)',
          width: 1,
        },
      },
    },
    series: [
      {
        name: 'Cardiac Phonocardiogram',
        type: 'line',
        data: samples,
        sampling: 'lttb',
        showSymbol: false,
        smooth: false,
        animation: false,
        lineStyle: {
          color: lineColor,
          width: 1.85,
        },
        areaStyle: {
          color: 'rgba(42, 239, 75, 0.07)',
        },
      },
    ],
  }
}

export function buildPulmonaryEnvelopeOption(
  samples: number[],
  tone: AuscultationHudTone = 'reference',
) {
  const remColor = readCssToken('--color-rem-accent', '#2994A6')
  const iceColor = readCssToken('--color-text-secondary', '#F2DEC0')
  const critColor = readCssToken('--color-status-critical', '#D5110B')
  const lineColor = tone === 'critical'
    ? critColor
    : tone === 'warn'
      ? remColor
      : iceColor

  return {
    backgroundColor: 'transparent',
    animation: false,
    grid: {
      top: 10,
      right: 10,
      bottom: 10,
      left: 10,
    },
    tooltip: {
      trigger: 'axis',
      confine: true,
      valueFormatter: (val: number) => `${Math.round(Number(val) * 100)}%`,
    },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: samples.map((_, idx) => `${idx}`),
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { show: false },
      splitLine: {
        show: true,
        interval: 29,
        lineStyle: {
          color: 'rgba(38, 59, 176, 0.28)',
          width: 1,
        },
      },
    },
    yAxis: {
      type: 'value',
      min: 0,
      max: 1.05,
      interval: 0.25,
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { show: false },
      splitLine: {
        show: true,
        lineStyle: {
          color: 'rgba(21, 97, 109, 0.30)',
          width: 1,
        },
      },
    },
    series: [
      {
        name: 'Pulmonary Breath Envelope',
        type: 'line',
        data: samples,
        sampling: 'lttb',
        showSymbol: false,
        smooth: true,
        animation: false,
        lineStyle: {
          color: lineColor,
          width: 2.0,
        },
        areaStyle: {
          color: 'rgba(41, 148, 166, 0.22)',
        },
      },
    ],
  }
}

export function buildCabinCo2TrendOption(input: CabinCo2ChartInput) {
  const okColor = readCssToken('--color-status-ok', '#2AEF4B')
  const warnColor = readCssToken('--color-rem-accent', '#2994A6')
  const critColor = readCssToken('--color-status-critical', '#D5110B')
  const textColor = readCssToken('--color-text-primary', '#FFECD1')
  const mutedColor = readCssToken('--color-text-muted', '#C8B69C')
  const cardColor = readCssToken('--color-surface-card', '#15616D')

  const lineColor = input.tone === 'critical'
    ? critColor
    : input.tone === 'warn'
      ? warnColor
      : okColor

  const values = input.points.map(p => p.co2_mmhg)
  const minSample = values.length > 0 ? Math.min(...values) : 2.2
  const maxSample = values.length > 0 ? Math.max(...values) : 3.0
  const yMin = minSample < 1.8 ? 0.5 : 1.8
  const yMax = Math.max(4.4, Number((maxSample + 0.3).toFixed(1)))

  return {
    backgroundColor: 'transparent',
    animation: false,
    grid: {
      top: 22,
      right: 22,
      bottom: 24,
      left: 38,
    },
    tooltip: {
      trigger: 'axis',
      confine: true,
      valueFormatter: (val: number) => `${Number(val).toFixed(2)} mmHg`,
    },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: input.points.map(p => p.label),
      axisLine: { lineStyle: { color: cardColor } },
      axisTick: { show: false },
      axisLabel: {
        color: mutedColor,
        fontSize: 10,
      },
      splitLine: {
        show: true,
        lineStyle: {
          color: 'rgba(38, 59, 176, 0.26)',
          width: 1,
        },
      },
    },
    yAxis: {
      type: 'value',
      min: yMin,
      max: yMax,
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
          color: 'rgba(38, 59, 176, 0.32)',
          width: 1,
        },
      },
    },
    series: [
      {
        name: 'Cabin CO2 Partial Pressure',
        type: 'line',
        data: values,
        sampling: 'lttb',
        symbol: 'circle',
        symbolSize: 6.5,
        smooth: true,
        animation: false,
        itemStyle: {
          color: lineColor,
        },
        lineStyle: {
          color: lineColor,
          width: 2.3,
        },
        areaStyle: {
          color: 'rgba(21, 97, 109, 0.20)',
        },
        markArea: {
          silent: true,
          itemStyle: {
            color: 'rgba(42, 239, 75, 0.08)',
          },
          data: [
            [
              { yAxis: yMin },
              { yAxis: input.targetMaxMmhg },
            ],
          ],
        },
        markLine: {
          silent: true,
          symbol: 'none',
          animation: false,
          data: [
            {
              yAxis: input.alertLimitMmhg,
              lineStyle: {
                color: critColor,
                width: 1.5,
                type: 'dashed',
              },
              label: {
                show: true,
                position: 'insideStartTop',
                color: textColor,
                fontSize: 9,
                fontWeight: 700,
                formatter: `ALERT LIMIT (${input.alertLimitMmhg.toFixed(1)} mmHg)`,
              },
            },
            {
              yAxis: input.targetMaxMmhg,
              lineStyle: {
                color: 'rgba(42, 239, 75, 0.48)',
                width: 1.2,
                type: 'solid',
              },
              label: {
                show: true,
                position: 'insideEndBottom',
                color: mutedColor,
                fontSize: 8.8,
                fontWeight: 600,
                formatter: `TARGET ZONE (< ${input.targetMaxMmhg.toFixed(1)} mmHg)`,
              },
            },
          ],
        },
      },
    ],
  }
}

export function computeRmsDba(samples: ArrayLike<number>): number {
  const length = samples.length
  if (length === 0) return 44.0
  let sumSq = 0
  for (let i = 0; i < length; i++) {
    const v = Number(samples[i] ?? 0)
    sumSq += v * v
  }
  const rms = Math.sqrt(sumSq / length)
  if (rms <= 0.0002) return 42.0
  const db = 38.0 + 20.0 * Math.log10(1.0 + rms * 28.0)
  return Number(Math.max(36.0, Math.min(84.0, db)).toFixed(1))
}

export async function computeSha256Hex(input: ArrayBuffer | Uint8Array): Promise<string> {
  let payload: ArrayBuffer
  if (input instanceof Uint8Array) {
    const copy = new Uint8Array(input.byteLength)
    copy.set(input)
    payload = copy.buffer
  }
  else {
    payload = input
  }
  const digest = await globalThis.crypto.subtle.digest('SHA-256', payload)
  return Array.from(new Uint8Array(digest))
    .map(b => b.toString(16).padStart(2, '0'))
    .join('')
}

export function buildSyntheticStethoscopeBytes(
  organType: AuscultationOrgan,
  site: string,
  durationSec: number,
): Uint8Array {
  const header = [0x1A, 0x45, 0xDF, 0xA3, 0x9F, 0x42, 0x86, 0x81, 0x01]
  const metaText = `ARESVII:${organType}:${site}:${durationSec}S`
  const metaBytes = Array.from(metaText, ch => ch.charCodeAt(0) & 0xFF)
  const frameCount = Math.max(64, Math.min(960, durationSec * 32))
  const out = new Uint8Array(header.length + metaBytes.length + frameCount)
  out.set(header, 0)
  out.set(metaBytes, header.length)
  const offset = header.length + metaBytes.length
  for (let i = 0; i < frameCount; i++) {
    const phase = i / 32
    const wave = organType === 'CARDIAC'
      ? Math.sin(phase * Math.PI * 6) * Math.exp(-(((phase % 1) - 0.2) ** 2) * 40)
      : 0.5 + 0.42 * Math.sin(phase * Math.PI * 1.4)
    out[offset + i] = Math.max(0, Math.min(255, Math.round((wave + 1) * 127.5)))
  }
  return out
}

export function generateLivePreviewWave(
  organType: AuscultationOrgan,
  tick: number,
  count = 140,
): number[] {
  const out: number[] = []
  const phaseShift = tick * 0.09
  for (let i = 0; i < count; i++) {
    const t = (i / Math.max(1, count - 1)) * 3.2 + phaseShift
    const cyc = t - Math.floor(t)
    if (organType === 'CARDIAC') {
      const s1 = Math.exp(-(((cyc - 0.16) / 0.045) ** 2)) * Math.sin(2 * Math.PI * 22 * cyc)
      const s2 = 0.72 * Math.exp(-(((cyc - 0.47) / 0.036) ** 2)) * Math.sin(2 * Math.PI * 31 * cyc)
      out.push(Number((0.92 * s1 + s2).toFixed(4)))
    }
    else {
      const inh = 0.76 * Math.exp(-(((cyc - 0.29) / 0.15) ** 2))
      const exh = 0.50 * Math.exp(-(((cyc - 0.67) / 0.18) ** 2))
      const rip = 0.04 * Math.sin(2 * Math.PI * 10 * t)
      out.push(Number(Math.max(0.05, Math.min(0.98, 0.12 + inh + exh + rip)).toFixed(4)))
    }
  }
  return out
}
