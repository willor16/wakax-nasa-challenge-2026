<script setup lang="ts">
// 07 · Sleep Architecture & Quality (read-only).
import VChart from 'vue-echarts'
import type { SleepBout } from '~/utils/charts'
import { sleepHistoryOption, sleepRibbonOption } from '~/utils/charts'
import { formatDuration } from '~/utils/format'

type Period = 'last_night' | '7d' | '14d' | '30d'
interface StageCard { stage: string, label: string, minutes: number, pct: number, target_low_pct?: number
  target_high_pct?: number, limit_min?: number, status: string, status_text: string }
interface Lapse { stage: string, label: string, bouts: number, avg_min: number, max_min: number, total_min: number
  intervals: { start: string, end: string, minutes: number }[] }
interface SleepMonitor {
  nights: number
  target_min: number
  summary: null | { score: number, score_label: string, total_min: number, target_met: boolean, in_bed_min: number
    efficiency_pct: number | null, day_label: string, window_start: string, window_end: string, stages_recorded: boolean }
  stages: StageCard[]
  night: null | { bouts: SleepBout[], bout_count: number, cycles: number, lapses: Lapse[] }
  trend: { day_label: string, deep_min: number, rem_min: number, light_min: number, awake_min: number }[]
}

const { crew } = useSession()
const { api } = useApi()
const period = ref<Period>('last_night')
const { data, loading, error, refresh } = useResource(
  () => api<SleepMonitor>(`/sleep/${crew.value!.id}`, { query: { period: period.value } }), 60_000, ['sleep', 'psych'])
watch(period, () => void refresh())

const summary = computed(() => data.value?.summary ?? null)
const lastNight = computed(() => period.value === 'last_night')
const STAGE_HELP: Record<string, string> = { DEEP: 'sleep_deep', REM: 'sleep_rem', LIGHT: 'sleep_light', AWAKE: 'sleep_awake' }
const tabs = computed(() => [
  { id: 'last_night', label: summary.value && lastNight.value ? `Last Night (${summary.value.day_label})` : 'Last Night' },
  { id: '7d', label: 'Last 7 Days' },
  { id: '14d', label: 'Last 14 Days' },
  { id: '30d', label: 'Last 30 Days' },
])

usePageHeader(() => ({
  title: 'Sleep Architecture & Quality',
  status: summary.value
    ? { text: `Score ${summary.value.score} · ${summary.value.score_label}`, tone: summary.value.score >= 65 ? 'ok' : 'critical' }
    : null,
}))

const stageColor: Record<string, string> = {
  DEEP: 'bg-cabin-ok', REM: 'bg-cabin-rem', LIGHT: 'bg-cabin-navy-edge', AWAKE: 'bg-cabin-crit',
}
function stageNote(card: StageCard): string {
  if (card.stage === 'AWAKE') return `${card.pct}% in bed · Limit < ${formatDuration(card.limit_min)}`
  const kind = card.stage === 'LIGHT' ? 'Normal' : 'Target'
  return `${card.pct}% of sleep · ${kind} ${card.target_low_pct}–${card.target_high_pct}%`
}
function stagePill(card: StageCard): string {
  if (card.stage !== 'AWAKE' || !data.value?.night) return card.status_text
  const bouts = data.value.night.lapses.find(l => l.stage === 'AWAKE')?.bouts ?? 0
  return card.status === 'NOMINAL' ? `${bouts} Brief` : card.status_text
}
const ribbon = computed(() => (lastNight.value && data.value?.night?.bouts.length
  ? sleepRibbonOption(data.value.night.bouts) : null))
const history = computed(() => (!lastNight.value && data.value?.trend.length
  ? sleepHistoryOption(data.value.trend, data.value.target_min) : null))
const legend = computed(() => {
  const totals = Object.fromEntries((data.value?.night?.lapses ?? []).map(l => [l.stage, l.total_min]))
  return [
    { stage: 'AWAKE', label: 'Awake' }, { stage: 'REM', label: 'REM' },
    { stage: 'LIGHT', label: 'Light' }, { stage: 'DEEP', label: 'Deep' },
  ].map(item => ({ ...item, text: lastNight.value ? `${item.label} (${formatDuration(totals[item.stage] ?? 0).replace(/^0h /, '')})` : item.label }))
})
function intervalText(lapse: Lapse): string {
  if (lapse.stage === 'LIGHT') {
    const first = lapse.intervals[0]
    const last = lapse.intervals.at(-1)
    return `${lapse.bouts} transition lapses across ${data.value?.night?.cycles ?? 0} cycles (${first?.start} – ${last?.end} UTC)`
  }
  return lapse.intervals.map(i => `${i.start}–${i.end} (${i.minutes}m)`).join(' · ')
}
</script>

<template>
  <div class="page">
    <ShellSubnavTabs v-model="period" :tabs="tabs" :tab-width="186" label="Sleep period">
      <div v-if="summary" class="h-[30px] w-[300px] rounded-full menu-item-active flex items-center justify-center text-[10px] font-bold tracking-[0.03em]">
        REST WINDOW · {{ summary.window_start }} – {{ summary.window_end }} UTC
      </div>
    </ShellSubnavTabs>
    <UiStateNote v-if="!data" :loading="loading" :error="error" @retry="refresh()" />
    <UiStateNote v-else-if="!summary" empty="No sleep logged yet. Confirm last night's sleep window in Capture · Psych, Motor & Sleep." />
    <div v-else class="flex-1 min-h-0 flex gap-[18px]">
      <ShellHudWindow
class="w-[31.1%] shrink-0" title="Sleep Quality & Stage Time" icon="moon"
                      :tag-text="lastNight ? `DAY ${summary.day_label.replace('D', '0').padStart(3, '0')}` : `${data.nights} NIGHTS`" flush>
        <div class="flex-1 min-h-0 flex flex-col px-[19px] pt-[clamp(10px,1.9dvh,18px)] pb-[14px]">
          <div class="flex gap-[12px] h-[clamp(132px,18.3dvh,200px)] shrink-0">
            <div class="tile relative w-[44%] shrink-0 flex items-center justify-center">
              <span class="absolute top-[7px] right-[7px]"><UiParamHelp metric-key="sleep_score" /></span>
              <UiArcGauge
:fraction="summary.score / 100" :tone="summary.score >= 65 ? 'ok' : 'critical'"
                          label="Sleep Score" :value="String(summary.score)"
                          :caption="`of 100 · ${summary.score_label.charAt(0)}${summary.score_label.slice(1).toLowerCase()}`"
                          size="clamp(110px, 14.9dvh, 160px)" :value-size="26" />
            </div>
            <div class="tile-hi relative flex-1 min-w-0 px-[16px] pt-[clamp(10px,2.1dvh,20px)]">
              <span class="absolute top-0 left-0 right-0 h-[3px]" :class="summary.target_met ? 'bg-cabin-ok' : 'bg-cabin-crit'" />
              <p class="label-caps flex items-center gap-[6px]">{{ lastNight ? 'Total sleep time' : 'Average sleep time' }}<UiParamHelp metric-key="sleep_duration" /></p>
              <p class="text-[30px] font-bold mt-[clamp(6px,1.3dvh,12px)] leading-none">{{ formatDuration(summary.total_min) }}</p>
              <p class="text-[11px] font-bold mt-[clamp(6px,1.3dvh,12px)]" :class="summary.target_met ? 'text-cabin-ok' : 'text-cabin-text'">
                Target ≥ {{ formatDuration(data.target_min) }} {{ summary.target_met ? 'Met' : 'Missed' }}
              </p>
              <p class="text-[10.5px] text-cabin-ice mt-[clamp(4px,1dvh,10px)]">In Bed: {{ formatDuration(summary.in_bed_min) }}</p>
              <p class="text-[10.5px] text-cabin-ice mt-[6px] flex items-center gap-[6px]">Sleep Efficiency: {{ summary.efficiency_pct ?? '—' }}%<UiParamHelp metric-key="sleep_efficiency" /></p>
            </div>
          </div>
          <p class="label-caps mt-[clamp(10px,2.3dvh,22px)]">Time in each sleep stage</p>
          <div v-if="data.stages.length" class="flex-1 min-h-0 flex flex-col justify-between gap-[8px] mt-[10px]">
            <div v-for="card in data.stages" :key="card.stage" class="tile relative flex-1 min-h-0 max-h-[112px] pl-[22px] pr-[16px] flex flex-col justify-center">
              <span class="absolute left-0 top-[10px] bottom-[10px] w-[3px] rounded-full" :class="stageColor[card.stage]" />
              <div class="flex items-center justify-between">
                <span class="text-[13px] font-bold flex items-center gap-[6px]">{{ card.label }}<UiParamHelp v-if="STAGE_HELP[card.stage]" :metric-key="STAGE_HELP[card.stage]!" /></span>
                <div class="flex items-center gap-[8px]">
                  <span class="mono text-[17px] font-bold">{{ formatDuration(card.minutes) }}</span>
                  <UiStatusPill size="sm" :tone="card.status === 'WARNING' ? 'critical' : card.status === 'WATCH' ? 'watch' : 'reference'">
                    {{ stagePill(card) }}
                  </UiStatusPill>
                </div>
              </div>
              <p class="text-[10.5px] text-cabin-ice mt-[clamp(2px,0.6dvh,6px)] truncate">{{ stageNote(card) }}</p>
              <div class="mt-[clamp(5px,1dvh,10px)] h-[5px] rounded-full bg-cabin-track overflow-hidden">
                <div
class="h-full rounded-full" :class="stageColor[card.stage]"
                     :style="{ width: `${Math.min(100, card.stage === 'AWAKE' ? (card.minutes / (card.limit_min ?? 35)) * 100 * 0.6 : card.pct * 1.4)}%` }" />
              </div>
            </div>
          </div>
          <UiStateNote v-else empty="Only the sleep window was logged for this period, so stage times are not available." />
        </div>
      </ShellHudWindow>

      <div class="flex-1 min-w-0 flex flex-col gap-[18px]">
        <ShellHudWindow
class="flex-[1.3] min-h-0" icon="reticle" flush
                        :title="lastNight ? `Sleep Stage Ribbon Chart · ${summary.window_start} – ${summary.window_end} UTC` : 'Nightly Sleep Stages'"
                        :tag-text="lastNight && data.night ? `${data.night.cycles} CYCLES` : `${data.nights} NIGHTS`">
          <div class="flex-1 min-h-0 m-[clamp(12px,1.9dvh,18px)] tile relative">
            <div class="absolute top-[12px] left-[22px] right-[18px] z-10 flex items-center gap-[30px] text-[10.5px] font-semibold pointer-events-none">
              <span v-for="item in legend" :key="item.stage" class="flex items-center gap-[8px]">
                <i class="w-[14px] h-[8px] rounded-[2px]" :class="stageColor[item.stage]" />{{ item.text }}
              </span>
              <span v-if="lastNight" class="ml-auto mono text-[9.5px] text-cabin-ice">
                REST WINDOW: {{ summary.window_start }} – {{ summary.window_end }} UTC
              </span>
            </div>
            <ClientOnly>
              <VChart
v-if="ribbon || history" :option="(ribbon ?? history)!" theme="spacescan-hud" autoresize
                      class="absolute inset-0 top-[30px]" aria-label="Sleep stages through the night" />
            </ClientOnly>
            <UiStateNote v-if="!ribbon && !history" class="h-full" empty="Stage detail is not available for this night." />
          </div>
        </ShellHudWindow>

        <ShellHudWindow
class="flex-1 min-h-0" title="Stage Lapses & Cycle Intervals" icon="moon"
                        :tag-text="data.night && lastNight ? `${data.night.bout_count} BOUTS LOGGED` : undefined" flush>
          <div v-if="data.night && lastNight" class="flex-1 min-h-0 flex flex-col px-[18px] pb-[14px]">
            <div class="grid grid-cols-[150px_1fr_86px_150px_70px] px-[16px] h-[30px] items-center label-caps !text-cabin-muted">
              <span>Sleep stage</span><span>Recorded UTC lapses (bout intervals)</span><span>Bouts</span>
              <span>Avg / max lapse</span><span class="text-right">Total</span>
            </div>
            <div class="flex-1 min-h-0 flex flex-col justify-between gap-[6px]">
              <div
v-for="lapse in data.night.lapses" :key="lapse.stage"
                   class="tile relative flex-1 min-h-0 max-h-[52px] grid grid-cols-[150px_1fr_86px_150px_70px] items-center pl-[18px] pr-[16px]">
                <span class="absolute left-0 top-[7px] bottom-[7px] w-[3px] rounded-full" :class="stageColor[lapse.stage]" />
                <span class="text-[12.5px] font-bold">{{ lapse.label }}</span>
                <span class="mono text-[10.5px] truncate pr-3">{{ intervalText(lapse) }}</span>
                <span class="text-[11.5px] font-bold">{{ lapse.bouts }} bouts</span>
                <span class="text-[11px] font-semibold">Avg {{ lapse.avg_min }}m · Max {{ lapse.max_min }}m</span>
                <span class="mono text-[14px] font-bold text-right">{{ formatDuration(lapse.total_min) }}</span>
              </div>
            </div>
          </div>
          <div v-else class="flex-1 flex flex-col px-[18px] pb-[14px] pt-[8px] gap-[10px]">
            <div
v-for="item in [
              { label: 'Nights logged', help: 'sleep_duration', value: `${data.nights} of ${period === '7d' ? 7 : period === '14d' ? 14 : 30}` },
              { label: 'Nights meeting the 7 h target', help: 'sleep_target_nights', value: String(data.trend.filter(n => n.deep_min + n.rem_min + n.light_min >= data!.target_min).length) },
              { label: 'Average deep sleep', help: 'sleep_deep', value: formatDuration(data.trend.reduce((s, n) => s + n.deep_min, 0) / Math.max(1, data.trend.length)) },
            ]" :key="item.label" class="tile h-[clamp(40px,5.5dvh,60px)] px-[18px] flex items-center justify-between">
              <span class="text-[12.5px] font-bold flex items-center gap-[6px]">{{ item.label }}<UiParamHelp :metric-key="item.help" /></span>
              <span class="mono text-[15px] font-bold">{{ item.value }}</span>
            </div>
          </div>
        </ShellHudWindow>
      </div>
    </div>
  </div>
</template>
