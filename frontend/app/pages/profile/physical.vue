<script setup lang="ts">
// 06 · Astronaut Profile · Physical (read-only): daily vitals and habits, live ECG, labs.
import VChart from 'vue-echarts'
import type { MetricView } from '~/composables/useProfile'
import { ecgOption } from '~/utils/charts'
import { digitsFor, formatNumber, toneOf } from '~/utils/format'

const { data: profile, loading, error, refresh } = useProfile(20_000)

usePageHeader(() => ({
  title: 'Astronaut Profile · Physical',
  status: profile.value
    ? { text: `${profile.value.on_target} / ${profile.value.daily_count} on target`,
        tone: profile.value.daily.some(row => row.status === 'CRITICAL') ? 'critical' : 'ok' }
    : null,
}))

function reference(row: MetricView): string {
  const unit = row.unit
  if (row.target != null) {
    const target = row.metric_key === 'hydration_ml' ? `${(row.target / 1000).toFixed(1)} L` : `${formatNumber(row.target)} ${unit}`
    if (row.value == null) return `Daily target: ${target}`
    const left = row.target - row.value
    return row.metric_key === 'hydration_ml' && left > 0
      ? `Daily target: ${target} (${formatNumber(left)} mL remaining)`
      : `Daily target: ${target}`
  }
  if (row.metric_key === 'blood_pressure' && row.baseline_mean != null) {
    return `Baseline: ${formatNumber(row.baseline_mean)}/${formatNumber(row.baseline_secondary)} mmHg`
  }
  if (row.metric_key === 'spo2_pct') return `Nominal range: ${row.nominal_min}–${row.nominal_max}%`
  if (row.baseline_low != null && row.baseline_high != null) {
    return `Baseline: ${formatNumber(row.baseline_low)}–${formatNumber(row.baseline_high)} ${unit}`
  }
  return 'No pre-flight value'
}
function valueText(row: MetricView): string {
  if (row.value == null) return '—'
  if (row.metric_key === 'blood_pressure') return `${formatNumber(row.value)}/${formatNumber(row.value_secondary)}`
  if (row.metric_key === 'hydration_ml') return (row.value / 1000).toFixed(1)
  return formatNumber(row.value, digitsFor(row.unit, row.metric_key))
}
const unitText = (row: MetricView) => (row.metric_key === 'hydration_ml' ? 'L' : row.unit)
function band(row: MetricView): [number | null | undefined, number | null | undefined] {
  if (row.target != null) return [row.target, row.nominal_max]
  if (row.metric_key === 'spo2_pct') return [row.nominal_min, row.nominal_max]
  return [row.baseline_low ?? row.nominal_min, row.baseline_high ?? row.nominal_max]
}
const label = (row: MetricView) => ({
  spo2_pct: 'Oxygen Saturation (SpO₂)', exercise_min: 'Daily Exercise', resting_hr_bpm: 'Resting Heart Rate',
} as Record<string, string>)[row.metric_key] ?? row.label

const ecg = computed(() => profile.value?.ecg ?? null)
const ecgChart = computed(() => (ecg.value ? ecgOption(ecg.value.samples, ecg.value.sample_rate_hz) : null))
function labValue(lab: MetricView): string {
  if (lab.value_text !== undefined) return lab.value_text ?? '—'
  if (lab.value == null) return '—'
  const digits = digitsFor(lab.unit, lab.metric_key)
  return lab.unit === 'SG' ? `${lab.value.toFixed(3)} SG` : `${formatNumber(lab.value, digits)} ${lab.unit}`
}
const accent = (lab: MetricView) => ({
  ok: 'bg-cabin-ok', watch: 'bg-cabin-navy-edge', critical: 'bg-cabin-crit', neutral: 'bg-cabin-dim',
})[toneOf(lab.status)]
</script>

<template>
  <div class="page">
    <ShellProfileTabs />
    <UiStateNote v-if="!profile" :loading="loading" :error="error" @retry="refresh()" />
    <div v-else class="flex-1 min-h-0 flex gap-[18px]">
      <ShellHudWindow
class="w-[621px]" title="Daily Vitals, Exercise & Nutrition" icon="heart"
                      tag-text="CONTINUOUS" flush>
        <div class="flex-1 flex flex-col justify-around px-[23px] py-[10px]">
          <UiBandRow
            v-for="row in profile.daily"
            :key="row.metric_key"
            :label="label(row)"
            :reference="reference(row)"
            :value-text="valueText(row)"
            :unit="unitText(row)"
            :status="row.status"
            :status-text="row.status_text"
            :value="row.value"
            :scale-min="row.scale_min"
            :scale-max="row.scale_max"
            :band-low="band(row)[0]"
            :band-high="band(row)[1]"
          />
        </div>
      </ShellHudWindow>

      <div class="flex-1 min-w-0 flex flex-col gap-[18px]">
        <ShellHudWindow
class="h-[292px]" title="Live ECG & Body Temperature" icon="bolt"
                        :tag-text="ecg ? ecg.rhythm_text.toUpperCase() : 'NO SIGNAL'"
                        :tag-tone="ecg && ecg.rhythm_text !== 'Normal Sinus' ? 'critical' : 'reference'" flush>
          <div class="flex-1 m-[20px] tile relative">
            <template v-if="ecg && ecgChart">
              <span class="absolute top-[12px] left-[14px] mono text-[9.5px] text-cabin-ok z-10">
                LEAD {{ ecg.lead }} · {{ ecg.paper_speed_mm_s }} mm/s
              </span>
              <span class="absolute top-[12px] right-[14px] mono text-[9.5px] z-10">
                {{ ecg.heart_rate_bpm ?? '—' }} BPM · HRV {{ ecg.hrv_ms ?? '—' }} MS · {{ ecg.body_temp_c?.toFixed(1) ?? '—' }} °C
              </span>
              <ClientOnly>
                <VChart
:option="ecgChart" theme="spacescan-hud" autoresize class="absolute inset-0"
                        :aria-label="`Heart tracing, ${ecg.heart_rate_bpm} beats per minute, ${ecg.rhythm_text}`" />
              </ClientOnly>
            </template>
            <UiStateNote v-else empty="No heart tracing recorded yet." class="h-full" />
          </div>
        </ShellHudWindow>

        <ShellHudWindow class="flex-1" title="Periodic Clinical Lab Results" icon="kit" tag-text="LATEST RESULTS" flush>
          <div class="flex-1 grid grid-cols-2 gap-x-[16px] gap-y-[18px] p-[20px]">
            <div v-for="lab in profile.labs" :key="lab.metric_key" class="tile relative pl-[22px] pr-[16px] flex flex-col justify-center">
              <span class="absolute left-0 top-[14px] bottom-[14px] w-[3px] rounded-full" :class="accent(lab)" />
              <div class="flex items-center justify-between">
                <span
class="text-[9.5px] font-bold tracking-[0.04em] uppercase"
                      :class="lab.status === 'NOMINAL' ? 'text-cabin-ok' : 'text-cabin-ice'">{{ lab.title }}</span>
                <UiStatusPill size="sm" :tone="toneOf(lab.status) === 'critical' ? 'critical' : toneOf(lab.status) === 'watch' ? 'watch' : 'reference'">
                  {{ lab.status_text }}
                </UiStatusPill>
              </div>
              <p class="text-[24px] font-bold mt-[18px] leading-none">{{ labValue(lab) }}</p>
              <p class="text-[11.5px] text-cabin-ice mt-[16px] truncate">{{ lab.value == null && lab.value_text == null ? 'No result yet' : lab.note }}</p>
            </div>
          </div>
        </ShellHudWindow>
      </div>
    </div>
  </div>
</template>
