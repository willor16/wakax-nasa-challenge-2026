import type { components, paths } from '~/types/api'

export type CrewProfileOut
  = paths['/api/v1/crew/{crew_id}/profile']['get']['responses'][200]['content']['application/json']

export type ProfileStageFilter = 'ALL' | 'LAUNCH' | 'MISSION' | 'RETURN'
export type BiometricCard = components['schemas']['BiometricCardOut']
export type ClinicalProgressItem = components['schemas']['ClinicalProgressItemOut']
export type ClinicalLabCard = components['schemas']['ClinicalLabCardOut']

export function useCrewProfile() {
  const { activeCrew, authHeaders, setCabinMode } = useSession()

  const selectedStage = ref<ProfileStageFilter>('ALL')
  const profile = ref<CrewProfileOut | null>(null)
  const isLoading = ref(true)
  const errorMessage = ref('')

  const effectiveCrewId = computed(() => activeCrew.value?.id ?? 'ID-01')

  async function loadProfile() {
    isLoading.value = true
    errorMessage.value = ''
    try {
      const query = selectedStage.value === 'ALL'
        ? undefined
        : { stage: selectedStage.value }
      const data = await $fetch<CrewProfileOut>(
        `/api/v1/crew/${encodeURIComponent(effectiveCrewId.value)}/profile`,
        {
          query,
          headers: authHeaders(),
        },
      )
      profile.value = data
    }
    catch {
      errorMessage.value = 'Unable to load crew biometric telemetry from local storage.'
    }
    finally {
      isLoading.value = false
    }
  }

  function openTelemetryStream(onTick?: () => void): () => void {
    if (!import.meta.client || typeof EventSource === 'undefined') {
      return () => {}
    }

    const url = `/api/v1/stream/telemetry?crew_id=${encodeURIComponent(effectiveCrewId.value)}`
    const source = new EventSource(url)

    source.addEventListener('cabin', (evt: MessageEvent<string>) => {
      try {
        const parsed = JSON.parse(evt.data) as {
          cabin?: {
            co2_ppm: number
            noise_dba: number
            temp_c: number
            humidity_pct: number
            radiation_msv: number
          } | null
          cabin_mode?: 'nominal' | 'critical'
        }
        if (parsed.cabin_mode) {
          setCabinMode(parsed.cabin_mode)
        }
        if (parsed.cabin && profile.value) {
          const co2Mmhg = Number(((parsed.cabin.co2_ppm / 1_000_000) * 760).toFixed(2))
          profile.value.environment_work.co2_ppm = parsed.cabin.co2_ppm
          profile.value.environment_work.co2_mmhg = co2Mmhg
          for (const g of profile.value.environment_work.gauges) {
            if (g.key === 'temp_c') {
              g.display_value = parsed.cabin.temp_c.toFixed(1)
            }
            else if (g.key === 'humidity_pct') {
              g.display_value = `${Math.round(parsed.cabin.humidity_pct)}%`
            }
            else if (g.key === 'noise_dba') {
              g.display_value = `${Math.round(parsed.cabin.noise_dba)}`
            }
            else if (g.key === 'co2_mmhg') {
              g.display_value = co2Mmhg.toFixed(1)
            }
          }
        }
        onTick?.()
      }
      catch {
        return
      }
    })

    return () => {
      source.close()
    }
  }

  watch([effectiveCrewId, selectedStage], () => {
    void loadProfile()
  })

  return {
    profile,
    selectedStage,
    effectiveCrewId,
    isLoading,
    errorMessage,
    loadProfile,
    openTelemetryStream,
  }
}
