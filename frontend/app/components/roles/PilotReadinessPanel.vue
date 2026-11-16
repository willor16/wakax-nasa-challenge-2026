<script setup lang="ts">
// Flight & Docking Readiness of the pilot: retention, sustained attention, focus, reaction
// and recovery, with the visual and sleep gates and a stricter traffic light than the rest
// of the crew. Read-only; every value comes from the pilot's own logged tests.
import VChart from 'vue-echarts'
import type { ChartClick } from '~/composables/useChartPins'
import { statusFor } from '~/utils/chartDecor'
import { pilotHistoryOption } from '~/utils/charts'
import { formatTime } from '~/utils/format'

const props = withDefaults(defineProps<{ crewId: string, variant?: 'full' | 'summary' }>(), { variant: 'full' })

interface Readiness {
  score: number | null
  state: 'CLEARED' | 'CROSS_CHECK' | 'RESTRICTED'
  state_en: string
  reasons_en: string[]
  retention: { cognitive_retention_pct: number | null, measured: boolean, note_en: string | null }
  attention: { sustained_attention_pct: number | null, attention_lapses: number | null }
  focus: { focus_index_score: number | null }
  sensorimotor: { reaction_time_ms: number | null, recovery_days: number | null }
  gate: { visual_acuity_snellen: number | null, visual_acuity_text: string | null, sleep_24h_h: number | null, sleep_48h_h: number | null }
  tests_used: number
  last_test_utc: string | null
  history: { recorded_at_utc: string, attention: number, focus: number, reaction_ms: number }[]
}

const { api } = useApi()
const { data, loading, error, refresh } = useResource(
  () => api<Readiness>(`/crew/${props.crewId}/pilot-readiness`), 60_000, ['psych', 'sleep', 'vision'])
watch(() => props.crewId, () => void refresh())

const view = ref<'gauges' | 'history'>('gauges')
const tone = computed(() => (data.value?.state === 'CLEARED' ? 'ok' : data.value?.state === 'RESTRICTED' ? 'critical' : 'watch'))
const pct = (v: number | null) => (v == null ? 0 : Math.max(0, Math.min(1, v / 100)))
const shown = (v: number | null, unit = '') => (v == null ? '—' : `${Math.round(v)}${unit}`)

const dials = computed(() => {
  const d = data.value
  if (!d) return []
  const reaction = d.sensorimotor.reaction_time_ms
  return [
    { label: 'Retention', value: d.retention.measured ? shown(d.retention.cognitive_retention_pct, '%') : '—',
      caption: d.retention.note_en ?? 'working memory', fraction: pct(d.retention.cognitive_retention_pct),
      ok: (d.retention.cognitive_retention_pct ?? 100) >= 85 },
    { label: 'Attention', value: shown(d.attention.sustained_attention_pct), caption: `${d.attention.attention_lapses ?? 0} lapses`,
      fraction: pct(d.attention.sustained_attention_pct), ok: (d.attention.sustained_attention_pct ?? 0) >= 85 },
    { label: 'Focus', value: shown(d.focus.focus_index_score), caption: 'index / 100',
      fraction: pct(d.focus.focus_index_score), ok: (d.focus.focus_index_score ?? 0) >= 85 },
    { label: 'Reaction', value: shown(reaction), caption: 'ms (< 300 ms)',
      fraction: reaction ? Math.min(1, reaction / 500) : 0, ok: (reaction ?? 999) < 300 },
  ]
})
const gates = computed(() => {
  const d = data.value
  if (!d) return []
  const sleep = d.gate.sleep_24h_h
  return [
    { label: 'Recovery', value: d.sensorimotor.recovery_days == null ? 'Not yet' : `${d.sensorimotor.recovery_days} d`,
      note: 'back to usual reaction', ok: d.sensorimotor.recovery_days != null && d.sensorimotor.recovery_days <= 2 },
    { label: 'Sleep 24 h', value: sleep == null ? 'Not logged' : `${sleep} h`, note: `${d.gate.sleep_48h_h ?? '—'} h in 48 h · min 6 h`,
      ok: sleep != null && sleep >= 6 },
    { label: 'Visual Acuity', value: d.gate.visual_acuity_text ?? '—', note: 'flight standard 20/30',
      ok: d.gate.visual_acuity_snellen != null && d.gate.visual_acuity_snellen <= 30 },
  ]
})

const labelOf = (iso: string) => `${iso.slice(5, 10)} ${iso.slice(11, 16)}`
const pins = useChartPins((click: ChartClick) => {
  const point = data.value?.history[click.dataIndex]
  if (!point || !click.seriesName || click.seriesName === 'Reaction') return null
  const value = click.seriesName === 'Attention' ? point.attention : point.focus
  return {
    key: `${click.seriesName}-${point.recorded_at_utc}`, series: click.seriesName, value, unit: '/ 100', digits: 0,
    time_utc: point.recorded_at_utc, stage: null, delta: value - 85, reference_label: 'flight standard',
    status: statusFor(value, { band: [85, 100], watch: [70], critical: [60], alertWhen: 'below' }),
    coord: [labelOf(point.recorded_at_utc), value],
  }
})
const chart = computed(() => (data.value?.history.length
  ? pilotHistoryOption(data.value.history.map(h => ({ ...h, label: labelOf(h.recorded_at_utc) })),
      { Attention: pins.marks('Attention'), Focus: pins.marks('Focus') })
  : null))
</script>

<template>
  <UiStateNote v-if="!data" :loading="loading" :error="error" @retry="refresh()" />
  <!-- Summary card (Profile · Personal) -->
  <div v-else-if="variant === 'summary'" class="tile relative px-[16px] py-[12px] flex items-center gap-[14px]" data-pilot-readiness>
    <span class="absolute left-0 top-[8px] bottom-[8px] w-[3px] rounded-full" :class="tone === 'ok' ? 'bg-cabin-ok' : tone === 'critical' ? 'bg-cabin-crit' : 'bg-cabin-navy-edge'" />
    <div class="min-w-0 flex-1">
      <p class="label-caps">Flight &amp; Docking Readiness</p>
      <p class="text-[12.5px] font-bold mt-[5px] truncate" :class="tone === 'ok' ? 'text-cabin-ok' : ''">{{ data.state_en }}</p>
    </div>
    <p class="text-[26px] font-bold leading-none">{{ data.score ?? '—' }}<span class="text-[10.5px] text-cabin-ice font-normal ml-[4px]">/ 100</span></p>
  </div>
  <!-- Full panel (Profile · Psychological) -->
  <div v-else class="flex-1 min-h-0 flex flex-col px-[20px] pt-[12px] pb-[14px] gap-[10px]" data-pilot-readiness>
    <div class="flex items-center gap-[14px] shrink-0">
      <div
        class="flex-1 min-w-0 h-[40px] rounded-[5px] border-[1.4px] px-[14px] flex items-center gap-[10px]"
        :class="tone === 'ok' ? 'border-cabin-ok/80 bg-cabin-ok/10' : tone === 'critical' ? 'border-cabin-crit/85 bg-[var(--color-crit-soft)]' : 'border-cabin-navy-edge bg-cabin-navy/40'"
        role="status"
      >
        <i class="w-[9px] h-[9px] rounded-full shrink-0" :class="tone === 'ok' ? 'bg-cabin-ok' : tone === 'critical' ? 'bg-cabin-crit' : 'bg-cabin-navy-edge'" />
        <span class="text-[12px] font-bold tracking-[0.03em] truncate">{{ data.state_en }}</span>
        <span class="ml-auto mono text-[12px] font-bold">{{ data.score ?? '—' }} / 100</span>
      </div>
      <div class="flex gap-[6px]" role="group" aria-label="Readiness view">
        <button
          v-for="option in [{ id: 'gauges', label: 'Readiness' }, { id: 'history', label: 'History' }] as const" :key="option.id" type="button"
          class="focus-ring h-[30px] px-[14px] rounded-[4px] text-[10.5px] font-bold border-[1.3px]"
          :class="view === option.id ? 'menu-item-active' : 'bg-cabin-tile border-cabin-line text-cabin-ice'"
          :aria-pressed="view === option.id" @click="view = option.id"
        >{{ option.label }}</button>
      </div>
    </div>
    <p v-if="data.reasons_en.length" class="text-[11px] text-cabin-ice shrink-0 truncate">{{ data.reasons_en.join(' ') }}</p>

    <div v-if="view === 'gauges'" class="flex-1 min-h-0 flex gap-[12px]">
      <div v-for="dial in dials" :key="dial.label" class="tile relative flex-1 min-w-0 flex items-center justify-center">
        <span class="absolute top-0 left-0 right-0 h-[3px]" :class="dial.ok ? 'bg-cabin-ok' : 'bg-cabin-crit'" />
        <UiArcGauge
          :fraction="dial.fraction" :tone="dial.ok ? 'ok' : 'critical'" :label="dial.label" :value="dial.value"
          :caption="dial.caption" size="clamp(84px, 12.6dvh, 136px)" :value-size="20"
        />
      </div>
      <div class="w-[24%] shrink-0 flex flex-col gap-[8px]">
        <div v-for="gate in gates" :key="gate.label" class="tile relative flex-1 min-h-0 px-[12px] flex flex-col justify-center">
          <span class="absolute left-0 top-[6px] bottom-[6px] w-[3px] rounded-full" :class="gate.ok ? 'bg-cabin-ok' : 'bg-cabin-crit'" />
          <p class="label-caps">{{ gate.label }}</p>
          <p class="text-[15px] font-bold leading-tight mt-[3px]">{{ gate.value }}</p>
          <p class="text-[9.5px] text-cabin-ice truncate">{{ gate.note }}</p>
        </div>
      </div>
    </div>
    <div v-else class="flex-1 min-h-0 flex flex-col">
      <UiInteractiveChartFrame v-if="chart" :pins="pins.pins.value" interpretation="Dashed line: 85 / 100 flight standard. Click a point to pin it." @unpin="pins.remove" @point="pins.onClick">
        <VChart class="w-full h-full" :option="chart" autoresize />
      </UiInteractiveChartFrame>
      <UiStateNote v-else empty="No reaction test yet. Run the 2-minute test in Capture." />
    </div>
    <p class="text-[9.5px] text-cabin-muted shrink-0">
      Based on the last {{ data.tests_used }} reaction tests<template v-if="data.last_test_utc"> · latest {{ formatTime(data.last_test_utc) }} UTC</template>
    </p>
  </div>
</template>
