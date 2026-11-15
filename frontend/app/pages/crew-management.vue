<script setup lang="ts">
// Crew administration (operator only, requirement 3.1): roster, accounts and mission stage.
import { z } from 'zod'
import { apiErrorMessage } from '~/composables/useApi'
import { sexText } from '~/utils/format'

interface CrewRecord { id: string, code: string, full_name: string, role: string, title_en: string | null
  age: number | null, sex: string | null, is_active: number, failed_attempts: number, locked_until_utc: string | null }

const { api } = useApi()
const { mission, load: loadMission } = useMission()
const { data, loading, error, refresh } = useResource(() => api<CrewRecord[]>('/crew'))
const notice = ref<{ tone: 'ok' | 'critical', title: string, text: string } | null>(null)
const busy = ref(false)

usePageHeader(() => ({ title: 'Crew Administration', subtitle: 'Operator only',
  status: data.value ? { text: `${data.value.filter(c => c.is_active).length} active crew`, tone: 'ok' } : null }))

const ROLES = ['ASTRONAUT', 'PILOT', 'OPERATOR', 'PHYSICIAN'] as const
const form = reactive({ id: '', full_name: '', role: 'ASTRONAUT' as typeof ROLES[number], title_en: '', pin: '', age: '', sex: 'F' })
const schema = z.object({
  id: z.string().regex(/^ID-\d{2,4}$/, 'Crew ID: use the ID-05 format'),
  full_name: z.string().trim().min(2, 'Full name: at least 2 characters'),
  role: z.enum(ROLES),
  title_en: z.string().trim().max(40).optional(),
  pin: z.string().regex(/^\d{4}$/, 'PIN: exactly 4 digits'),
  age: z.number().int().min(18, 'Age: 18 or older').max(80, 'Age: 80 or younger').optional(),
  sex: z.enum(['F', 'M', 'X']),
})

async function run(action: () => Promise<unknown>, done: string) {
  busy.value = true
  notice.value = null
  try {
    await action()
    notice.value = { tone: 'ok', title: 'Saved', text: done }
    await refresh(true)
  }
  catch (reason) {
    notice.value = { tone: 'critical', title: 'Not saved', text: apiErrorMessage(reason) }
  }
  finally {
    busy.value = false
  }
}
async function create() {
  const parsed = schema.safeParse({ ...form, title_en: form.title_en || undefined, age: form.age ? Number(form.age) : undefined })
  if (!parsed.success) {
    notice.value = { tone: 'critical', title: 'Not saved', text: parsed.error.issues[0]!.message }
    return
  }
  const body = { ...parsed.data, code: parsed.data.id.replace('-', '·') }
  await run(() => api('/crew', { method: 'POST', body }), `${parsed.data.full_name} can now sign in with the new PIN.`)
  if (notice.value?.tone === 'ok') Object.assign(form, { id: '', full_name: '', title_en: '', pin: '', age: '' })
}
const setActive = (member: CrewRecord, active: boolean) => run(
  () => api(`/crew/${member.id}`, { method: 'PATCH', body: { is_active: active } }),
  `${member.full_name} is now ${active ? 'active' : 'inactive'}.`)
const unlock = (member: CrewRecord) => run(
  () => api(`/crew/${member.id}`, { method: 'PATCH', body: { unlock_account: true } }), `${member.full_name} can try the PIN again.`)

const NEXT_STAGE: Record<string, string | undefined> = { LAUNCH: 'MISSION', MISSION: 'RETURN' }
const nextStage = computed(() => NEXT_STAGE[mission.value?.current_stage ?? ''])
const confirmStage = ref(false)
async function advanceStage() {
  if (!nextStage.value) return
  if (!confirmStage.value) {
    confirmStage.value = true
    return
  }
  confirmStage.value = false
  await run(() => api('/mission/stage', { method: 'POST', body: { stage: nextStage.value } }),
    `The mission is now in the ${nextStage.value!.toLowerCase()} stage. New readings are filed under it.`)
  await loadMission()
}
const isLocked = (member: CrewRecord) => Boolean(member.locked_until_utc && new Date(member.locked_until_utc) > new Date())
</script>

<template>
  <div class="page">
    <ShellProfileTabs />
    <UiStateNote v-if="!data" :loading="loading" :error="error" @retry="refresh()" />
    <div v-else class="flex-1 min-h-0 flex gap-[18px]">
      <ShellHudWindow class="w-[57%] shrink-0" title="Crew Roster & Access" icon="profile" :tag-text="`${data.length} PROFILES`" flush>
        <div class="flex-1 min-h-0 hud-scroll flex flex-col gap-[12px] p-[22px]">
          <div v-for="member in data" :key="member.id" class="tile h-[74px] shrink-0 px-[20px] flex items-center gap-[18px]">
            <span class="mono text-[11px] w-[52px]">{{ member.code }}</span>
            <div class="flex-1 min-w-0">
              <p class="text-[14px] font-bold truncate" :class="member.is_active ? '' : 'text-cabin-dim'">{{ member.full_name }}</p>
              <p class="text-[11px] text-cabin-ice mt-[4px]">{{ member.title_en ?? member.role }} · {{ member.role.toLowerCase() }} · {{ sexText(member.sex) }}{{ member.age ? ` · ${member.age} yrs` : '' }}</p>
            </div>
            <UiStatusPill :tone="isLocked(member) ? 'critical' : 'reference'">{{ isLocked(member) ? 'LOCKED' : member.is_active ? 'ACTIVE' : 'INACTIVE' }}</UiStatusPill>
            <button v-if="isLocked(member)" type="button" class="hud-button !w-[96px] !h-[34px] !text-[11px]" :disabled="busy" @click="unlock(member)">Unlock</button>
            <button
type="button" class="hud-button !w-[110px] !h-[34px] !text-[11px]" :class="member.is_active ? 'hud-button-critical' : ''" :disabled="busy"
                    @click="setActive(member, !member.is_active)">{{ member.is_active ? 'Deactivate' : 'Activate' }}</button>
          </div>
        </div>
      </ShellHudWindow>

      <div class="flex-1 min-w-0 flex flex-col gap-[18px]">
        <ShellHudWindow class="flex-1" title="Add Crew Member" icon="capture" tag-text="LOCAL" flush>
          <form class="flex-1 flex flex-col gap-[14px] px-[22px] pt-[18px] pb-[18px]" novalidate @submit.prevent="create">
            <div class="grid grid-cols-2 gap-[14px]">
              <UiNumberField id="new-id" v-model="form.id" label="Crew ID" placeholder="ID-05" inputmode="text" />
              <UiNumberField id="new-pin" v-model="form.pin" label="4-Digit PIN" placeholder="••••" inputmode="numeric" />
            </div>
            <UiNumberField id="new-name" v-model="form.full_name" label="Full Name" placeholder="First and last name" inputmode="text" />
            <div class="grid grid-cols-2 gap-[14px]">
              <UiNumberField id="new-title" v-model="form.title_en" label="Position" placeholder="e.g. Flight Engineer" inputmode="text" />
              <UiNumberField id="new-age" v-model="form.age" label="Age" placeholder="e.g. 35" inputmode="numeric" />
            </div>
            <div class="flex gap-[8px]" role="radiogroup" aria-label="Role">
              <button
v-for="role in ROLES" :key="role" type="button" role="radio" :aria-checked="form.role === role"
                      class="focus-ring flex-1 h-[34px] rounded-[4px] text-[10.5px] font-bold border-[1.3px]"
                      :class="form.role === role ? 'menu-item-active' : 'bg-cabin-tile border-cabin-line text-cabin-ice'" @click="form.role = role">{{ role }}</button>
            </div>
            <button type="submit" class="hud-button !h-[48px] mt-auto" :disabled="busy">Create Crew Profile</button>
          </form>
        </ShellHudWindow>
        <ShellHudWindow class="h-[214px] shrink-0" title="Mission Stage" icon="rocket" :tag-text="mission?.current_stage" flush>
          <div class="flex-1 flex flex-col justify-center gap-[14px] px-[22px]">
            <UiSaveResult v-if="notice" v-bind="notice" />
            <p v-else class="text-[12.5px] text-cabin-ice">Readings are filed under the current stage. Stages only move forward: Launch → Mission → Return.</p>
            <button type="button" class="hud-button !h-[48px]" :class="confirmStage ? 'hud-button-critical' : ''" :disabled="!nextStage || busy" @click="advanceStage">
              {{ !nextStage ? 'Mission complete' : confirmStage ? `Confirm: start the ${nextStage.toLowerCase()} stage` : `Start ${nextStage.toLowerCase()} stage` }}
            </button>
          </div>
        </ShellHudWindow>
      </div>
    </div>
  </div>
</template>
