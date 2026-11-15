<script setup lang="ts">
import { physicalCaptureSchema } from '~/schemas/capture'

interface IngestionResponse {
  inserted_ids: number[]
  alerts_created: number[]
  streak: {
    logs_completed: number
    daily_compliant: boolean
  }
  recorded_at_utc: string
}

const { activeCrew, authHeaders, refreshMissionStatus } = useSession()

const form = reactive({
  missionStage: 'MISSION' as 'LAUNCH' | 'MISSION' | 'RETURN',
  restingHrBpm: 64,
  spo2Pct: 98,
  bpSystolicMmhg: 118,
  bodyTempC: 36.7,
  bodyWeightKg: 63.0,
  hydrationMl: 2500,
  exerciseMin: 85,
  caloriesKcal: 2400,
  bloodGlucoseMgDl: 92,
})

const validationErrors = ref<Record<string, string>>({})
const isSubmitting = ref(false)
const submitResult = ref<IngestionResponse | null>(null)
const submitError = ref('')

async function handleSubmit() {
  validationErrors.value = {}
  submitResult.value = null
  submitError.value = ''

  const parsed = physicalCaptureSchema.safeParse(form)
  if (!parsed.success) {
    for (const issue of parsed.error.issues) {
      const key = String(issue.path[0] ?? 'form')
      validationErrors.value[key] = issue.message
    }
    return
  }

  isSubmitting.value = true
  try {
    const crewId = activeCrew.value?.id ?? 'ID-01'
    const d = parsed.data
    const res = await $fetch<IngestionResponse>('/api/v1/measurements', {
      method: 'POST',
      headers: authHeaders(),
      body: {
        crew_id: crewId,
        mission_stage: d.missionStage,
        source_type: 'MANUAL',
        items: [
          { metric_key: 'resting_hr_bpm', value_num: d.restingHrBpm },
          { metric_key: 'spo2_pct', value_num: d.spo2Pct },
          { metric_key: 'bp_systolic_mmhg', value_num: d.bpSystolicMmhg },
          { metric_key: 'body_temp_c', value_num: d.bodyTempC },
          { metric_key: 'body_weight_kg', value_num: d.bodyWeightKg },
          { metric_key: 'hydration_ml', value_num: d.hydrationMl },
          { metric_key: 'exercise_min', value_num: d.exerciseMin },
          { metric_key: 'calories_kcal', value_num: d.caloriesKcal },
          { metric_key: 'blood_glucose_mg_dl', value_num: d.bloodGlucoseMgDl },
        ],
      },
    })
    submitResult.value = res
    await refreshMissionStatus()
  }
  catch (err: unknown) {
    const detail = (err as { data?: { detail?: string } })?.data?.detail
    submitError.value = detail || 'Unable to save clinical measurements.'
  }
  finally {
    isSubmitting.value = false
  }
}
</script>

<template>
  <ShellHudWindow
    class="flex-1"
    title="Capture · Physical & Labs"
    subtitle="Guided entry for vitals, daily habits, and point-of-care strips"
    icon="capture"
    tag-text="DATA CAPTURE"
  >
    <CaptureSubnavBar />

    <form class="grid grid-cols-1 lg:grid-cols-12 gap-4" @submit.prevent="handleSubmit">
      <div class="lg:col-span-4 p-4 rounded-[6px] bg-cabin-inset border border-cabin-card/65 flex flex-col gap-3">
        <div class="text-[11px] font-bold uppercase tracking-[0.05em] text-cabin-text">
          Vital Signs
        </div>

        <label class="flex flex-col gap-1">
          <span class="text-[10.5px] text-cabin-muted">Mission Stage</span>
          <select
            v-model="form.missionStage"
            class="h-9 px-3 rounded-[4px] bg-cabin-bg border border-cabin-card/80 text-[12px] text-cabin-text"
          >
            <option value="LAUNCH">Launch (Baseline)</option>
            <option value="MISSION">Mission (In-Flight)</option>
            <option value="RETURN">Return (Recovery)</option>
          </select>
        </label>

        <label class="flex flex-col gap-1">
          <span class="text-[10.5px] text-cabin-muted">Resting Heart Rate (bpm)</span>
          <input
            v-model.number="form.restingHrBpm"
            type="number"
            step="1"
            class="h-9 px-3 rounded-[4px] bg-cabin-bg border border-cabin-card/80 font-mono text-[12.5px] text-cabin-text"
          >
          <span v-if="validationErrors.restingHrBpm" class="text-[10px] text-cabin-crit">
            {{ validationErrors.restingHrBpm }}
          </span>
        </label>

        <label class="flex flex-col gap-1">
          <span class="text-[10.5px] text-cabin-muted">Blood Oxygen SpO2 (%)</span>
          <input
            v-model.number="form.spo2Pct"
            type="number"
            step="0.5"
            class="h-9 px-3 rounded-[4px] bg-cabin-bg border border-cabin-card/80 font-mono text-[12.5px] text-cabin-text"
          >
          <span v-if="validationErrors.spo2Pct" class="text-[10px] text-cabin-crit">
            {{ validationErrors.spo2Pct }}
          </span>
        </label>

        <label class="flex flex-col gap-1">
          <span class="text-[10.5px] text-cabin-muted">Systolic Blood Pressure (mmHg)</span>
          <input
            v-model.number="form.bpSystolicMmhg"
            type="number"
            step="1"
            class="h-9 px-3 rounded-[4px] bg-cabin-bg border border-cabin-card/80 font-mono text-[12.5px] text-cabin-text"
          >
          <span v-if="validationErrors.bpSystolicMmhg" class="text-[10px] text-cabin-crit">
            {{ validationErrors.bpSystolicMmhg }}
          </span>
        </label>

        <label class="flex flex-col gap-1">
          <span class="text-[10.5px] text-cabin-muted">Core Body Temperature (C)</span>
          <input
            v-model.number="form.bodyTempC"
            type="number"
            step="0.1"
            class="h-9 px-3 rounded-[4px] bg-cabin-bg border border-cabin-card/80 font-mono text-[12.5px] text-cabin-text"
          >
          <span v-if="validationErrors.bodyTempC" class="text-[10px] text-cabin-crit">
            {{ validationErrors.bodyTempC }}
          </span>
        </label>
      </div>

      <div class="lg:col-span-4 p-4 rounded-[6px] bg-cabin-inset border border-cabin-card/65 flex flex-col gap-3">
        <div class="text-[11px] font-bold uppercase tracking-[0.05em] text-cabin-text">
          Daily Countermeasures & Biometrics
        </div>

        <label class="flex flex-col gap-1">
          <span class="text-[10.5px] text-cabin-muted">Body Mass (kg)</span>
          <input
            v-model.number="form.bodyWeightKg"
            type="number"
            step="0.1"
            class="h-9 px-3 rounded-[4px] bg-cabin-bg border border-cabin-card/80 font-mono text-[12.5px] text-cabin-text"
          >
          <span v-if="validationErrors.bodyWeightKg" class="text-[10px] text-cabin-crit">
            {{ validationErrors.bodyWeightKg }}
          </span>
        </label>

        <label class="flex flex-col gap-1">
          <span class="text-[10.5px] text-cabin-muted">Daily Fluid Intake (mL)</span>
          <input
            v-model.number="form.hydrationMl"
            type="number"
            step="50"
            class="h-9 px-3 rounded-[4px] bg-cabin-bg border border-cabin-card/80 font-mono text-[12.5px] text-cabin-text"
          >
          <span v-if="validationErrors.hydrationMl" class="text-[10px] text-cabin-crit">
            {{ validationErrors.hydrationMl }}
          </span>
        </label>

        <label class="flex flex-col gap-1">
          <span class="text-[10.5px] text-cabin-muted">Exercise Load (min)</span>
          <input
            v-model.number="form.exerciseMin"
            type="number"
            step="5"
            class="h-9 px-3 rounded-[4px] bg-cabin-bg border border-cabin-card/80 font-mono text-[12.5px] text-cabin-text"
          >
          <span v-if="validationErrors.exerciseMin" class="text-[10px] text-cabin-crit">
            {{ validationErrors.exerciseMin }}
          </span>
        </label>

        <label class="flex flex-col gap-1">
          <span class="text-[10.5px] text-cabin-muted">Caloric Intake (kcal)</span>
          <input
            v-model.number="form.caloriesKcal"
            type="number"
            step="50"
            class="h-9 px-3 rounded-[4px] bg-cabin-bg border border-cabin-card/80 font-mono text-[12.5px] text-cabin-text"
          >
          <span v-if="validationErrors.caloriesKcal" class="text-[10px] text-cabin-crit">
            {{ validationErrors.caloriesKcal }}
          </span>
        </label>
      </div>

      <div class="lg:col-span-4 p-4 rounded-[6px] bg-cabin-inset border border-cabin-card/65 flex flex-col justify-between gap-4">
        <div class="flex flex-col gap-3">
          <div class="text-[11px] font-bold uppercase tracking-[0.05em] text-cabin-text">
            Point-of-Care Labs
          </div>

          <label class="flex flex-col gap-1">
            <span class="text-[10.5px] text-cabin-muted">Blood Glucose (mg/dL)</span>
            <input
              v-model.number="form.bloodGlucoseMgDl"
              type="number"
              step="1"
              class="h-9 px-3 rounded-[4px] bg-cabin-bg border border-cabin-card/80 font-mono text-[12.5px] text-cabin-text"
            >
            <span v-if="validationErrors.bloodGlucoseMgDl" class="text-[10px] text-cabin-crit">
              {{ validationErrors.bloodGlucoseMgDl }}
            </span>
          </label>
        </div>

        <div class="flex flex-col gap-2.5">
          <button
            type="submit"
            :disabled="isSubmitting"
            class="h-11 px-6 rounded-[6px] bg-cabin-card hover:bg-cabin-card/85 border border-cabin-text/25 text-[12px] font-bold uppercase tracking-[0.05em] text-cabin-text cursor-pointer disabled:opacity-45"
          >
            {{ isSubmitting ? 'Saving Entry...' : 'Save Physical & Lab Panel' }}
          </button>

          <p
            v-if="submitResult"
            class="px-3 py-2 rounded-[4px] bg-cabin-navy/45 border border-cabin-ok/70 text-[11px] text-cabin-text"
          >
            Saved {{ submitResult.inserted_ids.length }} metrics. Alerts triggered:
            {{ submitResult.alerts_created.length }}. Daily logs: {{ submitResult.streak.logs_completed }}.
          </p>

          <p
            v-if="submitError"
            class="px-3 py-2 rounded-[4px] bg-cabin-crit/20 border border-cabin-crit text-[11px] text-cabin-text"
          >
            {{ submitError }}
          </p>
        </div>
      </div>
    </form>
  </ShellHudWindow>
</template>
