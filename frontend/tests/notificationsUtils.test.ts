import { describe, expect, it } from 'vitest'
import type { AdvisoryItem, CheckItem } from '../app/utils/notifications'
import {
  captureRoute,
  defaultSelection,
  dueLabel,
  guideRoute,
  itemDetail,
  itemKey,
  itemLabel,
  itemTone,
  timeAgo,
} from '../app/utils/notifications'

const NOW = new Date('2026-11-15T14:32:00Z')

function advisory(overrides: Partial<AdvisoryItem> = {}): AdvisoryItem {
  return {
    id: 1,
    kind: 'ADVISORY',
    severity: 'CRITICAL',
    category: 'VISION',
    title_en: 'Right optic nerve sheath elevated (5.9 mm)',
    message_en: 'Above personal baseline (4.7 mm). Review preventive care on the right.',
    care_steps: [{ title_en: 'Repeat the eye scan', detail_en: 'Both eyes.' }],
    guide_article_id: 'wiki-vision-01',
    is_quiet_deferred: false,
    created_at_utc: '2026-11-15T14:20:00Z',
    acknowledged_at_utc: null,
    ...overrides,
  }
}

const check: CheckItem = {
  id: 1,
  kind: 'SCHEDULED',
  check_type: 'OCULAR_EXAM',
  title_en: 'Weekly eye scan',
  detail_en: 'Both eyes with the 3.0 mm guide, plus eye pressure.',
  due_at_utc: '2026-11-16T07:30:00Z',
  status: 'PENDING',
}

describe('Notifications screen helpers', () => {
  it('labels cards like the design', () => {
    expect(itemLabel(advisory(), NOW)).toBe('CRITICAL ADVISORY · 12 MIN AGO')
    expect(itemLabel(advisory({ severity: 'WARNING', created_at_utc: '2026-11-15T11:00:00Z' }), NOW))
      .toBe('WARNING · 3 H AGO')
    expect(itemLabel(advisory({ severity: 'INFO', created_at_utc: '2026-11-14T09:05:00Z' }), NOW))
      .toBe('ADVISORY · 09:05 UTC')
    expect(itemLabel(check, NOW)).toBe('SCHEDULED · TOMORROW 07:30 UTC')
  })

  it('formats due times for checks', () => {
    expect(dueLabel('2026-11-15T19:30:00Z', NOW)).toBe('TODAY 19:30 UTC')
    expect(dueLabel('2026-11-15T09:00:00Z', NOW)).toBe('OVERDUE · 09:00 UTC')
    expect(dueLabel('2026-11-21T14:00:00Z', NOW)).toBe('NOV 21 · 14:00 UTC')
    expect(timeAgo('2026-11-15T14:32:20Z', NOW)).toBe('JUST NOW')
  })

  it('keeps advisory and check ids apart and picks tones', () => {
    expect(itemKey(advisory())).not.toBe(itemKey(check))
    expect(itemTone(advisory())).toBe('critical')
    expect(itemTone(advisory({ severity: 'WARNING' }))).toBe('warning')
    expect(itemTone(advisory({ severity: 'INFO' }))).toBe('info')
    expect(itemTone(check)).toBe('scheduled')
    expect(itemDetail(check)).toBe(check.detail_en)
  })

  it('routes to the guide protocol and the right capture tab', () => {
    expect(guideRoute('wiki-vision-01')).toBe('/guide?article=wiki-vision-01')
    expect(guideRoute(null)).toBe('/guide')
    expect(captureRoute('OCULAR_EXAM')).toBe('/capture/vision')
    expect(captureRoute('VITALS_CHECK')).toBe('/capture/physical')
    expect(captureRoute('UNKNOWN')).toBe('/capture/physical')
  })

  it('selects the first open advisory before anything else', () => {
    const read = advisory({ id: 2, acknowledged_at_utc: '2026-11-15T10:00:00Z' })
    const open = advisory({ id: 3, severity: 'WARNING' })
    expect(defaultSelection([check, read, open])).toBe(open)
    expect(defaultSelection([check])).toBe(check)
    expect(defaultSelection([])).toBeNull()
  })
})
