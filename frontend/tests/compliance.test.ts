import { readdirSync, readFileSync } from 'node:fs'
import { join, resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const FRONTEND_ROOT = resolve(import.meta.dirname, '..')
const APP_DIR = join(FRONTEND_ROOT, 'app')

function collectFiles(dir: string, ext: string): string[] {
  const entries = readdirSync(dir, { withFileTypes: true })
  const files: string[] = []
  for (const entry of entries) {
    const full = join(dir, entry.name)
    if (entry.isDirectory()) {
      files.push(...collectFiles(full, ext))
    }
    else if (entry.name.endsWith(ext)) {
      files.push(full)
    }
  }
  return files
}

describe('SpaceScan UI & Regulatory Compliance', () => {
  it('defines all 6 official palette colors in tokens.css', () => {
    const css = readFileSync(join(APP_DIR, 'assets/css/tokens.css'), 'utf-8')
    for (const hex of ['#001524', '#15616D', '#FFECD1', '#2AEF4B', '#000C5C', '#D5110B']) {
      expect(css).toContain(hex)
    }
  })

  it('contains zero raw hex literals in Vue components and pages', () => {
    const vueFiles = collectFiles(APP_DIR, '.vue')
    for (const file of vueFiles) {
      const content = readFileSync(file, 'utf-8')
      expect(content).not.toMatch(/#[0-9a-fA-F]{3,8}\b/)
    }
  })

  it('contains zero forbidden entities or internal tech jargon in UI files', () => {
    const uiFiles = [
      ...collectFiles(APP_DIR, '.vue'),
      join(APP_DIR, 'locales/en.ts'),
      join(FRONTEND_ROOT, 'i18n/locales/en.ts'),
    ]
    const restrictedEntities = [atob('bmFzYQ=='), atob('Y2hpbmE=')]
    const entityPattern = new RegExp(`\\b(${restrictedEntities.join('|')})\\b`, 'i')
    const jargon = /\b(sqlite|json|fhir|hl7|kiwix|zim|fts5|wal|offline|break-glass|dtn|osdr|donki|onnx|ollama|nuxt|python)\b/i
    for (const file of uiFiles) {
      const content = readFileSync(file, 'utf-8')
      expect(content).not.toMatch(entityPattern)
      expect(content).not.toMatch(jargon)
    }
  })
})
