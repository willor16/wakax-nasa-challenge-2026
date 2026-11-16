<script setup lang="ts">
// 14 · Medical Guide & Kit Locator: protocol search by symptom or topic, kit drawers.
import { apiErrorMessage } from '~/composables/useApi'

interface Step { title_en: string, detail_en: string }
interface Article { id: string, category_en: string, title_en: string, drawer_code: string, steps: Step[]
  escalation_en: string, source_en: string | null, assisted?: boolean, mission_protocol?: boolean
  origin?: 'shipped' | 'mission_case' | 'physician' }
interface Drawer { code: string, name_en: string, items: { slot_code: string, name_en: string, status_en: string }[] }
interface EmergencyItem { id: string, title_en: string, drawer_code: string, escalation_en: string }

const route = useRoute()
const { api } = useApi()
const { isPhysician } = useSession()

const query = ref(typeof route.query.q === 'string' ? route.query.q : '')
const category = ref<string | null>(null)
const categories = ref<string[]>([])
const results = ref<Article[]>([])
const article = ref<Article | null>(null)
const drawers = ref<Drawer[]>([])
const emergency = ref<EmergencyItem[] | null>(null)
const physician = ref<string>('the crew physician')
const error = ref<string | null>(null)
const busy = ref(false)
const lit = ref(false)
let lightTimer: ReturnType<typeof setTimeout> | null = null

usePageHeader(() => ({ title: 'Medical Guide & Kit Locator', status: { text: 'Ready', tone: 'ok' } }))

async function search(open = true) {
  busy.value = true
  error.value = null
  emergency.value = null
  try {
    const found = await api<{ results: Article[], categories: string[] }>('/wiki/search', {
      query: { q: query.value, category: category.value ?? undefined },
    })
    categories.value = found.categories
    results.value = found.results
    // Keep the open protocol while it is still in the list; otherwise open the best match.
    const keep = article.value && found.results.some(a => a.id === article.value!.id)
    if (open && !keep) article.value = found.results[0] ?? null
  }
  catch (reason) {
    error.value = apiErrorMessage(reason)
  }
  finally {
    busy.value = false
  }
}
async function openArticle(id: string) {
  try {
    article.value = await api<Article>(`/wiki/articles/${id}`)
    emergency.value = null
  }
  catch (reason) {
    error.value = apiErrorMessage(reason, 'That protocol could not be opened.')
  }
}
async function showEmergency() {
  try {
    emergency.value = (await api<{ items: EmergencyItem[] }>('/wiki/emergency-index')).items
  }
  catch (reason) {
    error.value = apiErrorMessage(reason)
  }
}
function pickCategory(name: string) {
  category.value = category.value === name ? null : name
  void search()
}
onMounted(async () => {
  try {
    const [kit, profiles] = await Promise.all([
      api<{ drawers: Drawer[] }>('/kit/drawers'),
      api<{ full_name: string, title_en: string, id: string }[]>('/crew/profiles'),
    ])
    drawers.value = kit.drawers
    const doctor = profiles.find(p => p.title_en === 'Medical Officer')
    if (doctor) physician.value = `Medical Officer (Dr. ${doctor.full_name.split(' ').at(-1)})`
  }
  catch (reason) {
    error.value = apiErrorMessage(reason)
  }
  // Coming from a notification opens its exact protocol; otherwise the first one is open.
  if (typeof route.query.article === 'string') {
    await search(false)
    await openArticle(route.query.article)
  }
  else {
    await search()
  }
  ready = true
})
// Instant search while typing (200 ms after the last key), as well as the Search button.
let ready = false
let typing: ReturnType<typeof setTimeout> | null = null
watch(query, () => {
  if (!ready) return
  if (typing) clearTimeout(typing)
  typing = setTimeout(() => void search(), 200)
})
onBeforeUnmount(() => {
  if (lightTimer) clearTimeout(lightTimer)
  if (typing) clearTimeout(typing)
})

// ---- New mission protocol (crew physician only) --------------------------------------
interface Draft { title_en: string, category_en: string, drawer_code: string, steps: Step[], escalation_en: string }
const blankStep = (): Step => ({ title_en: '', detail_en: '' })
const composing = ref(false)
const saving = ref(false)
const draftError = ref<string | null>(null)
const draft = ref<Draft>({ title_en: '', category_en: '', drawer_code: '', steps: [], escalation_en: '' })
const firstField = ref<HTMLInputElement | null>(null)
function startProtocol() {
  draft.value = {
    title_en: '',
    category_en: category.value ?? categories.value[0] ?? '',
    drawer_code: article.value?.drawer_code ?? drawers.value[0]?.code ?? '',
    steps: [blankStep(), blankStep(), blankStep()],
    escalation_en: '',
  }
  draftError.value = null
  composing.value = true
  void nextTick(() => firstField.value?.focus())
}
const draftReady = computed(() => {
  const d = draft.value
  return d.title_en.trim().length >= 5 && d.category_en.trim().length >= 3 && Boolean(d.drawer_code)
    && d.escalation_en.trim().length >= 10
    && d.steps.every(s => s.title_en.trim().length >= 3 && s.detail_en.trim().length >= 5)
})
async function saveProtocol() {
  if (!draftReady.value) return
  saving.value = true
  draftError.value = null
  try {
    const created = await api<Article>('/wiki/articles', { method: 'POST', body: draft.value })
    composing.value = false
    query.value = ''
    category.value = null
    await search(false)
    article.value = created
    emergency.value = null
  }
  catch (reason) {
    draftError.value = apiErrorMessage(reason, 'The protocol could not be saved.')
  }
  finally {
    saving.value = false
  }
}
const originLabel = (a: Article) => (a.origin === 'physician'
  ? (a.source_en ?? 'Mission protocol')
  : a.origin === 'mission_case' ? 'Mission-Validated · ' + (a.source_en ?? '') : null)

const activeDrawer = computed(() => drawers.value.find(d => d.code === article.value?.drawer_code) ?? null)
function illuminate() {
  lit.value = true
  if (lightTimer) clearTimeout(lightTimer)
  lightTimer = setTimeout(() => { lit.value = false }, 30_000)
}
const drawerShort = (code: string) => code.replace('DRAWER ', '')
const subscript = (text: string) => text.replace(/CO2/g, 'CO₂')
</script>

<template>
  <div class="page">
    <ShellHudWindow class="shrink-0" flush>
      <form class="flex-1 flex flex-col px-[19px] pt-[18px] pb-[clamp(12px,2dvh,22px)]" role="search" @submit.prevent="search()">
        <div class="flex gap-[14px]">
          <label class="hud-field flex-1 !h-[48px] !bg-cabin-tile">
            <Icon name="spacescan:search" class="w-[17px] h-[17px] text-cabin-ice" />
            <span class="sr-only">Search the medical guide by symptom</span>
            <input v-model="query" class="!font-sans !text-[14px]" placeholder="Search by symptom, e.g. headache, cut, eye pressure">
          </label>
          <button type="submit" class="hud-button relative !w-[174px] !h-[48px]" :disabled="busy">
            <Icon name="spacescan:search" class="w-[16px] h-[16px] absolute left-[18px]" />Search Guide
          </button>
          <button type="button" class="hud-button hud-button-critical relative !w-[190px] !h-[48px] !pl-[26px]" @click="showEmergency">
            <Icon name="spacescan:alert" class="w-[16px] h-[16px] absolute left-[18px]" />Emergency Index
          </button>
          <button v-if="isPhysician" type="button" class="hud-button relative !w-[236px] !h-[48px] !pl-[26px]" @click="startProtocol">
            <Icon name="spacescan:wiki" class="w-[16px] h-[16px] absolute left-[18px]" />New Mission Protocol
          </button>
        </div>
        <div class="flex flex-wrap gap-[10px] mt-[14px]" role="group" aria-label="Topics">
          <button
v-for="name in categories" :key="name" type="button"
                  class="focus-ring h-[30px] px-[22px] rounded-full text-[10.5px] font-bold border-[1.2px]"
                  :class="category === name ? 'bg-cabin-card border-cabin-text/70' : 'bg-[var(--color-pill-fill)] border-[var(--color-pill-edge)]'"
                  :aria-pressed="category === name" @click="pickCategory(name)">{{ subscript(name) }}</button>
        </div>
      </form>
    </ShellHudWindow>

    <UiStateNote v-if="error" :error="error" @retry="search()" />
    <div v-else class="flex-1 min-h-0 flex gap-[18px]">
      <ShellHudWindow class="w-[24%] shrink-0" title="Protocols" icon="wiki" :tag-text="`${results.length}`" flush>
        <UiStateNote v-if="!results.length" :loading="busy" empty="No protocol matches that search. Try another word or a topic." />
        <ul v-else class="flex-1 min-h-0 hud-scroll px-[14px] py-[14px] flex flex-col gap-[8px]" aria-label="Protocols">
          <li v-for="item in results" :key="item.id">
            <button
type="button" class="tile focus-ring w-full text-left px-[14px] py-[11px] border-[1.3px]"
                    :class="item.id === article?.id && !emergency ? '!border-cabin-ok bg-[var(--color-card-head)]' : ''"
                    :aria-current="item.id === article?.id ? 'true' : undefined" @click="openArticle(item.id)">
              <p class="text-[12.5px] font-bold leading-[1.35]">{{ subscript(item.title_en) }}</p>
              <p class="mono text-[9.5px] text-cabin-ice mt-[6px] flex flex-wrap gap-x-[8px] gap-y-[3px] tracking-[0.04em]">
                <span>{{ subscript(item.category_en).toUpperCase() }}</span>
                <span :class="item.id === article?.id ? 'text-cabin-ok' : ''">{{ item.drawer_code }}</span>
                <span v-if="item.mission_protocol" class="text-cabin-ok">MISSION PROTOCOL</span>
              </p>
            </button>
          </li>
        </ul>
      </ShellHudWindow>
      <ShellHudWindow
v-if="emergency" class="flex-1 min-w-0" title="Emergency Index · When to Call the Physician" icon="alert"
                      tag-text="ALL PROTOCOLS" tag-tone="critical" flush>
        <div class="flex-1 hud-scroll px-[19px] py-[16px] flex flex-col gap-[10px]">
          <button v-for="item in emergency" :key="item.id" type="button" class="tile focus-ring text-left px-[18px] py-[12px]" @click="openArticle(item.id)">
            <p class="text-[12.5px] font-bold">{{ subscript(item.title_en) }} <span class="mono text-[10px] text-cabin-ice ml-2">{{ item.drawer_code }}</span></p>
            <p class="text-[11.5px] text-cabin-ice mt-[6px]">{{ subscript(item.escalation_en) }}</p>
          </button>
        </div>
      </ShellHudWindow>
      <ShellHudWindow
v-else class="flex-1 min-w-0" flush icon="wiki"
                      :title="article ? `Care Protocol · ${subscript(article.title_en)}` : 'Care Protocol'"
                      :tag-text="article ? (article.mission_protocol ? 'MISSION PROTOCOL' : 'QUICK GUIDE') : undefined"
                      >
        <UiStateNote v-if="!article" :loading="busy" :empty="query || category ? 'No protocol matches that search. Try another word or a topic.' : 'Choose a protocol from the list.'" />
        <div v-else class="relative flex-1 min-h-0 flex flex-col px-[19px] pt-[14px] pb-[20px]">
          <UiAiWatermark v-if="article.assisted" position="top-right" />
          <p v-if="originLabel(article)" class="mono text-[10px] tracking-[0.05em] text-cabin-ok mb-[12px] pr-[70px]">
            {{ originLabel(article) }}
          </p>
          <div class="flex-1 min-h-0 hud-scroll flex flex-col gap-[14px] pr-[2px]">
            <div v-for="(step, index) in article.steps" :key="index" class="tile min-h-[98px] px-[20px] py-[18px] flex gap-[22px]">
              <span
class="w-[37px] h-[37px] shrink-0 rounded-[4px] mono text-[15px] font-bold flex items-center justify-center border-[1.3px]"
                    :class="index < 2 ? 'border-cabin-ok/80 bg-cabin-ok/10 text-cabin-text' : 'border-cabin-navy-edge bg-cabin-navy/50'">
                {{ String(index + 1).padStart(2, '0') }}
              </span>
              <div>
                <p class="text-[13px] font-bold uppercase tracking-[0.02em]">{{ subscript(step.title_en) }}</p>
                <p class="text-[12px] text-cabin-ice mt-[10px] leading-[1.75]">{{ subscript(step.detail_en) }}</p>
              </div>
            </div>
          </div>
          <div class="mt-[16px] h-[90px] shrink-0 rounded-[5px] border-[1.4px] border-cabin-crit/85 bg-[var(--color-crit-soft)] px-[22px] flex flex-col justify-center" role="note">
            <p class="text-[11.5px] font-bold uppercase flex items-center gap-[10px]">
              <Icon name="spacescan:alert" class="w-[15px] h-[15px] text-cabin-crit" />Escalate immediately to {{ physician }}
            </p>
            <p class="text-[12px] mt-[10px] pl-[25px]">{{ subscript(article.escalation_en) }}</p>
          </div>
        </div>
      </ShellHudWindow>

      <ShellHudWindow class="w-[30%] shrink-0" title="Medical Kit Locator" icon="kit" :tag-text="activeDrawer?.code" flush>
        <div class="flex-1 flex flex-col px-[19px] pt-[18px] pb-[20px]">
          <div class="grid grid-cols-2 gap-[11px]">
            <div
v-for="drawer in drawers" :key="drawer.code" class="h-[87px] rounded-[5px] px-[16px] flex flex-col justify-center border-[1.3px]"
                 :class="drawer.code === activeDrawer?.code ? 'border-cabin-ok bg-[var(--color-card-head)]' : 'border-cabin-line bg-cabin-tile'">
              <p class="mono text-[10px] tracking-[0.06em]" :class="drawer.code === activeDrawer?.code ? 'text-cabin-ok' : 'text-cabin-ice'">
                {{ drawer.code }}<template v-if="drawer.code === activeDrawer?.code"> · ACTIVE</template>
              </p>
              <p class="text-[13px] font-bold mt-[10px]">{{ drawer.name_en }}</p>
            </div>
          </div>
          <template v-if="activeDrawer">
            <p class="label-caps mt-[20px]">Contents in {{ activeDrawer.code }}</p>
            <div class="flex-1 min-h-0 hud-scroll flex flex-col gap-[10px] mt-[10px]">
              <div v-for="item in activeDrawer.items" :key="item.slot_code" class="tile h-[62px] shrink-0 px-[16px] flex flex-col justify-center">
                <p class="text-[13px] font-bold">{{ item.name_en }}</p>
                <p class="mono text-[10.5px] mt-[6px]" :class="/charged|100%/i.test(item.status_en) ? 'text-cabin-ok' : 'text-cabin-ice'">
                  {{ item.slot_code }} · {{ item.status_en }}
                </p>
              </div>
            </div>
            <button type="button" class="hud-button relative mt-[14px] !h-[50px]" :class="lit ? '!border-cabin-ok' : ''" :aria-pressed="lit" @click="illuminate">
              <Icon name="spacescan:bolt" class="w-[16px] h-[16px] absolute left-[20px]" />
              {{ lit ? `Drawer ${drawerShort(activeDrawer.code)} light on · 30 s` : `Illuminate Drawer ${drawerShort(activeDrawer.code)} Light` }}
            </button>
          </template>
          <UiStateNote v-else empty="Open a protocol to see which drawer holds its supplies." />
        </div>
      </ShellHudWindow>
    </div>

    <div
v-if="composing" class="fixed inset-0 z-50 flex items-center justify-center bg-cabin-navy/80 backdrop-blur-[2px] px-[16px]"
         @click.self="composing = false" @keydown.esc="composing = false">
      <form
role="dialog" aria-modal="true" aria-labelledby="new-protocol-title"
            class="w-[min(760px,100%)] max-h-[90dvh] hud-scroll rounded-[6px] border-[1.4px] border-cabin-line bg-cabin-card px-[24px] py-[22px] flex flex-col gap-[14px]"
            @submit.prevent="saveProtocol">
        <div class="flex items-center justify-between">
          <h2 id="new-protocol-title" class="text-[15px] font-bold uppercase tracking-[0.03em]">New Mission Protocol</h2>
          <button type="button" class="focus-ring text-[12px] text-cabin-ice" aria-label="Close" @click="composing = false">Close</button>
        </div>
        <p class="text-[11.5px] text-cabin-ice">Validated by the crew physician during the mission. Plain English only; every crew member can read it.</p>
        <label class="flex flex-col gap-[6px]">
          <span class="label-caps">Title</span>
          <span class="hud-field !h-[42px]"><input ref="firstField" v-model="draft.title_en" class="!font-sans !text-[13px]" maxlength="120" placeholder="e.g. Dry skin and cracked hands"></span>
        </label>
        <div class="flex gap-[12px]">
          <label class="flex-1 flex flex-col gap-[6px]">
            <span class="label-caps">Topic</span>
            <span class="hud-field !h-[42px]"><input v-model="draft.category_en" class="!font-sans !text-[13px]" maxlength="40" list="guide-topics" placeholder="Choose or type a topic"></span>
            <datalist id="guide-topics"><option v-for="name in categories" :key="name" :value="name" /></datalist>
          </label>
          <label class="w-[44%] flex flex-col gap-[6px]">
            <span class="label-caps">Kit drawer</span>
            <select v-model="draft.drawer_code" class="hud-field !h-[42px] !font-sans text-[13px]">
              <option v-for="drawer in drawers" :key="drawer.code" :value="drawer.code">{{ drawer.code }} · {{ drawer.name_en }}</option>
            </select>
          </label>
        </div>
        <fieldset class="flex flex-col gap-[10px]">
          <legend class="label-caps mb-[6px]">Steps (3 to 5)</legend>
          <div v-for="(step, index) in draft.steps" :key="index" class="flex gap-[10px] items-start">
            <span class="mono text-[12px] w-[24px] pt-[12px]">{{ String(index + 1).padStart(2, '0') }}</span>
            <span class="hud-field !h-[42px] w-[34%]"><input v-model="step.title_en" class="!font-sans !text-[13px]" maxlength="32" :aria-label="`Step ${index + 1} title`" placeholder="Short title"></span>
            <span class="hud-field !h-[42px] flex-1"><input v-model="step.detail_en" class="!font-sans !text-[13px]" maxlength="220" :aria-label="`Step ${index + 1} detail`" placeholder="What to do"></span>
            <button
v-if="draft.steps.length > 3" type="button" class="focus-ring text-[11px] text-cabin-ice pt-[12px]"
                    :aria-label="`Remove step ${index + 1}`" @click="draft.steps.splice(index, 1)">Remove</button>
          </div>
          <button
v-if="draft.steps.length < 5" type="button" class="focus-ring self-start text-[11.5px] font-bold text-cabin-ok"
                  @click="draft.steps.push(blankStep())">+ Add step</button>
        </fieldset>
        <label class="flex flex-col gap-[6px]">
          <span class="label-caps">When to call the physician</span>
          <span class="hud-field !h-[42px]"><input v-model="draft.escalation_en" class="!font-sans !text-[13px]" maxlength="300" placeholder="e.g. Call the physician if the cracks bleed or swell."></span>
        </label>
        <p v-if="draftError" class="text-[12px] text-cabin-crit" role="alert">{{ draftError }}</p>
        <div class="flex justify-end gap-[12px]">
          <button type="button" class="hud-button !w-[140px] !h-[44px] !bg-none !bg-cabin-tile" @click="composing = false">Cancel</button>
          <button type="submit" class="hud-button !w-[200px] !h-[44px]" :disabled="!draftReady || saving">
            {{ saving ? 'Saving...' : 'Publish Protocol' }}
          </button>
        </div>
      </form>
    </div>
  </div>
</template>
