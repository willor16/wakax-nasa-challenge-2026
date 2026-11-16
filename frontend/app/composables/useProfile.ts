// Read-only crew profile for the Personal Data and Physical screens.
import type { CabinSnapshot } from '~/composables/useMission'
import type { StatusCode } from '~/utils/format'

export interface MetricView {
  metric_key: string
  label: string
  unit: string
  value: number | null
  value_secondary?: number | null
  status: StatusCode
  status_text: string
  is_above?: boolean
  recorded_at_utc?: string | null
  day_label?: string | null
  baseline_mean?: number | null
  baseline_secondary?: number | null
  baseline_low?: number | null
  baseline_high?: number | null
  baseline_pct?: number | null
  nominal_min?: number | null
  nominal_max?: number | null
  scale_min?: number | null
  scale_max?: number | null
  target?: number | null
  reference_low?: number
  reference_high?: number
  stages?: Record<'LAUNCH' | 'MISSION' | 'RETURN', number | null>
  title?: string
  note?: string | null
  value_text?: string | null
  /** Skeletal muscle index (muscle mass card only), judged against the sex limit. */
  smi?: { value: number, min: number, dxa_min: number, status: StatusCode } | null
}

export interface CrewProfile {
  crew: { id: string, code: string, full_name: string, short_name: string, title_en: string
    role: string, age: number | null, sex: string | null, blood_type: string | null }
  /** ``Female ranges`` / ``Male ranges``. */
  reference_profile_en: string
  mission_stage: 'LAUNCH' | 'MISSION' | 'RETURN'
  mission_day: number | null
  habits_day_label: string
  status: string
  biometrics: MetricView[]
  scan: { core_temp: MetricView, hydration_ml: number | null, hydration_target_ml: number }
  environment: CabinSnapshot | null
  work: { interior_min: number | null, interior_location_en: string | null, exterior_min: number
    exterior_mission_min: number, mission_elapsed_days: number | null }
  daily: MetricView[]
  on_target: number
  daily_count: number
  ecg: null | { lead: string, paper_speed_mm_s: number, sample_rate_hz: number, samples: number[]
    recorded_at_utc: string, heart_rate_bpm: number | null, rhythm_text: string, hrv_ms: number | null
    body_temp_c: number | null }
  labs: MetricView[]
}

export function useProfile(refreshMs = 30_000) {
  const { crew } = useSession()
  const { api } = useApi()
  return useResource(() => api<CrewProfile>(`/crew/${crew.value!.id}/profile`), refreshMs,
    ['vitals', 'vision', 'sleep', 'psych', 'auscultation', 'alerts', 'streaks'])
}
