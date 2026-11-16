// The change stamps decide which screens reload after a saved entry.
import { describe, expect, it } from 'vitest'
import { domainsForPath, knownDomains } from '../app/composables/useDataSync'

describe('data sync domains', () => {
  it('maps each saved entry to the screens that show it', () => {
    expect(domainsForPath('/measurements')).toEqual(['vitals', 'vision', 'alerts', 'streaks'])
    expect(domainsForPath('/psych/checkins')).toEqual(['psych', 'sleep', 'alerts', 'streaks'])
    expect(domainsForPath('/auscultation/samples')).toEqual(['auscultation', 'alerts'])
    expect(domainsForPath('/alerts/12/acknowledge')).toEqual(['alerts'])
    expect(domainsForPath('/diagnosis/4/review')).toEqual(['alerts'])
    expect(domainsForPath('/comms/packets')).toEqual(['alerts'])
  })

  it('ignores paths that change no crew data', () => {
    expect(domainsForPath('/auth/login')).toEqual([])
    expect(domainsForPath('/mission/stage')).toEqual([])
  })

  it('keeps only known domains from the live stream', () => {
    expect(knownDomains(['vitals', 'unknown', 'alerts'])).toEqual(['vitals', 'alerts'])
    expect(knownDomains('vitals')).toEqual([])
  })
})
