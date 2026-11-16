<script setup lang="ts">
// 09 · Cardiac & Pulmonary Auscultation (read-only). Recording lives in Capture.
import VChart from 'vue-echarts'
import type { MetricView } from '~/composables/useProfile'
import { co2TrendOption, envelopeOption } from '~/utils/charts'
import type { ChartClick } from '~/composables/useChartPins'
import { interpretation, statusFor, type Thresholds } from '~/utils/chartDecor'
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
  co2: { current_mmhg: number | null, status: string, period: string, limits_mmhg: { target: number, alert: number }
    trend: { recorded_at_utc: string, co2_mmhg: number }[] }
}

const { crew } = useSession()
const { api } = useApi()
const CO2_PERIODS = [{ id: '24h', label: '24H' }, { id: '7d', label: '7D' }, { id: '30d', label: '30D' }]
const co2Period = ref('24h')
const { data, loading, error, refresh } = useResource(
  () => api<Results>(`/auscultation/${crew.value!.id}`, { query: { co2_period: co2Period.value } }), 60_000, ['auscultation', 'alerts'])

usePageHeader(() => ({
  title: 'Cardiac & Pulmonary Auscultation',
  status: data.value ? { text: data.value.header_text, tone: data.value.status === 'WARNING' ? 'critical' : 'ok' } : null,
}))

const SITE_NAMES: Record<string, string> = {
  aortic: 'Aortic', pulmonic: 'Pulmonic', tricuspid: 'Tricuspid', mitral: 'Mitral',
  upper_left: 'Upper Left', upper_right: 'Upper Right', lower_left: 'Lower Left', lower_right: 'Lower Right',
}
// Recorded sound envelopes: 600 points over 30 s (20 per second); time in seconds on the x axis.
const ENVELOPE_RATE = 20
function envelopePin(kind: 'cardiac' | 'pulmonary') {
  return (click: ChartClick) => {
    const organ = data.value?.[kind]
    const point = click.value as [number, number] | undefined
    if (!organ || !point) return null
    return {
      key: `${kind}-${click.dataIndex}`, series: kind === 'cardiac' ? 'Heart' : 'Lungs', value: Math.abs(point[1]), unit: '', digits: 2,
      time_utc: organ.recorded_at_utc, stage: null, delta: null, reference_label: `at ${point[0].toFixed(2)} s`,
      status: 'NOMINAL' as const, coord: [point[0], point[1]] as [number, number],
    }
  }
}
const cardiacPins = useChartPins(envelopePin('cardiac'))
const lungPins = useChartPins(envelopePin('pulmonary'))
const cardiacChart = computed(() => (data.value?.cardiac?.envelope.length
  ? envelopeOption(data.value.cardiac.envelope.slice(0, 150), 'cardiac', cardiacPins.marks(), ENVELOPE_RATE) : null))
const lungChart = computed(() => (data.value?.pulmonary?.envelope.length
  ? envelopeOption(data.value.pulmonary.envelope, 'pulmonary', lungPins.marks(), ENVELOPE_RATE) : null))

// Cabin CO2: target zone = band, target = watch line, alert limit = red line.
const co2Thresholds = computed<Thresholds>(() => {
  const l = data.value?.co2.limits_mmhg
  return { band: l ? [0, l.target] : null, watch: l ? [l.target] : [], critical: l ? [l.alert] : [], alertWhen: 'above' }
})
const co2Pins = useChartPins((click: ChartClick) => {
  const point = data.value?.co2.trend[click.dataIndex]
  if (!point) return null
  const target = data.value!.co2.limits_mmhg.target
  return {
    key: point.recorded_at_utc, series: 'CO₂', value: point.co2_mmhg, unit: 'mmHg', digits: 2,
    time_utc: point.recorded_at_utc, stage: null, delta: point.co2_mmhg - target, reference_label: 'target',
    status: statusFor(point.co2_mmhg, co2Thresholds.value), coord: [point.recorded_at_utc, point.co2_mmhg],
  }
})
watch(co2Period, () => {
  co2Pins.clear()
  void refresh()
})
const co2Chart = computed(() => (data.value?.co2.trend.length
  ? co2TrendOption(data.value.co2.trend, co2Thresholds.value, co2Pins.marks(), co2Period.value !== '24h') : null))
const co2Reading = computed(() => interpretation(co2Thresholds.value, 'mmHg'))
const pinsFor = (kind: 'cardiac' | 'pulmonary') => (kind === 'cardiac' ? cardiacPins : lungPins)
const wavePins = computed(() => [...cardiacPins.pins.value, ...lungPins.pins.value])
function onWaveClick(click: ChartClick) {
  pinsFor(click.seriesName === 'Heart sound' ? 'cardiac' : 'pulmonary').onClick(click)
}
function unpinWave(key: string) {
  cardiacPins.remove(key)
  lungPins.remove(key)
}
const co2Title = computed(() => ({ '24h': '24-Hour', '7d': '7-Day', '30d': '30-Day' } as Record<string, string>)[co2Period.value])

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
class="w-[30.2%] shrink-0" title="Cardiac & Pulmonary Audio Results" icon="stethoscope" flush
                      :tag-text="data.status === 'NO_DATA' ? 'NO DATA' : data.status === 'NOMINAL' ? 'NOMINAL' : 'REVIEW'"
                      :tag-tone="data.status === 'WARNING' ? 'critical' : 'reference'">
        <div class="flex-1 min-h-0 flex flex-col px-[19px] pt-[clamp(10px,1.8dvh,17px)] pb-[14px]">
          <div
v-for="organ in ([['cardiac', 'heart'], ['pulmonary', 'lungs']] as const)" :key="organ[0]"
               class="tile relative h-[clamp(112px,15.7dvh,170px)] shrink-0 mb-[clamp(8px,1.7dvh,16px)] flex items-center px-[clamp(14px,1.5vw,22px)] gap-[clamp(14px,1.5vw,22px)]">
            <span class="absolute top-[7px] right-[7px]"><UiParamHelp :metric-key="organ[0] === 'cardiac' ? 'heart_sound_rate' : 'lung_sound_rate'" /></span>
            <UiHoloFigure :figure="organ[1]" size="clamp(72px, 10.4dvh, 112px)" :label="organ[0] === 'cardiac' ? 'Heart' : 'Lungs'" />
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
          <div class="flex-1 min-h-0 flex flex-col justify-around gap-[6px]">
            <UiBandRow
v-for="view in data.fitness" :key="view.metric_key" :label="fitnessLabel[view.metric_key] ?? view.label" :help-key="view.metric_key"
                       :reference="fitnessRef(view)" :value-text="fitnessValue(view)" :unit="fitnessUnit[view.metric_key]"
                       :status="view.status" :status-text="view.status_text" :value="view.value"
                       :scale-min="fitnessScale[view.metric_key]?.[0]" :scale-max="fitnessScale[view.metric_key]?.[1]"
                       :band-low="view.baseline_low ?? view.nominal_min" :band-high="view.baseline_high ?? view.nominal_max" />
          </div>
        </div>
      </ShellHudWindow>

      <div class="flex-1 min-w-0 flex flex-col gap-[18px]">
        <ShellHudWindow
class="flex-[1.6] min-h-0" title="Recorded Cardiac & Pulmonary Acoustic Waveforms" icon="mic" help-key="signal_quality" flush
                        :tag-text="data.signal_quality_pct === null ? undefined : `SIGNAL ${data.signal_quality_pct}%`">
          <div class="flex-1 min-h-0 flex flex-col p-[clamp(12px,2.1dvh,20px)]">
            <UiInteractiveChartFrame :pins="wavePins" interpretation="MAX / MIN mark the loudest and quietest sound in view · click the trace to pin a moment (seconds into the 30 s recording)" @unpin="unpinWave" @point="onWaveClick">
            <div class="absolute inset-0 flex flex-col gap-[clamp(10px,1.7dvh,16px)]">
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
v-if="channel[1]" :option="channel[1]" theme="spacescan-hud" autoresize class="absolute inset-0 top-[26px] !h-auto"
                        :aria-label="`${channel[0]} recording waveform`" />
              </ClientOnly>
              <p v-if="!channel[1]" class="absolute inset-0 flex items-center justify-center text-[12px] text-cabin-ice">No recording yet.</p>
            </div>
            </div>
            </UiInteractiveChartFrame>
          </div>
        </ShellHudWindow>

        <ShellHudWindow
class="flex-1 min-h-0" :title="`${co2Title} Cabin CO₂ Trend (mmHg)`" icon="rocket" help-key="cabin_co2_ppm" flush
                        :tag-text="data.co2.current_mmhg === null ? undefined : `${data.co2.current_mmhg.toFixed(1)} mmHg · ${data.co2.status === 'NOMINAL' ? 'NOMINAL' : 'HIGH'}`"
                        :tag-tone="toneOf(data.co2.status) === 'critical' ? 'critical' : 'reference'">
          <div class="flex-1 min-h-0 flex flex-col m-[clamp(10px,1.6dvh,16px)]">
            <UiInteractiveChartFrame v-model:period="co2Period" :periods="CO2_PERIODS" :pins="co2Pins.pins.value" :interpretation="co2Reading" @unpin="co2Pins.remove" @point="co2Pins.onClick">
              <div class="absolute inset-0 tile">
                <ClientOnly>
                  <VChart
v-if="co2Chart" :option="co2Chart" theme="spacescan-hud" autoresize class="absolute inset-0"
                          :aria-label="`Cabin carbon dioxide, ${co2Title}`" />
                </ClientOnly>
                <UiStateNote v-if="!co2Chart" class="h-full" empty="No cabin readings in this window." />
              </div>
            </UiInteractiveChartFrame>
          </div>
        </ShellHudWindow>
      </div>
    </div>
  </div>
</template>
