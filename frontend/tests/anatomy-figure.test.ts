// Whole-body figures follow the crew member's sex everywhere they appear.
import { readFileSync } from 'node:fs'
import { join, resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const APP = join(resolve(import.meta.dirname, '..'), 'app')
const HOLO = join(APP, 'assets/hologram')
const viewBox = (svg: string) => svg.match(/viewBox="([^"]+)"/)?.[1]

describe('anatomical figure by sex', () => {
  it('ships a female version of each body figure on the same canvas', () => {
    for (const name of ['body_small', 'body_scan']) {
      const male = readFileSync(join(HOLO, `${name}.svg`), 'utf-8')
      const female = readFileSync(join(HOLO, `${name}_f.svg`), 'utf-8')
      expect(female.startsWith('<svg'), name).toBe(true)
      expect(viewBox(female), name).toBe(viewBox(male))
      expect(female, name).not.toMatch(/<text/)
      expect(female, name).not.toBe(male)
    }
  })

  it('picks the figure from the sex on every screen that draws a body', () => {
    const figure = readFileSync(join(APP, 'components/ui/HoloFigure.vue'), 'utf-8')
    expect(figure).toContain('body_small_f.svg')
    expect(figure).toContain('body_scan_f.svg')
    for (const page of ['pages/login.vue', 'pages/crew-overview.vue', 'pages/profile/personal.vue']) {
      const source = readFileSync(join(APP, page), 'utf-8')
      for (const use of source.match(/<UiHoloFigure[\s\S]*?\/>/g) ?? []) {
        if (/figure="body(-scan)?"/.test(use)) expect(use, page).toMatch(/:sex="/)
      }
    }
  })
})
