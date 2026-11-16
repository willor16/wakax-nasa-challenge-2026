<script setup lang="ts">
// 16 · Notifications (opened only from the header): advisories, scheduled checks,
// Mission Control messages and recommended care. The physician also reviews assisted findings.
import { apiErrorMessage } from '~/composables/useApi'
import { formatAgo, formatTime } from '~/utils/format'

interface CareStep { title_en: string, detail_en: string, done_at_utc: string | null }
interface Item {
  id: number
  kind: 'ADVISORY' | 'SCHEDULED' | 'MISSION_CONTROL'
  severity?: 'INFO' | 'WARNING' | 'CRITICAL'
  category?: string
  title_en: string
  message_en?: string
  detail_en?: string
  care_steps?: CareStep[]
  guide_article_id?: string | null
  is_quiet_deferred?: boolean
  created_at_utc?: string
  due_at_utc?: string
  sender_en?: string
}
interface Alerts {
  summary: { crew_name: string, text_en: string }
  counts: { all: number, advisories: number, checks: number, urgent: number }
  quiet_hours: { start_utc: string, end_utc: string, active: boolean }
  items: Item[]
}
interface Finding {
  id: number
  crew_name: string
  pattern_label_en: string
  llm_summary_en: string
  preventive_steps: { title_en: string, detail_en: string }[]
  top_metrics: { display_name_en?: string, label?: string, value: number, unit: string, baseline?: number }[]
  created_at_utc: string
  guidance_source: string
  validation_status: string
}

const { api } = useApi()
const { isPhysician } = useSession()
const { now, unread, mission, load: reloadMission } = useMission()
const view = ref<'all' | 'advisories' | 'checks' | 'reviews'>('all')
const selectedId = ref<string | null>(null)
const actionError = ref<string | null>(null)
const busy = ref(false)

const { data, loading, error, refresh } = useResource(() => api<Alerts>('/alerts', { query: { view: 'all' } }), 20_000, ['alerts'])
const reviews = useResource(() => (isPhysician.value
  ? api<{ items: Finding[] }>('/diagnosis', { query: { status: 'PENDING_REVIEW' } })
  : Promise.resolve({ items: [] as Finding[] })), 30_000, ['alerts'])
watch(data, (value) => {
  if (value) unread.value = value.counts.advisories
})

const tabs = computed(() => [
  { id: 'all', label: `All (${data.value?.counts.all ?? 0})` },
  { id: 'advisories', label: `Health Advisories (${data.value?.counts.advisories ?? 0})` },
  { id: 'checks', label: `Scheduled Checks (${data.value?.counts.checks ?? 0})` },
  ...(isPhysician.value ? [{ id: 'reviews', label: `Pending Reviews (${reviews.data.value?.items.length ?? 0})` }] : []),
])

const items = computed(() => {
  const list = data.value?.items ?? []
  if (view.value === 'advisories') return list.filter(i => i.kind === 'ADVISORY')
  if (view.value === 'checks') return list.filter(i => i.kind === 'SCHEDULED')
  return list
})
const keyOf = (item: Item) => `${item.kind}-${item.id}`
const selected = computed<Item | null>(() => items.value.find(i => keyOf(i) === selectedId.value)
  ?? items.value.find(i => i.kind === 'ADVISORY') ?? null)
const selectedFinding = ref<Finding | null>(null)
watch(() => reviews.data.value, (value) => {
  if (value && !value.items.some(f => f.id === selectedFinding.value?.id)) selectedFinding.value = value.items[0] ?? null
})

const advisoryCount = computed(() => data.value?.counts.urgent ?? 0)
usePageHeader(() => ({
  title: 'Notifications',
  subtitle: 'Opened from top header',
  status: data.value
    ? advisoryCount.value
      ? { text: `${advisoryCount.value} advisor${advisoryCount.value === 1 ? 'y' : 'ies'}`, tone: 'critical' }
      : { text: 'All clear', tone: 'ok' }
    : null,
}))

function kicker(item: Item): string {
  if (item.kind === 'SCHEDULED') {
    const due = new Date(item.due_at_utc!)
    const today = new Date(now.value)
    const tomorrow = new Date(today.getTime() + 86_400_000)
    const day = due.toISOString().slice(0, 10)
    const launch = mission.value?.launch_utc ? new Date(mission.value.launch_utc) : null
    const missionDay = launch ? Math.floor((Date.UTC(due.getUTCFullYear(), due.getUTCMonth(), due.getUTCDate())
      - Date.UTC(launch.getUTCFullYear(), launch.getUTCMonth(), launch.getUTCDate())) / 86_400_000) + 1 : null
    const label = day === today.toISOString().slice(0, 10) ? 'TODAY'
      : day === tomorrow.toISOString().slice(0, 10) ? 'TOMORROW'
        : missionDay ? `DAY ${String(missionDay).padStart(3, '0')}` : day
    return `Scheduled · ${label} ${formatTime(item.due_at_utc)} UTC`
  }
  if (item.kind === 'MISSION_CONTROL') return `Mission Control · ${formatTime(item.created_at_utc)} UTC`
  const level = { CRITICAL: 'Critical Advisory', WARNING: 'Warning', INFO: 'Health Notice' }[item.severity ?? 'INFO']
  return `${level} · ${formatAgo(item.created_at_utc!, now.value)}`
}
function accent(item: Item): string {
  if (item.kind === 'MISSION_CONTROL') return 'bg-cabin-ok'
  if (item.severity === 'CRITICAL') return 'bg-cabin-crit'
  return 'bg-cabin-navy-edge'
}

async function toggleStep(index: number) {
  if (!selected.value || selected.value.kind !== 'ADVISORY') return
  try {
    await api(`/alerts/${selected.value.id}/steps/${index}/complete`, { method: 'POST' })
    await refresh(true)
  }
  catch (reason) {
    actionError.value = apiErrorMessage(reason)
  }
}
async function acknowledge() {
  if (!selected.value || selected.value.kind !== 'ADVISORY') return
  busy.value = true
  actionError.value = null
  try {
    await api(`/alerts/${selected.value.id}/acknowledge`, { method: 'POST' })
    selectedId.value = null
    await refresh(true)
    await reloadMission() // the cabin leaves alert mode once no emergency is open
  }
  catch (reason) {
    actionError.value = apiErrorMessage(reason)
  }
  finally {
    busy.value = false
  }
}
async function openGuide() {
  const id = selected.value?.guide_article_id
  await navigateTo(id ? { path: '/guide', query: { article: id } } : '/guide')
}
async function review(decision: 'APPROVED' | 'REJECTED' | 'PROMOTED_TO_GUIDE') {
  if (!selectedFinding.value) return
  busy.value = true
  actionError.value = null
  try {
    await api(`/diagnosis/${selectedFinding.value.id}/review`, { method: 'POST', body: { decision, notes_en: reviewNote.value || undefined } })
    reviewNote.value = ''
    await reviews.refresh(true)
  }
  catch (reason) {
    actionError.value = apiErrorMessage(reason)
  }
  finally {
    busy.value = false
  }
}
const reviewNote = ref('')
function stepKicker(step: CareStep, index: number): string {
  if (step.done_at_utc) return `Step ${index + 1} · Completed ${formatTime(step.done_at_utc)} UTC`
  return `Step ${index + 1} · ${index === 0 ? 'Now' : index === 1 ? 'Next' : 'Before rest period'}`
}
</script>

<template>
  <div class="page">
    <ShellSubnavTabs v-model="view" :tabs="tabs" :tab-width="0" label="Notification filters">
      <div v-if="data" class="h-[30px] w-[284px] rounded-full menu-item-active flex items-center justify-center text-[10px] font-bold tracking-[0.03em]">
        QUIET HOURS {{ data.quiet_hours.start_utc }} – {{ data.quiet_hours.end_utc }} UTC<template v-if="data.quiet_hours.active"> · ACTIVE</template>
      </div>
    </ShellSubnavTabs>
    <UiStateNote v-if="!data" :loading="loading" :error="error" @retry="refresh()" />

    <div v-else-if="view === 'reviews'" class="flex-1 min-h-0 flex gap-[18px]">
      <ShellHudWindow
class="w-[45.2%] shrink-0" title="Assisted Findings Awaiting Review" icon="bell"
                      :tag-text="`${reviews.data.value?.items.length ?? 0} PENDING`" flush>
        <UiStateNote
v-if="!reviews.data.value?.items.length" :loading="reviews.loading.value"
                     empty="No findings are waiting for review. The pattern scan runs every 6 hours." />
        <div v-else class="flex-1 hud-scroll flex flex-col gap-[16px] p-[23px]">
          <button
v-for="finding in reviews.data.value.items" :key="finding.id" type="button"
                  class="focus-ring text-left relative shrink-0 rounded-[5px] pl-[24px] pr-[20px] py-[18px] border-[1.4px]"
                  :class="selectedFinding?.id === finding.id ? 'border-cabin-text/70 bg-[var(--color-card-head)]' : 'border-cabin-line bg-cabin-tile'"
                  @click="selectedFinding = finding">
            <span class="absolute left-0 top-[16px] bottom-[16px] w-[3px] rounded-full bg-cabin-navy-edge" />
            <UiAiWatermark position="top-right" />
            <p class="text-[10px] font-bold uppercase tracking-[0.04em]">{{ finding.crew_name }} · {{ formatAgo(finding.created_at_utc, now) }}</p>
            <p class="text-[15px] font-bold mt-[10px]">{{ finding.pattern_label_en }}</p>
            <p class="text-[12px] text-cabin-ice mt-[8px]">{{ finding.top_metrics.map(m => `${m.display_name_en ?? m.label} ${m.value} ${m.unit}`).join(' · ') }}</p>
          </button>
        </div>
      </ShellHudWindow>
      <ShellHudWindow class="flex-1" title="Physician Review" icon="shield" tag-text="SUGGESTION ONLY" flush>
        <UiStateNote v-if="!selectedFinding" empty="Select a finding to review it." />
        <div v-else class="flex-1 flex flex-col px-[23px] pt-[22px] pb-[20px]">
          <div class="tile-hi relative px-[20px] py-[16px]">
            <UiAiWatermark position="top-right" />
            <p class="text-[10px] font-bold uppercase text-cabin-ok">{{ selectedFinding.guidance_source === 'assistant' ? 'Onboard assistant summary' : 'Care-step summary' }}</p>
            <p class="text-[13px] mt-[10px] leading-[1.7]">{{ selectedFinding.llm_summary_en }}</p>
          </div>
          <div class="flex flex-col gap-[12px] mt-[16px]">
            <div v-for="(step, index) in selectedFinding.preventive_steps" :key="index" class="tile px-[18px] py-[12px]">
              <p class="text-[10px] font-bold uppercase">Step {{ index + 1 }}</p>
              <p class="text-[13.5px] font-bold mt-[6px]">{{ step.title_en }}</p>
              <p class="text-[11.5px] text-cabin-ice mt-[5px]">{{ step.detail_en }}</p>
            </div>
          </div>
          <label class="label-caps mt-[16px]" for="review-note">Physician note (optional)</label>
          <textarea
id="review-note" v-model="reviewNote" rows="2" maxlength="500"
                    class="mt-[8px] rounded-[4px] bg-cabin-tile border border-cabin-line p-[10px] text-[12.5px] outline-none focus:border-cabin-text resize-none" />
          <p v-if="actionError" class="text-[11px] mt-[8px]" role="alert">{{ actionError }}</p>
          <div class="mt-auto grid grid-cols-3 gap-[12px]">
            <button type="button" class="hud-button !h-[50px]" :disabled="busy" @click="review('APPROVED')">Approve &amp; Notify</button>
            <button type="button" class="hud-button !h-[50px]" :disabled="busy" @click="review('PROMOTED_TO_GUIDE')">Add to Guide</button>
            <button type="button" class="hud-button hud-button-critical !h-[50px]" :disabled="busy" @click="review('REJECTED')">Reject</button>
          </div>
        </div>
      </ShellHudWindow>
    </div>

    <div v-else class="flex-1 min-h-0 flex gap-[18px]">
      <ShellHudWindow class="w-[45.2%] shrink-0" title="Recent Notifications" icon="bell" :tag-text="`${items.length} ITEMS`" flush>
        <UiStateNote v-if="!items.length" empty="Nothing here right now. New advisories and checks appear as they arrive." />
        <div v-else class="flex-1 min-h-0 hud-scroll flex flex-col gap-[18px] p-[23px]">
          <div
v-for="item in items" :key="keyOf(item)"
               class="relative shrink-0 rounded-[5px] pl-[24px] pr-[20px] py-[20px] border-[1.4px]"
               :class="selected && keyOf(selected) === keyOf(item)
                 ? (item.severity === 'CRITICAL' ? 'border-cabin-crit/90 bg-[var(--color-card-head)]' : 'border-cabin-text/70 bg-[var(--color-card-head)]')
                 : 'border-cabin-line bg-cabin-tile'">
            <span class="absolute left-0 top-[18px] bottom-[18px] w-[3px] rounded-full" :class="accent(item)" />
            <!-- Advisories from a physician-reviewed pattern finding started from assisted analysis. -->
            <UiAiWatermark v-if="item.category === 'REVIEWED_PATTERN'" position="top-right" />
            <p class="text-[10px] font-bold uppercase tracking-[0.04em]" :class="item.kind === 'MISSION_CONTROL' ? 'text-cabin-ok' : ''">{{ kicker(item) }}</p>
            <p class="text-[15.5px] font-bold mt-[12px]">{{ item.title_en }}</p>
            <p class="text-[12px] text-cabin-ice mt-[10px]">{{ item.message_en ?? item.detail_en }}</p>
            <button
v-if="item.kind === 'ADVISORY'" type="button"
                    class="focus-ring mt-[14px] h-[24px] w-[150px] rounded-full text-[10px] font-bold border-[1.2px]"
                    :class="selected && keyOf(selected) === keyOf(item)
                      ? (item.severity === 'CRITICAL' ? 'bg-cabin-crit/40 border-cabin-crit/90' : 'bg-cabin-card border-cabin-text/70')
                      : 'bg-[var(--color-pill-fill)] border-[var(--color-pill-edge)]'"
                    @click="selectedId = keyOf(item)">{{ selected && keyOf(selected) === keyOf(item) ? 'Selected' : 'View Care Plan' }}</button>
            <NuxtLink
v-else-if="item.kind === 'SCHEDULED'" to="/capture/physical"
                      class="focus-ring mt-[14px] h-[24px] w-[150px] rounded-full text-[10px] font-bold border-[1.2px] bg-[var(--color-pill-fill)] border-[var(--color-pill-edge)] flex items-center justify-center">Open Capture</NuxtLink>
            <NuxtLink v-else to="/comms" class="focus-ring mt-[14px] h-[24px] w-[150px] rounded-full text-[10px] font-bold border-[1.2px] bg-[var(--color-pill-fill)] border-[var(--color-pill-edge)] flex items-center justify-center">View</NuxtLink>
          </div>
        </div>
      </ShellHudWindow>

      <ShellHudWindow class="flex-1" title="Recommended Care" icon="shield" tag-text="PREVENTIVE PLAN" flush>
        <div class="flex-1 min-h-0 flex flex-col px-[23px] pt-[clamp(12px,2.3dvh,22px)] pb-[clamp(12px,2.1dvh,20px)]">
          <div class="tile-hi h-[clamp(80px,10.4dvh,110px)] shrink-0 px-[20px] flex flex-col justify-center">
            <p class="text-[10px] font-bold uppercase tracking-[0.04em] text-cabin-ok">Summary · {{ data.summary.crew_name }}</p>
            <p class="text-[13px] mt-[10px]">{{ data.summary.text_en }}</p>
            <p class="text-[12.5px] text-cabin-ice mt-[6px]">
              {{ selected?.care_steps?.length ? 'Follow these three preventive steps before tonight\'s rest period:' : 'Select an advisory to see its care steps.' }}
            </p>
          </div>
          <div class="flex-1 min-h-0 flex flex-col justify-around gap-[8px] py-[8px]">
            <template v-if="selected?.care_steps?.length">
              <button
v-for="(step, index) in selected.care_steps" :key="index" type="button"
                      class="focus-ring tile relative text-left flex-1 min-h-0 max-h-[130px] overflow-hidden pl-[24px] pr-[20px] flex items-center gap-[20px]"
                      :aria-pressed="Boolean(step.done_at_utc)" @click="toggleStep(index)">
                <span class="absolute left-0 top-[12px] bottom-[12px] w-[3px] rounded-full" :class="step.done_at_utc ? 'bg-cabin-ok' : 'bg-cabin-navy-edge'" />
                <span
class="w-[36px] h-[36px] shrink-0 rounded-[4px] flex items-center justify-center text-[14px] font-bold border-[1.3px]"
                      :class="step.done_at_utc ? 'border-cabin-ok bg-cabin-ok/15' : 'border-cabin-navy-edge bg-cabin-navy/60'">
                  <Icon v-if="step.done_at_utc" name="spacescan:check" class="w-[16px] h-[16px]" />
                  <template v-else>{{ index + 1 }}</template>
                </span>
                <span>
                  <span class="block text-[10.5px] font-bold uppercase tracking-[0.03em]" :class="step.done_at_utc ? 'text-cabin-ok' : ''">{{ stepKicker(step, index) }}</span>
                  <span class="block text-[16px] font-bold mt-[clamp(4px,0.85dvh,8px)]">{{ step.title_en }}</span>
                  <span class="block text-[12px] text-cabin-ice mt-[clamp(4px,0.85dvh,8px)]">{{ step.detail_en }}</span>
                </span>
              </button>
            </template>
            <UiStateNote v-else empty="No open advisory. Scheduled checks are listed on the left." />
          </div>
          <p v-if="actionError" class="text-[11px] mb-[8px]" role="alert">{{ actionError }}</p>
          <div class="tile h-[clamp(72px,10.2dvh,104px)] shrink-0 px-[24px] flex items-center gap-[20px]">
            <button type="button" class="hud-button relative !h-[52px]" :disabled="busy || selected?.kind !== 'ADVISORY'" @click="acknowledge">
              <Icon name="spacescan:shield" class="w-[17px] h-[17px] absolute left-[20px]" />Acknowledge Advisory
            </button>
            <button type="button" class="hud-button relative !h-[52px] !bg-none !bg-cabin-tile" :disabled="selected?.kind !== 'ADVISORY'" @click="openGuide">
              <Icon name="spacescan:wiki" class="w-[17px] h-[17px] absolute left-[20px]" />Open Medical Guide
            </button>
          </div>
        </div>
      </ShellHudWindow>
    </div>
  </div>
</template>
