// Physician review tab (Notifications, PHYSICIAN only): types and display rules.
import type { Translate } from './notifications'

export type ReviewDecision = 'APPROVED' | 'REJECTED' | 'PROMOTED_TO_GUIDE'

export interface ReviewMetric {
  metric_key: string
  display_name_en: string
  unit: string
  value: number
  baseline: number
  z: number
}

export interface ReviewItem {
  id: number
  crew_id: string
  crew_name: string
  crew_role: string
  anomaly_score: number
  pattern_key: string | null
  pattern_label_en: string | null
  llm_summary_en: string
  preventive_steps: { title_en: string, detail_en: string }[]
  cited_article_ids: string[]
  top_metrics: ReviewMetric[]
  guidance_source: 'assistant' | 'fallback' | null
  validation_status: string
  created_at_utc: string
}

export interface ReviewListResponse {
  items: ReviewItem[]
  pending: number
}

function formatNumber(value: number): string {
  return Number.isInteger(value) ? String(value) : value.toFixed(1)
}

function withUnit(value: number, unit: string): string {
  return unit === '%' ? `${formatNumber(value)}%` : `${formatNumber(value)} ${unit}`
}

/** "Right Intraocular Pressure 17.5 mmHg · usual 14.5 mmHg" */
export function metricLine(metric: ReviewMetric, t: Translate): string {
  return t('notifications.reviews.metric', {
    name: metric.display_name_en,
    value: withUnit(metric.value, metric.unit),
    usual: withUnit(metric.baseline, metric.unit),
  })
}

/** Higher than 1 means above the review line; shown as a plain strength word. */
export function strengthLabel(score: number, t: Translate): string {
  const level = score >= 2 ? 'strong' : score >= 1.3 ? 'clear' : 'mild'
  return t(`notifications.reviews.strength.${level}`)
}

/** Who wrote the suggested steps, in plain words. */
export function sourceLabel(source: ReviewItem['guidance_source'], t: Translate): string {
  return t(`notifications.reviews.source.${source === 'assistant' ? 'assistant' : 'standard'}`)
}
