import type {
  ClinicalLabsInput,
  DailyVitalsHabitsInput,
  OcularCaptureInput,
} from '../schemas/capture'
import { normalizeSnellen, parseWorkShiftMinutes, snellenToLogMar } from '../schemas/capture'
import type { components } from '../types/api'

export type MetricCatalogItem = components['schemas']['MetricCatalogItem']
export type MetricCategory = MetricCatalogItem['category']
export type MeasurementItemIn = components['schemas']['MeasurementItemIn']
export type MeasurementBatchIn = components['schemas']['MeasurementBatchIn']
export type MeasurementRowOut = components['schemas']['MeasurementRowOut']
export type MissionStage = MeasurementRowOut['mission_stage']
export type MeasurementSource = MeasurementRowOut['source_type']
export type StreakUpdateSummary = components['schemas']['StreakUpdateSummary']
export type MeasurementIngestOut = components['schemas']['MeasurementIngestOut']

export interface MeasurementQueryParams {
  crew_id: string
  metric_key?: string
  category?: MetricCategory
  mission_stage?: MissionStage
  source_type?: MeasurementSource
  from_utc?: string
  to_utc?: string
  limit?: number
  offset?: number
}

export type HttpFetcher = <T>(
  url: string,
  options?: {
    method?: 'GET' | 'POST'
    headers?: Record<string, string>
    params?: Record<string, string | number | undefined>
    body?: unknown
  },
) => Promise<T>

export function resolveApiEndpoint(apiBase: string, path: string): string {
  const normalizedBase = apiBase.trim().replace(/\/+$/, '')
  const normalizedPath = path.startsWith('/') ? path : `/${path}`
  return `${normalizedBase}${normalizedPath}`
}

export function cleanQueryParams(
  query?: MeasurementQueryParams,
): Record<string, string | number> | undefined {
  if (!query) {
    return undefined
  }
  const cleaned: Record<string, string | number> = {}
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined && value !== '') {
      cleaned[key] = value as string | number
    }
  }
  return Object.keys(cleaned).length > 0 ? cleaned : undefined
}

export function buildDailyVitalsItems(
  input: DailyVitalsHabitsInput,
  previousHydrationMl = 2400,
): MeasurementItemIn[] {
  const shiftMinutes = parseWorkShiftMinutes(input.workShiftText) ?? 320
  const station = input.workShiftMode === 'EVA' ? 'Airlock Exterior' : 'Command Bridge'
  return [
    { metric_key: 'body_weight_kg', value_num: input.bodyWeightKg },
    { metric_key: 'bp_systolic_mmhg', value_num: input.bpSystolicMmhg },
    { metric_key: 'bp_diastolic_mmhg', value_num: input.bpDiastolicMmhg },
    { metric_key: 'resting_hr_bpm', value_num: input.restingHrBpm },
    { metric_key: 'body_temp_c', value_num: input.bodyTempC },
    {
      metric_key: 'hydration_ml',
      value_num: previousHydrationMl + input.hydrationAddMl,
      payload_json: {
        added_ml: input.hydrationAddMl,
        previous_ml: previousHydrationMl,
      },
    },
    { metric_key: 'calories_kcal', value_num: input.caloriesKcal },
    { metric_key: 'exercise_min', value_num: input.exerciseMin },
    {
      metric_key: 'work_shift_min',
      value_num: shiftMinutes,
      payload_json: {
        shift_mode: input.workShiftMode,
        station,
        formatted_duration: input.workShiftText.trim(),
      },
    },
  ]
}

export function buildClinicalLabsItems(input: ClinicalLabsInput): MeasurementItemIn[] {
  return [
    { metric_key: 'blood_glucose_mg_dl', value_num: input.bloodGlucoseMgDl },
    { metric_key: 'hemoglobin_g_dl', value_num: input.hemoglobinGDl },
    { metric_key: 'urine_specific_gravity', value_num: input.urineSpecificGravity },
    { metric_key: 'spo2_pct', value_num: input.spo2Pct },
  ]
}

export function buildOcularExamItems(input: OcularCaptureInput): MeasurementItemIn[] {
  const snellen = normalizeSnellen(input.visualAcuity)
  const ocularContext = {
    retinal_thickness_um: input.retinalThicknessUm,
    visual_acuity: snellen,
    visual_acuity_logmar: snellenToLogMar(snellen),
  }
  return [
    {
      metric_key: 'optic_sheath_left_mm',
      value_num: input.leftOpticSheathMm,
      payload_json: ocularContext,
    },
    {
      metric_key: 'optic_sheath_right_mm',
      value_num: input.rightOpticSheathMm,
      payload_json: ocularContext,
    },
    { metric_key: 'iop_left_mmhg', value_num: input.leftIopMmhg },
    { metric_key: 'iop_right_mmhg', value_num: input.rightIopMmhg },
  ]
}

export function extractErrorMessage(err: unknown, fallback: string): string {
  const detail = (err as { data?: { detail?: unknown } })?.data?.detail
  if (typeof detail === 'string' && detail.trim().length > 0) {
    return detail
  }
  if (err instanceof Error && err.message.trim().length > 0) {
    return err.message
  }
  return fallback
}

export function createMeasurementsClient(fetcher: HttpFetcher, apiBase = '') {
  return {
    listMetrics(category?: MetricCategory): Promise<MetricCatalogItem[]> {
      return fetcher<MetricCatalogItem[]>(resolveApiEndpoint(apiBase, '/api/v1/metrics/catalog'), {
        method: 'GET',
        params: category ? { category } : undefined,
      })
    },

    listMeasurements(query: MeasurementQueryParams): Promise<MeasurementRowOut[]> {
      return fetcher<MeasurementRowOut[]>(resolveApiEndpoint(apiBase, '/api/v1/measurements'), {
        method: 'GET',
        params: cleanQueryParams(query),
      })
    },

    ingestMeasurements(
      payload: MeasurementBatchIn,
      headers?: Record<string, string>,
    ): Promise<MeasurementIngestOut> {
      return fetcher<MeasurementIngestOut>(resolveApiEndpoint(apiBase, '/api/v1/measurements'), {
        method: 'POST',
        headers,
        body: payload,
      })
    },
  }
}

export function useMeasurements() {
  const runtimeConfig = useRuntimeConfig()
  const session = useSession()

  const metricCatalog = useState<MetricCatalogItem[]>('clinical_metric_catalog', () => [])
  const isSubmitting = useState<boolean>('measurements_submitting', () => false)
  const lastError = useState<string | null>('measurements_last_error', () => null)

  const apiBase = String(runtimeConfig.public.apiBase ?? '')
  const client = createMeasurementsClient($fetch as HttpFetcher, apiBase)

  async function fetchMetricCatalog(options?: {
    category?: MetricCategory
    force?: boolean
  }): Promise<MetricCatalogItem[]> {
    lastError.value = null
    if (!options?.category && !options?.force && metricCatalog.value.length > 0) {
      return metricCatalog.value
    }
    try {
      const items = await client.listMetrics(options?.category)
      if (!options?.category) {
        metricCatalog.value = items
      }
      return items
    }
    catch (err) {
      lastError.value = err instanceof Error ? err.message : 'Unable to load clinical metric catalog.'
      throw err
    }
  }

  function getMetricByKey(metricKey: string): MetricCatalogItem | undefined {
    return metricCatalog.value.find(item => item.metric_key === metricKey)
  }

  async function fetchMeasurements(query: MeasurementQueryParams): Promise<MeasurementRowOut[]> {
    lastError.value = null
    try {
      return await client.listMeasurements(query)
    }
    catch (err) {
      lastError.value = err instanceof Error ? err.message : 'Unable to load clinical measurements.'
      throw err
    }
  }

  async function ingestMeasurements(payload: MeasurementBatchIn): Promise<MeasurementIngestOut> {
    isSubmitting.value = true
    lastError.value = null
    try {
      const response = await client.ingestMeasurements(payload, session.authHeaders())
      await session.refreshMissionStatus()
      return response
    }
    catch (err) {
      lastError.value = err instanceof Error ? err.message : 'Unable to save clinical measurements.'
      throw err
    }
    finally {
      isSubmitting.value = false
    }
  }

  return {
    metricCatalog,
    isSubmitting,
    lastError,
    fetchMetricCatalog,
    getMetricByKey,
    fetchMeasurements,
    ingestMeasurements,
  }
}
