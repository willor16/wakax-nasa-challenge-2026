// Medical guide screen (14) helpers: API types and pure display rules.

export interface GuideStep {
  title_en: string
  detail_en: string
}

export interface GuideArticle {
  id: string
  category_en: string
  title_en: string
  drawer_code: string
  steps: GuideStep[]
  escalation_en: string
  source_en: string | null
}

export interface GuideSearchResponse {
  query: string
  category: string | null
  categories: string[]
  results: GuideArticle[]
}

export interface EmergencyItem {
  id: string
  category_en: string
  title_en: string
  drawer_code: string
  escalation_en: string
}

export interface KitItem {
  slot_code: string
  name_en: string
  status_en: string
}

export interface KitDrawer {
  code: string
  name_en: string
  items: KitItem[]
}

/** "01", "02"... as on the protocol step badges. */
export function stepNumber(index: number): string {
  return String(index + 1).padStart(2, '0')
}

/** Medical words shown with a proper subscript on screen: "CO2" -> "CO₂". */
export function displayText(text: string): string {
  return text.replace(/\bCO2\b/g, 'CO₂')
}

/** Charge or battery readings are shown in the "ready" color. */
export function isPoweredStatus(status: string): boolean {
  return /^(charged|battery)\b/i.test(status)
}

/** " (DR. OKAFOR)" from the physician's full name, or nothing if unknown. */
export function physicianSuffix(fullName: string | null | undefined): string {
  const last = fullName?.trim().split(/\s+/).at(-1)
  return last ? ` (DR. ${last.toUpperCase()})` : ''
}

/** Drawer to highlight: the open protocol's drawer, else the first drawer. */
export function activeDrawer(article: GuideArticle | null, drawers: KitDrawer[]): string | null {
  return article?.drawer_code ?? drawers[0]?.code ?? null
}
