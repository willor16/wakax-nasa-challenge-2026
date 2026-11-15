export interface CabinTelemetryFrame {
  cabin: {
    co2_ppm: number
    noise_dba: number
    temp_c: number
    humidity_pct: number
    radiation_msv: number
    solar_event_flag: number
    recorded_at_utc: string
  } | null
  cabin_mode: 'nominal' | 'critical'
  server_utc: string
}

export function useTelemetryStream(onCabinFrame: (frame: CabinTelemetryFrame) => void) {
  let source: EventSource | null = null

  function connect() {
    if (!import.meta.client) return
    source = new EventSource('/api/v1/stream/telemetry')
    source.addEventListener('cabin', (event: MessageEvent) => {
      try {
        const frame = JSON.parse(event.data) as CabinTelemetryFrame
        onCabinFrame(frame)
      }
      catch {
        // Ignore malformed stream frame
      }
    })
  }

  function disconnect() {
    source?.close()
    source = null
  }

  onMounted(connect)
  onUnmounted(disconnect)
}
