<script setup lang="ts">
// 05 · Astronaut Profile · Psychological (read-only): mood scales, 14-day trend, reaction test.
import VChart from 'vue-echarts'
import { moodTrendOption } from '~/utils/charts'
import { formatTime } from '~/utils/format'

interface Scale { value: number, range?: [number, number], target_below?: number, label: string }
interface PsychProfile {
  latest_state: { mood_state: string | null, recorded_at_utc: string, wellbeing_index: number } | null
  scales: { mood: Scale, stress_index: Scale, isolation: Scale, motivation: Scale } | null
  trend: { day_label: string, mood: number, calmness: number }[]
  optimal_zone: [number, number]
  stability_pct: number
  reaction: null | { reaction_ms: number | null, reaction_target_ms: number, accuracy_pct: number
    accuracy_target_pct: number, attention_score: number, lapses: number, trials_total: number
    valid_responses: number }
}

const { api } = useApi()
const { data, loading, error, refresh } = useResource(() => api<PsychProfile>('/psych/profile'), 60_000, ['psych', 'sleep', 'alerts'])

const STATES: Record<string, { title: string, detail: string }> = {
  CALM: { title: 'Calm & Focused', detail: 'Emotional stability and crew cohesion within optimal personal baseline.' },
  FOCUSED: { title: 'Focused', detail: 'Alert and engaged; keep regular breaks between demanding tasks.' },
  TIRED: { title: 'Tired', detail: 'Rest is the priority today; plan lighter tasks and an early rest period.' },
  STRESSED: { title: 'Under Strain', detail: 'Stress is above the usual level; the crew physician is available to talk.' },
}
const state = computed(() => STATES[data.value?.latest_state?.mood_state ?? ''] ?? null)
const scalesOk = computed(() => {
  const s = data.value?.scales
  return !!s && s.stress_index.label === 'Low' && s.isolation.label === 'Low' && s.mood.label !== 'Low'
})
const reactionOk = computed(() => {
  const r = data.value?.reaction
  return !!r && r.reaction_ms !== null && r.reaction_ms < r.reaction_target_ms && r.accuracy_pct >= r.accuracy_target_pct
})

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
    { label: 'Overall Mood', help: 'overall_mood', ref: range(s.mood), value: s.mood.value.toFixed(1), max: '/ 5', pill: s.mood.label,
      pct: (s.mood.value - 1) / 4, band: s.mood.range ? [(s.mood.range[0] - 1) / 4, (s.mood.range[1] - 1) / 4] : null,
      good: s.mood.label !== 'Low' },
    { label: 'Stress Index', help: 'stress_index', ref: `Target range: < ${s.stress_index.target_below}`, value: String(s.stress_index.value),
      max: '/ 100', pill: s.stress_index.label, pct: s.stress_index.value / 100,
      band: [0.1, (s.stress_index.target_below ?? 40) / 100], good: s.stress_index.label === 'Low' },
    { label: 'Isolation', help: 'isolation', ref: `Target range: < ${s.isolation.target_below}`, value: s.isolation.value.toFixed(1),
      max: '/ 5', pill: s.isolation.label, pct: (s.isolation.value - 1) / 4,
      band: [0.08, ((s.isolation.target_below ?? 2.5) - 1) / 4], good: s.isolation.label === 'Low' },
    { label: 'Motivation', help: 'motivation', ref: range(s.motivation), value: s.motivation.value.toFixed(1), max: '/ 5',
      pill: s.motivation.label === 'Positive' ? 'High' : s.motivation.label, pct: (s.motivation.value - 1) / 4,
      band: s.motivation.range ? [(s.motivation.range[0] - 1) / 4, (s.motivation.range[1] - 1) / 4] : null,
      good: s.motivation.label !== 'Low' },
  ]
})
const chart = computed(() => (data.value?.trend.length ? moodTrendOption(data.value.trend, data.value.optimal_zone) : null))
const lastTrend = computed(() => data.value?.trend.at(-1) ?? null)
</script>

<template>
  <div class="page">
    <ShellProfileTabs />
    <UiStateNote v-if="!data" :loading="loading" :error="error" @retry="refresh()" />
    <div v-else class="flex-1 min-h-0 flex gap-[18px]">
      <ShellHudWindow
class="w-[40.5%] shrink-0" title="Behavioral & Mood Results" icon="profile"
                      :tag-text="data.scales ? (scalesOk ? 'OPTIMAL' : 'SUPPORT') : 'NO DATA'"
                      :tag-tone="data.scales && !scalesOk ? 'critical' : 'reference'" flush>
        <UiStateNote v-if="!data.scales" empty="No daily check-in logged yet. Use Capture · Psych, Motor & Sleep." />
        <div v-else class="flex-1 min-h-0 flex flex-col px-[23px] pt-[clamp(12px,2.1dvh,20px)] pb-[14px]">
          <div class="tile-hi relative h-[clamp(66px,8.7dvh,96px)] shrink-0 pl-[20px] pr-[18px] flex flex-col justify-center">
            <span class="absolute left-0 top-[10px] bottom-[10px] w-[3px] rounded-full" :class="scalesOk ? 'bg-cabin-ok' : 'bg-cabin-crit'" />
            <div class="flex items-center justify-between">
              <span class="text-[10px] font-bold tracking-[0.04em] uppercase" :class="scalesOk ? 'text-cabin-ok' : 'text-cabin-text'">
                Latest daily state<template v-if="state"> · {{ state.title }}</template>
              </span>
              <UiStatusPill>{{ formatTime(data.latest_state?.recorded_at_utc) }} UTC LOG</UiStatusPill>
            </div>
            <p class="text-[12.5px] mt-[10px]">{{ state?.detail ?? 'Daily check-in recorded.' }}</p>
          </div>
          <div class="flex-1 min-h-0 flex flex-col justify-around gap-[6px]">
            <div v-for="row in rows" :key="row.label">
              <div class="flex items-start justify-between">
                <div>
                  <p class="text-[13px] font-semibold flex items-center gap-[6px]">{{ row.label }}<UiParamHelp :metric-key="row.help" /></p>
                  <p class="text-[10px] text-cabin-ice mt-[3px]">{{ row.ref }}</p>
                </div>
                <div class="flex items-center gap-[18px]">
                  <p class="text-[21px] font-bold leading-none">{{ row.value }}<span class="text-[10.5px] text-cabin-ice font-normal ml-[6px]">{{ row.max }}</span></p>
                  <UiStatusPill :tone="row.good ? 'reference' : 'critical'" class="min-w-[78px]">{{ row.pill }}</UiStatusPill>
                </div>
              </div>
              <div class="relative h-[10px] mt-[clamp(6px,1.3dvh,12px)]" aria-hidden="true">
                <div class="absolute left-0 right-0 top-[3.5px] h-[3px] rounded-full bg-cabin-track" />
                <div
v-if="row.band" class="absolute top-[1px] h-[8px] rounded-full bg-[var(--color-band-fill)] border border-cabin-navy-edge/70"
                     :style="{ left: `${row.band[0]! * 100}%`, width: `${Math.max(2, (row.band[1]! - row.band[0]!) * 100)}%` }" />
                <i
class="absolute top-[1px] w-[8px] h-[8px] -ml-[4px] rounded-full" :class="row.good ? 'bg-cabin-ok' : 'bg-cabin-crit'"
                   :style="{ left: `${Math.min(100, Math.max(0, row.pct * 100))}%` }" />
              </div>
            </div>
          </div>
        </div>
      </ShellHudWindow>

      <div class="flex-1 min-w-0 flex flex-col gap-[18px]">
        <ShellHudWindow
class="flex-[1.35] min-h-0" title="Mood & Calmness Trend · Last 14 Days" icon="reticle" help-key="mood_calmness"
                        :tag-text="data.trend.length ? `STABILITY ${data.stability_pct}%` : undefined" flush>
          <div class="flex-1 min-h-0 relative mx-[20px] my-[14px]">
            <template v-if="chart">
              <div class="absolute top-[22px] left-[56px] right-[30px] z-10 flex items-center justify-between pointer-events-none">
                <span class="text-[10px] font-bold">OPTIMAL WELLBEING ZONE ({{ data.optimal_zone[0].toFixed(1) }} – {{ data.optimal_zone[1].toFixed(1) }})</span>
                <span v-if="lastTrend" class="flex items-center gap-[18px] text-[10.5px]">
                  <span class="flex items-center gap-[6px] font-bold"><i class="w-[8px] h-[8px] rounded-full bg-cabin-ok" />Mood Score ({{ lastTrend.mood.toFixed(1) }} / 5)</span>
                  <span class="flex items-center gap-[6px]"><i class="w-[8px] h-[8px] rounded-full bg-cabin-rem" />Calmness ({{ lastTrend.calmness.toFixed(1) }} / 5)</span>
                </span>
              </div>
              <ClientOnly>
                <VChart
:option="chart" theme="spacescan-hud" autoresize class="absolute inset-0"
                        aria-label="Mood and calmness over the last 14 days" />
              </ClientOnly>
            </template>
            <UiStateNote v-else empty="The trend appears after the first check-ins." class="h-full" />
          </div>
        </ShellHudWindow>

        <ShellHudWindow
class="flex-1 min-h-0" title="Cognitive & Motor Reaction Results" icon="bolt"
                        :tag-text="data.reaction ? (reactionOk ? 'OPTIMAL' : 'BELOW TARGET') : 'NO TEST YET'"
                        :tag-tone="data.reaction && !reactionOk ? 'critical' : 'reference'" flush>
          <UiStateNote v-if="!data.reaction" empty="No reaction test yet. Run the 2-minute test in Capture." />
          <div v-else class="flex-1 min-h-0 flex gap-[16px] px-[24px] py-[clamp(12px,2.3dvh,22px)]">
            <div class="tile relative w-[22%] shrink-0 flex items-center justify-center">
              <span class="absolute top-[7px] right-[7px]"><UiParamHelp metric-key="reaction_time" /></span>
              <UiArcGauge
:fraction="data.reaction.reaction_ms ? Math.min(1, data.reaction.reaction_ms / 500) : 0"
                          :tone="data.reaction.reaction_ms && data.reaction.reaction_ms < data.reaction.reaction_target_ms ? 'ok' : 'critical'"
                          label="Reaction Time" :value="data.reaction.reaction_ms ? String(Math.round(data.reaction.reaction_ms)) : '—'"
                          :caption="`ms (<${data.reaction.reaction_target_ms} ms)`" size="clamp(96px, 13.6dvh, 150px)" :value-size="24" />
            </div>
            <div
v-for="card in [
              { label: 'Attention Lapses', help: 'attention_lapses', value: String(data.reaction.lapses), note: 'Errors in 2-min session', ok: data.reaction.lapses <= 1 },
              { label: 'Motor Precision', help: 'motor_precision', value: `${data.reaction.accuracy_pct.toFixed(1)}%`,
                note: `Target accuracy ≥ ${data.reaction.accuracy_target_pct}%`, ok: data.reaction.accuracy_pct >= data.reaction.accuracy_target_pct },
              { label: 'Vigilance Score', help: 'vigilance_score', value: `${Math.round(data.reaction.attention_score)} / 100`,
                note: data.reaction.attention_score >= 85 ? 'Alertness baseline met' : 'Below alertness baseline', ok: data.reaction.attention_score >= 85 },
            ]" :key="card.label" class="tile relative flex-1 px-[16px] flex flex-col justify-center">
              <span class="absolute top-0 left-0 right-0 h-[3px]" :class="card.ok ? 'bg-cabin-ok' : 'bg-cabin-crit'" />
              <p class="label-caps flex items-center gap-[6px]">{{ card.label }}<UiParamHelp :metric-key="card.help" /></p>
              <p class="text-[26px] font-bold mt-[clamp(10px,2.6dvh,24px)] leading-none">{{ card.value }}</p>
              <p class="text-[11px] text-cabin-ice mt-[clamp(10px,2.6dvh,24px)]">{{ card.note }}</p>
            </div>
          </div>
        </ShellHudWindow>
      </div>
    </div>
  </div>
</template>
