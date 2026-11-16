// Metric catalog (units, usual ranges, possible ranges) and the crew member's baselines.
// Capture forms validate entries against these instead of hard-coded limits.
import { z } from 'zod'
import { nominalFor, type Sex } from '~/utils/admission'

export interface CatalogItem {
  metric_key: string
  display_name_en: string
  unit: string
  nominal_min: number
  nominal_max: number
  warning_min: number | null
  warning_max: number | null
  critical_min: number | null
  critical_threshold: number | null
  plausible_min: number | null
  plausible_max: number | null
  /** Female / male limits for metrics whose normal range differs by sex. */
  by_sex?: Record<string, { nominal_min?: number | null, nominal_max?: number | null }> | null
}
export interface BaselineItem { metric_key: string, mean_val: number, std_dev: number, sample_count: number }

export function useCatalog() {
  const { api } = useApi()
  const { crew } = useSession()
  const catalog = useState<Record<string, CatalogItem>>('metric-catalog', () => ({}))
  const baselines = shallowRef<Record<string, BaselineItem>>({})
  const ready = ref(false)

  async function load() {
    const [items, own] = await Promise.all([
      Object.keys(catalog.value).length ? Promise.resolve(null) : api<CatalogItem[]>('/metrics/catalog'),
      api<BaselineItem[]>(`/crew/${crew.value!.id}/baselines`),
    ])
    if (items) catalog.value = Object.fromEntries(items.map(item => [item.metric_key, item]))
    baselines.value = Object.fromEntries(own.map(item => [item.metric_key, item]))
    ready.value = true
  }

  /** Zod rule for one numeric entry: required, a number, and physically possible. */
  function numberRule(metricKey: string, label: string) {
    const item = catalog.value[metricKey]
    const range = item?.plausible_min != null && item.plausible_max != null
      ? `Non-admissible reading · admissible ${item.plausible_min}–${item.plausible_max} ${item.unit}`
      : `${label}: not possible`
    let rule = z.number({ invalid_type_error: `${label}: enter a number`, required_error: `${label}: required` })
    if (item?.plausible_min != null) rule = rule.min(item.plausible_min, range)
    if (item?.plausible_max != null) rule = rule.max(item.plausible_max, range)
    return rule
  }

  /** ``Baseline: 64.5 kg`` / ``58–72 bpm baseline`` style hint. */
  function baselineHint(metricKey: string, digits = 1, range = false): string {
    const base = baselines.value[metricKey]
    const unit = catalog.value[metricKey]?.unit ?? ''
    if (!base) return 'No pre-flight value'
    if (range && base.sample_count >= 3) {
      const spread = Math.max(base.std_dev, 0)
      return `Baseline: ${(base.mean_val - 2 * spread).toFixed(digits)}–${(base.mean_val + 2 * spread).toFixed(digits)} ${unit}`
    }
    return `Baseline: ${base.mean_val.toFixed(digits)} ${unit}`
  }

  /** ``Normal 12–16 g/dL`` using the female or male range when the metric has one. */
  function usualRange(metricKey: string, sex?: Sex): string {
    const item = catalog.value[metricKey]
    if (!item) return ''
    const [low, high] = nominalFor(item, sex)
    return `Normal ${low}–${high} ${item.unit}`
  }

  return { catalog, baselines, ready, load, numberRule, baselineHint, usualRange }
}

/** Turns a text field into a number (``''`` -> undefined so Zod reports "required"). */
export function toNumber(text: string | number | null | undefined): number | undefined {
  if (text === null || text === undefined) return undefined
  const cleaned = String(text).replace(/,/g, '').trim()
  if (cleaned === '') return undefined
  const value = Number(cleaned)
  return Number.isFinite(value) ? value : Number.NaN
}
