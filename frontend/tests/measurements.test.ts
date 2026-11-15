import { describe, expect, it, vi } from 'vitest'
import {
  cleanQueryParams,
  createMeasurementsClient,
  resolveApiEndpoint,
} from '../app/composables/useMeasurements'

describe('useMeasurements client & query utilities (D2-01)', () => {
  it('normalizes relative and explicit base URLs cleanly', () => {
    expect(resolveApiEndpoint('', '/api/v1/metrics/catalog')).toBe('/api/v1/metrics/catalog')
    expect(resolveApiEndpoint('http://127.0.0.1:8000/', 'api/v1/measurements')).toBe(
      'http://127.0.0.1:8000/api/v1/measurements',
    )
  })

  it('strips empty or undefined query parameters', () => {
    expect(cleanQueryParams(undefined)).toBeUndefined()
    expect(
      cleanQueryParams({
        crew_id: 'ID-01',
        category: 'VISION',
        metric_key: '',
        limit: 25,
      }),
    ).toEqual({
      crew_id: 'ID-01',
      category: 'VISION',
      limit: 25,
    })
  })

  it('dispatches typed GET and POST calls aligned with /api/v1/measurements', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      inserted_ids: [101, 102],
      alerts_created: [],
      streak: {
        crew_id: 'ID-01',
        streak_date_utc: '2026-11-15',
        logs_completed: 2,
        habits_met: true,
        daily_compliant: true,
      },
      recorded_at_utc: '2026-11-15T10:00:00Z',
    })

    const client = createMeasurementsClient(mockFetch, 'http://127.0.0.1:8000')

    await client.listMetrics('VITALS')
    expect(mockFetch).toHaveBeenCalledWith('http://127.0.0.1:8000/api/v1/metrics/catalog', {
      method: 'GET',
      params: { category: 'VITALS' },
    })

    await client.ingestMeasurements(
      {
        crew_id: 'ID-01',
        mission_stage: 'MISSION',
        source_type: 'MANUAL',
        items: [
          { metric_key: 'bp_systolic_mmhg', value_num: 118 },
          { metric_key: 'bp_diastolic_mmhg', value_num: 76 },
        ],
      },
      { Authorization: 'Bearer test-token' },
    )

    expect(mockFetch).toHaveBeenLastCalledWith('http://127.0.0.1:8000/api/v1/measurements', {
      method: 'POST',
      headers: { Authorization: 'Bearer test-token' },
      body: {
        crew_id: 'ID-01',
        mission_stage: 'MISSION',
        source_type: 'MANUAL',
        items: [
          { metric_key: 'bp_systolic_mmhg', value_num: 118 },
          { metric_key: 'bp_diastolic_mmhg', value_num: 76 },
        ],
      },
    })
  })
})
