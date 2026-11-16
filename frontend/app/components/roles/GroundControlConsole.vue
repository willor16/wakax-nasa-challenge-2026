<script setup lang="ts">
// Ground Station Console (Mission Control). Mission Control holds no crew PIN card: it opens
// the console with the pre-flight link key, which the onboard server exchanges for an
// eight-hour ground session (the key itself is never kept in the browser). From here the
// ground sees everything the crew sent down, manages the roster from Earth and sends
// guidance; every order reaches the ship only after the one-way signal delay.
import { apiErrorMessage } from '~/composables/useApi'
import { formatTime } from '~/utils/format'

type Role = 'ASTRONAUT' | 'PILOT' | 'OPERATOR' | 'PHYSICIAN'
interface CrewRow {
  id: string, code: string, full_name: string, role: Role, title_en: string | null, sex: string | null, age: number | null
  status: string, readiness_score: number
  vitals: { resting_hr_bpm: number | null, spo2_pct: number | null, hrv_rmssd_ms: number | null, sleep_min_24h: number | null }
  psych: { mood_score: number, stress_score: number, wellbeing_index: number, mood_state: string | null } | null
  vision: { acuity_snellen: number | null, optic_sheath_right_mm: number | null }
  body: { weight_kg: number | null, muscle_mass_kg: number | null }
  alerts: { open: number, critical: number }
  streak_days: number
}
interface Packet { id: number, packet_type: string, title_en: string, state: string, sent_at_utc: string
  arrives_at_utc: string, bundle: Record<string, unknown> | null }
interface Order { id: number, packet_type: string, crew_id: string | null, summary_en: string, state: string
  sent_at_utc: string, arrives_at_utc: string }
interface Overview { earth_latency_min: number, crew: CrewRow[], packets: Packet[], uplink: Order[]
  roster: { id: string, code: string, full_name: string, role: Role, is_active: number }[] }

const KEY = 'spacescan.ground'
const base = useRuntimeConfig().public.apiBase
const token = ref<string | null>(null)
const linkKey = ref('')
const opening = ref(false)
const keyError = ref<string | null>(null)
const data = shallowRef<Overview | null>(null)
const loadError = ref<string | null>(null)
const now = ref(Date.now())
let ticker: ReturnType<typeof setInterval> | null = null
let poller: ReturnType<typeof setInterval> | null = null

function readToken() {
  try {
    return window.sessionStorage.getItem(KEY)
  }
  catch {
    return null
  }
}
function keepToken(value: string | null) {
  token.value = value
  try {
    if (value) window.sessionStorage.setItem(KEY, value)
    else window.sessionStorage.removeItem(KEY)
  }
  catch {
    // Storage unavailable: the session lasts until this page is closed.
  }
}

async function ground<T>(path: string, method: 'GET' | 'POST' = 'GET', body?: unknown): Promise<T> {
  try {
    return await $fetch<T>(`${base}/api/v1${path}`, { method, body: body as Record<string, unknown> | undefined,
      headers: token.value ? { Authorization: `Bearer ${token.value}` } : {} })
  }
  catch (error) {
    if ((error as { status?: number })?.status === 401) {
      keepToken(null)
      data.value = null
      keyError.value = 'The ground station session has ended. Enter the link key again.'
    }
    throw error
  }
}

async function openStation() {
  opening.value = true
  keyError.value = null
  try {
    const session = await $fetch<{ access_token: string }>(`${base}/api/v1/ground/session`,
      { method: 'POST', body: { link_key: linkKey.value.trim() } })
    keepToken(session.access_token)
    linkKey.value = ''
    await load()
  }
  catch (reason) {
    keyError.value = apiErrorMessage(reason, 'That link key is not valid.')
  }
  finally {
    opening.value = false
  }
}
function closeStation() {
  keepToken(null)
  data.value = null
}

async function load() {
  if (!token.value) return
  try {
    data.value = await ground<Overview>('/comms/ground/overview')
    loadError.value = null
  }
  catch (reason) {
    if (token.value) loadError.value = apiErrorMessage(reason)
  }
}

onMounted(() => {
  keepToken(readToken())
  void load()
  ticker = setInterval(() => { now.value = Date.now() }, 1000)
  poller = setInterval(() => void load(), 15_000)
})
onBeforeUnmount(() => {
  if (ticker) clearInterval(ticker)
  if (poller) clearInterval(poller)
})

// ---- what the crew sent down ------------------------------------------------------------
const openPacket = ref<number | null>(null)
const packetCrew = (p: Packet) => (Array.isArray(p.bundle?.crew) ? (p.bundle!.crew as Record<string, unknown>[]) : [])
const fmt = (v: number | null | undefined, unit = '', digits = 0) => (v == null ? '—' : `${v.toFixed(digits)}${unit}`)
const sleepText = (min: number | null) => (min == null ? '—' : `${Math.floor(min / 60)}h ${String(min % 60).padStart(2, '0')}m`)

// ---- roster orders from Earth -------------------------------------------------------------
const ROLES: Role[] = ['ASTRONAUT', 'PILOT', 'OPERATOR', 'PHYSICIAN']
const ACTIONS = [{ id: 'CREATE', label: 'Add' }, { id: 'UPDATE', label: 'Change' }, { id: 'DEACTIVATE', label: 'Remove' }] as const
const order = reactive({ action: 'CREATE' as 'CREATE' | 'UPDATE' | 'DEACTIVATE', crew_id: '', full_name: '', role: 'ASTRONAUT' as Role,
  title_en: '', pin: '', sex: '' as '' | 'F' | 'M' | 'X', age: '', height_cm: '' })
type TextKey = 'crew_id' | 'full_name' | 'title_en' | 'pin' | 'age' | 'height_cm'
const fields = computed(() => [
  ...(order.action === 'CREATE' ? [{ id: 'g-id', key: 'crew_id' as TextKey, label: 'Crew ID', placeholder: 'ID-05', mode: 'text' as const, wide: false }] : []),
  { id: 'g-name', key: 'full_name' as TextKey, label: 'Full Name', placeholder: 'First and last name', mode: 'text' as const, wide: order.action !== 'CREATE' },
  { id: 'g-title', key: 'title_en' as TextKey, label: 'Position', placeholder: 'e.g. Flight Engineer', mode: 'text' as const, wide: false },
  { id: 'g-pin', key: 'pin' as TextKey, label: order.action === 'CREATE' ? '4-Digit PIN' : 'New PIN (optional)', placeholder: '••••', mode: 'numeric' as const, wide: false },
  { id: 'g-age', key: 'age' as TextKey, label: 'Age', placeholder: 'e.g. 35', mode: 'numeric' as const, wide: false },
  { id: 'g-height', key: 'height_cm' as TextKey, label: 'Height (cm)', placeholder: 'e.g. 172', mode: 'decimal' as const, wide: false },
])
const orderNote = ref<{ tone: 'ok' | 'critical', text: string } | null>(null)
const sendingOrder = ref(false)
function pickMember(id: string) {
  const member = data.value?.roster.find(r => r.id === id)
  order.crew_id = id
  if (member && order.action === 'UPDATE') Object.assign(order, { full_name: member.full_name, role: member.role })
}
async function sendOrder() {
  orderNote.value = null
  if (!/^ID-\d{2,4}$/.test(order.crew_id)) {
    orderNote.value = { tone: 'critical', text: 'Crew ID: use the ID-05 format.' }
    return
  }
  if (order.action === 'CREATE' && (order.full_name.trim().length < 2 || !/^\d{4}$/.test(order.pin))) {
    orderNote.value = { tone: 'critical', text: 'A new crew member needs a full name and a 4-digit PIN.' }
    return
  }
  const body: Record<string, unknown> = { action: order.action, crew_id: order.crew_id }
  if (order.action !== 'DEACTIVATE') {
    Object.assign(body, {
      code: order.action === 'CREATE' ? order.crew_id.replace('-', '·') : undefined,
      full_name: order.full_name.trim() || undefined, role: order.role, title_en: order.title_en.trim() || undefined,
      pin: order.pin || undefined, sex: order.sex || undefined, age: order.age ? Number(order.age) : undefined,
      height_cm: order.height_cm ? Number(order.height_cm) : undefined,
    })
  }
  sendingOrder.value = true
  try {
    const sent = await ground<{ applies_after_min: number }>('/comms/ground/crew', 'POST', body)
    orderNote.value = { tone: 'ok', text: `Sent. It takes effect on board in about ${sent.applies_after_min} min (signal delay).` }
    Object.assign(order, { crew_id: '', full_name: '', title_en: '', pin: '', sex: '', age: '', height_cm: '' })
    await load()
  }
  catch (reason) {
    orderNote.value = { tone: 'critical', text: apiErrorMessage(reason) }
  }
  finally {
    sendingOrder.value = false
  }
}

// ---- guidance to the ship -----------------------------------------------------------------
const SENDERS = ['Flight Surgeon', 'Mission Control'] as const
const directive = reactive({ crew_id: null as string | null, sender_en: 'Flight Surgeon' as string, title_en: '', guidance_en: '' })
const directiveNote = ref<{ tone: 'ok' | 'critical', text: string } | null>(null)
const sendingDirective = ref(false)
async function sendDirective() {
  directiveNote.value = null
  if (directive.title_en.trim().length < 2 || directive.guidance_en.trim().length < 4) {
    directiveNote.value = { tone: 'critical', text: 'Write a title and the guidance before sending.' }
    return
  }
  sendingDirective.value = true
  try {
    const sent = await ground<{ arrives_after_min: number }>('/comms/ground/directives', 'POST', { ...directive })
    directiveNote.value = { tone: 'ok', text: `On its way. Arrives on board in about ${sent.arrives_after_min} min.` }
    Object.assign(directive, { title_en: '', guidance_en: '' })
    await load()
  }
  catch (reason) {
    directiveNote.value = { tone: 'critical', text: apiErrorMessage(reason) }
  }
  finally {
    sendingDirective.value = false
  }
}

const passing = ref(false)
async function completePass() {
  passing.value = true
  try {
    await ground('/comms/ground/flush', 'POST')
    await load()
  }
  catch (reason) {
    directiveNote.value = { tone: 'critical', text: apiErrorMessage(reason) }
  }
  finally {
    passing.value = false
  }
}
function countdown(o: Order): string {
  if (o.state !== 'IN TRANSIT') return 'ON BOARD'
  const left = Math.max(0, Math.round((new Date(o.arrives_at_utc).getTime() - now.value) / 1000))
  return `${Math.floor(left / 60)}:${String(left % 60).padStart(2, '0')}`
}
const travelling = computed(() => data.value?.uplink.filter(o => o.state === 'IN TRANSIT').length ?? 0)
</script>

<template>
  <!-- Link key -->
  <div v-if="!token || !data" class="flex-1 min-h-0 flex items-center justify-center">
    <ShellHudWindow class="w-[min(560px,100%)]" title="Ground Station Console" icon="earth" tag-text="MISSION CONTROL" flush>
      <UiStateNote v-if="token && !data" :loading="!loadError" :error="loadError" @retry="load()" />
      <form v-else class="flex flex-col gap-[14px] px-[24px] py-[22px]" @submit.prevent="openStation">
        <p class="text-[12.5px] text-cabin-ice leading-[1.7]">
          Mission Control opens this console with the link key shared before launch. Orders and guidance reach the ship after the signal delay.
        </p>
        <label class="flex flex-col gap-[6px]">
          <span class="label-caps">Link key</span>
          <span class="hud-field !h-[46px]">
            <input v-model="linkKey" type="password" autocomplete="off" class="!font-sans !text-[13px]" placeholder="Paste the pre-flight link key" aria-label="Link key">
          </span>
        </label>
        <p v-if="keyError" class="text-[12px] text-cabin-crit" role="alert">{{ keyError }}</p>
        <button type="submit" class="hud-button !h-[48px]" :disabled="opening || linkKey.trim().length < 8">
          {{ opening ? 'Opening…' : 'Open Ground Station' }}
        </button>
      </form>
    </ShellHudWindow>
  </div>

  <div v-else class="flex-1 min-h-0 flex gap-[18px]" data-ground-console>
    <!-- Everything received from the crew -->
    <div class="w-[50%] shrink-0 flex flex-col gap-[18px] min-h-0">
      <ShellHudWindow class="flex-[1.3] min-h-0" title="Crew Telemetry Received" icon="profile" :tag-text="`${data.crew.length} ACTIVE`" flush>
        <div class="flex-1 min-h-0 hud-scroll grid grid-cols-2 gap-[10px] p-[16px] content-start">
          <div v-for="c in data.crew" :key="c.id" class="tile relative px-[14px] py-[10px]">
            <span class="absolute left-0 top-[8px] bottom-[8px] w-[3px] rounded-full" :class="c.alerts.critical ? 'bg-cabin-crit' : c.status === 'Attention' ? 'bg-cabin-navy-edge' : 'bg-cabin-ok'" />
            <div class="flex items-center justify-between gap-[8px]">
              <p class="text-[12.5px] font-bold truncate"><span class="mono text-[10px] text-cabin-ice mr-[6px]">{{ c.code }}</span>{{ c.full_name }}</p>
              <span class="mono text-[11px] font-bold">{{ c.readiness_score }}</span>
            </div>
            <p class="text-[10px] text-cabin-ice">{{ c.title_en ?? c.role }} · {{ c.role.toLowerCase() }} · {{ c.status }}</p>
            <dl class="grid grid-cols-3 gap-x-[8px] gap-y-[3px] mt-[6px] text-[10.5px]">
              <div><dt class="text-cabin-muted text-[9px]">HEART</dt><dd class="mono">{{ fmt(c.vitals.resting_hr_bpm, ' bpm') }}</dd></div>
              <div><dt class="text-cabin-muted text-[9px]">SpO₂</dt><dd class="mono">{{ fmt(c.vitals.spo2_pct, '%') }}</dd></div>
              <div><dt class="text-cabin-muted text-[9px]">HRV</dt><dd class="mono">{{ fmt(c.vitals.hrv_rmssd_ms, ' ms') }}</dd></div>
              <div><dt class="text-cabin-muted text-[9px]">SLEEP 24H</dt><dd class="mono">{{ sleepText(c.vitals.sleep_min_24h) }}</dd></div>
              <div><dt class="text-cabin-muted text-[9px]">MOOD</dt><dd class="mono">{{ c.psych ? `${c.psych.mood_score}/5` : '—' }}</dd></div>
              <div><dt class="text-cabin-muted text-[9px]">WELLBEING</dt><dd class="mono">{{ c.psych ? Math.round(c.psych.wellbeing_index) : '—' }}</dd></div>
              <div><dt class="text-cabin-muted text-[9px]">EYE NERVE</dt><dd class="mono">{{ fmt(c.vision.optic_sheath_right_mm, ' mm', 1) }}</dd></div>
              <div><dt class="text-cabin-muted text-[9px]">ACUITY</dt><dd class="mono">{{ c.vision.acuity_snellen ? `20/${c.vision.acuity_snellen}` : '—' }}</dd></div>
              <div><dt class="text-cabin-muted text-[9px]">WEIGHT</dt><dd class="mono">{{ fmt(c.body.weight_kg, ' kg', 1) }}</dd></div>
            </dl>
            <p class="text-[10px] mt-[6px]" :class="c.alerts.critical ? 'text-cabin-crit' : 'text-cabin-ice'">
              {{ c.alerts.open }} open advisories<template v-if="c.alerts.critical"> · {{ c.alerts.critical }} critical</template> · streak {{ c.streak_days }} d
            </p>
          </div>
        </div>
      </ShellHudWindow>
      <ShellHudWindow class="flex-1 min-h-0" title="Health Packets Received" icon="mail" :tag-text="`+${data.earth_latency_min} MIN`" flush>
        <div class="flex-1 min-h-0 hud-scroll flex flex-col gap-[8px] p-[16px]">
          <UiStateNote v-if="!data.packets.length" empty="Nothing received from the ship yet." />
          <div v-for="p in data.packets" :key="p.id" class="tile shrink-0">
            <button
              type="button" class="focus-ring w-full text-left px-[14px] py-[9px] flex items-center gap-[12px]" :disabled="!p.bundle"
              :aria-expanded="openPacket === p.id" @click="openPacket = openPacket === p.id ? null : p.id"
            >
              <span class="mono text-[11px] w-[70px] shrink-0">{{ formatTime(p.sent_at_utc) }} UTC</span>
              <span class="text-[12px] flex-1 truncate">{{ p.title_en }}</span>
              <UiStatusPill :tone="p.state === 'RECEIVED' ? 'reference' : 'watch'" class="min-w-[100px]">{{ p.state }}</UiStatusPill>
            </button>
            <div v-if="openPacket === p.id && p.bundle" class="px-[14px] pb-[10px] text-[11px] text-cabin-ice flex flex-col gap-[3px]">
              <p v-if="p.bundle.mission_day">Mission day {{ p.bundle.mission_day }} · {{ String(p.bundle.mission_stage ?? '').toLowerCase() }}</p>
              <p v-for="(m, i) in packetCrew(p)" :key="i">
                <span class="text-cabin-text font-semibold">{{ m.full_name }}</span> · {{ m.status }} · readiness {{ m.readiness_score }}
                <template v-if="Array.isArray(m.open_advisories) && m.open_advisories.length"> · {{ (m.open_advisories as { title_en: string }[]).map(a => a.title_en).join('; ') }}</template>
              </p>
              <p v-if="p.bundle.note_en">Note: {{ p.bundle.note_en }}</p>
            </div>
          </div>
        </div>
      </ShellHudWindow>
    </div>

    <!-- Orders and guidance to the ship -->
    <div class="flex-1 min-w-0 flex flex-col gap-[18px] min-h-0">
      <ShellHudWindow class="flex-1 min-h-0" title="Crew Roster from Earth" icon="capture" tag-text="SIGNED ORDER" flush>
        <form class="flex-1 min-h-0 hud-scroll flex flex-col gap-[10px] px-[18px] py-[14px]" novalidate @submit.prevent="sendOrder">
          <div class="flex gap-[6px]" role="radiogroup" aria-label="Order">
            <button
              v-for="a in ACTIONS" :key="a.id" type="button" role="radio" :aria-checked="order.action === a.id"
              class="focus-ring flex-1 h-[30px] rounded-[4px] text-[10.5px] font-bold border-[1.3px]"
              :class="order.action === a.id ? 'menu-item-active' : 'bg-cabin-tile border-cabin-line text-cabin-ice'"
              @click="order.action = a.id"
            >{{ a.label }}</button>
          </div>
          <div v-if="order.action !== 'CREATE'" class="flex flex-wrap gap-[6px]" role="radiogroup" aria-label="Crew member">
            <button
              v-for="m in data.roster.filter(r => r.is_active)" :key="m.id" type="button" role="radio" :aria-checked="order.crew_id === m.id"
              class="focus-ring h-[28px] px-[10px] rounded-[4px] text-[10.5px] font-bold border-[1.2px]"
              :class="order.crew_id === m.id ? 'menu-item-active' : 'bg-cabin-tile border-cabin-line text-cabin-ice'"
              @click="pickMember(m.id)"
            >{{ m.code }} {{ m.full_name.split(' ').at(-1) }}</button>
          </div>
          <template v-if="order.action !== 'DEACTIVATE'">
            <div class="grid grid-cols-3 gap-x-[10px] gap-y-[8px]">
              <label
                v-for="f in fields" :key="f.id" :for="f.id" class="flex flex-col gap-[4px]"
                :class="f.wide ? 'col-span-2' : ''"
              >
                <span class="label-caps">{{ f.label }}</span>
                <span class="hud-field !h-[34px]">
                  <input
                    :id="f.id" v-model="order[f.key]" class="!font-sans !text-[12.5px]" :placeholder="f.placeholder"
                    :inputmode="f.mode" autocomplete="off"
                  >
                </span>
              </label>
            </div>
            <div class="flex gap-[6px]" role="radiogroup" aria-label="Role">
              <button
                v-for="r in ROLES" :key="r" type="button" role="radio" :aria-checked="order.role === r"
                class="focus-ring flex-1 h-[28px] rounded-[4px] text-[10px] font-bold border-[1.2px]"
                :class="order.role === r ? 'menu-item-active' : 'bg-cabin-tile border-cabin-line text-cabin-ice'"
                @click="order.role = r"
              >{{ r }}</button>
            </div>
            <div class="flex gap-[6px]" role="radiogroup" aria-label="Sex">
              <button
                v-for="s in [{ id: 'F', label: 'Female' }, { id: 'M', label: 'Male' }, { id: 'X', label: 'Not stated' }] as const" :key="s.id"
                type="button" role="radio" :aria-checked="order.sex === s.id"
                class="focus-ring flex-1 h-[28px] rounded-[4px] text-[10px] font-bold border-[1.2px]"
                :class="order.sex === s.id ? 'menu-item-active' : 'bg-cabin-tile border-cabin-line text-cabin-ice'"
                @click="order.sex = order.sex === s.id ? '' : s.id"
              >{{ s.label }}</button>
            </div>
          </template>
          <p v-if="orderNote" class="text-[11.5px]" :class="orderNote.tone === 'ok' ? 'text-cabin-ok' : 'text-cabin-crit'" role="status">{{ orderNote.text }}</p>
          <button
            type="submit" class="hud-button !h-[42px] mt-auto shrink-0" :class="order.action === 'DEACTIVATE' ? 'hud-button-critical' : ''"
            :disabled="sendingOrder || (order.action !== 'CREATE' && !order.crew_id)"
          >{{ sendingOrder ? 'Sending…' : order.action === 'CREATE' ? 'Send: Add Crew Member' : order.action === 'UPDATE' ? 'Send: Change Crew Member' : 'Send: Remove Crew Member' }}</button>
        </form>
      </ShellHudWindow>

      <ShellHudWindow class="flex-1 min-h-0" title="Guidance to the Ship" icon="mail" :tag-text="travelling ? `${travelling} IN TRANSIT` : 'LINK CLEAR'" flush>
        <div class="flex-1 min-h-0 flex gap-[14px] px-[18px] py-[14px]">
          <form class="flex-1 min-w-0 flex flex-col gap-[8px]" novalidate @submit.prevent="sendDirective">
            <div class="flex flex-wrap gap-[6px]" role="radiogroup" aria-label="Send to">
              <button
                v-for="t in [{ id: null, label: 'All crew' }, ...data.roster.filter(r => r.is_active).map(r => ({ id: r.id as string | null, label: `${r.code} ${r.full_name.split(' ').at(-1)}` }))]"
                :key="t.id ?? 'all'" type="button" role="radio" :aria-checked="directive.crew_id === t.id"
                class="focus-ring h-[26px] px-[9px] rounded-[4px] text-[10px] font-bold border-[1.2px]"
                :class="directive.crew_id === t.id ? 'menu-item-active' : 'bg-cabin-tile border-cabin-line text-cabin-ice'"
                @click="directive.crew_id = t.id"
              >{{ t.label }}</button>
            </div>
            <div class="flex gap-[6px]" role="radiogroup" aria-label="Sender">
              <button
                v-for="s in SENDERS" :key="s" type="button" role="radio" :aria-checked="directive.sender_en === s"
                class="focus-ring flex-1 h-[26px] rounded-[4px] text-[10px] font-bold border-[1.2px]"
                :class="directive.sender_en === s ? 'menu-item-active' : 'bg-cabin-tile border-cabin-line text-cabin-ice'"
                @click="directive.sender_en = s"
              >{{ s }}</button>
            </div>
            <span class="hud-field !h-[36px]"><input v-model="directive.title_en" maxlength="120" class="!font-sans !text-[12.5px]" placeholder="Title, e.g. Hydration check" aria-label="Title"></span>
            <textarea
              v-model="directive.guidance_en" maxlength="500" rows="3" aria-label="Guidance"
              class="flex-1 min-h-[54px] rounded-[4px] border-[1.3px] border-cabin-line bg-cabin-tile px-[12px] py-[8px] text-[12.5px] resize-none focus-ring"
              placeholder="Plain English guidance for the crew"
            />
            <p v-if="directiveNote" class="text-[11px]" :class="directiveNote.tone === 'ok' ? 'text-cabin-ok' : 'text-cabin-crit'" role="status">{{ directiveNote.text }}</p>
            <button type="submit" class="hud-button !h-[38px] shrink-0" :disabled="sendingDirective">{{ sendingDirective ? 'Sending…' : 'Send Guidance' }}</button>
          </form>
          <div class="w-[42%] shrink-0 flex flex-col gap-[6px] min-h-0">
            <p class="label-caps">Uplink queue</p>
            <div class="flex-1 min-h-0 hud-scroll flex flex-col gap-[6px]">
              <div v-for="o in data.uplink.slice(0, 10)" :key="o.id" class="tile shrink-0 px-[10px] py-[6px] flex items-center gap-[8px]">
                <span class="text-[11px] flex-1 truncate">{{ o.summary_en }}</span>
                <span class="mono text-[10.5px] font-bold" :class="o.state === 'IN TRANSIT' ? 'text-cabin-text' : 'text-cabin-ok'">{{ countdown(o) }}</span>
              </div>
            </div>
            <button type="button" class="hud-button !h-[36px] !text-[11px] shrink-0" :disabled="passing || !travelling" @click="completePass">
              {{ passing ? 'Transmitting…' : 'Complete Orbital Pass' }}
            </button>
            <button type="button" class="hud-button !h-[32px] !text-[10.5px] shrink-0 !bg-none !bg-cabin-tile" @click="closeStation">Close Ground Station</button>
          </div>
        </div>
      </ShellHudWindow>
    </div>
  </div>
</template>
