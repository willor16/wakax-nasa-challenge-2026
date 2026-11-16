<script setup lang="ts">
// Crew administration (operator only, requirement 3.1): roster, accounts and mission stage.
import { z } from 'zod'
import { apiErrorMessage } from '~/composables/useApi'
import { sexText } from '~/utils/format'

interface CrewRecord { id: string, code: string, full_name: string, role: string, title_en: string | null
  age: number | null, sex: string | null, blood_type: string | null, height_cm: number | null
  is_active: number, failed_attempts: number, locked_until_utc: string | null }

const { api } = useApi()
const { mission, load: loadMission } = useMission()
const { data, loading, error, refresh } = useResource(() => api<CrewRecord[]>('/crew'))
const notice = ref<{ tone: 'ok' | 'critical', title: string, text: string } | null>(null)
const busy = ref(false)

usePageHeader(() => ({ title: 'Crew Administration', subtitle: 'Operator only',
  status: data.value ? { text: `${data.value.filter(c => c.is_active).length} active crew`, tone: 'ok' } : null }))

const ROLES = ['ASTRONAUT', 'PILOT', 'OPERATOR', 'PHYSICIAN'] as const
const SEXES = [{ id: 'F', label: 'Female' }, { id: 'M', label: 'Male' }, { id: 'X', label: 'Not stated' }] as const
const BLOOD = ['O+', 'O-', 'A+', 'A-', 'B+', 'B-', 'AB+', 'AB-'] as const
const blank = () => ({ id: '', full_name: '', role: 'ASTRONAUT' as typeof ROLES[number], title_en: '', pin: '', age: '',
  sex: 'F' as 'F' | 'M' | 'X', blood_type: '', height_cm: '' })
const form = reactive(blank())
// Editing an existing crew member re-uses the same form; the PIN is only changed when typed.
const editing = ref<CrewRecord | null>(null)
const common = {
  full_name: z.string().trim().min(2, 'Full name: at least 2 characters'),
  role: z.enum(ROLES),
  title_en: z.string().trim().max(40).optional(),
  age: z.number().int().min(18, 'Age: 18 or older').max(80, 'Age: 80 or younger').optional(),
  sex: z.enum(['F', 'M', 'X']),
  blood_type: z.enum(BLOOD).optional(),
  height_cm: z.number().gt(100, 'Height: in centimetres, e.g. 172').lt(240, 'Height: in centimetres, e.g. 172').optional(),
}
const schema = z.object({
  id: z.string().regex(/^ID-\d{2,4}$/, 'Crew ID: use the ID-05 format'),
  pin: z.string().regex(/^\d{4}$/, 'PIN: exactly 4 digits'),
  ...common,
})
const editSchema = z.object({ pin: z.string().regex(/^\d{4}$/, 'New PIN: exactly 4 digits').optional(), ...common })
function values() {
  return { ...form, title_en: form.title_en || undefined, age: form.age ? Number(form.age) : undefined,
    blood_type: form.blood_type || undefined, height_cm: form.height_cm ? Number(form.height_cm) : undefined }
}
function startEdit(member: CrewRecord) {
  editing.value = member
  notice.value = null
  Object.assign(form, { id: member.id, full_name: member.full_name, role: member.role as typeof ROLES[number],
    title_en: member.title_en ?? '', pin: '', age: member.age ? String(member.age) : '',
    sex: (member.sex ?? 'X') as 'F' | 'M' | 'X', blood_type: member.blood_type ?? '',
    height_cm: member.height_cm ? String(member.height_cm) : '' })
}
function cancelEdit() {
  editing.value = null
  Object.assign(form, blank())
}
async function saveEdit() {
  const member = editing.value
  if (!member) return
  const { id: _id, ...rest } = values()
  const parsed = editSchema.safeParse({ ...rest, pin: rest.pin || undefined })
  if (!parsed.success) {
    notice.value = { tone: 'critical', title: 'Not saved', text: parsed.error.issues[0]!.message }
    return
  }
  await run(() => api(`/crew/${member.id}`, { method: 'PATCH', body: parsed.data }),
    parsed.data.pin ? `${parsed.data.full_name} was updated. The new PIN works from the next sign-in.` : `${parsed.data.full_name} was updated.`)
  if (notice.value?.tone === 'ok') cancelEdit()
}

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
  if (editing.value) return saveEdit()
  const parsed = schema.safeParse(values())
  if (!parsed.success) {
    notice.value = { tone: 'critical', title: 'Not saved', text: parsed.error.issues[0]!.message }
    return
  }
  const body = { ...parsed.data, code: parsed.data.id.replace('-', '·') }
  await run(() => api('/crew', { method: 'POST', body }), `${parsed.data.full_name} can now sign in with the new PIN.`)
  if (notice.value?.tone === 'ok') Object.assign(form, blank())
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
    `The mission is now in the ${nextStage.value!.toLowerCase()} stage. New readings are filed under it.`
      + (nextStage.value === 'MISSION' ? ' Pre-flight baselines are now frozen.' : ''))
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
              <p class="text-[11px] text-cabin-ice mt-[4px] truncate">{{ member.title_en ?? member.role }} · {{ member.role.toLowerCase() }} · {{ sexText(member.sex) }}{{ member.age ? ` · ${member.age} yrs` : '' }}{{ member.blood_type ? ` · ${member.blood_type}` : '' }}{{ member.height_cm ? ` · ${member.height_cm} cm` : '' }}</p>
            </div>
            <UiStatusPill :tone="isLocked(member) ? 'critical' : 'reference'">{{ isLocked(member) ? 'LOCKED' : member.is_active ? 'ACTIVE' : 'INACTIVE' }}</UiStatusPill>
            <button v-if="isLocked(member)" type="button" class="hud-button !w-[96px] !h-[34px] !text-[11px]" :disabled="busy" @click="unlock(member)">Unlock</button>
            <button
type="button" class="hud-button !w-[72px] !h-[34px] !text-[11px] !bg-none !bg-cabin-tile" :disabled="busy"
                    :aria-pressed="editing?.id === member.id" :aria-label="`Edit ${member.full_name}`" @click="startEdit(member)">Edit</button>
            <button
type="button" class="hud-button !w-[110px] !h-[34px] !text-[11px]" :class="member.is_active ? 'hud-button-critical' : ''" :disabled="busy"
                    @click="setActive(member, !member.is_active)">{{ member.is_active ? 'Deactivate' : 'Activate' }}</button>
          </div>
        </div>
      </ShellHudWindow>

      <div class="flex-1 min-w-0 flex flex-col gap-[18px]">
        <ShellHudWindow
class="flex-1 min-h-0" :title="editing ? `Edit · ${editing.full_name}` : 'Add Crew Member'" icon="capture"
                        :tag-text="editing ? editing.code : 'LOCAL'" flush>
          <form class="flex-1 min-h-0 hud-scroll flex flex-col gap-[12px] px-[22px] pt-[16px] pb-[16px]" novalidate @submit.prevent="create">
            <div class="grid grid-cols-3 gap-[12px]">
              <UiNumberField v-if="!editing" id="new-id" v-model="form.id" label="Crew ID" placeholder="ID-05" inputmode="text" />
              <UiNumberField
id="new-pin" v-model="form.pin" :label="editing ? 'New PIN (optional)' : '4-Digit PIN'"
                             :placeholder="editing ? 'Keep' : '••••'" inputmode="numeric" />
              <UiNumberField id="new-age" v-model="form.age" label="Age" placeholder="e.g. 35" inputmode="numeric" />
              <UiNumberField v-if="editing" id="new-height" v-model="form.height_cm" label="Height" unit="cm" placeholder="e.g. 172" inputmode="decimal" />
            </div>
            <div class="grid grid-cols-2 gap-[12px]">
              <UiNumberField id="new-name" v-model="form.full_name" label="Full Name" placeholder="First and last name" inputmode="text" />
              <UiNumberField id="new-title" v-model="form.title_en" label="Position" placeholder="e.g. Flight Engineer" inputmode="text" />
            </div>
            <div class="grid gap-[12px]" :class="editing ? 'grid-cols-1' : 'grid-cols-2'">
              <UiNumberField v-if="!editing" id="new-height" v-model="form.height_cm" label="Height" unit="cm" placeholder="e.g. 172" inputmode="decimal" />
              <div>
                <p class="label-caps mb-[6px]">Blood Group</p>
                <div class="grid grid-cols-4 gap-[4px]" role="radiogroup" aria-label="Blood group">
                  <button
v-for="group in BLOOD" :key="group" type="button" role="radio" :aria-checked="form.blood_type === group"
                          class="focus-ring h-[26px] rounded-[4px] text-[10px] font-bold border-[1.2px]"
                          :class="form.blood_type === group ? 'menu-item-active' : 'bg-cabin-tile border-cabin-line text-cabin-ice'"
                          @click="form.blood_type = form.blood_type === group ? '' : group">{{ group }}</button>
                </div>
              </div>
            </div>
            <div class="flex gap-[8px]" role="radiogroup" aria-label="Sex">
              <button
v-for="option in SEXES" :key="option.id" type="button" role="radio" :aria-checked="form.sex === option.id"
                      class="focus-ring flex-1 h-[30px] rounded-[4px] text-[10.5px] font-bold border-[1.3px]"
                      :class="form.sex === option.id ? 'menu-item-active' : 'bg-cabin-tile border-cabin-line text-cabin-ice'"
                      @click="form.sex = option.id">{{ option.label }}</button>
            </div>
            <div class="flex gap-[8px]" role="radiogroup" aria-label="Role">
              <button
v-for="role in ROLES" :key="role" type="button" role="radio" :aria-checked="form.role === role"
                      class="focus-ring flex-1 h-[34px] rounded-[4px] text-[10.5px] font-bold border-[1.3px]"
                      :class="form.role === role ? 'menu-item-active' : 'bg-cabin-tile border-cabin-line text-cabin-ice'" @click="form.role = role">{{ role }}</button>
            </div>
            <div class="flex gap-[10px] mt-auto">
              <button v-if="editing" type="button" class="hud-button !w-[130px] !h-[46px] !bg-none !bg-cabin-tile" @click="cancelEdit">Cancel</button>
              <button type="submit" class="hud-button flex-1 !h-[46px]" :disabled="busy">{{ editing ? 'Save Changes' : 'Create Crew Profile' }}</button>
            </div>
          </form>
        </ShellHudWindow>
        <ShellHudWindow class="h-[178px] shrink-0" title="Mission Stage" icon="rocket" :tag-text="mission?.current_stage" flush>
          <div class="flex-1 flex flex-col justify-center gap-[10px] px-[22px]">
            <UiSaveResult v-if="notice" v-bind="notice" />
            <p v-else class="text-[12.5px] text-cabin-ice">Readings are filed under the current stage. Stages only move forward: Launch → Mission → Return. Leaving Launch freezes the pre-flight baselines.</p>
            <button type="button" class="hud-button !h-[48px]" :class="confirmStage ? 'hud-button-critical' : ''" :disabled="!nextStage || busy" @click="advanceStage">
              {{ !nextStage ? 'Mission complete' : confirmStage ? `Confirm: start the ${nextStage.toLowerCase()} stage` : `Start ${nextStage.toLowerCase()} stage` }}
            </button>
          </div>
        </ShellHudWindow>
      </div>
    </div>
  </div>
</template>
