<script setup lang="ts">
import type { MeasurementIngestOut, MissionStage } from '~/composables/useMeasurements'
import {
  buildClinicalLabsItems,
  buildDailyVitalsItems,
  extractErrorMessage,
} from '~/composables/useMeasurements'
import { clinicalLabsSchema, dailyVitalsHabitsSchema } from '~/schemas/capture'

const { activeCrew } = useSession()
const { ingestMeasurements } = useMeasurements()

const missionStage = ref<MissionStage>('MISSION')
const baseHydrationMl = ref(2400)

const vitalsForm = reactive({
  bodyWeightKg: 63.8,
  bpSystolicMmhg: 118,
  bpDiastolicMmhg: 76,
  restingHrBpm: 64,
  bodyTempC: 36.8,
  hydrationAddMl: 400,
  caloriesKcal: 2420,
  exerciseMin: 85,
  workShiftText: '5h 20m',
  workShiftMode: 'IVA' as 'IVA' | 'EVA',
})

const labsForm = reactive({
  bloodGlucoseMgDl: 89,
  hemoglobinGDl: 13.8,
  urineSpecificGravity: 1.018,
  spo2Pct: 98,
})

const vitalsErrors = ref<Record<string, string>>({})
const isSavingVitals = ref(false)
const vitalsResult = ref<MeasurementIngestOut | null>(null)
const vitalsSubmitError = ref('')

const labsErrors = ref<Record<string, string>>({})
const isSavingLabs = ref(false)
const labsResult = ref<MeasurementIngestOut | null>(null)
const labsSubmitError = ref('')

const projectedHydrationLiters = computed(() => {
  const addMl = Number.isFinite(vitalsForm.hydrationAddMl) ? Math.max(0, vitalsForm.hydrationAddMl) : 0
  return ((baseHydrationMl.value + addMl) / 1000).toFixed(1)
})

const baselineHydrationLiters = computed(() => (baseHydrationMl.value / 1000).toFixed(1))

const workStationLabel = computed(() =>
  vitalsForm.workShiftMode === 'EVA' ? 'Airlock Exterior' : 'Command Bridge',
)

const labsWithinNominalBounds = computed(() => {
  return (
    labsForm.bloodGlucoseMgDl >= 70 &&
    labsForm.bloodGlucoseMgDl <= 99 &&
    labsForm.hemoglobinGDl >= 12.5 &&
    labsForm.hemoglobinGDl <= 16.0 &&
    labsForm.urineSpecificGravity >= 1.005 &&
    labsForm.urineSpecificGravity <= 1.02 &&
    labsForm.spo2Pct >= 96 &&
    labsForm.spo2Pct <= 100
  )
})

function toggleWorkShiftMode() {
  vitalsForm.workShiftMode = vitalsForm.workShiftMode === 'IVA' ? 'EVA' : 'IVA'
}

async function handleSaveVitals() {
  vitalsErrors.value = {}
  vitalsResult.value = null
  vitalsSubmitError.value = ''

  const parsed = dailyVitalsHabitsSchema.safeParse({
    missionStage: missionStage.value,
    ...vitalsForm,
  })
  if (!parsed.success) {
    for (const issue of parsed.error.issues) {
      const key = String(issue.path[0] ?? 'form')
      vitalsErrors.value[key] = issue.message
    }
    return
  }

  isSavingVitals.value = true
  try {
    const crewId = activeCrew.value?.id ?? 'ID-01'
    const res = await ingestMeasurements({
      crew_id: crewId,
      mission_stage: parsed.data.missionStage,
      source_type: 'MANUAL',
      items: buildDailyVitalsItems(parsed.data, baseHydrationMl.value),
    })
    vitalsResult.value = res
    baseHydrationMl.value += parsed.data.hydrationAddMl
  }
  catch (err: unknown) {
    vitalsSubmitError.value = extractErrorMessage(err, 'Unable to save daily vitals and habits.')
  }
  finally {
    isSavingVitals.value = false
  }
}

async function handleSaveLabs() {
  labsErrors.value = {}
  labsResult.value = null
  labsSubmitError.value = ''

  const parsed = clinicalLabsSchema.safeParse({
    missionStage: missionStage.value,
    ...labsForm,
  })
  if (!parsed.success) {
    for (const issue of parsed.error.issues) {
      const key = String(issue.path[0] ?? 'form')
      labsErrors.value[key] = issue.message
    }
    return
  }

  isSavingLabs.value = true
  try {
    const crewId = activeCrew.value?.id ?? 'ID-01'
    const res = await ingestMeasurements({
      crew_id: crewId,
      mission_stage: parsed.data.missionStage,
      source_type: 'MANUAL',
      items: buildClinicalLabsItems(parsed.data),
    })
    labsResult.value = res
  }
  catch (err: unknown) {
    labsSubmitError.value = extractErrorMessage(err, 'Unable to save clinical lab results.')
  }
  finally {
    isSavingLabs.value = false
  }
}
</script>

<template>
  <div class="flex flex-col gap-[18px] flex-1">
    <CaptureSubnavBar v-model:mission-stage="missionStage" show-stage-selector />

    <div class="grid grid-cols-1 lg:grid-cols-12 gap-[18px] flex-1">
      <ShellHudWindow
        class="lg:col-span-7"
        title="DAILY VITALS, BIOMETRICS & HABITS ENTRY"
        icon="vitruvian"
        tag-text="FEEDS PROFILE"
      >
        <form class="h-full flex flex-col justify-between gap-5" @submit.prevent="handleSaveVitals">
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-x-5 gap-y-4">
            <label class="flex flex-col gap-1.5">
              <div class="flex items-baseline justify-between gap-2">
                <span class="text-[10px] font-bold tracking-[0.05em] uppercase text-cabin-muted">
                  BODY WEIGHT
                </span>
                <span class="text-[10px] font-mono text-cabin-ice/80">
                  Baseline: 64.5 kg
                </span>
              </div>
              <div class="h-12 px-3.5 rounded-[4px] bg-cabin-inset border border-cabin-text/55 focus-within:border-cabin-text flex items-center justify-between gap-2">
                <input
                  v-model.number="vitalsForm.bodyWeightKg"
                  type="number"
                  step="0.1"
                  aria-label="Body weight in kilograms"
                  class="w-full bg-transparent outline-none font-mono text-[16px] font-bold text-cabin-text"
                >
                <span class="font-mono text-[11.5px] text-cabin-muted shrink-0">kg</span>
              </div>
              <span v-if="vitalsErrors.bodyWeightKg" class="text-[10px] text-cabin-crit">
                {{ vitalsErrors.bodyWeightKg }}
              </span>
            </label>

            <div class="flex flex-col gap-1.5">
              <div class="flex items-baseline justify-between gap-2">
                <span class="text-[10px] font-bold tracking-[0.05em] uppercase text-cabin-muted">
                  BLOOD PRESSURE
                </span>
                <span class="text-[10px] font-mono text-cabin-ice/80">
                  Systolic / Diastolic
                </span>
              </div>
              <div class="h-12 px-3.5 rounded-[4px] bg-cabin-inset border border-cabin-card/75 focus-within:border-cabin-text flex items-center justify-between gap-2">
                <div class="flex items-center gap-1.5 flex-1 min-w-0">
                  <input
                    v-model.number="vitalsForm.bpSystolicMmhg"
                    type="number"
                    step="1"
                    aria-label="Systolic blood pressure in mmHg"
                    class="w-16 bg-transparent outline-none font-mono text-[16px] font-bold text-cabin-text"
                  >
                  <span class="font-mono text-[15px] font-bold text-cabin-muted">/</span>
                  <input
                    v-model.number="vitalsForm.bpDiastolicMmhg"
                    type="number"
                    step="1"
                    aria-label="Diastolic blood pressure in mmHg"
                    class="w-16 bg-transparent outline-none font-mono text-[16px] font-bold text-cabin-text"
                  >
                </div>
                <span class="font-mono text-[11.5px] text-cabin-muted shrink-0">mmHg</span>
              </div>
              <span
                v-if="vitalsErrors.bpSystolicMmhg || vitalsErrors.bpDiastolicMmhg"
                class="text-[10px] text-cabin-crit"
              >
                {{ vitalsErrors.bpSystolicMmhg || vitalsErrors.bpDiastolicMmhg }}
              </span>
            </div>

            <label class="flex flex-col gap-1.5">
              <div class="flex items-baseline justify-between gap-2">
                <span class="text-[10px] font-bold tracking-[0.05em] uppercase text-cabin-muted">
                  RESTING HEART RATE
                </span>
                <span class="text-[10px] font-mono text-cabin-ice/80">
                  58–72 bpm baseline
                </span>
              </div>
              <div class="h-12 px-3.5 rounded-[4px] bg-cabin-inset border border-cabin-card/75 focus-within:border-cabin-text flex items-center justify-between gap-2">
                <input
                  v-model.number="vitalsForm.restingHrBpm"
                  type="number"
                  step="1"
                  aria-label="Resting heart rate in bpm"
                  class="w-full bg-transparent outline-none font-mono text-[16px] font-bold text-cabin-text"
                >
                <span class="font-mono text-[11.5px] text-cabin-muted shrink-0">bpm</span>
              </div>
              <span v-if="vitalsErrors.restingHrBpm" class="text-[10px] text-cabin-crit">
                {{ vitalsErrors.restingHrBpm }}
              </span>
            </label>

            <label class="flex flex-col gap-1.5">
              <div class="flex items-baseline justify-between gap-2">
                <span class="text-[10px] font-bold tracking-[0.05em] uppercase text-cabin-muted">
                  CORE BODY TEMP
                </span>
                <span class="text-[10px] font-mono text-cabin-ice/80">
                  36.4–37.2 °C
                </span>
              </div>
              <div class="h-12 px-3.5 rounded-[4px] bg-cabin-inset border border-cabin-card/75 focus-within:border-cabin-text flex items-center justify-between gap-2">
                <input
                  v-model.number="vitalsForm.bodyTempC"
                  type="number"
                  step="0.1"
                  aria-label="Core body temperature in Celsius"
                  class="w-full bg-transparent outline-none font-mono text-[16px] font-bold text-cabin-text"
                >
                <span class="font-mono text-[11.5px] text-cabin-muted shrink-0">°C</span>
              </div>
              <span v-if="vitalsErrors.bodyTempC" class="text-[10px] text-cabin-crit">
                {{ vitalsErrors.bodyTempC }}
              </span>
            </label>

            <label class="flex flex-col gap-1.5">
              <div class="flex items-baseline justify-between gap-2">
                <span class="text-[10px] font-bold tracking-[0.05em] uppercase text-cabin-muted">
                  HYDRATION INTAKE
                </span>
                <span class="text-[10px] font-mono text-cabin-ice/80">
                  Updates {{ baselineHydrationLiters }} -> {{ projectedHydrationLiters }} L
                </span>
              </div>
              <div class="h-12 px-3.5 rounded-[4px] bg-cabin-inset border border-cabin-card/75 focus-within:border-cabin-text flex items-center justify-between gap-2">
                <div class="flex items-center gap-1 flex-1 min-w-0">
                  <span class="font-mono text-[16px] font-bold text-cabin-ok">+</span>
                  <input
                    v-model.number="vitalsForm.hydrationAddMl"
                    type="number"
                    step="50"
                    aria-label="Added hydration intake in milliliters"
                    class="w-full bg-transparent outline-none font-mono text-[16px] font-bold text-cabin-text"
                  >
                </div>
                <span class="font-mono text-[11.5px] text-cabin-muted shrink-0">mL</span>
              </div>
              <span v-if="vitalsErrors.hydrationAddMl" class="text-[10px] text-cabin-crit">
                {{ vitalsErrors.hydrationAddMl }}
              </span>
            </label>

            <label class="flex flex-col gap-1.5">
              <div class="flex items-baseline justify-between gap-2">
                <span class="text-[10px] font-bold tracking-[0.05em] uppercase text-cabin-muted">
                  CALORIC INTAKE
                </span>
                <span class="text-[10px] font-mono text-cabin-ice/80">
                  Target: 2,500 kcal
                </span>
              </div>
              <div class="h-12 px-3.5 rounded-[4px] bg-cabin-inset border border-cabin-card/75 focus-within:border-cabin-text flex items-center justify-between gap-2">
                <input
                  v-model.number="vitalsForm.caloriesKcal"
                  type="number"
                  step="50"
                  aria-label="Daily caloric intake in kilocalories"
                  class="w-full bg-transparent outline-none font-mono text-[16px] font-bold text-cabin-text"
                >
                <span class="font-mono text-[11.5px] text-cabin-muted shrink-0">kcal</span>
              </div>
              <span v-if="vitalsErrors.caloriesKcal" class="text-[10px] text-cabin-crit">
                {{ vitalsErrors.caloriesKcal }}
              </span>
            </label>

            <label class="flex flex-col gap-1.5">
              <div class="flex items-baseline justify-between gap-2">
                <span class="text-[10px] font-bold tracking-[0.05em] uppercase text-cabin-muted">
                  DAILY EXERCISE
                </span>
                <span class="text-[10px] font-mono text-cabin-ice/80">
                  Target: 90 min
                </span>
              </div>
              <div class="h-12 px-3.5 rounded-[4px] bg-cabin-inset border border-cabin-card/75 focus-within:border-cabin-text flex items-center justify-between gap-2">
                <input
                  v-model.number="vitalsForm.exerciseMin"
                  type="number"
                  step="5"
                  aria-label="Daily exercise load in minutes"
                  class="w-full bg-transparent outline-none font-mono text-[16px] font-bold text-cabin-text"
                >
                <span class="font-mono text-[11.5px] text-cabin-muted shrink-0">min</span>
              </div>
              <span v-if="vitalsErrors.exerciseMin" class="text-[10px] text-cabin-crit">
                {{ vitalsErrors.exerciseMin }}
              </span>
            </label>

            <div class="flex flex-col gap-1.5">
              <div class="flex items-baseline justify-between gap-2">
                <span class="text-[10px] font-bold tracking-[0.05em] uppercase text-cabin-muted">
                  WORK SHIFT (IVA / EVA)
                </span>
                <span class="text-[10px] font-mono text-cabin-ice/80">
                  {{ workStationLabel }}
                </span>
              </div>
              <div class="h-12 px-3.5 rounded-[4px] bg-cabin-inset border border-cabin-card/75 focus-within:border-cabin-text flex items-center justify-between gap-2">
                <input
                  v-model="vitalsForm.workShiftText"
                  type="text"
                  placeholder="5h 20m"
                  aria-label="Operational work shift duration"
                  class="w-full bg-transparent outline-none font-mono text-[16px] font-bold text-cabin-text"
                >
                <button
                  type="button"
                  class="px-2.5 h-7 rounded-[3px] menu-item-active font-mono text-[11px] font-bold text-cabin-text shrink-0 cursor-pointer"
                  title="Switch between interior and exterior duty"
                  @click="toggleWorkShiftMode"
                >
                  {{ vitalsForm.workShiftMode }}
                </button>
              </div>
              <span v-if="vitalsErrors.workShiftText" class="text-[10px] text-cabin-crit">
                {{ vitalsErrors.workShiftText }}
              </span>
            </div>
          </div>

          <div class="flex flex-col gap-3.5">
            <div
              v-if="vitalsSubmitError"
              class="px-4 py-3 rounded-[4px] bg-cabin-crit/18 border border-cabin-crit flex flex-col gap-1"
            >
              <span class="text-[10px] font-bold tracking-[0.05em] uppercase text-cabin-text">
                SUBMISSION ALERT
              </span>
              <span class="text-[12px] text-cabin-ice">
                {{ vitalsSubmitError }}
              </span>
            </div>

            <div
              v-else
              class="px-4 py-3 rounded-[4px] bg-cabin-inset border border-cabin-card/75 flex flex-col gap-1"
            >
              <span class="text-[10px] font-bold tracking-[0.05em] uppercase text-cabin-ok">
                AUTOMATIC SYNC TO PERSONAL PROFILE & CREW STREAKS
              </span>
              <span v-if="vitalsResult" class="text-[12px] text-cabin-ice">
                Saved {{ vitalsResult.inserted_ids.length }} daily metrics. Alerts triggered:
                {{ vitalsResult.alerts_created.length }}. Daily logs completed:
                {{ vitalsResult.streak.logs_completed }} ({{ vitalsResult.streak.daily_compliant ? '4 / 4 Goal Met' : 'In Progress' }}).
              </span>
              <span v-else class="text-[12px] text-cabin-ice">
                Saving +{{ vitalsForm.hydrationAddMl }} mL completes today's {{ projectedHydrationLiters }} L hydration goal and updates Crew Streaks to 4 / 4.
              </span>
            </div>

            <button
              type="submit"
              :disabled="isSavingVitals"
              class="h-[52px] w-full px-5 rounded-[5px] bg-cabin-card hover:bg-cabin-card/85 border border-cabin-text/45 flex items-center justify-center gap-2.5 text-[13px] font-bold tracking-[0.03em] text-cabin-text cursor-pointer disabled:opacity-45 transition-colors"
            >
              <Icon name="spacescan:capture" class="w-4 h-4 text-cabin-text" />
              <span>{{ isSavingVitals ? 'Saving Daily Vitals & Habits...' : 'Save Daily Vitals & Habits' }}</span>
            </button>
          </div>
        </form>
      </ShellHudWindow>

      <ShellHudWindow
        class="lg:col-span-5"
        title="PERIODIC CLINICAL LABS ENTRY"
        icon="kit"
        tag-text="LAB STRIPS"
      >
        <form class="h-full flex flex-col justify-between gap-5" @submit.prevent="handleSaveLabs">
          <div class="flex flex-col gap-4">
            <label class="flex flex-col gap-1.5">
              <div class="flex items-baseline justify-between gap-2">
                <span class="text-[10px] font-bold tracking-[0.05em] uppercase text-cabin-muted">
                  FASTING BLOOD GLUCOSE
                </span>
                <span class="text-[10px] font-mono text-cabin-ice/80">
                  Biweekly check · Normal 70–99 mg/dL
                </span>
              </div>
              <div class="h-12 px-3.5 rounded-[4px] bg-cabin-inset border border-cabin-card/75 focus-within:border-cabin-text flex items-center justify-between gap-2">
                <input
                  v-model.number="labsForm.bloodGlucoseMgDl"
                  type="number"
                  step="1"
                  aria-label="Fasting blood glucose in mg per dL"
                  class="w-full bg-transparent outline-none font-mono text-[16px] font-bold text-cabin-text"
                >
                <span class="font-mono text-[11.5px] text-cabin-muted shrink-0">mg/dL</span>
              </div>
              <span v-if="labsErrors.bloodGlucoseMgDl" class="text-[10px] text-cabin-crit">
                {{ labsErrors.bloodGlucoseMgDl }}
              </span>
            </label>

            <label class="flex flex-col gap-1.5">
              <div class="flex items-baseline justify-between gap-2">
                <span class="text-[10px] font-bold tracking-[0.05em] uppercase text-cabin-muted">
                  HEMOGLOBIN (BLOOD PANEL)
                </span>
                <span class="text-[10px] font-mono text-cabin-ice/80">
                  Monthly check · Normal 12.5–16.0 g/dL
                </span>
              </div>
              <div class="h-12 px-3.5 rounded-[4px] bg-cabin-inset border border-cabin-card/75 focus-within:border-cabin-text flex items-center justify-between gap-2">
                <input
                  v-model.number="labsForm.hemoglobinGDl"
                  type="number"
                  step="0.1"
                  aria-label="Blood hemoglobin in g per dL"
                  class="w-full bg-transparent outline-none font-mono text-[16px] font-bold text-cabin-text"
                >
                <span class="font-mono text-[11.5px] text-cabin-muted shrink-0">g/dL</span>
              </div>
              <span v-if="labsErrors.hemoglobinGDl" class="text-[10px] text-cabin-crit">
                {{ labsErrors.hemoglobinGDl }}
              </span>
            </label>

            <label class="flex flex-col gap-1.5">
              <div class="flex items-baseline justify-between gap-2">
                <span class="text-[10px] font-bold tracking-[0.05em] uppercase text-cabin-muted">
                  URINE SPECIFIC GRAVITY
                </span>
                <span class="text-[10px] font-mono text-cabin-ice/80">
                  Weekly strip · Target 1.005–1.020
                </span>
              </div>
              <div class="h-12 px-3.5 rounded-[4px] bg-cabin-inset border border-cabin-text/55 focus-within:border-cabin-text flex items-center justify-between gap-2">
                <input
                  v-model.number="labsForm.urineSpecificGravity"
                  type="number"
                  step="0.001"
                  aria-label="Urine specific gravity"
                  class="w-full bg-transparent outline-none font-mono text-[16px] font-bold text-cabin-text"
                >
                <span class="font-mono text-[11.5px] text-cabin-muted shrink-0">SG</span>
              </div>
              <span v-if="labsErrors.urineSpecificGravity" class="text-[10px] text-cabin-crit">
                {{ labsErrors.urineSpecificGravity }}
              </span>
            </label>

            <label class="flex flex-col gap-1.5">
              <div class="flex items-baseline justify-between gap-2">
                <span class="text-[10px] font-bold tracking-[0.05em] uppercase text-cabin-muted">
                  OXYGEN SATURATION (SPO₂)
                </span>
                <span class="text-[10px] font-mono text-cabin-ice/80">
                  Spot oximetry · Nominal 96–100%
                </span>
              </div>
              <div class="h-12 px-3.5 rounded-[4px] bg-cabin-inset border border-cabin-card/75 focus-within:border-cabin-text flex items-center justify-between gap-2">
                <input
                  v-model.number="labsForm.spo2Pct"
                  type="number"
                  step="0.5"
                  aria-label="Blood oxygen saturation percentage"
                  class="w-full bg-transparent outline-none font-mono text-[16px] font-bold text-cabin-text"
                >
                <span class="font-mono text-[11.5px] text-cabin-muted shrink-0">%</span>
              </div>
              <span v-if="labsErrors.spo2Pct" class="text-[10px] text-cabin-crit">
                {{ labsErrors.spo2Pct }}
              </span>
            </label>
          </div>

          <div class="flex flex-col gap-3.5">
            <div
              v-if="labsSubmitError"
              class="px-4 py-3 rounded-[4px] bg-cabin-crit/18 border border-cabin-crit flex flex-col gap-1"
            >
              <span class="text-[10px] font-bold tracking-[0.05em] uppercase text-cabin-text">
                LAB ENTRY ERROR
              </span>
              <span class="text-[12px] text-cabin-ice">
                {{ labsSubmitError }}
              </span>
            </div>

            <div
              v-else
              class="px-4 py-3 rounded-[4px] border flex flex-col gap-1"
              :class="
                labsWithinNominalBounds
                  ? 'bg-cabin-inset border-cabin-card/75'
                  : 'bg-cabin-navy/45 border-cabin-navy-edge/90'
              "
            >
              <span
                class="text-[10px] font-bold tracking-[0.05em] uppercase"
                :class="labsWithinNominalBounds ? 'text-cabin-ok' : 'text-cabin-text'"
              >
                {{
                  labsWithinNominalBounds
                    ? 'RANGE VALIDATION · ALL ENTRIES WITHIN BOUNDS'
                    : 'RANGE VALIDATION · DEVIATION FROM NOMINAL STRIP TARGET'
                }}
              </span>
              <span v-if="labsResult" class="text-[12px] text-cabin-ice">
                Saved {{ labsResult.inserted_ids.length }} lab strips. Alerts triggered:
                {{ labsResult.alerts_created.length }}. Results updated in Profile -> Physical.
              </span>
              <span v-else class="text-[12px] text-cabin-ice">
                Results appear immediately in Profile -> Physical.
              </span>
            </div>

            <button
              type="submit"
              :disabled="isSavingLabs"
              class="h-[52px] w-full px-5 rounded-[5px] bg-cabin-inset hover:bg-cabin-card/45 border border-cabin-text/75 flex items-center justify-center gap-2.5 text-[13px] font-bold tracking-[0.03em] text-cabin-text cursor-pointer disabled:opacity-45 transition-colors"
            >
              <Icon name="spacescan:kit" class="w-4 h-4 text-cabin-text" />
              <span>{{ isSavingLabs ? 'Saving Clinical Lab Results...' : 'Save Clinical Lab Results' }}</span>
            </button>
          </div>
        </form>
      </ShellHudWindow>
    </div>
  </div>
</template>
