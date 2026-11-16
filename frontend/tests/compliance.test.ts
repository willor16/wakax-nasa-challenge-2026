// Project rules checked on every run: palette tokens only, plain English without internal
// technology names or restricted names, no external network calls, and the screen map.
import { existsSync, readdirSync, readFileSync } from 'node:fs'
import { join, relative, resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const ROOT = resolve(import.meta.dirname, '..')
const APP = join(ROOT, 'app')

function files(dir: string, ...exts: string[]): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const full = join(dir, entry.name)
    if (entry.isDirectory()) return files(full, ...exts)
    return exts.some(ext => entry.name.endsWith(ext)) ? [full] : []
  })
}

const vueFiles = files(APP, '.vue')
const codeFiles = [...vueFiles, ...files(APP, '.ts'), join(ROOT, 'i18n/locales/en.ts'), join(ROOT, 'nuxt.config.ts')]
const restricted = [atob('bmFzYQ=='), atob('Y2hpbmE='), atob('Y2hpbmVzZQ==')]

/** Project-relative path with forward slashes, so results read the same on Windows and Linux. */
function rel(from: string, file: string): string {
  return relative(from, file).replaceAll('\\', '/')
}

/** Text a crew member can see: template content and quoted strings, comments removed. */
function visibleText(source: string): string {
  return source
    .replace(/<!--[\s\S]*?-->/g, '')
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .replace(/^\s*\/\/.*$/gm, '')
}

describe('palette', () => {
  it('defines the six official colors in the token file', () => {
    const css = readFileSync(join(APP, 'assets/css/tokens.css'), 'utf-8')
    for (const hex of ['#001524', '#15616D', '#FFECD1', '#2AEF4B', '#000C5C', '#D5110B']) expect(css).toContain(hex)
  })

  it('uses no raw color codes outside the token file', () => {
    for (const file of codeFiles) {
      const source = readFileSync(file, 'utf-8')
      expect(source, rel(ROOT, file)).not.toMatch(/#[0-9a-fA-F]{6}\b|#[0-9a-fA-F]{3}\b(?![\w-])|rgba?\(/)
    }
  })

  it('uses no default framework colors', () => {
    const defaults = /\b(?:bg|text|border)-(?:gray|slate|zinc|red|blue|green|yellow|white|black)-?\d*\b/
    for (const file of vueFiles) expect(readFileSync(file, 'utf-8'), rel(ROOT, file)).not.toMatch(defaults)
  })
})

describe('language and restricted words', () => {
  const jargon = /\b(sqlite|json|fhir|hl7|kiwix|zim|fts5|wal|offline|break-glass|dtn|osdr|donki|onnx|ollama|nuxt|python|cnn|llm|neural|autoencoder)\b/i

  it('shows no internal technology names on screen', () => {
    for (const file of [...vueFiles, join(ROOT, 'i18n/locales/en.ts')]) {
      const template = readFileSync(file, 'utf-8').split('<template>').slice(1).join('<template>')
      expect(visibleText(template), rel(ROOT, file)).not.toMatch(jargon)
    }
  })

  it('never names restricted entities anywhere in the app', () => {
    const pattern = new RegExp(`\\b(${restricted.join('|')})\\b`, 'i')
    for (const file of codeFiles) expect(readFileSync(file, 'utf-8'), rel(ROOT, file)).not.toMatch(pattern)
  })

  it('carries no retired mission identity', () => {
    for (const file of codeFiles) expect(readFileSync(file, 'utf-8'), rel(ROOT, file)).not.toMatch(/ares[\s_-]*vii/i)
  })

  it('declares the page as English and blocks browser auto-translation', () => {
    const config = readFileSync(join(ROOT, 'nuxt.config.ts'), 'utf-8')
    expect(config).toContain('lang: \'en\'')
    expect(config).toContain('translate: \'no\'')
    expect(config).toContain('notranslate')
  })

  it('contains no Spanish words in code or text', () => {
    const spanish = /\b(?:usuario|guardar|fecha|paciente|sueño|tripulante|medición|configuración|pantalla|botón|también|está)\b|[ñáéíóú¿¡]/i
    for (const file of codeFiles) expect(readFileSync(file, 'utf-8'), rel(ROOT, file)).not.toMatch(spanish)
  })

  it('keeps the interface catalog in a TypeScript file only', () => {
    expect(existsSync(join(ROOT, 'i18n/locales/en.ts'))).toBe(true)
    expect(readdirSync(join(ROOT, 'i18n/locales')).filter(f => f.endsWith('.json'))).toEqual([])
  })
})

describe('works fully on board', () => {
  it('loads nothing from outside the habitat', () => {
    const external = /https?:\/\/(?!localhost|127\.0\.0\.1)[\w.-]+/
    for (const file of [...codeFiles, join(APP, 'assets/css/tokens.css')]) {
      expect(readFileSync(file, 'utf-8'), rel(ROOT, file)).not.toMatch(external)
    }
  })

  it('bundles the fonts and the icon set locally', () => {
    for (const font of ['Inter-Regular.woff2', 'JetBrainsMono-Medium.woff2', 'JetBrainsMono-Bold.woff2']) {
      expect(existsSync(join(ROOT, 'public/fonts', font)), font).toBe(true)
    }
    const config = readFileSync(join(ROOT, 'nuxt.config.ts'), 'utf-8')
    expect(config).toContain('provider: \'none\'')
    for (const icon of ['rocket', 'sans', 'moon', 'stethoscope', 'profile', 'capture', 'wiki', 'earth', 'bell', 'mic',
      'lock', 'flame', 'vitruvian', 'reticle', 'kit', 'shield']) {
      expect(existsSync(join(APP, 'assets/icons/spacescan', `${icon}.svg`)), icon).toBe(true)
    }
  })
})

describe('delivered build', () => {
  const output = join(ROOT, '.output/public')
  it.skipIf(!existsSync(output))('carries no restricted names and no build-machine paths', () => {
    const pattern = new RegExp(`\\b(${restricted.join('|')})\\b`, 'i')
    const baseUrl = process.env.NUXT_APP_BASE_URL?.replace(/^\/+|\/+$/g, '') ?? ''
    for (const file of files(output, '.html', '.js', '.css')) {
      const content = readFileSync(file, 'utf-8')
      const scrubbed = baseUrl ? content.split(baseUrl).join('') : content
      expect(scrubbed, rel(ROOT, file)).not.toMatch(pattern)
      for (const form of new Set([ROOT, ROOT.replaceAll('\\', '/')])) expect(content, rel(ROOT, file)).not.toContain(form)
    }
  })
})

describe('screen map', () => {
  it('has the 16 design screens plus the operator administration', () => {
    const pages = files(join(APP, 'pages'), '.vue').map(f => rel(join(APP, 'pages'), f)).sort()
    expect(pages).toEqual([
      'auscultation.vue', 'capture/auscultation.vue', 'capture/physical.vue', 'capture/psych-sleep.vue',
      'capture/vision.vue', 'comms.vue', 'crew-management.vue', 'crew-overview.vue', 'crew-streaks.vue', 'guide.vue',
      'index.vue', 'login.vue', 'notifications.vue', 'profile/personal.vue', 'profile/physical.vue',
      'profile/psychological.vue', 'profile/streak.vue', 'sleep.vue', 'vision.vue',
    ])
  })

  it('keeps every input on the capture screens (results screens are read-only)', () => {
    const resultScreens = ['profile/personal.vue', 'profile/physical.vue', 'profile/psychological.vue', 'profile/streak.vue', 'sleep.vue',
      'vision.vue', 'auscultation.vue', 'crew-overview.vue', 'crew-streaks.vue']
    for (const page of resultScreens) {
      const source = readFileSync(join(APP, 'pages', page), 'utf-8')
      expect(source, page).not.toMatch(/<input|<textarea|<select|method: 'POST'/)
    }
  })

  it('draws the body without an animated scanner sweep', () => {
    for (const file of [...vueFiles, join(APP, 'assets/css/tokens.css')]) {
      expect(readFileSync(file, 'utf-8'), rel(ROOT, file)).not.toMatch(/scanline|scan-sweep/)
    }
  })

  it('puts the seven dock modules in order with Profile in the centre', () => {
    const dock = readFileSync(join(APP, 'components/shell/BottomCockpitDock.vue'), 'utf-8')
    const order = [...dock.matchAll(/label: 'nav\.(\w+)'/g)].map(m => m[1])
    expect(order).toEqual(['vision', 'sleep', 'auscultation', 'profile', 'capture', 'guide', 'comms'])
    expect(dock).not.toContain('notifications')
  })

  it('redirects the root page declaratively', () => {
    const index = readFileSync(join(APP, 'pages/index.vue'), 'utf-8')
    expect(index).toContain('redirect: \'/login\'')
    for (const file of vueFiles) expect(readFileSync(file, 'utf-8'), rel(ROOT, file)).not.toMatch(/^await navigateTo/m)
  })
})
