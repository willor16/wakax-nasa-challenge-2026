<script setup lang="ts">
// 08 · Vision & Ocular Exam (read-only): both eyes, optic nerve sheath trend, care plan.
import VChart from 'vue-echarts'
import type { MetricView } from '~/composables/useProfile'
import type { OcularPoint } from '~/utils/charts'
import { ocularTrendOption } from '~/utils/charts'
import { dayText, formatNumber, formatTime, scalePct, toneOf } from '~/utils/format'

interface Eye extends MetricView { eye_text: string }
interface VisionExam {
  status: string
  header_text: string
  headline: string
  worst_side: 'left' | 'right' | null
  review: { state: string, text: string, notes_en: string | null }
  eyes: { left: Eye, right: Eye }
  pressure: MetricView
  retina: MetricView
  acuity: MetricView
  exam_at_utc: string | null
  exam_day_label: string | null
  follow_up_day_label: string | null
  trend: OcularPoint[]
  limits: { nominal_max_mm: number | null, alert_mm: number | null, baseline_low_mm: number | null }
  care_plan: { title_en: string, detail_en: string }[]
}

const { crew } = useSession()
const { api } = useApi()
const { data, loading, error, refresh } = useResource(() => api<VisionExam>(`/vision/${crew.value!.id}`), 60_000)

usePageHeader(() => ({
  title: 'Vision & Ocular Exam',
  status: data.value ? { text: data.value.header_text, tone: toneOf(data.value.status) === 'critical' ? 'critical' : 'ok' } : null,
}))

const chart = computed(() => {
  const d = data.value
  if (!d?.trend.length) return null
  const elevated = d.worst_side !== null && (d.limits.nominal_max_mm ?? 0) > 0
  return ocularTrendOption(d.trend, {
    alert: d.limits.alert_mm, nominalMax: d.limits.nominal_max_mm, baselineLow: d.limits.baseline_low_mm,
  }, elevated && d.follow_up_day_label ? { label: `Target ${d.follow_up_day_label}`, value: d.limits.nominal_max_mm! } : null)
})
const eyeFraction = (eye: Eye) => (eye.value === null ? 0 : scalePct(eye.value, 3, 6.5) / 100)
const rows = computed(() => {
  const d = data.value
  if (!d) return []
  const p = d.pressure
  return [
    { label: 'Intraocular Pressure', reference: p.baseline_low != null ? `Baseline: ${formatNumber(p.baseline_low, 1)}–${formatNumber(p.baseline_high, 1)} mmHg` : `Normal ${p.nominal_min}–${p.nominal_max} mmHg`,
      value: p.value === null ? '—' : p.value.toFixed(1), unit: 'mmHg', view: p, band: [p.baseline_low ?? p.nominal_min, p.baseline_high ?? p.nominal_max], scale: [6, 30] },
    { label: 'Retinal Layer Thickness', reference: d.retina.baseline_low != null ? `Baseline: ${formatNumber(d.retina.baseline_low)}–${formatNumber(d.retina.baseline_high)} µm` : 'No pre-flight value',
      value: formatNumber(d.retina.value), unit: 'µm', view: d.retina, band: [d.retina.baseline_low ?? d.retina.nominal_min, d.retina.baseline_high ?? d.retina.nominal_max], scale: [60, 150] },
    { label: 'Visual Acuity', reference: 'Clear central & peripheral vision',
      value: d.acuity.value === null ? '—' : `20/${formatNumber(d.acuity.value)}`, unit: '', view: d.acuity, band: [10, 25], scale: [5, 80] },
  ]
})
const stepTone = (index: number) => (index < 2 ? 'bg-cabin-ok' : 'bg-cabin-navy-edge')
const KICKERS: Record<string, string> = {
  'Lower-Body Negative Pressure': 'Evening Pressure Session',
  'Sleep Station Ventilation': 'Cabin Airflow',
  'Scheduled Ultrasound': 'Follow-up Check',
}
</script>

<template>
  <div class="page">
    <UiStateNote v-if="!data" :loading="loading" :error="error" @retry="refresh()" />
    <div v-else class="flex-1 min-h-0 flex gap-[18px]">
      <ShellHudWindow
class="w-[470px]" title="Ocular Measurements" icon="sans" flush
                      :tag-text="data.exam_day_label ? dayText(data.exam_day_label).toUpperCase() : 'NO EXAM'"
                      :tag-tone="toneOf(data.status) === 'critical' ? 'critical' : 'reference'">
        <UiStateNote v-if="!data.exam_at_utc" empty="No eye exam recorded yet. Use Capture · Vision & Ocular." />
        <div v-else class="flex-1 flex flex-col px-[19px] pt-[17px] pb-[16px]">
          <div class="tile h-[124px] shrink-0 flex items-center px-[24px] gap-[28px]">
            <UiHoloFigure figure="brain" :tone="toneOf(data.status)" :size="88" label="Neuro-ocular summary" />
            <div>
              <p class="label-caps">Ocular alert summary</p>
              <p class="text-[16px] font-bold mt-[10px]">{{ data.headline }}</p>
              <p class="text-[11.5px] text-cabin-ice mt-[10px]">{{ data.review.text }}</p>
            </div>
          </div>
          <div class="grid grid-cols-2 gap-[16px] mt-[22px] h-[126px] shrink-0">
            <div v-for="side in (['left', 'right'] as const)" :key="side" class="tile flex items-center justify-center">
              <UiArcGauge
:fraction="eyeFraction(data.eyes[side])" :tone="toneOf(data.eyes[side].status) === 'watch' ? 'watch' : toneOf(data.eyes[side].status)"
                          :label="`${side} eye`" :value="data.eyes[side].value === null ? '—' : data.eyes[side].value!.toFixed(1)"
                          :caption="`mm (${data.eyes[side].eye_text})`" :size="104" :value-size="22" />
            </div>
          </div>
          <div class="flex-1 flex flex-col justify-around">
            <UiBandRow
v-for="row in rows" :key="row.label" :label="row.label" :reference="row.reference" :value-text="row.value"
                       :unit="row.unit" :status="row.view.status" :status-text="row.view.status_text" :value="row.view.value"
                       :scale-min="row.scale[0]" :scale-max="row.scale[1]" :band-low="row.band[0]" :band-high="row.band[1]" />
          </div>
          <div class="tile-hi h-[74px] shrink-0 px-[18px] flex flex-col justify-center">
            <p class="text-[10px] font-bold tracking-[0.04em] uppercase text-cabin-ok">
              Latest ultrasound · {{ dayText(data.exam_day_label) }} · {{ formatTime(data.exam_at_utc) }} UTC
            </p>
            <p class="text-[12px] mt-[9px]">
              Bilateral scan recorded<template v-if="data.follow_up_day_label"> · Next follow-up scheduled {{ dayText(data.follow_up_day_label) }}</template>
            </p>
          </div>
        </div>
      </ShellHudWindow>

      <div class="flex-1 min-w-0 flex flex-col gap-[18px]">
        <ShellHudWindow class="h-[442px] shrink-0" title="Optic Nerve Sheath Trend (mm)" icon="reticle" tag-text="BILATERAL" flush>
          <div class="flex-1 relative m-[16px]">
            <template v-if="chart">
              <div class="absolute top-[10px] right-[30px] z-10 flex gap-[26px] text-[11px] font-semibold pointer-events-none">
                <span class="flex items-center gap-[7px]"><i class="w-[8px] h-[8px] rounded-full bg-cabin-crit" />Right Eye ({{ data.eyes.right.value?.toFixed(1) ?? '—' }} mm)</span>
                <span class="flex items-center gap-[7px]"><i class="w-[8px] h-[8px] rounded-full bg-cabin-ok" />Left Eye ({{ data.eyes.left.value?.toFixed(1) ?? '—' }} mm)</span>
              </div>
              <div class="absolute left-[64px] top-[34px] z-10 flex flex-col gap-[2px] text-[10px] font-bold pointer-events-none">
                <span v-if="data.limits.alert_mm">ALERT THRESHOLD ({{ data.limits.alert_mm }} mm)</span>
                <span v-if="data.limits.baseline_low_mm" class="text-cabin-ice">PERSONAL BASELINE ({{ data.limits.baseline_low_mm.toFixed(1) }} – {{ data.limits.nominal_max_mm?.toFixed(1) }} mm)</span>
              </div>
              <ClientOnly>
                <VChart
:option="chart" theme="spacescan-hud" autoresize class="absolute inset-0"
                        aria-label="Optic nerve sheath of both eyes at each exam" />
              </ClientOnly>
            </template>
            <UiStateNote v-else class="h-full" empty="The trend appears after the first in-flight exam." />
          </div>
        </ShellHudWindow>

        <ShellHudWindow class="flex-1" title="Preventive Care Plan" icon="shield" :tag-text="`${data.care_plan.length} STEPS`" flush>
          <div class="flex-1 grid grid-cols-3 gap-[16px] p-[22px]">
            <div v-for="(step, index) in data.care_plan" :key="step.title_en" class="tile relative px-[20px] pt-[30px]">
              <span class="absolute top-0 left-0 right-0 h-[3px]" :class="stepTone(index)" />
              <p class="text-[10.5px] font-bold tracking-[0.03em] uppercase" :class="index < 2 ? 'text-cabin-ok' : 'text-cabin-ice'">
                0{{ index + 1 }} · {{ KICKERS[step.title_en] ?? 'Care Step' }}
              </p>
              <p class="text-[16px] font-bold mt-[18px]">{{ step.title_en }}</p>
              <p class="text-[12px] text-cabin-ice mt-[18px] leading-[1.9]">{{ step.detail_en }}</p>
            </div>
          </div>
        </ShellHudWindow>
      </div>
    </div>
  </div>
</template>
