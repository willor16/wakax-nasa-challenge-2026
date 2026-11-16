// M9 contract: the physician's patient switch is made of buttons only and every results
// screen follows the active patient; capture screens keep recording for the signed-in crew
// member; the pilot panel and the clinical record are read-only on results screens; the
// ground console lives inside /comms and never keeps the link key.
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const APP = resolve(import.meta.dirname, '../app')
const read = (path: string) => readFileSync(resolve(APP, path), 'utf8')

describe('physician patient switch', () => {
  const bar = read('components/shell/TopTelemetryBar.vue')
  it('is built from buttons only', () => {
    expect(bar).toMatch(/v-for="p in patients"[\s\S]*?@click="setActivePatient\(p\.id\)"/)
    expect(bar).toContain('aria-pressed')
    expect(bar).not.toMatch(/<select|<input/)
  })

  it('drives every results screen', () => {
    for (const file of ['composables/useProfile.ts', 'pages/vision.vue', 'pages/sleep.vue', 'pages/auscultation.vue',
      'pages/profile/streak.vue', 'pages/profile/psychological.vue']) {
      const source = read(file)
      expect(source, file).toContain('activePatientId')
      expect(source, file).not.toMatch(/crew\.value!\.id/)
    }
    expect(read('composables/useApi.ts')).toMatch(/watch\(activePatientId/)
  })

  it('keeps capture screens on the signed-in crew member', () => {
    for (const file of ['pages/capture/physical.vue', 'pages/capture/vision.vue', 'pages/capture/psych-sleep.vue',
      'pages/capture/auscultation.vue', 'composables/useCatalog.ts']) {
      expect(read(file), file).not.toContain('activePatientId')
    }
  })
})

describe('role panels', () => {
  it('shows the pilot panel only for a pilot subject', () => {
    expect(read('pages/profile/psychological.vue')).toMatch(/activePatient\?\.role === 'PILOT'[\s\S]*RolesPilotReadinessPanel/)
    const panel = read('components/roles/PilotReadinessPanel.vue')
    expect(panel).not.toMatch(/<input|<select|method: 'POST'/)
    expect(panel).toContain('pilot-readiness')
  })

  it('opens the clinical record for the physician only', () => {
    expect(read('pages/profile/personal.vue')).toMatch(/v-if="recordOpen && isPhysician"/)
    expect(read('components/roles/PhysicianPatientHistory.vue')).toMatch(/role="dialog" aria-modal="true"/)
  })
})

describe('ground station console', () => {
  const consoleSource = read('components/roles/GroundControlConsole.vue')
  it('exchanges the link key for a session and never stores the key', () => {
    expect(consoleSource).toContain('/ground/session')
    expect(consoleSource).toMatch(/linkKey\.value = ''/)
    expect(consoleSource).not.toMatch(/setItem\([^)]*linkKey/)
  })

  it('opens from the sign-in screen inside /comms', () => {
    expect(read('pages/login.vue')).toMatch(/station: 'ground'/)
    expect(read('pages/comms.vue')).toContain('RolesGroundControlConsole')
    expect(read('middleware/auth.global.ts')).toMatch(/to\.query\.station === 'ground'/)
  })
})
