// Display helpers shared by every screen. All output is plain English.

export type StatusCode = 'NOMINAL' | 'WATCH' | 'WARNING' | 'CRITICAL' | 'NO_DATA'
export type Tone = 'ok' | 'watch' | 'critical' | 'neutral'

/** Visual tone of a clinical status: green, navy (watch / warning) or red. */
export function toneOf(status: StatusCode | string | null | undefined): Tone {
  switch (status) {
    case 'NOMINAL': return 'ok'
    case 'WATCH':
    case 'WARNING': return 'watch'
    case 'CRITICAL': return 'critical'
    default: return 'neutral'
  }
}

/** Tone of a crew member's overall state on the public screens. */
export function crewTone(status: string | null | undefined): Tone {
  if (status === 'Optimal') return 'ok'
  if (status === 'Nominal') return 'watch'
  if (status === 'Attention') return 'critical'
  return 'neutral'
}

const pad = (value: number, size = 2) => String(value).padStart(size, '0')

/** ``DAY 047 · 14:32 UTC`` */
export function formatClock(day: number | null, epochMs: number): string {
  const date = new Date(epochMs)
  const time = `${pad(date.getUTCHours())}:${pad(date.getUTCMinutes())} UTC`
  return day !== null && day > 0 ? `DAY ${pad(day, 3)} · ${time}` : time
}

/** ``D47`` -> ``Day 047`` */
export function dayText(label: string | null | undefined): string {
  if (!label) return '—'
  const digits = label.replace(/\D/g, '')
  return digits ? `Day ${pad(Number(digits), 3)}` : 'Pre-flight'
}

/** ``7h 12m`` from minutes; ``—`` when unknown. */
export function formatDuration(minutes: number | null | undefined): string {
  if (minutes === null || minutes === undefined || Number.isNaN(minutes)) return '—'
  const total = Math.max(0, Math.round(minutes))
  return `${Math.floor(total / 60)}h ${pad(total % 60)}m`
}

/** ``14:32`` (UTC) from an ISO timestamp. */
export function formatTime(iso: string | null | undefined): string {
  if (!iso) return '--:--'
  const date = new Date(iso)
  return Number.isNaN(date.getTime()) ? '--:--' : `${pad(date.getUTCHours())}:${pad(date.getUTCMinutes())}`
}

/** Number for display with fixed decimals and thousands separators; ``—`` when unknown. */
export function formatNumber(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  return value.toLocaleString('en-US', { minimumFractionDigits: digits, maximumFractionDigits: digits })
}

/** Sensible decimals for a clinical unit. */
export function digitsFor(unit: string | undefined, metricKey = ''): number {
  if (metricKey.includes('specific_gravity') || metricKey.includes('bone_density')) return 3
  if (['bpm', '%', 'mmHg', 'min', 'mL', 'kcal', 'ms', 'level', 'pts', 'µm', 'mg/dL'].includes(unit ?? '')) {
    return metricKey.startsWith('iop_') ? 1 : 0
  }
  return 1
}

/** ``12 MIN AGO``, ``3 H AGO`` or the UTC time for older events. */
export function formatAgo(iso: string, nowMs: number): string {
  const minutes = Math.round((nowMs - new Date(iso).getTime()) / 60_000)
  if (minutes < 1) return 'JUST NOW'
  if (minutes < 60) return `${minutes} MIN AGO`
  if (minutes < 24 * 60) return `${formatTime(iso)} UTC`
  return `${Math.floor(minutes / 1440)} D AGO`
}

/** Position (0-100 %) of a value on a scale, clamped. */
export function scalePct(value: number | null | undefined, min: number, max: number): number {
  if (value === null || value === undefined || max <= min) return 0
  return Math.min(100, Math.max(0, ((value - min) / (max - min)) * 100))
}

/** Litres with one decimal from millilitres. */
export function litres(ml: number | null | undefined): string {
  return ml === null || ml === undefined ? '—' : (ml / 1000).toFixed(1)
}

export function sexText(sex: string | null | undefined): string {
  return sex === 'F' ? 'Female' : sex === 'M' ? 'Male' : sex === 'X' ? 'Other' : '—'
}

export function titleCase(text: string): string {
  return text.toLowerCase().replace(/\b\w/g, c => c.toUpperCase())
}
