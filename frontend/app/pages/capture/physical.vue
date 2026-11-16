<script setup lang="ts">
// 11 · Data Capture · Physical & Clinical Labs.
import { apiErrorMessage } from '~/composables/useApi'
import { toNumber } from '~/composables/useCatalog'
import { admissionOf, noticeOf, pressureAdmission, type Admission, type Sex } from '~/utils/admission'

usePageHeader({ title: 'Data Capture · Physical & Clinical Labs', status: { text: 'Ready to log', tone: 'ok' } })
const { api } = useApi()
const { load, baselineHint, usualRange, catalog } = useCatalog()
const loadError = ref<string | null>(null)
const todayHydration = ref<{ value: number | null, target: number } | null>(null)
const workLocation = ref('')
// Physiological sex of the signed-in crew member: picks the female or male normal range.
const sex = ref<Sex>(null)

onMounted(async () => {
  try {
    await load()
    const { crew } = useSession()
    const profile = await api<{ crew: { sex: 'F' | 'M' | null }, daily: { metric_key: string, value: number | null, target?: number }[], work: { interior_location_en: string | null } }>(
      `/crew/${crew.value!.id}/profile`)
    sex.value = profile.crew.sex
    const row = profile.daily.find(r => r.metric_key === 'hydration_ml')
    if (row?.target) todayHydration.value = { value: row.value, target: row.target }
    workLocation.value = profile.work.interior_location_en ?? ''
  }
  catch (error) {
    loadError.value = apiErrorMessage(error)
  }
})

const vitals = reactive({ weight: '', bp: '', hr: '', temp: '', water: '', kcal: '', exercise: '', shift: '', shiftMode: 'IVA' as 'IVA' | 'EVA' })
const labs = reactive({ glucose: '', hemoglobin: '', sg: '', spo2: '' })
const vitalErrors = ref<Record<string, string>>({})
const labErrors = ref<Record<string, string>>({})
const vitalResult = ref<{ tone: 'ok' | 'critical', title: string, text: string } | null>(null)
const labResult = ref<{ tone: 'ok' | 'critical', title: string, text: string } | null>(null)
const busy = ref<'vitals' | 'labs' | null>(null)

function parseShift(text: string): number | undefined {
  const cleaned = text.trim().toLowerCase()
  if (!cleaned) return undefined
  const match = cleaned.match(/^(?:(\d{1,2})\s*h)?\s*(?:(\d{1,2})\s*m?)?$/)
  if (!match || (!match[1] && !match[2])) return Number.NaN
  return Number(match[1] ?? 0) * 60 + Number(match[2] ?? 0)
}
function parsePressure(text: string): [number | undefined, number | undefined] {
  if (!text.trim()) return [undefined, undefined]
  const parts = text.split(/[/\s]+/).filter(Boolean)
  return [toNumber(parts[0]), parts[1] === undefined ? Number.NaN : toNumber(parts[1])]
}

type Item = { metric_key: string, value_num: number, payload_json?: Record<string, unknown> }

// Daily habits are judged on the day's total, so a single entry is only checked for being possible.
const HABITS = new Set(['hydration_ml', 'calories_kcal', 'exercise_min'])
const VITAL_FIELDS = [
  ['weight', 'body_weight_kg'], ['hr', 'resting_hr_bpm'], ['temp', 'body_temp_c'],
  ['water', 'hydration_ml'], ['kcal', 'calories_kcal'], ['exercise', 'exercise_min'],
] as const
const LAB_FIELDS = [
  ['glucose', 'blood_glucose_mg_dl'], ['hemoglobin', 'hemoglobin_g_dl'], ['sg', 'urine_specific_gravity'], ['spo2', 'spo2_pct'],
] as const

function fieldText(field: string): string {
  const source = field in labs ? (labs as Record<string, string>)[field]! : (vitals as Record<string, string>)[field] ?? ''
  return field === 'water' ? source.replace('+', '') : source
}
function admissionFor(field: string, metricKey: string): Admission {
  return admissionOf(catalog.value[metricKey], toNumber(fieldText(field)), sex.value, !HABITS.has(metricKey))
}
const pressure = computed(() => {
  const [systolic, diastolic] = parsePressure(vitals.bp)
  return pressureAdmission(systolic, diastolic, catalog.value.bp_systolic_mmhg, catalog.value.bp_diastolic_mmhg, sex.value)
})
/** Live notice under every field: non-admissible (blocks saving) or outside the normal range. */
const notices = computed(() => {
  const found: Record<string, ReturnType<typeof noticeOf>> = {}
  for (const [field, metricKey] of [...VITAL_FIELDS, ...LAB_FIELDS]) found[field] = noticeOf(admissionFor(field, metricKey))
  found.bp = noticeOf(pressure.value)
  return found
})
const blocked = (fields: readonly (readonly [string, string])[], extra: string[] = []) =>
  [...fields.map(f => f[0]), ...extra].some(field => notices.value[field]?.tone === 'critical')
const vitalsBlocked = computed(() => blocked(VITAL_FIELDS, ['bp']))
const labsBlocked = computed(() => blocked(LAB_FIELDS))

function collect(fields: readonly (readonly [string, string])[], errors: Ref<Record<string, string>>): Item[] | null {
  const found: Record<string, string> = {}
  const items: Item[] = []
  for (const [field, metricKey] of fields) {
    const admission = admissionFor(field, metricKey)
    if (admission.level === 'empty') continue
    if (admission.level === 'invalid' || admission.level === 'non_admissible') found[field] = admission.text
    else items.push({ metric_key: metricKey, value_num: toNumber(fieldText(field))! })
  }
  errors.value = found
  return Object.keys(found).length ? null : items
}

const { unread, load: reloadMission } = useMission()

function summarise(result: { inserted_ids: number[], alerts_created: number[], streak: { daily_compliant: boolean } }, what: string) {
  const advisories = result.alerts_created.length
  if (advisories) {
    unread.value += advisories
    void reloadMission()
  }
  return advisories
    ? { tone: 'critical' as const, title: `Saved · ${advisories} advisor${advisories === 1 ? 'y' : 'ies'} raised`,
        text: 'Open Notifications for the recommended care steps.' }
    : { tone: 'ok' as const, title: `Saved · ${result.inserted_ids.length} ${what}`,
        text: result.streak.daily_compliant ? 'Profile and crew streak updated. Today counts toward your streak.' : 'Profile updated. Results appear in Profile → Physical.' }
}

async function saveVitals() {
  vitalResult.value = null
  const items = collect(VITAL_FIELDS, vitalErrors)
  if (!items) return
  const bp = pressure.value
  if (bp.level === 'invalid' || bp.level === 'non_admissible') {
    vitalErrors.value = { ...vitalErrors.value, bp: bp.text }
    return
  }
  if (bp.level !== 'empty') {
    const [systolic, diastolic] = parsePressure(vitals.bp)
    items.push({ metric_key: 'bp_systolic_mmhg', value_num: systolic! }, { metric_key: 'bp_diastolic_mmhg', value_num: diastolic! })
  }
  const minutes = parseShift(vitals.shift)
  if (minutes !== undefined) {
    if (Number.isNaN(minutes) || minutes > 1440) {
      vitalErrors.value = { ...vitalErrors.value, shift: 'Work shift: enter as 5h 20m' }
      return
    }
    const payload = { mode: vitals.shiftMode, location_en: vitals.shiftMode === 'EVA' ? 'Exterior Truss' : (workLocation.value || 'Habitat A') }
    items.push({ metric_key: 'work_shift_min', value_num: minutes, payload_json: payload })
    if (vitals.shiftMode === 'EVA') items.push({ metric_key: 'eva_shift_min', value_num: minutes, payload_json: payload })
  }
  if (!items.length) {
    vitalErrors.value = { form: 'Enter at least one reading.' }
    return
  }
  busy.value = 'vitals'
  try {
    const result = await api<Parameters<typeof summarise>[0]>('/measurements', { method: 'POST', body: { items } })
    vitalResult.value = summarise(result, 'readings')
    Object.assign(vitals, { weight: '', bp: '', hr: '', temp: '', water: '', kcal: '', exercise: '', shift: '' })
  }
  catch (error) {
    vitalErrors.value = { form: apiErrorMessage(error) }
  }
  finally {
    busy.value = null
  }
}

async function saveLabs() {
  labResult.value = null
  const items = collect(LAB_FIELDS, labErrors)
  if (!items) return
  if (!items.length) {
    labErrors.value = { form: 'Enter at least one result.' }
    return
  }
  busy.value = 'labs'
  try {
    const result = await api<Parameters<typeof summarise>[0]>('/measurements', { method: 'POST', body: { items } })
    labResult.value = summarise(result, 'results')
    Object.assign(labs, { glucose: '', hemoglobin: '', sg: '', spo2: '' })
  }
  catch (error) {
    labErrors.value = { form: apiErrorMessage(error) }
  }
  finally {
    busy.value = null
  }
}

const hydrationHint = computed(() => {
  const h = todayHydration.value
  if (!h) return 'Adds to today\'s total'
  return `Today ${((h.value ?? 0) / 1000).toFixed(1)} → ${(h.target / 1000).toFixed(1)} L`
})
const vitalNote = computed(() => {
  const h = todayHydration.value
  const added = toNumber(vitals.water.replace('+', ''))
  if (h && added && !Number.isNaN(added)) {
    const total = (h.value ?? 0) + added
    return total >= h.target
      ? `Saving +${added} mL completes today's ${(h.target / 1000).toFixed(1)} L hydration goal and updates Crew Streaks.`
      : `Saving +${added} mL brings today to ${(total / 1000).toFixed(1)} L of ${(h.target / 1000).toFixed(1)} L.`
  }
  return 'Every saved reading updates your Profile, advisories and Crew Streaks straight away.'
})
const labNote = computed(() => (sex.value
  ? `Impossible values are blocked; abnormal results are saved with an advisory. Ranges use ${sex.value === 'F' ? 'female' : 'male'} physiology.`
  : 'Impossible values are blocked; abnormal results are saved with an advisory.'))
const glucoseHint = computed(() => `Biweekly check · ${usualRange('blood_glucose_mg_dl')}`)
</script>

<template>
  <div class="page">
    <ShellCaptureTabs />
    <UiStateNote v-if="loadError" :error="loadError" @retry="() => reloadNuxtApp()" />
    <div v-else class="flex-1 min-h-0 flex gap-[18px]">
      <ShellHudWindow class="w-[56.7%] shrink-0" title="Daily Vitals, Biometrics & Habits Entry" icon="heart" tag-text="FEEDS PROFILE" flush>
        <form class="flex-1 min-h-0 flex flex-col px-[23px] pt-[clamp(12px,2.5dvh,24px)] pb-[clamp(12px,2.1dvh,20px)]" novalidate @submit.prevent="saveVitals">
          <div class="grid grid-cols-2 gap-x-[19px] gap-y-[clamp(12px,2.8dvh,26px)]">
            <UiNumberField id="weight" v-model="vitals.weight" help-key="body_weight_kg" label="Body Weight" :hint="baselineHint('body_weight_kg')" unit="kg" placeholder="e.g. 63.8" :error="vitalErrors.weight" :notice="notices.weight" />
            <UiNumberField id="bp" v-model="vitals.bp" help-key="blood_pressure" label="Blood Pressure" hint="Systolic / Diastolic" unit="mmHg" placeholder="118 / 76" inputmode="text" :error="vitalErrors.bp" :notice="notices.bp" />
            <UiNumberField id="hr" v-model="vitals.hr" help-key="resting_hr_bpm" label="Resting Heart Rate" :hint="baselineHint('resting_hr_bpm', 0, true)" unit="bpm" placeholder="e.g. 64" inputmode="numeric" :error="vitalErrors.hr" :notice="notices.hr" />
            <UiNumberField id="temp" v-model="vitals.temp" help-key="body_temp_c" label="Core Body Temp" :hint="`${catalog.body_temp_c?.nominal_min ?? ''}–${catalog.body_temp_c?.nominal_max ?? ''} °C`" unit="°C" placeholder="e.g. 36.8" :error="vitalErrors.temp" :notice="notices.temp" />
            <UiNumberField id="water" v-model="vitals.water" help-key="hydration_ml" label="Hydration Intake" :hint="hydrationHint" unit="mL" placeholder="+ 400" inputmode="numeric" :error="vitalErrors.water" :notice="notices.water" />
            <UiNumberField id="kcal" v-model="vitals.kcal" help-key="calories_kcal" label="Caloric Intake" hint="Today's meals" unit="kcal" placeholder="e.g. 2,420" inputmode="numeric" :error="vitalErrors.kcal" :notice="notices.kcal" />
            <UiNumberField id="exercise" v-model="vitals.exercise" help-key="exercise_min" label="Daily Exercise" hint="Target: 30 min session" unit="min" placeholder="e.g. 45" inputmode="numeric" :error="vitalErrors.exercise" :notice="notices.exercise" />
            <div>
              <div class="flex items-baseline justify-between mb-[8px]">
                <span class="flex items-center gap-[6px]"><label for="shift" class="label-caps">Work Shift (IVA / EVA)</label><UiParamHelp metric-key="work_shift_min" /></span>
                <span class="text-[9.5px] text-cabin-ice">{{ vitals.shiftMode === 'EVA' ? 'Exterior work' : workLocation || 'Interior work' }}</span>
              </div>
              <div class="hud-field" :data-invalid="vitalErrors.shift ? 'true' : undefined">
                <input id="shift" v-model="vitals.shift" placeholder="5h 20m" autocomplete="off">
                <div class="flex gap-[4px]" role="radiogroup" aria-label="Work type">
                  <button
v-for="mode in (['IVA', 'EVA'] as const)" :key="mode" type="button" role="radio" :aria-checked="vitals.shiftMode === mode"
                          class="focus-ring h-[28px] px-[10px] rounded-[3px] text-[10.5px] font-bold border"
                          :class="vitals.shiftMode === mode ? 'menu-item-active' : 'border-cabin-line text-cabin-ice'"
                          @click="vitals.shiftMode = mode">{{ mode }}</button>
                </div>
              </div>
              <p v-if="vitalErrors.shift" class="text-[10px] mt-[4px]" role="alert">{{ vitalErrors.shift }}</p>
            </div>
          </div>
          <div class="mt-auto pt-[10px] flex flex-col gap-[clamp(10px,1.7dvh,16px)]">
            <UiSaveResult v-if="vitalResult" :tone="vitalResult.tone" :title="vitalResult.title" :text="vitalResult.text" />
            <UiSaveResult v-else-if="vitalErrors.form" tone="critical" title="Not saved" :text="vitalErrors.form" />
            <UiSaveResult v-else tone="ok" title="Automatic sync to personal profile & crew streaks" :text="vitalNote" />
            <button type="submit" class="hud-button relative" :disabled="busy !== null || vitalsBlocked">
              <Icon name="spacescan:heart" class="w-[17px] h-[17px] absolute left-[22px]" />
              {{ busy === 'vitals' ? 'Saving…' : 'Save Daily Vitals & Habits' }}
            </button>
          </div>
        </form>
      </ShellHudWindow>

      <ShellHudWindow class="flex-1 min-w-0" title="Periodic Clinical Labs Entry" icon="kit" tag-text="LAB STRIPS" flush>
        <form class="flex-1 min-h-0 flex flex-col px-[23px] pt-[clamp(12px,2.5dvh,24px)] pb-[clamp(12px,2.1dvh,20px)]" novalidate @submit.prevent="saveLabs">
          <div class="flex flex-col gap-[clamp(12px,2.8dvh,26px)]">
            <UiNumberField id="glucose" v-model="labs.glucose" help-key="blood_glucose_mg_dl" label="Fasting Blood Glucose" :hint="glucoseHint" unit="mg/dL" placeholder="e.g. 89" inputmode="numeric" :error="labErrors.glucose" :notice="notices.glucose" />
            <UiNumberField id="hemoglobin" v-model="labs.hemoglobin" help-key="hemoglobin_g_dl" label="Hemoglobin (Blood Panel)" :hint="`Monthly check · ${usualRange('hemoglobin_g_dl', sex)} (${sex === 'F' ? 'female' : sex === 'M' ? 'male' : 'adult'})`" unit="g/dL" placeholder="e.g. 13.8" :error="labErrors.hemoglobin" :notice="notices.hemoglobin" />
            <UiNumberField id="sg" v-model="labs.sg" help-key="urine_specific_gravity" label="Urine Specific Gravity" :hint="`Weekly strip · Target ${catalog.urine_specific_gravity?.nominal_min ?? ''}–${catalog.urine_specific_gravity?.nominal_max ?? ''}`" unit="SG" placeholder="e.g. 1.018" :error="labErrors.sg" :notice="notices.sg" />
            <UiNumberField id="spo2" v-model="labs.spo2" help-key="spo2_pct" label="Oxygen Saturation (SpO₂)" :hint="`Spot oximetry · ${usualRange('spo2_pct')}`" unit="%" placeholder="e.g. 98" inputmode="numeric" :error="labErrors.spo2" :notice="notices.spo2" />
          </div>
          <div class="mt-auto pt-[10px] flex flex-col gap-[clamp(10px,1.7dvh,16px)]">
            <UiSaveResult v-if="labResult" :tone="labResult.tone" :title="labResult.title" :text="labResult.text" />
            <UiSaveResult v-else-if="labErrors.form" tone="critical" title="Not saved" :text="labErrors.form" />
            <UiSaveResult v-else tone="ok" title="Range validation before saving" :text="labNote" />
            <button type="submit" class="hud-button relative" :disabled="busy !== null || labsBlocked">
              <Icon name="spacescan:kit" class="w-[17px] h-[17px] absolute left-[22px]" />
              {{ busy === 'labs' ? 'Saving…' : 'Save Clinical Lab Results' }}
            </button>
          </div>
        </form>
      </ShellHudWindow>
    </div>
  </div>
</template>
