// M8 contract of the medical guide screen: the protocol list is always on screen, the
// first protocol (or the one a notification asked for) opens by itself, search reacts while
// typing, protocols made during the mission are labelled, and only the physician can add one.
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const page = readFileSync(resolve(import.meta.dirname, '../app/pages/guide.vue'), 'utf8')
const template = page.slice(page.indexOf('<template>'))
const script = page.slice(0, page.indexOf('<template>'))

describe('medical guide screen', () => {
  it('always lists the protocols and opens one on arrival', () => {
    expect(template).toMatch(/v-for="item in results"/)
    expect(template).toContain('aria-label="Protocols"')
    expect(script).toMatch(/route\.query\.article/)
    expect(script).toMatch(/else \{\s*await search\(\)\s*\}/) // no words: first protocol opens
  })

  it('searches while typing after a short pause', () => {
    expect(script).toMatch(/watch\(query/)
    expect(script).toMatch(/setTimeout\(\(\) => void search\(\), 200\)/)
  })

  it('labels mission protocols and marks assisted ones', () => {
    expect(template).toContain('MISSION PROTOCOL')
    expect(template).toMatch(/<UiAiWatermark v-if="article\.assisted"/)
    expect(script).toContain('Mission-Validated')
  })

  it('offers the protocol form to the physician only, as a modal dialog', () => {
    expect(template).toMatch(/v-if="isPhysician"[^>]*@click="startProtocol"/)
    expect(template).toMatch(/role="dialog" aria-modal="true"/)
    expect(script).toContain("'/wiki/articles', { method: 'POST'")
  })

  it('keeps the 30 second drawer light', () => {
    expect(script).toContain('30_000')
  })
})
