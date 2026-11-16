<script setup lang="ts">
// The crew physician's complete clinical record of one patient: pre-flight baselines against
// the latest value, every reading (filterable), labs, sleep, eye exams, heart and lung
// recordings, all advisories (open and acknowledged) and reviewed findings, with an
// on-demand pattern scan. Opens as a full-screen dialog over Profile · Personal.
import { apiErrorMessage } from '~/composables/useApi'
import { formatDuration, formatNumber, formatTime } from '~/utils/format'

const props = defineProps<{ crewId: string }>()
const emit = defineEmits<{ close: [] }>()

interface Reading { id: number, metric_key: string, value_num: number | null, mission_stage: string, source_type: string
  recorded_at_utc: string, display_name_en: string, unit: string, category: string }
interface ClinicalRecord {
  crew: { id: string, code: string, full_name: string, role: string, title_en: string | null, age: number | null
    sex: string | null, blood_type: string | null, height_cm: number | null }
  categories: string[]
  baselines: { metric_key: string, label: string, unit: string, category: string, baseline: number, current: number | null
    current_at_utc: string | null, z: number | null }[]
  timeline: Reading[]
  labs: Reading[]
  eyes: Reading[]
  sleep: { id: number, mission_stage: string, sleep_end_utc: string, total_sleep_min: number, sleep_score: number
    sleep_efficiency_pct: number, deep_min: number, rem_min: number }[]
  sounds: { id: number, organ_type: string, anatomical_site: string, duration_sec: number, cabin_noise_dba: number
    recorded_at_utc: string, audio_path: string, findings: { label_en?: string, summary_en?: string } }[]
  alerts: { id: number, severity: string, title_en: string, message_en: string, created_at_utc: string
    acknowledged_at_utc: string | null }[]
  findings: { id: number, created_at_utc: string | null, pattern_label_en: string | null, summary_en: string
    validation_status: string, reviews: { decision: string, notes_en: string | null, decided_at_utc: string }[] }[]
  counts: { open_alerts: number, findings: number, recordings: number }
}

const { api } = useApi()
const category = ref<string | null>(null)
const { data, loading, error, refresh } = useResource(() => api<ClinicalRecord>(`/crew/${props.crewId}/clinical-history`,
  { query: { category: category.value ?? undefined, limit: 300 } }), 0, ['alerts', 'vitals', 'sleep', 'vision', 'auscultation'])
watch(category, () => void refresh(true))

const TABS = ['Overview', 'Timeline', 'Labs', 'Sleep', 'Eyes', 'Sounds', 'Alerts', 'Findings'] as const
const tab = ref<typeof TABS[number]>('Overview')
const player = useRecordingPlayer()
onBeforeUnmount(() => player.stop())

const scanning = ref(false)
const scanNote = ref<{ tone: 'ok' | 'critical', text: string } | null>(null)
async function runAnalysis() {
  scanning.value = true
  scanNote.value = null
  try {
    const result = await api<{ diagnosis: { pattern_label_en?: string } | null, repeated: boolean }>(
      '/diagnosis/anomalies', { method: 'POST', body: { crew_id: props.crewId } })
    scanNote.value = { tone: 'ok', text: result.diagnosis
      ? `${result.repeated ? 'Already under review' : 'New finding for review'}: ${result.diagnosis.pattern_label_en ?? 'pattern found'}.`
      : 'No unusual pattern in the recent readings.' }
    await refresh(true)
  }
  catch (reason) {
    scanNote.value = { tone: 'critical', text: apiErrorMessage(reason) }
  }
  finally {
    scanning.value = false
  }
}

const value = (r: { value_num: number | null, unit: string }) => (r.value_num == null ? '—' : `${formatNumber(r.value_num, Math.abs(r.value_num) < 10 ? 2 : 1)} ${r.unit}`)
const zTone = (z: number | null) => (z == null ? '' : Math.abs(z) >= 3 ? 'text-cabin-crit' : Math.abs(z) >= 2 ? 'text-cabin-text font-bold' : 'text-cabin-ok')
const drifting = computed(() => (data.value?.baselines ?? []).filter(b => b.z != null)
  .sort((a, b) => Math.abs(b.z!) - Math.abs(a.z!)))
const day = (iso: string | null) => (iso ? `${iso.slice(0, 10)} ${formatTime(iso)}` : '—')
const dialog = ref<HTMLElement | null>(null)
onMounted(() => dialog.value?.focus())
</script>

<template>
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-cabin-navy/80 backdrop-blur-[2px] p-[24px]" @click.self="emit('close')" @keydown.esc="emit('close')">
    <section
      ref="dialog" role="dialog" aria-modal="true" aria-labelledby="clinical-record-title" tabindex="-1"
      class="w-[min(1400px,100%)] h-[min(860px,100%)] rounded-[6px] border-[1.4px] border-cabin-line bg-cabin-bg flex flex-col overflow-hidden focus:outline-none"
    >
      <header class="shrink-0 h-[58px] px-[22px] flex items-center gap-[16px] border-b border-cabin-line bg-[var(--color-card-head)]">
        <Icon name="spacescan:wiki" class="w-[18px] h-[18px]" />
        <h2 id="clinical-record-title" class="text-[15px] font-bold uppercase tracking-[0.03em]">
          Clinical Record<template v-if="data"> · {{ data.crew.code }} {{ data.crew.full_name }}</template>
        </h2>
        <span v-if="data" class="text-[11px] text-cabin-ice truncate">
          {{ data.crew.title_en ?? data.crew.role }} · {{ data.crew.age ?? '—' }} yrs · {{ data.crew.sex ?? '—' }} · {{ data.crew.blood_type ?? '—' }} · {{ data.crew.height_cm ?? '—' }} cm
        </span>
        <button type="button" class="hud-button ml-auto !w-[150px] !h-[36px] !text-[11.5px]" :disabled="scanning" @click="runAnalysis">
          {{ scanning ? 'Analysing...' : 'Run Analysis' }}
        </button>
        <button type="button" class="hud-button !w-[96px] !h-[36px] !text-[11.5px] !bg-none !bg-cabin-tile" @click="emit('close')">Close</button>
      </header>
      <p v-if="scanNote" class="shrink-0 px-[22px] py-[8px] text-[12px] border-b border-cabin-line" :class="scanNote.tone === 'critical' ? 'text-cabin-crit' : 'text-cabin-ok'" role="status">{{ scanNote.text }}</p>

      <nav class="shrink-0 flex gap-[6px] px-[22px] pt-[12px]" aria-label="Clinical record sections">
        <button
          v-for="name in TABS" :key="name" type="button"
          class="focus-ring h-[32px] px-[16px] rounded-[4px] text-[11px] font-bold border-[1.3px]"
          :class="tab === name ? 'menu-item-active' : 'bg-cabin-tile border-cabin-line text-cabin-ice'"
          :aria-pressed="tab === name" @click="tab = name"
        >
          {{ name }}<template v-if="data && name === 'Alerts'"> ({{ data.counts.open_alerts }})</template>
          <template v-if="data && name === 'Sounds'"> ({{ data.counts.recordings }})</template>
          <template v-if="data && name === 'Findings'"> ({{ data.counts.findings }})</template>
        </button>
      </nav>

      <UiStateNote v-if="!data" :loading="loading" :error="error" @retry="refresh()" />
      <div v-else class="flex-1 min-h-0 hud-scroll px-[22px] py-[14px]">
        <!-- Overview: pre-flight baseline against the latest value -->
        <table v-if="tab === 'Overview'" class="w-full text-[12px]">
          <caption class="sr-only">Pre-flight baselines against the latest value</caption>
          <thead class="label-caps text-left"><tr><th class="py-[6px]">Measure</th><th>Group</th><th>Pre-flight</th><th>Latest</th><th>Change (SD)</th><th>When (UTC)</th></tr></thead>
          <tbody>
            <tr v-for="b in drifting" :key="b.metric_key" class="border-t border-cabin-line/60">
              <td class="py-[7px] font-semibold">{{ b.label }}</td>
              <td class="text-cabin-ice">{{ b.category.toLowerCase() }}</td>
              <td class="mono">{{ formatNumber(b.baseline, Math.abs(b.baseline) < 10 ? 2 : 1) }} {{ b.unit }}</td>
              <td class="mono">{{ b.current == null ? '—' : `${formatNumber(b.current, Math.abs(b.current) < 10 ? 2 : 1)} ${b.unit}` }}</td>
              <td class="mono" :class="zTone(b.z)">{{ b.z! > 0 ? '+' : '' }}{{ b.z!.toFixed(1) }}</td>
              <td class="mono text-cabin-ice">{{ day(b.current_at_utc) }}</td>
            </tr>
          </tbody>
        </table>

        <!-- Every reading, filterable by group -->
        <template v-else-if="tab === 'Timeline' || tab === 'Labs' || tab === 'Eyes'">
          <div v-if="tab === 'Timeline'" class="flex flex-wrap gap-[6px] mb-[12px]" role="group" aria-label="Reading group">
            <button
              v-for="name in [null, ...data.categories]" :key="name ?? 'all'" type="button"
              class="focus-ring h-[28px] px-[14px] rounded-full text-[10.5px] font-bold border-[1.2px]"
              :class="category === name ? 'bg-cabin-card border-cabin-text/70' : 'bg-[var(--color-pill-fill)] border-[var(--color-pill-edge)]'"
              :aria-pressed="category === name" @click="category = name"
            >{{ name ? name.charAt(0) + name.slice(1).toLowerCase() : 'All' }}</button>
          </div>
          <table class="w-full text-[12px]">
            <caption class="sr-only">Readings</caption>
            <thead class="label-caps text-left"><tr><th class="py-[6px]">When (UTC)</th><th>Measure</th><th>Value</th><th>Stage</th><th>Source</th></tr></thead>
            <tbody>
              <tr v-for="r in (tab === 'Labs' ? data.labs : tab === 'Eyes' ? data.eyes : data.timeline)" :key="r.id" class="border-t border-cabin-line/60">
                <td class="py-[6px] mono text-cabin-ice">{{ day(r.recorded_at_utc) }}</td>
                <td class="font-semibold">{{ r.display_name_en }}</td>
                <td class="mono">{{ value(r) }}</td>
                <td class="text-cabin-ice">{{ r.mission_stage.toLowerCase() }}</td>
                <td class="text-cabin-ice">{{ r.source_type === 'AUTO' ? 'sensor' : 'logged' }}</td>
              </tr>
            </tbody>
          </table>
          <UiStateNote v-if="!(tab === 'Labs' ? data.labs : tab === 'Eyes' ? data.eyes : data.timeline).length" empty="No readings in this group yet." />
        </template>

        <table v-else-if="tab === 'Sleep'" class="w-full text-[12px]">
          <caption class="sr-only">Sleep sessions</caption>
          <thead class="label-caps text-left"><tr><th class="py-[6px]">Woke (UTC)</th><th>Total</th><th>Score</th><th>Efficiency</th><th>Deep</th><th>REM</th><th>Stage</th></tr></thead>
          <tbody>
            <tr v-for="s in data.sleep" :key="s.id" class="border-t border-cabin-line/60">
              <td class="py-[6px] mono text-cabin-ice">{{ day(s.sleep_end_utc) }}</td>
              <td class="font-semibold">{{ formatDuration(s.total_sleep_min) }}</td>
              <td class="mono">{{ s.sleep_score }} / 100</td>
              <td class="mono">{{ Math.round(s.sleep_efficiency_pct) }}%</td>
              <td class="mono">{{ formatDuration(s.deep_min) }}</td>
              <td class="mono">{{ formatDuration(s.rem_min) }}</td>
              <td class="text-cabin-ice">{{ s.mission_stage.toLowerCase() }}</td>
            </tr>
          </tbody>
        </table>

        <div v-else-if="tab === 'Sounds'" class="grid grid-cols-2 gap-[10px]">
          <UiStateNote v-if="!data.sounds.length" empty="No heart or lung recordings yet." />
          <div v-for="s in data.sounds" :key="s.id" class="tile px-[16px] py-[10px] flex items-center gap-[14px]">
            <button
              type="button" class="hud-button !w-[92px] !h-[34px] !text-[11px]"
              :aria-label="`${player.playing.value === `rec-${s.id}` ? 'Pause' : 'Play'} the ${s.organ_type.toLowerCase()} recording at the ${s.anatomical_site.replace('_', ' ')} site`"
              :disabled="player.loading.value === `rec-${s.id}`"
              @click="player.toggle(`rec-${s.id}`, s.audio_path)"
            >{{ player.playing.value === `rec-${s.id}` ? 'Pause' : 'Play' }}</button>
            <div class="min-w-0">
              <p class="text-[12.5px] font-bold">{{ s.organ_type === 'CARDIAC' ? 'Heart' : 'Lungs' }} · {{ s.anatomical_site.replace('_', ' ') }}</p>
              <p class="text-[11px] text-cabin-ice truncate">{{ day(s.recorded_at_utc) }} · {{ s.duration_sec }} s · cabin {{ Math.round(s.cabin_noise_dba) }} dBA<template v-if="s.findings.label_en"> · {{ s.findings.label_en }}</template></p>
            </div>
          </div>
        </div>

        <div v-else-if="tab === 'Alerts'" class="flex flex-col gap-[8px]">
          <div v-for="a in data.alerts" :key="a.id" class="tile px-[16px] py-[10px]" :class="a.acknowledged_at_utc ? 'opacity-70' : ''">
            <p class="text-[10px] font-bold tracking-[0.04em]" :class="a.severity === 'CRITICAL' ? 'text-cabin-crit' : 'text-cabin-ice'">
              {{ a.severity }} · {{ day(a.created_at_utc) }} · {{ a.acknowledged_at_utc ? `ACKNOWLEDGED ${day(a.acknowledged_at_utc)}` : 'OPEN' }}
            </p>
            <p class="text-[13px] font-bold mt-[4px]">{{ a.title_en }}</p>
            <p class="text-[11.5px] text-cabin-ice mt-[3px]">{{ a.message_en }}</p>
          </div>
        </div>

        <div v-else class="flex flex-col gap-[8px]">
          <UiStateNote v-if="!data.findings.length" empty="No findings yet. Use Run Analysis to scan the recent readings." />
          <div v-for="f in data.findings" :key="f.id" class="tile relative px-[16px] py-[10px]">
            <UiAiWatermark position="top-right" />
            <p class="text-[10px] font-bold tracking-[0.04em] text-cabin-ice">{{ f.validation_status.replaceAll('_', ' ') }} · {{ day(f.created_at_utc) }}</p>
            <p class="text-[13px] font-bold mt-[4px]">{{ f.pattern_label_en ?? 'Pattern finding' }}</p>
            <p class="text-[11.5px] text-cabin-ice mt-[3px]">{{ f.summary_en }}</p>
            <p v-for="(r, i) in f.reviews" :key="i" class="text-[11px] mt-[4px]">Physician: {{ r.decision.replaceAll('_', ' ').toLowerCase() }}<template v-if="r.notes_en"> · {{ r.notes_en }}</template></p>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>
