import type { components, paths } from '~/types/api'

export type SleepMonitorOut
  = paths['/api/v1/sleep/{crew_id}']['get']['responses'][200]['content']['application/json']

export type SleepSessionCreateIn = components['schemas']['SleepSessionCreateIn']
export type SleepSessionCreatedOut
  = paths['/api/v1/sleep/sessions']['post']['responses'][201]['content']['application/json']

export type SleepPeriodFilter = 'last_night' | '7d' | '14d' | '30d'
export type SleepStageCard = components['schemas']['SleepStageCardOut']
export type SleepStageLapseRow = components['schemas']['SleepStageLapseRowOut']

export function useSleep() {
  const { activeCrew, authHeaders } = useSession()

  const selectedPeriod = ref<SleepPeriodFilter>('last_night')
  const monitor = ref<SleepMonitorOut | null>(null)
  const isLoading = ref(true)
  const errorMessage = ref('')

  const effectiveCrewId = computed(() => activeCrew.value?.id ?? 'ID-01')

  async function loadSleepMonitor() {
    isLoading.value = true
    errorMessage.value = ''
    try {
      const data = await $fetch<SleepMonitorOut>(
        `/api/v1/sleep/${encodeURIComponent(effectiveCrewId.value)}`,
        {
          query: { period: selectedPeriod.value },
          headers: authHeaders(),
        },
      )
      monitor.value = data
    }
    catch {
      errorMessage.value = 'Unable to load sleep architecture telemetry from local storage.'
    }
    finally {
      isLoading.value = false
    }
  }

  async function createSleepSession(payload: SleepSessionCreateIn): Promise<SleepSessionCreatedOut> {
    return await $fetch<SleepSessionCreatedOut>('/api/v1/sleep/sessions', {
      method: 'POST',
      headers: authHeaders(),
      body: payload,
    })
  }

  watch([effectiveCrewId, selectedPeriod], () => {
    void loadSleepMonitor()
  })

  return {
    monitor,
    selectedPeriod,
    effectiveCrewId,
    isLoading,
    errorMessage,
    loadSleepMonitor,
    createSleepSession,
  }
}
