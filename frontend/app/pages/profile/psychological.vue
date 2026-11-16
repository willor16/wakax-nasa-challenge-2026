<script setup lang="ts">
import VChart from 'vue-echarts'
import type { ChartClick } from '~/composables/useChartPins'
import { cognitiveTrendOption, moodTrendOption } from '~/utils/charts'
import { interpretation, statusFor, type Thresholds } from '~/utils/chartDecor'
import { formatTime } from '~/utils/format'

interface Scale { value: number, range?: [number, number], target_below?: number, label: string }
interface MatrixSubscale { label: string, score: number, max: number, apa_mean: number, apa_label: string }
interface BehavioralMatrixData {
  total_load_score: number
  max_score: number
  mean_item_score: number
  readiness_status: string
  range_label: string
  subscales: Record<'T' | 'D' | 'C' | 'F' | 'S', MatrixSubscale>
  apa_crosswalk: { gad_mean: number, gad_scaled_40: number, gad_label: string, phq9_eq: number, phq9_category: string, stage2_triggered: boolean }
  elevated_alerts: string[]
  recorded_at_utc: string
}
interface AstroCowData {
  score: number
  high_score: number
  difficulty_level: number
  duration_sec: number
  mean_reaction_ms: number
  rt_variability_ms: number
  recovery_time_sec: number
  errors_after_change: number
  omitted_responses: number
  precision_pct: number
  collisions: number
  reticle_hits: number
  reticle_total: number
  focus_score: number
  pilot_readiness: string
  recorded_at_utc: string
}
interface NeuroFitData {
  copilot_id: string
  ecg_index: number
  total_score: number
  duration_sec: number
  overall_accuracy_pct: number
  mean_reaction_ms: number
  recovery_time_sec: number
  retention_pct: number
  sustained_attention_pct: number
  spatial_reasoning_pct: number
  visual_perception_pct: number
  focus_index_score: number
  recorded_at_utc: string
}
interface PsychProfile {
  crew_role?: string
  latest_state: { mood_state: string | null, recorded_at_utc: string, wellbeing_index: number } | null
  scales: { mood: Scale, stress_index: Scale, isolation: Scale, motivation: Scale } | null
  trend: { day_label: string, recorded_at_utc: string, mission_stage: string, mood: number, calmness: number }[]
  optimal_zone: [number, number]
  stability_pct: number
  reaction: null | {
    reaction_ms: number | null
    reaction_target_ms: number
    accuracy_pct: number
    accuracy_target_pct: number
    attention_score: number
    lapses: number
    trials_total: number
    valid_responses: number
  }
  behavioral_matrix?: BehavioralMatrixData | null
  astrocow?: AstroCowData | null
  astrocow_trend?: { day_label: string, precision_pct: number, focus_score: number, reaction_ms: number }[]
  neurofit?: NeuroFitData | null
  neurofit_trend?: { day_label: string, focus_index_score: number, retention_pct: number, sustained_attention_pct: number }[]
}

const { api } = useApi()
const PERIODS = [{ id: '7d', label: '7D' }, { id: '14d', label: '14D' }, { id: '30d', label: '30D' }, { id: 'all', label: 'ALL' }]
const period = ref('14d')
const { data, loading, error, refresh } = useResource(
  () => api<PsychProfile>('/psych/profile', { query: { period: period.value } }),
  60_000,
  ['psych', 'sleep', 'alerts'],
)

type TrendTab = 'mood' | 'astrocow' | 'neurofit'
type CogTab = 'reaction' | 'astrocow' | 'neurofit'
const trendTab = ref<TrendTab>('mood')
const cogTab = ref<CogTab>('reaction')

watch(data, (val) => {
  if (!val) return
  const entries: { tab: CogTab, ts: string }[] = []
  if (val.reaction) entries.push({ tab: 'reaction', ts: '' })
  if (val.astrocow) entries.push({ tab: 'astrocow', ts: val.astrocow.recorded_at_utc })
  if (val.neurofit) entries.push({ tab: 'neurofit', ts: val.neurofit.recorded_at_utc })
  if (val.astrocow && !val.reaction && !val.neurofit) cogTab.value = 'astrocow'
  else if (val.neurofit && !val.reaction && !val.astrocow) cogTab.value = 'neurofit'
  else if (entries.length > 1) {
    const latestGame = entries.filter(e => e.ts).sort((a, b) => b.ts.localeCompare(a.ts))[0]
    if (latestGame && cogTab.value === 'reaction') cogTab.value = latestGame.tab
  }
}, { immediate: true })

const STATES: Record<string, { title: string, detail: string }> = {
  CALM: { title: 'Calm & Focused', detail: 'Emotional stability and crew cohesion within optimal personal baseline.' },
  FOCUSED: { title: 'Focused', detail: 'Alert and engaged; keep regular breaks between demanding tasks.' },
  TIRED: { title: 'Tired', detail: 'Rest is the priority today; plan lighter tasks and an early rest period.' },
  STRESSED: { title: 'Under Strain', detail: 'Stress is above the usual level; the crew physician is available to talk.' },
}
const state = computed(() => STATES[data.value?.latest_state?.mood_state ?? ''] ?? null)
const scalesOk = computed(() => {
  const s = data.value?.scales
  const matrixBad = data.value?.behavioral_matrix && data.value.behavioral_matrix.total_load_score > 20
  return !!s && !matrixBad && s.stress_index.label === 'Low' && s.isolation.label === 'Low' && s.mood.label !== 'Low'
})
const reactionOk = computed(() => {
  const r = data.value?.reaction
  return !!r && r.reaction_ms !== null && r.reaction_ms < r.reaction_target_ms && r.accuracy_pct >= r.accuracy_target_pct
})

const isPilot = computed(() => data.value?.crew_role === 'PILOT')

usePageHeader(() => ({
  title: 'Astronaut Profile · Psychological',
  status: data.value?.scales
    ? { text: scalesOk.value ? 'Stable' : 'Support Advised', tone: scalesOk.value ? 'ok' : 'critical' }
    : null,
}))

const rows = computed(() => {
  const s = data.value?.scales
  if (!s) return []
  const range = (scale: Scale) => (scale.range ? `Personal baseline: ${scale.range[0].toFixed(1)}–${scale.range[1].toFixed(1)}` : '')
  return [
    {
      label: 'Overall Mood',
      help: 'overall_mood',
      ref: range(s.mood),
      value: s.mood.value.toFixed(1),
      max: '/ 5',
      pill: s.mood.label,
      pct: (s.mood.value - 1) / 4,
      band: s.mood.range ? [(s.mood.range[0] - 1) / 4, (s.mood.range[1] - 1) / 4] : null,
      good: s.mood.label !== 'Low',
    },
    {
      label: 'Stress Index',
      help: 'stress_index',
      ref: `Target range: < ${s.stress_index.target_below}`,
      value: String(s.stress_index.value),
      max: '/ 100',
      pill: s.stress_index.label,
      pct: s.stress_index.value / 100,
      band: [0.1, (s.stress_index.target_below ?? 40) / 100],
      good: s.stress_index.label === 'Low',
    },
    {
      label: 'Isolation',
      help: 'isolation',
      ref: `Target range: < ${s.isolation.target_below}`,
      value: s.isolation.value.toFixed(1),
      max: '/ 5',
      pill: s.isolation.label,
      pct: (s.isolation.value - 1) / 4,
      band: [0.08, ((s.isolation.target_below ?? 2.5) - 1) / 4],
      good: s.isolation.label === 'Low',
    },
    {
      label: 'Motivation',
      help: 'motivation',
      ref: range(s.motivation),
      value: s.motivation.value.toFixed(1),
      max: '/ 5',
      pill: s.motivation.label === 'Positive' ? 'High' : s.motivation.label,
      pct: (s.motivation.value - 1) / 4,
      band: s.motivation.range ? [(s.motivation.range[0] - 1) / 4, (s.motivation.range[1] - 1) / 4] : null,
      good: s.motivation.label !== 'Low',
    },
  ]
})

const thresholds = computed<Thresholds>(() => ({
  band: data.value?.optimal_zone ?? [3.8, 5],
  watch: [3],
  critical: [2],
  alertWhen: 'below',
}))
const pins = useChartPins((click: ChartClick) => {
  if (trendTab.value !== 'mood') return null
  const point = data.value?.trend[click.dataIndex]
  if (!point || !click.seriesName) return null
  const value = click.seriesName === 'Mood' ? point.mood : point.calmness
  const zone = thresholds.value.band!
  return {
    key: `${click.seriesName}-${point.recorded_at_utc}`,
    series: click.seriesName,
    value,
    unit: '/ 5',
    digits: 1,
    time_utc: point.recorded_at_utc,
    stage: point.mission_stage,
    delta: value - (zone[0] + zone[1]) / 2,
    reference_label: 'zone centre',
    status: statusFor(value, thresholds.value),
    coord: [point.day_label, value],
  }
})
watch(period, () => {
  pins.clear()
  void refresh()
})
watch(trendTab, () => pins.clear())

const chart = computed(() => {
  const d = data.value
  if (!d) return null
  if (trendTab.value === 'astrocow') {
    const pts = d.astrocow_trend ?? []
    if (!pts.length) return null
    return cognitiveTrendOption(
      pts.map(p => p.day_label),
      'Precision',
      pts.map(p => p.precision_pct),
      'Focus Score',
      pts.map(p => p.focus_score),
    )
  }
  if (trendTab.value === 'neurofit') {
    const pts = d.neurofit_trend ?? []
    if (!pts.length) return null
    return cognitiveTrendOption(
      pts.map(p => p.day_label),
      'Focus Index',
      pts.map(p => p.focus_index_score),
      'Retention',
      pts.map(p => p.retention_pct),
    )
  }
  return d.trend.length
    ? moodTrendOption(d.trend, thresholds.value, { Mood: pins.marks('Mood'), Calmness: pins.marks('Calmness') })
    : null
})
const reading = computed(() => (trendTab.value === 'mood' ? interpretation(thresholds.value, '/ 5') : null))
const periodTitle = computed(() => ({
  '7d': 'Last 7 Days',
  '14d': 'Last 14 Days',
  '30d': 'Last 30 Days',
  'all': 'Whole Mission',
} as Record<string, string>)[period.value])
const lastTrend = computed(() => data.value?.trend.at(-1) ?? null)

const cogWindowTag = computed(() => {
  if (cogTab.value === 'astrocow') {
    const a = data.value?.astrocow
    if (!a) return 'NO FLIGHT YET'
    return isPilot.value ? `PILOT · ${a.pilot_readiness}` : a.pilot_readiness
  }
  if (cogTab.value === 'neurofit') {
    const nf = data.value?.neurofit
    if (!nf) return 'NO BATTERY YET'
    return nf.focus_index_score >= 70 ? `FOCUS ${Math.round(nf.focus_index_score)}/100` : `LOW FOCUS ${Math.round(nf.focus_index_score)}/100`
  }
  return data.value?.reaction ? (reactionOk.value ? 'OPTIMAL' : 'BELOW TARGET') : 'NO TEST YET'
})

const cogWindowCritical = computed(() => {
  if (cogTab.value === 'astrocow') return Boolean(data.value?.astrocow && data.value.astrocow.pilot_readiness !== 'NOMINAL')
  if (cogTab.value === 'neurofit') return Boolean(data.value?.neurofit && data.value.neurofit.focus_index_score < 65)
  return Boolean(data.value?.reaction && !reactionOk.value)
})

function matrixTone(status: string | undefined) {
  if (status === 'RESTRICTED DUTY') return 'critical'
  if (status === 'MONITORING REQUIRED') return 'watch'
  return 'ok'
}
</script>

<template>
  <div class="page">
    <ShellProfileTabs />
    <UiStateNote v-if="!data" :loading="loading" :error="error" @retry="refresh()" />
    <div v-else class="flex-1 min-h-0 flex gap-[18px]">
      <ShellHudWindow
        class="w-[40.5%] shrink-0"
        title="Behavioral &amp; Mood Results"
        icon="profile"
        :tag-text="data.scales ? (scalesOk ? 'OPTIMAL' : 'SUPPORT') : 'NO DATA'"
        :tag-tone="data.scales && !scalesOk ? 'critical' : 'reference'"
        flush
      >
        <UiStateNote v-if="!data.scales" empty="No daily check-in logged yet. Use Capture · Psych, Motor &amp; Sleep." />
        <div v-else class="flex-1 min-h-0 flex flex-col px-[20px] pt-[clamp(10px,1.6dvh,16px)] pb-[12px] gap-[8px] hud-scroll">
          <div class="tile-hi relative h-[clamp(60px,8dvh,84px)] shrink-0 pl-[18px] pr-[16px] flex flex-col justify-center">
            <span class="absolute left-0 top-[10px] bottom-[10px] w-[3px] rounded-full" :class="scalesOk ? 'bg-cabin-ok' : 'bg-cabin-crit'" />
            <div class="flex items-center justify-between">
              <span class="text-[10px] font-bold tracking-[0.04em] uppercase" :class="scalesOk ? 'text-cabin-ok' : 'text-cabin-text'">
                Latest daily state<template v-if="state"> · {{ state.title }}</template>
              </span>
              <UiStatusPill>{{ formatTime(data.latest_state?.recorded_at_utc) }} UTC LOG</UiStatusPill>
            </div>
            <p class="text-[12px] mt-[6px]">{{ state?.detail ?? 'Daily check-in recorded.' }}</p>
          </div>

          <div class="flex-1 min-h-0 flex flex-col justify-around gap-[6px]">
            <div v-for="row in rows" :key="row.label">
              <div class="flex items-start justify-between">
                <div>
                  <p class="text-[12.5px] font-semibold flex items-center gap-[6px]">{{ row.label }}<UiParamHelp :metric-key="row.help" /></p>
                  <p class="text-[10px] text-cabin-ice mt-[2px]">{{ row.ref }}</p>
                </div>
                <div class="flex items-center gap-[14px]">
                  <p class="text-[19px] font-bold leading-none">{{ row.value }}<span class="text-[10px] text-cabin-ice font-normal ml-[5px]">{{ row.max }}</span></p>
                  <UiStatusPill :tone="row.good ? 'reference' : 'critical'" class="min-w-[74px]">{{ row.pill }}</UiStatusPill>
                </div>
              </div>
              <div class="relative h-[9px] mt-[clamp(4px,1dvh,10px)]" aria-hidden="true">
                <div class="absolute left-0 right-0 top-[3px] h-[3px] rounded-full bg-cabin-track" />
                <div
                  v-if="row.band"
                  class="absolute top-[1px] h-[7px] rounded-full bg-[var(--color-band-fill)] border border-cabin-navy-edge/70"
                  :style="{ left: `${row.band[0]! * 100}%`, width: `${Math.max(2, (row.band[1]! - row.band[0]!) * 100)}%` }"
                />
                <i
                  class="absolute top-[1px] w-[7px] h-[7px] -ml-[3.5px] rounded-full"
                  :class="row.good ? 'bg-cabin-ok' : 'bg-cabin-crit'"
                  :style="{ left: `${Math.min(100, Math.max(0, row.pct * 100))}%` }"
                />
              </div>
            </div>
          </div>

          <div v-if="data.behavioral_matrix" class="tile-hi p-[10px] shrink-0">
            <div class="flex items-center justify-between gap-[8px]">
              <p class="label-caps text-cabin-ok">20-Item Matrix · {{ data.behavioral_matrix.total_load_score }}/80 pts</p>
              <UiStatusPill size="sm" :tone="matrixTone(data.behavioral_matrix.readiness_status)">
                {{ data.behavioral_matrix.readiness_status }}
              </UiStatusPill>
            </div>
            <div class="grid grid-cols-5 gap-[6px] mt-[6px] mono text-[10px]">
              <div v-for="(sub, code) in data.behavioral_matrix.subscales" :key="code" class="tile px-[6px] py-[4px] text-center">
                <span class="font-bold">{{ code }}</span>
                <span class="block text-cabin-ice">{{ sub.score }}/16</span>
              </div>
            </div>
            <p class="mono text-[10px] text-cabin-ice mt-[6px] truncate">
              DSM-5-TR: GAD {{ data.behavioral_matrix.apa_crosswalk.gad_mean.toFixed(2) }}/4 · PHQ-9 {{ data.behavioral_matrix.apa_crosswalk.phq9_eq }}/27
            </p>
          </div>
        </div>
      </ShellHudWindow>

      <div class="flex-1 min-w-0 flex flex-col gap-[18px]">
        <ShellHudWindow
          class="flex-[1.25] min-h-0"
          :title="`Mood &amp; Cognitive Trend · ${periodTitle}`"
          icon="reticle"
          help-key="mood_calmness"
          :tag-text="data.trend.length ? `STABILITY ${data.stability_pct}%` : undefined"
          flush
        >
          <div class="flex-1 min-h-0 flex flex-col mx-[18px] my-[10px]">
            <div class="flex flex-wrap items-center justify-between gap-[8px] mb-[6px] shrink-0">
              <div class="flex gap-[6px]">
                <button
                  type="button"
                  class="focus-ring px-[10px] py-[3px] rounded-[4px] border mono text-[10px] font-bold"
                  :class="trendTab === 'mood' ? 'menu-item-active text-cabin-text' : 'border-cabin-line text-cabin-ice'"
                  @click="trendTab = 'mood'"
                >
                  Mood &amp; Calmness
                </button>
                <button
                  type="button"
                  class="focus-ring px-[10px] py-[3px] rounded-[4px] border mono text-[10px] font-bold"
                  :class="trendTab === 'astrocow' ? 'menu-item-active text-cabin-text' : 'border-cabin-line text-cabin-ice'"
                  @click="trendTab = 'astrocow'"
                >
                  AST-01 Precision
                </button>
                <button
                  type="button"
                  class="focus-ring px-[10px] py-[3px] rounded-[4px] border mono text-[10px] font-bold"
                  :class="trendTab === 'neurofit' ? 'menu-item-active text-cabin-text' : 'border-cabin-line text-cabin-ice'"
                  @click="trendTab = 'neurofit'"
                >
                  NeuroFit Focus
                </button>
              </div>
              <span v-if="isPilot" class="mono text-[10px] font-bold text-cabin-ok">PILOT FLIGHT COGNITION MONITOR</span>
            </div>

            <UiInteractiveChartFrame v-model:period="period" :periods="PERIODS" :pins="pins.pins.value" :interpretation="reading" @unpin="pins.remove" @point="pins.onClick">
              <template v-if="chart">
                <div v-if="trendTab === 'mood'" class="absolute top-[10px] left-[52px] right-[26px] z-10 flex items-center justify-between pointer-events-none">
                  <span class="text-[10px] font-bold">OPTIMAL WELLBEING ZONE ({{ data.optimal_zone[0].toFixed(1) }} – {{ data.optimal_zone[1].toFixed(1) }})</span>
                  <span v-if="lastTrend" class="flex items-center gap-[16px] text-[10px]">
                    <span class="flex items-center gap-[6px] font-bold"><i class="w-[8px] h-[8px] rounded-full bg-cabin-ok" />Mood Score ({{ lastTrend.mood.toFixed(1) }} / 5)</span>
                    <span class="flex items-center gap-[6px]"><i class="w-[8px] h-[8px] rounded-full bg-cabin-rem" />Calmness ({{ lastTrend.calmness.toFixed(1) }} / 5)</span>
                  </span>
                </div>
                <ClientOnly>
                  <VChart
                    :option="chart"
                    theme="spacescan-hud"
                    autoresize
                    class="absolute inset-0"
                    :aria-label="`Mood and cognitive telemetry, ${periodTitle}`"
                  />
                </ClientOnly>
              </template>
              <UiStateNote v-else class="h-full" empty="No sessions logged in this window." />
            </UiInteractiveChartFrame>
          </div>
        </ShellHudWindow>

        <ShellHudWindow
          class="flex-1 min-h-0"
          title="Cognitive &amp; Sensorimotor Results"
          icon="bolt"
          :tag-text="cogWindowTag"
          :tag-tone="cogWindowCritical ? 'critical' : 'reference'"
          flush
        >
          <div class="flex-1 min-h-0 flex flex-col px-[20px] py-[clamp(8px,1.5dvh,14px)] gap-[10px]">
            <div class="flex flex-wrap items-center justify-between gap-[8px] shrink-0">
              <div class="flex gap-[8px]">
                <button
                  type="button"
                  class="focus-ring px-[10px] py-[4px] rounded-[4px] border mono text-[10.5px] font-bold"
                  :class="cogTab === 'reaction' ? 'menu-item-active text-cabin-text' : 'border-cabin-line text-cabin-ice'"
                  @click="cogTab = 'reaction'"
                >
                  2-Min Reaction
                </button>
                <button
                  type="button"
                  class="focus-ring px-[10px] py-[4px] rounded-[4px] border mono text-[10.5px] font-bold"
                  :class="cogTab === 'astrocow' ? 'menu-item-active text-cabin-text' : 'border-cabin-line text-cabin-ice'"
                  @click="cogTab = 'astrocow'"
                >
                  AST-01 AstroCow
                </button>
                <button
                  type="button"
                  class="focus-ring px-[10px] py-[4px] rounded-[4px] border mono text-[10.5px] font-bold"
                  :class="cogTab === 'neurofit' ? 'menu-item-active text-cabin-text' : 'border-cabin-line text-cabin-ice'"
                  @click="cogTab = 'neurofit'"
                >
                  NeuroFit Battery
                </button>
              </div>
              <span v-if="cogTab === 'astrocow' && data.astrocow" class="mono text-[10.5px] text-cabin-ice">
                Recorded {{ formatTime(data.astrocow.recorded_at_utc) }} UTC · Level {{ data.astrocow.difficulty_level }}
              </span>
              <span v-else-if="cogTab === 'neurofit' && data.neurofit" class="mono text-[10.5px] text-cabin-ice">
                ECG Index {{ data.neurofit.ecg_index }} / 800 · {{ formatTime(data.neurofit.recorded_at_utc) }} UTC
              </span>
            </div>

            <template v-if="cogTab === 'reaction'">
              <UiStateNote v-if="!data.reaction" empty="No reaction test yet. Run the 2-minute test in Capture." />
              <div v-else class="flex-1 min-h-0 flex gap-[14px]">
                <div class="tile relative w-[22%] shrink-0 flex items-center justify-center">
                  <span class="absolute top-[7px] right-[7px]"><UiParamHelp metric-key="reaction_time" /></span>
                  <UiArcGauge
                    :fraction="data.reaction.reaction_ms ? Math.min(1, data.reaction.reaction_ms / 500) : 0"
                    :tone="data.reaction.reaction_ms && data.reaction.reaction_ms < data.reaction.reaction_target_ms ? 'ok' : 'critical'"
                    label="Reaction Time"
                    :value="data.reaction.reaction_ms ? String(Math.round(data.reaction.reaction_ms)) : '—'"
                    :caption="`ms (<${data.reaction.reaction_target_ms} ms)`"
                    size="clamp(86px, 11.5dvh, 130px)"
                    :value-size="22"
                  />
                </div>
                <div
                  v-for="card in [
                    { label: 'Attention Lapses', help: 'attention_lapses', value: String(data.reaction.lapses), note: 'Errors in 2-min session', ok: data.reaction.lapses <= 1 },
                    { label: 'Motor Precision', help: 'motor_precision', value: `${data.reaction.accuracy_pct.toFixed(1)}%`, note: `Target accuracy ≥ ${data.reaction.accuracy_target_pct}%`, ok: data.reaction.accuracy_pct >= data.reaction.accuracy_target_pct },
                    { label: 'Vigilance Score', help: 'vigilance_score', value: `${Math.round(data.reaction.attention_score)} / 100`, note: data.reaction.attention_score >= 85 ? 'Alertness baseline met' : 'Below alertness baseline', ok: data.reaction.attention_score >= 85 },
                  ]"
                  :key="card.label"
                  class="tile relative flex-1 px-[14px] flex flex-col justify-center"
                >
                  <span class="absolute top-0 left-0 right-0 h-[3px]" :class="card.ok ? 'bg-cabin-ok' : 'bg-cabin-crit'" />
                  <p class="label-caps flex items-center gap-[6px]">{{ card.label }}<UiParamHelp :metric-key="card.help" /></p>
                  <p class="text-[22px] font-bold mt-[clamp(6px,1.5dvh,16px)] leading-none">{{ card.value }}</p>
                  <p class="text-[11px] text-cabin-ice mt-[clamp(6px,1.5dvh,16px)]">{{ card.note }}</p>
                </div>
              </div>
            </template>

            <template v-else-if="cogTab === 'astrocow'">
              <UiStateNote v-if="!data.astrocow" empty="No AST-01 AstroCow flight logged yet. Launch it in Capture · Psych, Motor &amp; Sleep." />
              <div v-else class="flex-1 min-h-0 flex gap-[14px]">
                <div class="tile relative w-[22%] shrink-0 flex items-center justify-center">
                  <UiArcGauge
                    :fraction="data.astrocow.precision_pct / 100"
                    :tone="data.astrocow.precision_pct >= 75 ? 'ok' : 'critical'"
                    label="Motor Precision"
                    :value="`${Math.round(data.astrocow.precision_pct)}%`"
                    :caption="`RT ${Math.round(data.astrocow.mean_reaction_ms)} ms`"
                    size="clamp(86px, 11.5dvh, 130px)"
                    :value-size="21"
                  />
                </div>
                <div class="tile relative flex-1 px-[14px] flex flex-col justify-center">
                  <span class="absolute top-0 left-0 right-0 h-[3px]" :class="data.astrocow.recovery_time_sec < 1.8 ? 'bg-cabin-ok' : 'bg-cabin-crit'" />
                  <p class="label-caps">Recovery T_rec</p>
                  <p class="text-[22px] font-bold mt-[10px] leading-none">{{ data.astrocow.recovery_time_sec }} s</p>
                  <p class="text-[11px] text-cabin-ice mt-[10px]">t_stable − t_change</p>
                </div>
                <div class="tile relative flex-1 px-[14px] flex flex-col justify-center">
                  <span class="absolute top-0 left-0 right-0 h-[3px]" :class="data.astrocow.rt_variability_ms < 120 ? 'bg-cabin-ok' : 'bg-cabin-crit'" />
                  <p class="label-caps">RT Variability</p>
                  <p class="text-[22px] font-bold mt-[10px] leading-none">±{{ Math.round(data.astrocow.rt_variability_ms) }} ms</p>
                  <p class="text-[11px] text-cabin-ice mt-[10px]">Score {{ data.astrocow.score }} · Collisions {{ data.astrocow.collisions }}</p>
                </div>
                <div class="tile relative flex-1 px-[14px] flex flex-col justify-center">
                  <span class="absolute top-0 left-0 right-0 h-[3px]" :class="data.astrocow.omitted_responses + data.astrocow.errors_after_change <= 2 ? 'bg-cabin-ok' : 'bg-cabin-crit'" />
                  <p class="label-caps">Change Err / Omissions</p>
                  <p class="text-[22px] font-bold mt-[10px] leading-none">{{ data.astrocow.errors_after_change }} / {{ data.astrocow.omitted_responses }}</p>
                  <p class="text-[11px] text-cabin-ice mt-[10px]">Hits {{ data.astrocow.reticle_hits }}/{{ data.astrocow.reticle_total }}</p>
                </div>
              </div>
            </template>

            <template v-else>
              <UiStateNote v-if="!data.neurofit" empty="No NeuroFit battery recorded yet. Run all 4 stages in Capture · Psych, Motor &amp; Sleep." />
              <div v-else class="flex-1 min-h-0 flex gap-[14px]">
                <div class="tile relative w-[22%] shrink-0 flex items-center justify-center">
                  <UiArcGauge
                    :fraction="data.neurofit.focus_index_score / 100"
                    :tone="data.neurofit.focus_index_score >= 65 ? 'ok' : 'critical'"
                    label="Focus Index"
                    :value="String(Math.round(data.neurofit.focus_index_score))"
                    :caption="`RT ${Math.round(data.neurofit.mean_reaction_ms)} ms`"
                    size="clamp(86px, 11.5dvh, 130px)"
                    :value-size="22"
                  />
                </div>
                <div
                  v-for="card in [
                    { label: 'Retention (CAB-ME)', value: `${data.neurofit.retention_pct}%`, note: 'Working Memory (Corsi)', ok: data.neurofit.retention_pct >= 65 },
                    { label: 'Attention (CAB-AT)', value: `${data.neurofit.sustained_attention_pct}%`, note: 'Inhibition & Vigilance', ok: data.neurofit.sustained_attention_pct >= 65 },
                    { label: 'Reasoning & Scan', value: `${Math.round((data.neurofit.spatial_reasoning_pct + data.neurofit.visual_perception_pct) / 2)}%`, note: `RS ${data.neurofit.spatial_reasoning_pct}% · PC ${data.neurofit.visual_perception_pct}%`, ok: (data.neurofit.spatial_reasoning_pct + data.neurofit.visual_perception_pct) / 2 >= 65 },
                  ]"
                  :key="card.label"
                  class="tile relative flex-1 px-[14px] flex flex-col justify-center"
                >
                  <span class="absolute top-0 left-0 right-0 h-[3px]" :class="card.ok ? 'bg-cabin-ok' : 'bg-cabin-crit'" />
                  <p class="label-caps">{{ card.label }}</p>
                  <p class="text-[22px] font-bold mt-[10px] leading-none">{{ card.value }}</p>
                  <p class="text-[11px] text-cabin-ice mt-[10px]">{{ card.note }}</p>
                </div>
              </div>
            </template>
          </div>
        </ShellHudWindow>
      </div>
    </div>
  </div>
</template>
