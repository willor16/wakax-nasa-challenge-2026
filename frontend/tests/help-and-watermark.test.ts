// Every "?" button points at a parameter that has help text, and the AI mark reads "AI Used".
import { readdirSync, readFileSync } from 'node:fs'
import { join, resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const ROOT = resolve(import.meta.dirname, '..')
const APP = join(ROOT, 'app')
const REFERENCE = join(ROOT, '../backend/db/seed_snapshots/reference_ranges.json')

function vueFiles(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const full = join(dir, entry.name)
    if (entry.isDirectory()) return vueFiles(full)
    return entry.name.endsWith('.vue') ? [full] : []
  })
}

const reference = JSON.parse(readFileSync(REFERENCE, 'utf-8')) as {
  metrics: { metric_key: string }[]
  help_topics: { key: string }[]
}
const helpKeys = new Set([...reference.metrics.map(m => m.metric_key), ...reference.help_topics.map(t => t.key)])

/** Literal help keys used on screen (attributes, row tables and key maps). */
function usedKeys(source: string): string[] {
  const found = [
    ...source.matchAll(/(?:metric-key|help-key)="([a-z0-9_]+)"/g),
    ...source.matchAll(/\bhelp: '([a-z0-9_]+)'/g),
    ...source.matchAll(/_HELP[^=]*=\s*\{([^}]*)\}/g).flatMap(m => [...m[1]!.matchAll(/:\s*'([a-z0-9_]+)'/g)]),
  ]
  return found.map(m => m[1]!)
}

describe('parameter help', () => {
  it('only points at parameters that have help text', () => {
    let total = 0
    for (const file of vueFiles(APP)) {
      for (const key of usedKeys(readFileSync(file, 'utf-8'))) {
        total += 1
        expect(helpKeys.has(key), `${file.replace(ROOT, '')}: ${key}`).toBe(true)
      }
    }
    expect(total).toBeGreaterThan(40)
  })

  it('uses a button (never a form field) so read-only screens stay read-only', () => {
    const source = readFileSync(join(APP, 'components/ui/ParamHelp.vue'), 'utf-8')
    expect(source).toContain('type="button"')
    expect(source).not.toMatch(/<input|<textarea|<select|method: 'POST'/)
  })
})

describe('assisted-analysis mark', () => {
  it('reads "AI Used" in plain English', () => {
    const locale = readFileSync(join(ROOT, 'i18n/locales/en.ts'), 'utf-8')
    expect(locale).toContain('used: \'AI Used\'')
    expect(readFileSync(join(APP, 'components/ui/AiWatermark.vue'), 'utf-8')).toContain('t(\'ai.used\')')
  })

  it('never shows the Spanish abbreviation on screen', () => {
    for (const file of vueFiles(APP)) {
      const template = readFileSync(file, 'utf-8').split('<template>').slice(1).join('')
      expect(template, file.replace(ROOT, '')).not.toMatch(/>[^<]*\bIA\b[^<]*</)
    }
  })

  it('marks every place that shows assisted results or generated artwork', () => {
    for (const page of ['pages/notifications.vue', 'pages/guide.vue', 'components/ui/HoloFigure.vue']) {
      expect(readFileSync(join(APP, page), 'utf-8'), page).toContain('<UiAiWatermark')
    }
  })
})
