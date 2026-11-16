<script setup lang="ts">
import VChart from 'vue-echarts'
import type { MetricView } from '~/composables/useProfile'
import type { OcularPoint } from '~/utils/charts'
import { ocularTrendOption } from '~/utils/charts'
import type { ChartClick } from '~/composables/useChartPins'
import { interpretation, statusFor, type Thresholds } from '~/utils/chartDecor'
import { dayText, formatNumber, formatTime, scalePct, toneOf } from '~/utils/format'

interface Eye extends MetricView { eye_text: string }

interface FunctionalAcuitySide {
  snellen: string
  decimal: string
  logMar: string
  statusLabel: string
}

interface FunctionalAmslerEye {
  affectedCount: number
  affectedPercent: number
  hasMetamorphopsia: boolean
  hasScotoma: boolean
  status: string
  cells?: { r: number, c: number, t: string }[]
}

interface FunctionalExam {
  milestone: string
  next_milestone: string
  severity: string
  recorded_at_utc: string
  exam_day_label: string
  acuity_bilateral: {
    OD: FunctionalAcuitySide | null
    OS: FunctionalAcuitySide | null
    OU: FunctionalAcuitySide | null
  }
  amsler: {
    OD: FunctionalAmslerEye | null
    OS: FunctionalAmslerEye | null
  }
  symptoms: {
    risk_score: number
    risk_level: string
    triage_score: number
    triage_level: string
    active_flags: string[]
    answered_count: number
    total_questions: number
  }
}

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
  functional_exam?: FunctionalExam | null
  exam_at_utc: string | null
  exam_day_label: string | null
  follow_up_day_label: string | null
  trend: OcularPoint[]
  limits: { nominal_max_mm: number | null, alert_mm: number | null, baseline_low_mm: number | null }
  care_plan: { title_en: string, detail_en: string }[]
}

const { crew } = useSession()
const { api } = useApi()
const PERIODS = [{ id: '30d', label: '30D' }, { id: 'all', label: 'ALL' }]
const period = ref('all')
const { data, loading, error, refresh } = useResource(
  () => api<VisionExam>(`/vision/${crew.value!.id}`, { query: { period: period.value } }), 60_000, ['vision', 'alerts'])

usePageHeader(() => ({
  title: 'Vision & Ocular Exam',
  status: data.value ? { text: data.value.header_text, tone: toneOf(data.value.status) === 'critical' ? 'critical' : 'ok' } : null,
}))

const thresholds = computed<Thresholds>(() => {
  const l = data.value?.limits
  return {
    band: l?.baseline_low_mm != null && l.nominal_max_mm != null ? [Number(l.baseline_low_mm.toFixed(2)), l.nominal_max_mm] : null,
    watch: l?.nominal_max_mm != null ? [l.nominal_max_mm] : [],
    critical: l?.alert_mm != null ? [l.alert_mm] : [],
    alertWhen: 'above',
  }
})
const pins = useChartPins((click: ChartClick) => {
  const point = data.value?.trend[click.dataIndex]
  const side = click.seriesName === 'Right Eye' ? 'right' : click.seriesName === 'Left Eye' ? 'left' : null
  if (!point || !side || point[side] == null) return null
  const base = data.value!.trend.find(p => p.kind === 'BASELINE')?.[side] ?? null
  const value = point[side]!
  return {
    key: `${side}-${point.label}`, series: click.seriesName!, value, unit: 'mm', digits: 2,
    time_utc: point.recorded_at_utc ?? null, stage: point.mission_stage ?? null,
    delta: base == null ? null : value - base, reference_label: 'personal baseline',
    status: statusFor(value, thresholds.value), coord: [point.label, value],
  }
})
watch(period, () => {
  pins.clear()
  void refresh()
})
const chart = computed(() => {
  const d = data.value
  if (!d?.trend.length) return null
  const elevated = d.worst_side !== null && (d.limits.nominal_max_mm ?? 0) > 0
  return ocularTrendOption(d.trend, thresholds.value,
    elevated && d.follow_up_day_label ? { label: `Target ${d.follow_up_day_label}`, value: d.limits.nominal_max_mm! } : null,
    { 'Right Eye': pins.marks('Right Eye'), 'Left Eye': pins.marks('Left Eye') })
})
const reading = computed(() => interpretation(thresholds.value, 'mm'))
const eyeFraction = (eye: Eye) => (eye.value === null ? 0 : scalePct(eye.value, 3, 6.5) / 100)
const rows = computed(() => {
  const d = data.value
  if (!d) return []
  const p = d.pressure
  const fe = d.functional_exam
  const biAcuity = fe?.acuity_bilateral
  const acuityValue = biAcuity && (biAcuity.OD || biAcuity.OS)
    ? `OD ${biAcuity.OD?.snellen ?? '—'} · OS ${biAcuity.OS?.snellen ?? '—'}`
    : (d.acuity.value === null ? '—' : `20/${formatNumber(d.acuity.value)}`)
  return [
    { label: 'Intraocular Pressure', help: 'iop_left_mmhg', reference: p.baseline_low != null ? `Baseline: ${formatNumber(p.baseline_low, 1)}–${formatNumber(p.baseline_high, 1)} mmHg` : `Normal ${p.nominal_min}–${p.nominal_max} mmHg`,
      value: p.value === null ? '—' : p.value.toFixed(1), unit: 'mmHg', view: p, band: [p.baseline_low ?? p.nominal_min, p.baseline_high ?? p.nominal_max], scale: [6, 30] },
    { label: 'Retinal Layer Thickness', help: 'retinal_thickness_um', reference: d.retina.baseline_low != null ? `Baseline: ${formatNumber(d.retina.baseline_low)}–${formatNumber(d.retina.baseline_high)} µm` : 'No pre-flight value',
      value: formatNumber(d.retina.value), unit: 'µm', view: d.retina, band: [d.retina.baseline_low ?? d.retina.nominal_min, d.retina.baseline_high ?? d.retina.nominal_max], scale: [60, 150] },
    { label: 'Visual Acuity', help: 'visual_acuity_snellen', reference: fe?.milestone ? `${fe.milestone} · Clear central vision` : 'Clear central & peripheral vision',
      value: acuityValue, unit: '', view: d.acuity, band: [10, 25], scale: [5, 80] },
  ]
})

const amslerBadgeText = (eye: FunctionalAmslerEye | null | undefined) => {
  if (!eye) return 'PENDING'
  if (eye.hasScotoma) return 'SCOTOMA'
  if (eye.hasMetamorphopsia) return 'METAMORPHOPSIA'
  return 'NOMINAL'
}

const amslerBadgeTone = (eye: FunctionalAmslerEye | null | undefined) => {
  if (!eye) return 'neutral'
  if (eye.hasScotoma || eye.status === 'critica') return 'critical'
  if (eye.hasMetamorphopsia || eye.status === 'warn') return 'watch'
  return 'ok'
}

const formatFlagLabel = (flag: string) => flag.replaceAll('_', ' ')
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
        class="w-[31.1%] shrink-0"
        title="Ocular Measurements"
        icon="sans"
        flush
        :tag-text="data.exam_day_label ? dayText(data.exam_day_label).toUpperCase() : 'NO EXAM'"
        :tag-tone="toneOf(data.status) === 'critical' ? 'critical' : 'reference'"
      >
        <UiStateNote v-if="!data.exam_at_utc" empty="No eye exam recorded yet. Use Capture · Vision & Ocular." />
        <div v-else class="flex-1 min-h-0 flex flex-col px-[19px] pt-[clamp(10px,1.8dvh,17px)] pb-[16px]">
          <div class="tile h-[clamp(104px,13.2dvh,140px)] shrink-0 flex items-center px-[clamp(14px,1.6vw,24px)] gap-[clamp(14px,1.8vw,28px)]">
            <UiHoloFigure figure="brain" :tone="toneOf(data.status)" size="clamp(70px, 9.4dvh, 104px)" label="Neuro-ocular summary" />
            <div class="min-w-0">
              <p class="label-caps">Ocular alert summary</p>
              <p class="text-[16px] font-bold mt-[10px]">{{ data.headline }}</p>
              <p class="text-[11.5px] text-cabin-ice mt-[10px]">{{ data.review.text }}</p>
            </div>
          </div>
          <div class="grid grid-cols-2 gap-[16px] mt-[clamp(10px,2.3dvh,22px)] h-[clamp(108px,13.4dvh,150px)] shrink-0">
            <div v-for="side in (['left', 'right'] as const)" :key="side" class="tile relative flex items-center justify-center">
              <span class="absolute top-[7px] right-[7px]"><UiParamHelp :metric-key="`optic_sheath_${side}_mm`" /></span>
              <UiArcGauge
                :fraction="eyeFraction(data.eyes[side])"
                :tone="toneOf(data.eyes[side].status) === 'watch' ? 'watch' : toneOf(data.eyes[side].status)"
                :label="`${side} eye`"
                :value="data.eyes[side].value === null ? '—' : data.eyes[side].value!.toFixed(1)"
                :caption="`mm (${data.eyes[side].eye_text})`"
                size="clamp(92px, 11.1dvh, 124px)"
                :value-size="22"
              />
            </div>
          </div>
          <div class="flex-1 min-h-0 flex flex-col justify-around gap-[6px] py-[6px]">
            <UiBandRow
              v-for="row in rows"
              :key="row.label"
              :label="row.label"
              :help-key="row.help"
              :reference="row.reference"
              :value-text="row.value"
              :unit="row.unit"
              :status="row.view.status"
              :status-text="row.view.status_text"
              :value="row.view.value"
              :scale-min="row.scale[0]"
              :scale-max="row.scale[1]"
              :band-low="row.band[0]"
              :band-high="row.band[1]"
            />
          </div>
          <div class="tile-hi h-[clamp(60px,7.9dvh,84px)] shrink-0 px-[18px] flex flex-col justify-center">
            <p class="text-[10px] font-bold tracking-[0.04em] uppercase text-cabin-ok">
              Latest exam · {{ dayText(data.exam_day_label) }} · {{ formatTime(data.exam_at_utc) }} UTC
            </p>
            <p class="text-[12px] mt-[6px]">
              <template v-if="data.functional_exam?.next_milestone">
                {{ data.functional_exam.milestone }} · Next scheduled: {{ data.functional_exam.next_milestone }}
              </template>
              <template v-else>
                Bilateral scan recorded<template v-if="data.follow_up_day_label"> · Next follow-up scheduled {{ dayText(data.follow_up_day_label) }}</template>
              </template>
            </p>
          </div>
        </div>
      </ShellHudWindow>

      <div class="flex-1 min-w-0 flex flex-col gap-[18px]">
        <ShellHudWindow class="flex-[1.2] min-h-0" title="Optic Nerve Sheath Trend (mm)" icon="reticle" tag-text="BILATERAL" help-key="optic_sheath_left_mm" flush>
          <div class="flex-1 min-h-0 flex flex-col m-[14px]">
            <UiInteractiveChartFrame v-model:period="period" :periods="PERIODS" :pins="pins.pins.value" :interpretation="reading" @unpin="pins.remove" @point="pins.onClick">
              <template v-if="chart">
                <div class="absolute top-[4px] right-[40px] z-10 flex gap-[26px] text-[11px] font-semibold pointer-events-none">
                  <span class="flex items-center gap-[7px]"><i class="w-[8px] h-[8px] rounded-full bg-cabin-crit" />Right Eye ({{ data.eyes.right.value?.toFixed(1) ?? '—' }} mm)</span>
                  <span class="flex items-center gap-[7px]"><i class="w-[8px] h-[8px] rounded-full bg-cabin-ok" />Left Eye ({{ data.eyes.left.value?.toFixed(1) ?? '—' }} mm)</span>
                </div>
                <ClientOnly>
                  <VChart
                    :option="chart"
                    theme="spacescan-hud"
                    autoresize
                    class="absolute inset-0"
                    aria-label="Optic nerve sheath of both eyes at each exam"
                  />
                </ClientOnly>
              </template>
              <UiStateNote v-else class="h-full" empty="No exam in this window." />
            </UiInteractiveChartFrame>
          </div>
        </ShellHudWindow>

        <ShellHudWindow
          class="flex-1 min-h-0"
          :title="data.functional_exam ? 'Visual Battery Summary &amp; Preventive Care' : 'Preventive Care Plan'"
          icon="shield"
          :tag-text="data.functional_exam ? data.functional_exam.milestone.toUpperCase() : `${data.care_plan.length} STEPS`"
          flush
        >
          <div class="flex-1 min-h-0 flex flex-col gap-[12px] p-[clamp(10px,1.8dvh,18px)] hud-scroll">
            <div v-if="data.functional_exam" class="grid grid-cols-3 gap-[12px] shrink-0">
              <div class="tile px-[14px] py-[10px]">
                <p class="label-caps text-cabin-ok">Amsler Grid (OD / OS)</p>
                <div class="mt-[8px] flex items-center gap-[10px]">
                  <div v-for="eyeKey in (['OD', 'OS'] as const)" :key="eyeKey" class="flex items-center gap-[8px] flex-1 min-w-0">
                    <svg class="w-[44px] h-[44px] shrink-0 rounded-[4px] border border-cabin-line" viewBox="0 0 100 100" aria-hidden="true">
                      <rect width="100" height="100" class="fill-cabin-bg" />
                      <line v-for="n in 4" :key="'h'+n" x1="0" :y1="n * 20" x2="100" :y2="n * 20" class="stroke-cabin-line" stroke-width="1" />
                      <line v-for="n in 4" :key="'v'+n" :x1="n * 20" y1="0" :x2="n * 20" y2="100" class="stroke-cabin-line" stroke-width="1" />
                      <rect
                        v-for="(cell, idx) in (data.functional_exam.amsler[eyeKey]?.cells ?? [])"
                        :key="idx"
                        :x="cell.c * 5"
                        :y="cell.r * 5"
                        width="5"
                        height="5"
                        :class="cell.t === 'scotoma' ? 'fill-cabin-crit' : 'fill-cabin-navy-edge'"
                      />
                      <circle cx="50" cy="50" r="3.5" class="fill-cabin-text" />
                    </svg>
                    <div class="min-w-0">
                      <p class="mono text-[10.5px] font-bold">{{ eyeKey }} · {{ data.functional_exam.amsler[eyeKey]?.affectedPercent ?? 0 }}%</p>
                      <UiStatusPill size="sm" :tone="amslerBadgeTone(data.functional_exam.amsler[eyeKey])" class="mt-[3px]">
                        {{ amslerBadgeText(data.functional_exam.amsler[eyeKey]) }}
                      </UiStatusPill>
                    </div>
                  </div>
                </div>
              </div>

              <div class="tile px-[14px] py-[10px]">
                <p class="label-caps text-cabin-ok">Landolt C Acuity &amp; Schedule</p>
                <div class="mt-[8px] flex items-baseline justify-between gap-[8px]">
                  <span class="mono text-[13px] font-bold">
                    OD: {{ data.functional_exam.acuity_bilateral.OD?.snellen ?? '—' }}
                  </span>
                  <span class="mono text-[13px] font-bold">
                    OS: {{ data.functional_exam.acuity_bilateral.OS?.snellen ?? '—' }}
                  </span>
                </div>
                <p class="text-[11px] text-cabin-ice mt-[6px] truncate">
                  Next check: {{ data.functional_exam.next_milestone }}
                </p>
              </div>

              <div class="tile px-[14px] py-[10px]">
                <p class="label-caps text-cabin-ok">SANS Symptoms &amp; Risk</p>
                <div class="mt-[6px] flex items-center justify-between gap-[6px]">
                  <span class="mono text-[14px] font-bold">{{ data.functional_exam.symptoms.triage_score }} / 100</span>
                  <UiStatusPill size="sm" :tone="data.functional_exam.symptoms.triage_level === 'ALERT' ? 'critical' : data.functional_exam.symptoms.triage_level === 'OBSERVATION' ? 'watch' : 'ok'">
                    {{ data.functional_exam.symptoms.triage_level }}
                  </UiStatusPill>
                </div>
                <p class="text-[11px] text-cabin-ice mt-[5px] truncate">
                  <template v-if="data.functional_exam.symptoms.active_flags.length">
                    {{ data.functional_exam.symptoms.active_flags.map(formatFlagLabel).join(' · ') }}
                  </template>
                  <template v-else>
                    No active visual symptoms ({{ data.functional_exam.symptoms.answered_count }}/{{ data.functional_exam.symptoms.total_questions }})
                  </template>
                </p>
              </div>
            </div>

            <div class="flex-1 min-h-0 grid grid-cols-3 gap-[14px]">
              <div v-for="(step, index) in data.care_plan" :key="step.title_en" class="tile relative min-h-0 overflow-hidden px-[18px] pt-[clamp(12px,2.2dvh,22px)] pb-[10px]">
                <span class="absolute top-0 left-0 right-0 h-[3px]" :class="stepTone(index)" />
                <p class="text-[10.5px] font-bold tracking-[0.03em] uppercase" :class="index < 2 ? 'text-cabin-ok' : 'text-cabin-ice'">
                  0{{ index + 1 }} · {{ KICKERS[step.title_en] ?? 'Care Step' }}
                </p>
                <p class="text-[15px] font-bold mt-[clamp(6px,1.3dvh,14px)]">{{ step.title_en }}</p>
                <p class="text-[11.5px] text-cabin-ice mt-[clamp(4px,1.1dvh,12px)] leading-[1.55]">{{ step.detail_en }}</p>
              </div>
            </div>
          </div>
        </ShellHudWindow>
      </div>
    </div>
  </div>
</template>
