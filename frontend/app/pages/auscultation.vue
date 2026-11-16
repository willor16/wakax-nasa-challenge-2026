<script setup lang="ts">
// 09 · Cardiac & Pulmonary Auscultation (read-only). Recording lives in Capture.
import VChart from 'vue-echarts'
import type { MetricView } from '~/composables/useProfile'
import { co2TrendOption, envelopeOption } from '~/utils/charts'
import { dayText, formatNumber, formatTime, toneOf } from '~/utils/format'

interface OrganSummary {
  rate_per_min: number | null
  rhythm_text: string
  regular: boolean
  sites_recorded: number
  sites_regular: number
  sites_total: number
  signal_quality_pct: number
  cabin_noise_dba: number
  recorded_at_utc: string
  day_label: string
  waveform_site: string
  envelope: number[]
  needs_physician_review: boolean
}
interface Results {
  status: string
  header_text: string
  signal_quality_pct: number | null
  cardiac: OrganSummary | null
  pulmonary: OrganSummary | null
  spo2_pct: number | null
  fitness: MetricView[]
  co2: { current_mmhg: number | null, status: string, limits_mmhg: { target: number, alert: number }
    trend: { recorded_at_utc: string, co2_mmhg: number }[] }
}

const { crew } = useSession()
const { api } = useApi()
const { data, loading, error, refresh } = useResource(() => api<Results>(`/auscultation/${crew.value!.id}`), 60_000)

usePageHeader(() => ({
  title: 'Cardiac & Pulmonary Auscultation',
  status: data.value ? { text: data.value.header_text, tone: data.value.status === 'WARNING' ? 'critical' : 'ok' } : null,
}))

const SITE_NAMES: Record<string, string> = {
  aortic: 'Aortic', pulmonic: 'Pulmonic', tricuspid: 'Tricuspid', mitral: 'Mitral',
  upper_left: 'Upper Left', upper_right: 'Upper Right', lower_left: 'Lower Left', lower_right: 'Lower Right',
}
const cardiacChart = computed(() => (data.value?.cardiac?.envelope.length ? envelopeOption(data.value.cardiac.envelope.slice(0, 150), 'cardiac') : null))
const lungChart = computed(() => (data.value?.pulmonary?.envelope.length ? envelopeOption(data.value.pulmonary.envelope, 'pulmonary') : null))
const co2Chart = computed(() => (data.value?.co2.trend.length ? co2TrendOption(data.value.co2.trend, data.value.co2.limits_mmhg) : null))

function fitnessRef(view: MetricView): string {
  if (view.metric_key === 'vo2_max_ml_kg_min') {
    return view.baseline_mean != null ? `Keep ≥ 80% of pre-flight (${formatNumber(view.baseline_mean * 0.8, 1)} mL/kg/min)` : 'No pre-flight value'
  }
  if (view.metric_key === 'orthostatic_hr_delta_bpm') return `Allowed rise: < +${view.nominal_max} bpm`
  return view.baseline_low != null ? `Baseline: ${formatNumber(view.baseline_low)}–${formatNumber(view.baseline_high)}` : `Usual: ${view.nominal_min}–${view.nominal_max}`
}
function fitnessValue(view: MetricView): string {
  if (view.value === null) return '—'
  if (view.metric_key === 'orthostatic_hr_delta_bpm') return `+${formatNumber(view.value)}`
  return formatNumber(view.value, view.metric_key === 'vo2_max_ml_kg_min' ? 1 : 0)
}
const fitnessLabel: Record<string, string> = {
  vo2_max_ml_kg_min: 'Aerobic Capacity (VO₂ Max)', orthostatic_hr_delta_bpm: 'Orthostatic Response',
  cardiorespiratory_index: 'Cardiorespiratory Index',
}
const fitnessUnit: Record<string, string> = { vo2_max_ml_kg_min: 'mL/kg', orthostatic_hr_delta_bpm: 'bpm', cardiorespiratory_index: 'pts' }
const fitnessScale: Record<string, [number, number]> = {
  vo2_max_ml_kg_min: [20, 70], orthostatic_hr_delta_bpm: [-5, 40], cardiorespiratory_index: [40, 100],
}
</script>

<template>
  <div class="page">
    <UiStateNote v-if="!data" :loading="loading" :error="error" @retry="refresh()" />
    <div v-else class="flex-1 min-h-0 flex gap-[18px]">
      <ShellHudWindow
class="w-[456px]" title="Cardiac & Pulmonary Audio Results" icon="stethoscope" flush
                      :tag-text="data.status === 'NO_DATA' ? 'NO DATA' : data.status === 'NOMINAL' ? 'NOMINAL' : 'REVIEW'"
                      :tag-tone="data.status === 'WARNING' ? 'critical' : 'reference'">
        <div class="flex-1 flex flex-col px-[19px] pt-[17px] pb-[14px]">
          <div
v-for="organ in ([['cardiac', 'heart'], ['pulmonary', 'lungs']] as const)" :key="organ[0]"
               class="tile h-[148px] shrink-0 mb-[16px] flex items-center px-[22px] gap-[22px]">
            <UiHoloFigure :figure="organ[1]" :size="98" :label="organ[0] === 'cardiac' ? 'Heart' : 'Lungs'" />
            <div v-if="data[organ[0]]" class="min-w-0">
              <p class="text-[10px] font-bold tracking-[0.04em] uppercase text-cabin-ok">{{ organ[0] }} audio · 30s sample</p>
              <p class="mt-[8px] flex items-baseline gap-[12px]">
                <span class="text-[26px] font-bold">{{ data[organ[0]]!.rate_per_min === null ? '—' : formatNumber(data[organ[0]]!.rate_per_min, organ[0] === 'cardiac' ? 0 : 1) }}
                  {{ organ[0] === 'cardiac' ? 'bpm' : 'rpm' }}</span>
                <span v-if="organ[0] === 'cardiac'" class="text-[13px] font-bold" :class="data.cardiac!.regular ? 'text-cabin-ok' : 'text-cabin-text'">{{ data.cardiac!.rhythm_text }}</span>
                <span v-else-if="data.spo2_pct !== null" class="text-[13px] font-bold text-cabin-ok">SpO₂ {{ formatNumber(data.spo2_pct) }}%</span>
              </p>
              <p class="text-[11.5px] mt-[8px]">
                {{ data[organ[0]]!.sites_regular }} / {{ data[organ[0]]!.sites_total }}
                {{ organ[0] === 'cardiac' ? 'valve sites steady' : 'zones steady' }}
                <template v-if="data[organ[0]]!.sites_recorded < 4"> · {{ data[organ[0]]!.sites_recorded }} recorded</template>
              </p>
              <p class="text-[11px] text-cabin-ice mt-[8px]">
                <template v-if="data[organ[0]]!.needs_physician_review">Physician listening review advised</template>
                <template v-else>Recorded {{ dayText(data[organ[0]]!.day_label) }} · {{ formatTime(data[organ[0]]!.recorded_at_utc) }} UTC</template>
              </p>
            </div>
            <p v-else class="text-[12px] text-cabin-ice">No {{ organ[0] }} recording yet. Record in Capture · Auscultation Audio.</p>
          </div>
          <div class="flex-1 flex flex-col justify-around">
            <UiBandRow
v-for="view in data.fitness" :key="view.metric_key" :label="fitnessLabel[view.metric_key] ?? view.label"
                       :reference="fitnessRef(view)" :value-text="fitnessValue(view)" :unit="fitnessUnit[view.metric_key]"
                       :status="view.status" :status-text="view.status_text" :value="view.value"
                       :scale-min="fitnessScale[view.metric_key]?.[0]" :scale-max="fitnessScale[view.metric_key]?.[1]"
                       :band-low="view.baseline_low ?? view.nominal_min" :band-high="view.baseline_high ?? view.nominal_max" />
          </div>
        </div>
      </ShellHudWindow>

      <div class="flex-1 min-w-0 flex flex-col gap-[18px]">
        <ShellHudWindow
class="h-[438px] shrink-0" title="Recorded Cardiac & Pulmonary Acoustic Waveforms" icon="mic" flush
                        :tag-text="data.signal_quality_pct === null ? undefined : `SIGNAL ${data.signal_quality_pct}%`">
          <div class="flex-1 flex flex-col gap-[16px] p-[20px]">
            <div
v-for="channel in ([
              ['cardiac', cardiacChart, `Channel 1 · Cardiac phonocardiogram (${SITE_NAMES[data.cardiac?.waveform_site ?? 'mitral']} S1 / S2)`],
              ['pulmonary', lungChart, 'Channel 2 · Pulmonary breath envelope (bilateral)'],
            ] as const)" :key="channel[0]" class="tile relative flex-1">
              <span class="absolute top-[12px] left-[16px] mono text-[9.5px] z-10 uppercase" :class="channel[0] === 'cardiac' ? 'text-cabin-ok' : ''">{{ channel[2] }}</span>
              <span v-if="data[channel[0]]" class="absolute top-[12px] right-[16px] mono text-[9.5px] z-10 uppercase">
                {{ formatNumber(data[channel[0]]!.rate_per_min, channel[0] === 'cardiac' ? 0 : 1) }} {{ channel[0] === 'cardiac' ? 'BPM' : 'RPM' }}
                · {{ channel[0] === 'cardiac' ? `Signal ${data.cardiac!.signal_quality_pct}%` : `Cabin noise ${Math.round(data.pulmonary!.cabin_noise_dba)} dBA` }}
              </span>
              <ClientOnly>
                <VChart
v-if="channel[1]" :option="channel[1]" theme="spacescan-hud" autoresize class="absolute inset-0 top-[26px]"
                        :aria-label="`${channel[0]} recording waveform`" />
              </ClientOnly>
              <p v-if="!channel[1]" class="absolute inset-0 flex items-center justify-center text-[12px] text-cabin-ice">No recording yet.</p>
            </div>
          </div>
        </ShellHudWindow>

        <ShellHudWindow
class="flex-1" title="24-Hour Cabin CO₂ Trend (mmHg)" icon="rocket" flush
                        :tag-text="data.co2.current_mmhg === null ? undefined : `${data.co2.current_mmhg.toFixed(1)} mmHg · ${data.co2.status === 'NOMINAL' ? 'NOMINAL' : 'HIGH'}`"
                        :tag-tone="toneOf(data.co2.status) === 'critical' ? 'critical' : 'reference'">
          <div class="flex-1 relative m-[18px] tile">
            <template v-if="co2Chart">
              <span class="absolute top-[8px] right-[26px] z-10 text-[10px] font-bold">ALERT LIMIT ({{ data.co2.limits_mmhg.alert.toFixed(1) }} mmHg)</span>
              <span class="absolute bottom-[54px] left-[56px] z-10 text-[10px] font-bold">TARGET ZONE (&lt; {{ data.co2.limits_mmhg.target.toFixed(1) }} mmHg)</span>
              <ClientOnly>
                <VChart :option="co2Chart" theme="spacescan-hud" autoresize class="absolute inset-0" aria-label="Cabin carbon dioxide over 24 hours" />
              </ClientOnly>
            </template>
            <UiStateNote v-else class="h-full" empty="No cabin readings in the last 24 hours." />
          </div>
        </ShellHudWindow>
      </div>
    </div>
  </div>
</template>
