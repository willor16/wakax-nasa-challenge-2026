import { describe, expect, it } from 'vitest'
import type { GuideArticle, KitDrawer } from '../app/utils/guide'
import {
  activeDrawer,
  displayText,
  isPoweredStatus,
  physicianSuffix,
  stepNumber,
} from '../app/utils/guide'

const drawers: KitDrawer[] = [
  { code: 'DRAWER A1', name_en: 'Airway & Oxygen', items: [] },
  { code: 'DRAWER B2', name_en: 'Diagnostics & Relief', items: [] },
]

const article: GuideArticle = {
  id: 'wiki-co2-01',
  category_en: 'CO2 Exposure',
  title_en: 'Elevated Cabin CO2 Headache & Fatigue Protocol',
  drawer_code: 'DRAWER B2',
  steps: [{ title_en: 'Check Local Airflow', detail_en: 'Verify airflow.' }],
  escalation_en: 'Escalate if CO2 exceeds 4000 ppm.',
  source_en: null,
}

describe('Medical guide helpers', () => {
  it('numbers steps like the design badges', () => {
    expect(stepNumber(0)).toBe('01')
    expect(stepNumber(11)).toBe('12')
  })

  it('shows CO2 with a subscript only as a whole word', () => {
    expect(displayText('CO2 Exposure')).toBe('CO₂ Exposure')
    expect(displayText('ECO22 code')).toBe('ECO22 code')
  })

  it('colors charge readings and names the physician', () => {
    expect(isPoweredStatus('Charged 100%')).toBe(true)
    expect(isPoweredStatus('Battery 100%')).toBe(true)
    expect(isPoweredStatus('24 strips')).toBe(false)
    expect(physicianSuffix('Amara Okafor')).toBe(' (DR. OKAFOR)')
    expect(physicianSuffix(null)).toBe('')
  })

  it('highlights the open protocol drawer, else the first one', () => {
    expect(activeDrawer(article, drawers)).toBe('DRAWER B2')
    expect(activeDrawer(null, drawers)).toBe('DRAWER A1')
    expect(activeDrawer(null, [])).toBeNull()
  })
})
