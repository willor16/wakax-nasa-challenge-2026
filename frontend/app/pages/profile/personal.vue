<script setup lang="ts">
// 04 · Astronaut Profile · Personal Data (read-only).
import type { MetricView } from '~/composables/useProfile'
import { dayText, digitsFor, formatDuration, formatNumber, litres, scalePct, sexText, toneOf } from '~/utils/format'

const { data: profile, loading, error, refresh } = useProfile()

usePageHeader(() => ({
  title: 'Astronaut Profile · Personal Data',
  status: profile.value
    ? { text: profile.value.status === 'Attention' ? 'ATTENTION' : profile.value.status.toUpperCase(),
        tone: profile.value.status === 'Attention' ? 'critical' : 'ok' }
    : null,
}))

function caption(card: MetricView): string {
  if (card.value === null) return 'No reading yet'
  switch (card.metric_key) {
    case 'bmi_kg_m2': return `Normal: ${card.nominal_min}–${card.nominal_max}`
    case 'muscle_mass_kg': return card.baseline_pct != null ? `${card.baseline_pct}% retained` : 'No pre-flight value'
    case 'bone_density_g_cm2': return card.baseline_pct != null ? `${card.baseline_pct}% of baseline` : 'No pre-flight value'
    case 'vo2_max_ml_kg_min': return card.status === 'NOMINAL' ? 'Optimal range' : `${card.baseline_pct}% of pre-flight`
    default:
      return card.baseline_mean != null
        ? `Baseline: ${formatNumber(card.baseline_mean, digitsFor(card.unit, card.metric_key))} ${card.unit}`
        : 'No pre-flight value'
  }
}
const cardTitle: Record<string, string> = {
  height_cm: 'Height', body_weight_kg: 'Weight', bmi_kg_m2: 'Body Mass Index',
  muscle_mass_kg: 'Muscle Mass', bone_density_g_cm2: 'Bone Density', vo2_max_ml_kg_min: 'Aerobic Capacity',
}
const DIAL_HELP: Record<string, string> = {
  'Temperature': 'cabin_temp_c', 'Humidity': 'cabin_humidity_pct', 'Ambient Noise': 'cabin_noise_dba', 'Cabin CO₂': 'cabin_co2_ppm',
}
const cardUnit: Record<string, string> = { vo2_max_ml_kg_min: 'mL/kg', bmi_kg_m2: '' }
function valueText(card: MetricView): string {
  const digits = card.metric_key === 'bone_density_g_cm2' ? 2 : 1
  const unit = cardUnit[card.metric_key] ?? card.unit
  return card.value === null ? '—' : `${formatNumber(card.value, digits)}${unit ? ` ${unit}` : ''}`
}
const barClass = (card: MetricView) => ({
  ok: 'bg-cabin-ok', watch: 'bg-cabin-navy-edge', critical: 'bg-cabin-crit', neutral: 'bg-cabin-dim',
})[card.metric_key === 'height_cm' && card.value !== null ? 'ok' : toneOf(card.status)]

const env = computed(() => profile.value?.environment ?? null)
const dials = computed(() => {
  const e = env.value
  if (!e) return []
  return [
    { label: 'Temperature', value: e.temp_c.toFixed(1), caption: '°C', status: e.statuses.temp_c,
      fraction: scalePct(e.temp_c, 15, 32) / 100 },
    { label: 'Humidity', value: `${Math.round(e.humidity_pct)}%`,
      caption: `Optimal ${e.limits.humidity_pct[0]}–${e.limits.humidity_pct[1]}%`, status: e.statuses.humidity_pct,
      fraction: e.humidity_pct / 100 },
    { label: 'Ambient Noise', value: String(Math.round(e.noise_dba)),
      caption: `dBA (<${e.limits.noise_dba_max} dBA)`, status: e.statuses.noise_dba,
      fraction: scalePct(e.noise_dba, 30, 85) / 100 },
    { label: 'Cabin CO₂', value: e.co2_mmhg.toFixed(1), caption: `mmHg (<${e.limits.co2_mmhg.alert.toFixed(1)})`,
      status: e.statuses.co2_ppm, fraction: e.co2_mmhg / e.limits.co2_mmhg.physician },
  ]
})
const { clockText } = useMission()
const hydration = computed(() => profile.value?.scan)
</script>

<template>
  <div class="page">
  <ShellProfileTabs />
  <UiStateNote v-if="!profile" :loading="loading" :error="error" @retry="refresh()" />
  <div v-else class="flex-1 min-h-0 flex gap-[18px]">
    <ShellHudWindow class="w-[33.2%] shrink-0" title="Personal Biometrics" icon="profile" :tag-text="profile.crew.code" flush>
      <div class="flex-1 flex flex-col px-[19px] pt-[17px] pb-[16px]">
        <div class="tile-hi h-[80px] px-[18px] flex flex-col justify-center">
          <div class="flex items-center justify-between">
            <span class="text-[17px] font-bold">{{ profile.crew.full_name }}</span>
            <UiStatusPill>{{ profile.crew.title_en.toUpperCase() }}</UiStatusPill>
          </div>
          <p class="text-[12px] text-cabin-ice mt-[8px]">
            Age: {{ profile.crew.age ?? '—' }} yrs · Sex: {{ sexText(profile.crew.sex) }} · Blood Type: {{ profile.crew.blood_type ?? '—' }}
          </p>
        </div>
        <div class="grid grid-cols-2 gap-x-[14px] gap-y-[clamp(10px,1.9dvh,18px)] mt-[clamp(12px,2.6dvh,24px)] flex-1 min-h-0">
          <div v-for="card in profile.biometrics" :key="card.metric_key" class="tile relative overflow-hidden px-[18px] flex flex-col justify-center">
            <span class="absolute top-0 left-0 right-0 h-[3px]" :class="barClass(card)" />
            <p class="label-caps flex items-center gap-[6px]">{{ cardTitle[card.metric_key] }}<UiParamHelp :metric-key="card.metric_key" /></p>
            <p class="text-[23px] font-bold mt-[clamp(8px,1.9dvh,18px)] leading-none">{{ valueText(card) }}</p>
            <p class="text-[11px] text-cabin-ice mt-[clamp(8px,2.1dvh,20px)]">{{ caption(card) }}</p>
          </div>
        </div>
      </div>
    </ShellHudWindow>

    <ShellHudWindow
class="w-[30.8%] shrink-0" title="Biometric Scan" icon="vitruvian"
                    :tag-text="profile.status.toUpperCase()" :tag-tone="profile.status === 'Attention' ? 'critical' : 'reference'" flush>
      <div class="flex-1 flex flex-col items-center px-[19px] pb-[19px]">
        <UiHoloFigure
figure="body-scan" size="min(clamp(220px, 50dvh, 760px), calc(30.8vw - 60px))" class="mt-[clamp(10px,3.6dvh,34px)]"
                      :label="`Biometric scan of ${profile.crew.full_name}: ${profile.status}`" />
        <div class="mt-auto w-full grid grid-cols-2 gap-[12px]">
          <div class="tile h-[clamp(60px,7.7dvh,84px)] px-[16px] flex flex-col justify-center">
            <p class="label-caps flex items-center gap-[6px]">Core temp<UiParamHelp metric-key="body_temp_c" /></p>
            <p class="text-[17px] font-bold mt-[8px]">
              {{ profile.scan.core_temp.value === null ? '—' : `${profile.scan.core_temp.value.toFixed(1)} °C` }}
            </p>
          </div>
          <div class="tile h-[clamp(60px,7.7dvh,84px)] px-[16px] flex flex-col justify-center">
            <p class="label-caps flex items-center gap-[6px]">Hydration · {{ profile.habits_day_label }}<UiParamHelp metric-key="hydration_ml" /></p>
            <p class="text-[17px] font-bold mt-[8px]">
              {{ litres(hydration?.hydration_ml) }} / {{ litres(hydration?.hydration_target_ml) }} L
            </p>
          </div>
        </div>
      </div>
    </ShellHudWindow>

    <ShellHudWindow
class="flex-1" title="Environment & Work Hours" icon="rocket"
                    :tag-text="env?.location_en?.toUpperCase()" flush>
      <div class="flex-1 min-h-0 flex flex-col px-[clamp(16px,1.7vw,26px)] pt-[clamp(14px,2.8dvh,26px)] pb-[16px]">
        <div v-if="env" class="grid grid-cols-2 gap-[clamp(10px,1.9dvh,18px)]">
          <div v-for="dial in dials" :key="dial.label" class="tile relative h-[clamp(108px,15.2dvh,250px)] flex items-center justify-center">
            <span class="absolute top-[7px] right-[7px]"><UiParamHelp :metric-key="DIAL_HELP[dial.label]!" /></span>
            <UiArcGauge
:fraction="dial.fraction" :tone="toneOf(dial.status)" :label="dial.label" :value="dial.value"
                        :caption="dial.caption" size="clamp(98px, 11.9dvh, 190px)" :value-size="20" />
          </div>
        </div>
        <UiStateNote v-else empty="No cabin reading yet." class="!flex-none h-[clamp(228px,32dvh,360px)]" />

        <p class="label-caps mt-[clamp(12px,3.2dvh,30px)]">Work time · {{ dayText(profile.habits_day_label).toUpperCase() }}</p>
        <div class="flex flex-col gap-[clamp(8px,1.6dvh,15px)] mt-[12px]">
          <div
v-for="row in [
            { title: 'Interior Work (IVA)', help: 'work_shift_min', note: profile.work.interior_location_en ? `${profile.work.interior_location_en} · Active Shift` : 'No interior shift logged',
              value: formatDuration(profile.work.interior_min), tone: profile.work.interior_min ? 'ok' : 'neutral' },
            { title: 'Exterior Work (EVA)', help: 'eva_shift_min', note: `Mission Cumulative: ${formatDuration(profile.work.exterior_mission_min)}`,
              value: formatDuration(profile.work.exterior_min), tone: 'ok' },
            { title: 'Mission Elapsed Time', help: 'mission_elapsed', note: `${clockText.split('· ')[1] ?? ''} · Schedule ${profile.mission_stage === 'MISSION' ? 'Nominal' : profile.mission_stage.toLowerCase()}`,
              value: profile.work.mission_elapsed_days === null ? '—' : `${profile.work.mission_elapsed_days} Days`, tone: 'ok' },
          ]" :key="row.title" class="tile relative h-[clamp(56px,8dvh,120px)] pl-[22px] pr-[20px] flex items-center justify-between">
            <span class="absolute left-0 top-[12px] bottom-[12px] w-[3px] rounded-full" :class="row.tone === 'ok' ? 'bg-cabin-ok' : 'bg-cabin-dim'" />
            <div>
              <p class="label-caps flex items-center gap-[6px]">{{ row.title }}<UiParamHelp :metric-key="row.help" /></p>
              <p class="text-[12px] text-cabin-ice mt-[8px]">{{ row.note }}</p>
            </div>
            <span class="text-[22px] font-bold">{{ row.value }}</span>
          </div>
        </div>
      </div>
    </ShellHudWindow>
  </div>
  </div>
</template>
