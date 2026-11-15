// Notifications screen (16) helpers: types for GET /api/v1/alerts and pure
// formatting rules, kept out of the page so they can be unit tested.

export type NotificationView = 'all' | 'advisories' | 'checks'
export type Severity = 'CRITICAL' | 'WARNING' | 'INFO'

export interface CareStep {
  title_en: string
  detail_en: string
}

export interface AdvisoryItem {
  id: number
  kind: 'ADVISORY'
  severity: Severity
  category: string
  title_en: string
  message_en: string
  care_steps: CareStep[]
  guide_article_id: string | null
  is_quiet_deferred: boolean
  created_at_utc: string
  acknowledged_at_utc: string | null
}

export interface CheckItem {
  id: number
  kind: 'SCHEDULED'
  check_type: string
  title_en: string
  detail_en: string
  due_at_utc: string
  status: string
}

export type NotificationItem = AdvisoryItem | CheckItem

export interface NotificationsResponse {
  crew_id: string
  view: NotificationView
  counts: Record<NotificationView, number>
  quiet_hours: { start_utc: string, end_utc: string, active: boolean }
  items: NotificationItem[]
}

export type Tone = 'critical' | 'warning' | 'info' | 'scheduled'

/** Text lookup from the locale file; every word shown on screen comes through it. */
export type Translate = (key: string, params?: Record<string, unknown>) => string

export function itemKey(item: NotificationItem): string {
  return `${item.kind}-${item.id}`
}

export function itemTone(item: NotificationItem): Tone {
  if (item.kind === 'SCHEDULED') return 'scheduled'
  if (item.severity === 'CRITICAL') return 'critical'
  return item.severity === 'WARNING' ? 'warning' : 'info'
}

function parseUtc(isoUtc: string): Date {
  return new Date(isoUtc)
}

function hhmm(date: Date): string {
  return date.toISOString().slice(11, 16)
}

/** "12 MIN AGO", "3 H AGO", "14:00 UTC" (earlier days). */
export function timeAgo(isoUtc: string, now: Date, t: Translate): string {
  const then = parseUtc(isoUtc)
  const minutes = Math.max(0, Math.floor((now.getTime() - then.getTime()) / 60000))
  if (minutes < 1) return t('notifications.time.justNow')
  if (minutes < 60) return t('notifications.time.minutesAgo', { n: minutes })
  if (minutes < 24 * 60) return t('notifications.time.hoursAgo', { n: Math.floor(minutes / 60) })
  return t('notifications.time.clock', { time: hhmm(then) })
}

function dayIndex(date: Date): number {
  return Math.floor(date.getTime() / 86400000)
}

/** "TODAY 19:30 UTC", "TOMORROW 07:30 UTC", "OVERDUE · 14:00 UTC", "NOV 21 · 14:00 UTC". */
export function dueLabel(isoUtc: string, now: Date, t: Translate): string {
  const due = parseUtc(isoUtc)
  const time = hhmm(due)
  if (due.getTime() < now.getTime()) return t('notifications.due.overdue', { time })
  const days = dayIndex(due) - dayIndex(now)
  if (days === 0) return t('notifications.due.today', { time })
  if (days === 1) return t('notifications.due.tomorrow', { time })
  const month = due.toLocaleString('en-US', { month: 'short', timeZone: 'UTC' }).toUpperCase()
  return t('notifications.due.date', { month, day: due.getUTCDate(), time })
}

/** Small caps line above each card title, as on the design. */
export function itemLabel(item: NotificationItem, now: Date, t: Translate): string {
  if (item.kind === 'SCHEDULED') {
    return t('notifications.label.scheduled', { due: dueLabel(item.due_at_utc, now, t) })
  }
  return t('notifications.label.advisory', {
    severity: t(`notifications.severity.${item.severity}`),
    ago: timeAgo(item.created_at_utc, now, t),
  })
}

/** Card subtitle: the advisory message, or what to measure for a check. */
export function itemDetail(item: NotificationItem): string {
  return item.kind === 'SCHEDULED' ? item.detail_en : item.message_en
}

const CAPTURE_ROUTE: Record<string, string> = {
  OCULAR_EXAM: '/capture/vision',
  VITALS_CHECK: '/capture/physical',
  HABITS_LOG: '/capture/physical',
  GLUCOSE_STRIP: '/capture/physical',
  BODY_COMPOSITION: '/capture/physical',
  AEROBIC_TEST: '/capture/physical',
}

/** Data Capture tab where a scheduled check is recorded. */
export function captureRoute(checkType: string): string {
  return CAPTURE_ROUTE[checkType] ?? '/capture/physical'
}

/** Medical Guide link for an advisory, opening its protocol when there is one. */
export function guideRoute(articleId: string | null): string {
  return articleId ? `/guide?article=${encodeURIComponent(articleId)}` : '/guide'
}

/** First item to show in the care panel: the most urgent open advisory, else the first item. */
export function defaultSelection(items: NotificationItem[]): NotificationItem | null {
  return items.find(i => i.kind === 'ADVISORY' && i.acknowledged_at_utc === null) ?? items[0] ?? null
}
