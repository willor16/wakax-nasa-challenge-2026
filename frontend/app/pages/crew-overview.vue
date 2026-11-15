<script setup lang="ts">
import VChart from 'vue-echarts'
import { buildCrewGaugeOption } from '~/utils/charts'
import { type ClinicalBand, statusPillClasses } from '~/utils/status'

interface CrewCard {
  id: string
  code: string
  full_name: string
  short_name: string
  role: string
  status: ClinicalBand
  readiness_score: number
  unread_alerts: number
  vitals: {
    resting_hr_bpm: number | null
    hrv_rmssd_ms: number | null
    spo2_pct: number | null
    sleep_hours_24h: number | null
  }
}

interface CabinReading {
  co2_ppm: number
  noise_dba: number
  temp_c: number
  humidity_pct: number
  radiation_msv: number
  solar_event_flag: number
  recorded_at_utc: string
}

interface CrewOverviewPayload {
  crew_score: number
  crew_status: ClinicalBand
  cabin_mode: 'nominal' | 'critical'
  crew: CrewCard[]
  cabin: CabinReading | null
}

const { setCabinMode } = useSession()
const overview = ref<CrewOverviewPayload | null>(null)
const loadError = ref('')

const gaugeOption = computed(() => buildCrewGaugeOption(overview.value?.crew_score ?? 0))

const statusSummary = computed(() => {
  const list = overview.value?.crew ?? []
  return {
    optimal: list.filter(c => c.status === 'Optimal').length,
    nominal: list.filter(c => c.status === 'Nominal').length,
    attention: list.filter(c => c.status === 'Attention').length,
    critical: list.filter(c => c.status === 'Critical').length,
  }
})

async function fetchOverview() {
  try {
    const data = await $fetch<CrewOverviewPayload>('/api/v1/crew-overview')
    overview.value = data
    setCabinMode(data.cabin_mode)
  }
  catch {
    loadError.value = 'Unable to load crew telemetry overview.'
  }
}

useTelemetryStream((frame) => {
  if (overview.value && frame.cabin) {
    overview.value.cabin = frame.cabin
    overview.value.cabin_mode = frame.cabin_mode
    setCabinMode(frame.cabin_mode)
  }
})

onMounted(fetchOverview)
</script>

<template>
  <div class="grid grid-cols-1 lg:grid-cols-12 gap-[18px] flex-1">
    <ShellHudWindow
      class="lg:col-span-8"
      title="Crew Health Overview"
      subtitle="Read-only crew readiness and recent vital signs"
      icon="shield"
      :tag-text="overview ? `SCORE ${overview.crew_score} · ${overview.crew_status.toUpperCase()}` : 'READ ONLY'"
      :tag-tone="overview?.crew_status === 'Critical' ? 'critical' : overview?.crew_status === 'Attention' ? 'warn' : 'reference'"
    >
      <p
        v-if="loadError"
        class="mb-4 px-3 py-2 rounded-[4px] bg-cabin-crit/20 border border-cabin-crit text-[11.5px] text-cabin-text"
      >
        {{ loadError }}
      </p>

      <div class="grid grid-cols-1 md:grid-cols-12 gap-4 items-center mb-4">
        <div class="md:col-span-4 h-40 rounded-[6px] bg-cabin-inset border border-cabin-card/65 p-2 flex items-center justify-center">
          <VChart
            class="w-full h-full"
            theme="spacescan-hud"
            :option="gaugeOption"
            autoresize
          />
        </div>

        <div class="md:col-span-8 grid grid-cols-2 sm:grid-cols-4 gap-2.5">
          <div class="p-3 rounded-[6px] bg-cabin-inset border border-cabin-card/65">
            <div class="text-[10px] uppercase tracking-[0.05em] text-cabin-muted">Optimal</div>
            <div class="mt-1 font-mono text-[22px] font-bold text-cabin-ok">{{ statusSummary.optimal }}</div>
          </div>
          <div class="p-3 rounded-[6px] bg-cabin-inset border border-cabin-card/65">
            <div class="text-[10px] uppercase tracking-[0.05em] text-cabin-muted">Nominal</div>
            <div class="mt-1 font-mono text-[22px] font-bold text-cabin-text">{{ statusSummary.nominal }}</div>
          </div>
          <div class="p-3 rounded-[6px] bg-cabin-inset border border-cabin-card/65">
            <div class="text-[10px] uppercase tracking-[0.05em] text-cabin-muted">Attention</div>
            <div class="mt-1 font-mono text-[22px] font-bold text-cabin-ice">{{ statusSummary.attention }}</div>
          </div>
          <div class="p-3 rounded-[6px] bg-cabin-inset border border-cabin-card/65">
            <div class="text-[10px] uppercase tracking-[0.05em] text-cabin-muted">Critical</div>
            <div class="mt-1 font-mono text-[22px] font-bold text-cabin-crit">{{ statusSummary.critical }}</div>
          </div>
        </div>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
        <article
          v-for="member in overview?.crew ?? []"
          :key="member.id"
          class="p-4 rounded-[6px] bg-cabin-inset border border-cabin-card/70 flex flex-col gap-3"
        >
          <div class="flex items-start justify-between gap-2">
            <div>
              <div class="font-mono text-[10.5px] font-bold text-cabin-muted">
                {{ member.code }} · {{ member.role }}
              </div>
              <h3 class="text-[14px] font-bold text-cabin-text">
                {{ member.full_name }}
              </h3>
            </div>
            <span
              class="px-2.5 h-[22px] rounded-full border text-[10px] font-bold uppercase tracking-[0.04em] inline-flex items-center"
              :class="statusPillClasses(member.status)"
            >
              {{ member.status }}
            </span>
          </div>

          <div class="grid grid-cols-4 gap-2 pt-2 border-t border-cabin-card/45">
            <div>
              <div class="text-[9.5px] uppercase text-cabin-muted">HR</div>
              <div class="font-mono text-[13px] font-bold text-cabin-text">
                {{ member.vitals.resting_hr_bpm ?? '--' }}
                <span class="text-[9.5px] font-normal text-cabin-muted">bpm</span>
              </div>
            </div>
            <div>
              <div class="text-[9.5px] uppercase text-cabin-muted">HRV</div>
              <div class="font-mono text-[13px] font-bold text-cabin-text">
                {{ member.vitals.hrv_rmssd_ms ?? '--' }}
                <span class="text-[9.5px] font-normal text-cabin-muted">ms</span>
              </div>
            </div>
            <div>
              <div class="text-[9.5px] uppercase text-cabin-muted">Sleep 24h</div>
              <div class="font-mono text-[13px] font-bold text-cabin-text">
                {{ member.vitals.sleep_hours_24h ?? '--' }}
                <span class="text-[9.5px] font-normal text-cabin-muted">h</span>
              </div>
            </div>
            <div>
              <div class="text-[9.5px] uppercase text-cabin-muted">SpO2</div>
              <div class="font-mono text-[13px] font-bold text-cabin-ok">
                {{ member.vitals.spo2_pct ?? '--' }}
                <span class="text-[9.5px] font-normal text-cabin-muted">%</span>
              </div>
            </div>
          </div>
        </article>
      </div>
    </ShellHudWindow>

    <ShellHudWindow
      class="lg:col-span-4"
      title="Cabin Environment"
      subtitle="Habitat factors impacting crew health"
      icon="earth"
      :tag-text="overview?.cabin_mode === 'critical' ? 'ALERT' : 'NOMINAL'"
      :tag-tone="overview?.cabin_mode === 'critical' ? 'critical' : 'reference'"
    >
      <div class="flex flex-col gap-3">
        <div class="p-3.5 rounded-[6px] bg-cabin-inset border border-cabin-card/65 flex items-center justify-between">
          <div>
            <div class="text-[10.5px] uppercase tracking-[0.04em] text-cabin-muted">Cabin CO2</div>
            <div class="text-[10px] text-cabin-muted">Nominal &lt; 2000 ppm</div>
          </div>
          <div class="font-mono text-[20px] font-bold text-cabin-ok">
            {{ overview?.cabin?.co2_ppm ?? '--' }}
            <span class="text-[11px] font-normal text-cabin-muted">ppm</span>
          </div>
        </div>

        <div class="p-3.5 rounded-[6px] bg-cabin-inset border border-cabin-card/65 flex items-center justify-between">
          <div>
            <div class="text-[10.5px] uppercase tracking-[0.04em] text-cabin-muted">Ambient Noise</div>
            <div class="text-[10px] text-cabin-muted">Acoustic capture limit &lt; 55 dBA</div>
          </div>
          <div class="font-mono text-[20px] font-bold text-cabin-text">
            {{ overview?.cabin?.noise_dba ?? '--' }}
            <span class="text-[11px] font-normal text-cabin-muted">dBA</span>
          </div>
        </div>

        <div class="grid grid-cols-2 gap-3">
          <div class="p-3.5 rounded-[6px] bg-cabin-inset border border-cabin-card/65">
            <div class="text-[10px] uppercase text-cabin-muted">Temperature</div>
            <div class="mt-1 font-mono text-[18px] font-bold text-cabin-text">
              {{ overview?.cabin?.temp_c ?? '--' }} <span class="text-[11px] font-normal text-cabin-muted">C</span>
            </div>
          </div>
          <div class="p-3.5 rounded-[6px] bg-cabin-inset border border-cabin-card/65">
            <div class="text-[10px] uppercase text-cabin-muted">Humidity</div>
            <div class="mt-1 font-mono text-[18px] font-bold text-cabin-text">
              {{ overview?.cabin?.humidity_pct ?? '--' }} <span class="text-[11px] font-normal text-cabin-muted">%</span>
            </div>
          </div>
        </div>

        <div class="p-3.5 rounded-[6px] bg-cabin-inset border border-cabin-card/65 flex items-center justify-between">
          <div>
            <div class="text-[10.5px] uppercase tracking-[0.04em] text-cabin-muted">Radiation Dose Rate</div>
            <div class="text-[10px] text-cabin-muted">
              {{ overview?.cabin?.solar_event_flag ? 'Elevated solar particle alert' : 'Background transit nominal' }}
            </div>
          </div>
          <div class="font-mono text-[18px] font-bold text-cabin-text">
            {{ overview?.cabin?.radiation_msv ?? '--' }}
            <span class="text-[11px] font-normal text-cabin-muted">mSv/d</span>
          </div>
        </div>
      </div>
    </ShellHudWindow>
  </div>
</template>
