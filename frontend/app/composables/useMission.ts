// Mission clock, cabin environment and cabin alert mode, shared by every screen.
// The cabin values arrive on the public live stream; the clock follows the
// onboard server time so every display in the cabin shows the same minute.
import { knownDomains, useDataSync } from '~/composables/useDataSync'

export interface CabinSnapshot {
  location_en: string
  recorded_at_utc: string
  temp_c: number
  humidity_pct: number
  noise_dba: number
  co2_ppm: number
  co2_mmhg: number
  radiation_msv_day: number
  radiation_mission_msv: number
  radiation_yearly_limit_msv: number
  kp_index: number | null
  solar_event: boolean
  status: StatusCode
  statuses: Record<string, StatusCode>
  limits: {
    temp_c: [number, number]
    humidity_pct: [number, number]
    noise_dba_max: number
    co2_mmhg: { target: number, alert: number, physician: number }
    radiation_msv_day_max: number
  }
}

interface MissionSummary {
  mission: { launch_utc: string, mission_code: string, earth_latency_min: number
    quiet_hours_start_utc: string, quiet_hours_end_utc: string, current_stage: string } | null
  mission_day: number | null
  cabin: CabinSnapshot | null
  cabin_mode: 'nominal' | 'critical'
  server_utc: string
}

export function useMission() {
  const summary = useState<MissionSummary | null>('mission-summary', () => null)
  const offsetMs = useState('mission-clock-offset', () => 0)
  const now = useState('mission-now', () => Date.now())
  const unread = useState('mission-unread', () => 0)
  const base = useRuntimeConfig().public.apiBase.replace(/\/+$/, '')

  const cabin = computed(() => summary.value?.cabin ?? null)
  const cabinMode = computed(() => summary.value?.cabin_mode ?? 'nominal')
  const mission = computed(() => summary.value?.mission ?? null)

  const missionDay = computed(() => {
    const launch = summary.value?.mission?.launch_utc
    if (!launch) return summary.value?.mission_day ?? null
    const start = Date.UTC(
      new Date(launch).getUTCFullYear(), new Date(launch).getUTCMonth(), new Date(launch).getUTCDate(),
    )
    return Math.floor((now.value - start) / 86_400_000) + 1
  })

  const clockText = computed(() => formatClock(missionDay.value, now.value))

  function apply(next: Partial<MissionSummary>) {
    summary.value = { ...(summary.value ?? { mission: null, mission_day: null, cabin: null,
      cabin_mode: 'nominal', server_utc: '' }), ...next } as MissionSummary
    if (next.server_utc) offsetMs.value = new Date(next.server_utc).getTime() - Date.now()
    if (import.meta.client) document.documentElement.dataset.cabinMode = cabinMode.value
  }

  async function load() {
    try {
      apply(await $fetch<MissionSummary>(`${base}/api/v1/mission`))
    }
    catch {
      // The header simply keeps its last known values until the next update.
    }
  }

  return { summary, cabin, cabinMode, mission, missionDay, clockText, now, offsetMs, unread, apply, load }
}

/** Starts the shared clock and the public cabin stream; call once from the layout. */
export function useMissionFeed() {
  const { apply, load, now, offsetMs, unread } = useMission()
  const { isAuthenticated } = useSession()
  const { api } = useApi()
  const { bump, signature } = useDataSync()
  const base = useRuntimeConfig().public.apiBase.replace(/\/+$/, '')
  let stream: EventSource | null = null
  let clock: ReturnType<typeof setInterval> | null = null
  let badge: ReturnType<typeof setInterval> | null = null

  async function loadUnread() {
    if (!isAuthenticated.value) {
      unread.value = 0
      return
    }
    try {
      const result = await api<{ counts: { advisories: number } }>('/alerts', { query: { view: 'advisories' } })
      unread.value = result.counts.advisories
    }
    catch {
      // Keep the last count; the next refresh will correct it.
    }
  }

  onMounted(() => {
    void load()
    void loadUnread()
    clock = setInterval(() => {
      now.value = Date.now() + offsetMs.value
    }, 1000)
    badge = setInterval(() => void loadUnread(), 20_000)
    stream = new EventSource(`${base}/api/v1/stream/telemetry`)
    stream.addEventListener('cabin', (event) => {
      try {
        apply(JSON.parse((event as MessageEvent<string>).data))
      }
      catch {
        // A damaged frame is skipped; the next one arrives in two seconds.
      }
    })
    // Another display saved something: reload the screens that show that kind of data.
    stream.addEventListener('sync', (event) => {
      try {
        bump(...knownDomains(JSON.parse((event as MessageEvent<string>).data).domains))
      }
      catch {
        // Skipped; screens still refresh on their own timers.
      }
    })
  })
  onBeforeUnmount(() => {
    stream?.close()
    if (clock) clearInterval(clock)
    if (badge) clearInterval(badge)
  })
  watch(isAuthenticated, () => void loadUnread())
  watch(signature(['alerts']), () => void loadUnread())

  return { loadUnread }
}
