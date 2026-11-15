<script setup lang="ts">
import type { MeasurementIngestOut, MissionStage } from '~/composables/useMeasurements'
import { buildOcularExamItems, extractErrorMessage } from '~/composables/useMeasurements'
import { ocularCaptureSchema } from '~/schemas/capture'

const { activeCrew } = useSession()
const { ingestMeasurements } = useMeasurements()

const LEFT_BASELINE_MM = 4.6
const RIGHT_BASELINE_MM = 4.7
const ALERT_THRESHOLD_MM = 5.8

const form = reactive({
  missionStage: 'MISSION' as MissionStage,
  leftOpticSheathMm: 5.5,
  rightOpticSheathMm: 5.9,
  leftIopMmhg: 15.8,
  rightIopMmhg: 16.2,
  retinalThicknessUm: 104,
  visualAcuity: '20 / 20',
})

const validationErrors = ref<Record<string, string>>({})
const isSubmitting = ref(false)
const submitResult = ref<MeasurementIngestOut | null>(null)
const submitError = ref('')

const leftExceeded = computed(() => form.leftOpticSheathMm >= ALERT_THRESHOLD_MM)
const rightExceeded = computed(() => form.rightOpticSheathMm >= ALERT_THRESHOLD_MM)
const thresholdExceeded = computed(() => leftExceeded.value || rightExceeded.value)

const thresholdHeadline = computed(() => {
  if (leftExceeded.value && rightExceeded.value) {
    const peak = Math.max(form.leftOpticSheathMm, form.rightOpticSheathMm).toFixed(1)
    return `THRESHOLD DETECTION · BILATERAL OPTIC SHEATH ${peak} MM`
  }
  if (rightExceeded.value) {
    return `THRESHOLD DETECTION · RIGHT OPTIC SHEATH ${form.rightOpticSheathMm.toFixed(1)} MM`
  }
  if (leftExceeded.value) {
    return `THRESHOLD DETECTION · LEFT OPTIC SHEATH ${form.leftOpticSheathMm.toFixed(1)} MM`
  }
  return 'THRESHOLD DETECTION · BILATERAL SHEATH WITHIN NOMINAL BOUNDS'
})

const thresholdDeltaText = computed(() => {
  if (rightExceeded.value && (!leftExceeded.value || form.rightOpticSheathMm >= form.leftOpticSheathMm)) {
    const delta = (form.rightOpticSheathMm - RIGHT_BASELINE_MM).toFixed(1)
    return `Entered value exceeds 5.8 mm alert threshold (+${delta} mm above baseline).`
  }
  if (leftExceeded.value) {
    const delta = (form.leftOpticSheathMm - LEFT_BASELINE_MM).toFixed(1)
    return `Entered value exceeds 5.8 mm alert threshold (+${delta} mm above baseline).`
  }
  return 'Both Left and Right optic nerve sheath widths remain below the 5.8 mm alert threshold.'
})

const guideSteps = [
  {
    code: '01 · GEL COUPLING',
    detail: 'Apply sterile gel over closed eyelid with zero globe pressure.',
    tone: 'ok',
  },
  {
    code: '02 · 3.0 MM DEPTH MARKER',
    detail: 'Set axial caliper 3.0 mm posterior to the retina before freezing frame.',
    tone: 'ok',
  },
  {
    code: '03 · BILATERAL VERIFICATION',
    detail: 'Record both Left and Right eyes in supine microgravity posture.',
    tone: 'ice',
  },
] as const

async function handleSubmit() {
  validationErrors.value = {}
  submitResult.value = null
  submitError.value = ''

  const parsed = ocularCaptureSchema.safeParse(form)
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
    const res = await ingestMeasurements({
      crew_id: crewId,
      mission_stage: parsed.data.missionStage,
      source_type: 'MANUAL',
      items: buildOcularExamItems(parsed.data),
    })
    submitResult.value = res
  }
  catch (err: unknown) {
    submitError.value = extractErrorMessage(err, 'Unable to save vision and ocular exam.')
  }
  finally {
    isSubmitting.value = false
  }
}
</script>

<template>
  <div class="flex flex-col gap-[18px] flex-1">
    <CaptureSubnavBar v-model:mission-stage="form.missionStage" show-stage-selector />

    <div class="grid grid-cols-1 lg:grid-cols-12 gap-[18px] flex-1">
      <ShellHudWindow
        class="lg:col-span-7"
        title="OCULAR ULTRASOUND & TONOMETRY ENTRY"
        icon="sans"
        tag-text="FEEDS VISION"
      >
        <form class="h-full flex flex-col justify-between gap-5" @submit.prevent="handleSubmit">
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-x-5 gap-y-5">
            <label class="flex flex-col gap-1.5">
              <div class="flex items-baseline justify-between gap-2">
                <span class="text-[10px] font-bold tracking-[0.05em] uppercase text-cabin-muted">
                  LEFT OPTIC NERVE SHEATH
                </span>
                <span class="text-[10px] font-mono text-cabin-ice/80">
                  Personal baseline: 4.6 mm
                </span>
              </div>
              <div
                class="h-12 px-3.5 rounded-[4px] bg-cabin-inset border flex items-center justify-between gap-2"
                :class="
                  leftExceeded
                    ? 'border-cabin-crit/85 focus-within:border-cabin-crit'
                    : 'border-cabin-card/75 focus-within:border-cabin-text'
                "
              >
                <input
                  v-model.number="form.leftOpticSheathMm"
                  type="number"
                  step="0.1"
                  aria-label="Left optic nerve sheath diameter in millimeters"
                  class="w-full bg-transparent outline-none font-mono text-[16px] font-bold text-cabin-text"
                >
                <span class="font-mono text-[11.5px] text-cabin-muted shrink-0">mm</span>
              </div>
              <span v-if="validationErrors.leftOpticSheathMm" class="text-[10px] text-cabin-crit">
                {{ validationErrors.leftOpticSheathMm }}
              </span>
            </label>

            <label class="flex flex-col gap-1.5">
              <div class="flex items-baseline justify-between gap-2">
                <span class="text-[10px] font-bold tracking-[0.05em] uppercase text-cabin-muted">
                  RIGHT OPTIC NERVE SHEATH
                </span>
                <span class="text-[10px] font-mono text-cabin-ice/80">
                  Alert threshold ≥ 5.8 mm
                </span>
              </div>
              <div
                class="h-12 px-3.5 rounded-[4px] bg-cabin-inset border flex items-center justify-between gap-2"
                :class="
                  rightExceeded
                    ? 'border-cabin-text/75 focus-within:border-cabin-crit'
                    : 'border-cabin-card/75 focus-within:border-cabin-text'
                "
              >
                <input
                  v-model.number="form.rightOpticSheathMm"
                  type="number"
                  step="0.1"
                  aria-label="Right optic nerve sheath diameter in millimeters"
                  class="w-full bg-transparent outline-none font-mono text-[16px] font-bold text-cabin-text"
                >
                <span class="font-mono text-[11.5px] text-cabin-muted shrink-0">mm</span>
              </div>
              <span v-if="validationErrors.rightOpticSheathMm" class="text-[10px] text-cabin-crit">
                {{ validationErrors.rightOpticSheathMm }}
              </span>
            </label>

            <label class="flex flex-col gap-1.5">
              <div class="flex items-baseline justify-between gap-2">
                <span class="text-[10px] font-bold tracking-[0.05em] uppercase text-cabin-muted">
                  LEFT INTRAOCULAR PRESSURE
                </span>
                <span class="text-[10px] font-mono text-cabin-ice/80">
                  Baseline: 13.0–17.0 mmHg
                </span>
              </div>
              <div class="h-12 px-3.5 rounded-[4px] bg-cabin-inset border border-cabin-card/75 focus-within:border-cabin-text flex items-center justify-between gap-2">
                <input
                  v-model.number="form.leftIopMmhg"
                  type="number"
                  step="0.1"
                  aria-label="Left intraocular pressure in mmHg"
                  class="w-full bg-transparent outline-none font-mono text-[16px] font-bold text-cabin-text"
                >
                <span class="font-mono text-[11.5px] text-cabin-muted shrink-0">mmHg</span>
              </div>
              <span v-if="validationErrors.leftIopMmhg" class="text-[10px] text-cabin-crit">
                {{ validationErrors.leftIopMmhg }}
              </span>
            </label>

            <label class="flex flex-col gap-1.5">
              <div class="flex items-baseline justify-between gap-2">
                <span class="text-[10px] font-bold tracking-[0.05em] uppercase text-cabin-muted">
                  RIGHT INTRAOCULAR PRESSURE
                </span>
                <span class="text-[10px] font-mono text-cabin-ice/80">
                  Baseline: 13.0–17.0 mmHg
                </span>
              </div>
              <div class="h-12 px-3.5 rounded-[4px] bg-cabin-inset border border-cabin-card/75 focus-within:border-cabin-text flex items-center justify-between gap-2">
                <input
                  v-model.number="form.rightIopMmhg"
                  type="number"
                  step="0.1"
                  aria-label="Right intraocular pressure in mmHg"
                  class="w-full bg-transparent outline-none font-mono text-[16px] font-bold text-cabin-text"
                >
                <span class="font-mono text-[11.5px] text-cabin-muted shrink-0">mmHg</span>
              </div>
              <span v-if="validationErrors.rightIopMmhg" class="text-[10px] text-cabin-crit">
                {{ validationErrors.rightIopMmhg }}
              </span>
            </label>

            <label class="flex flex-col gap-1.5">
              <div class="flex items-baseline justify-between gap-2">
                <span class="text-[10px] font-bold tracking-[0.05em] uppercase text-cabin-muted">
                  RETINAL LAYER THICKNESS
                </span>
                <span class="text-[10px] font-mono text-cabin-ice/80">
                  Baseline: 98–106 µm
                </span>
              </div>
              <div class="h-12 px-3.5 rounded-[4px] bg-cabin-inset border border-cabin-card/75 focus-within:border-cabin-text flex items-center justify-between gap-2">
                <input
                  v-model.number="form.retinalThicknessUm"
                  type="number"
                  step="1"
                  aria-label="Retinal layer thickness in micrometers"
                  class="w-full bg-transparent outline-none font-mono text-[16px] font-bold text-cabin-text"
                >
                <span class="font-mono text-[11.5px] text-cabin-muted shrink-0">µm</span>
              </div>
              <span v-if="validationErrors.retinalThicknessUm" class="text-[10px] text-cabin-crit">
                {{ validationErrors.retinalThicknessUm }}
              </span>
            </label>

            <label class="flex flex-col gap-1.5">
              <div class="flex items-baseline justify-between gap-2">
                <span class="text-[10px] font-bold tracking-[0.05em] uppercase text-cabin-muted">
                  VISUAL ACUITY (BOTH EYES)
                </span>
                <span class="text-[10px] font-mono text-cabin-ice/80">
                  4-meter cabin chart
                </span>
              </div>
              <div class="h-12 px-3.5 rounded-[4px] bg-cabin-inset border border-cabin-card/75 focus-within:border-cabin-text flex items-center justify-between gap-2">
                <input
                  v-model="form.visualAcuity"
                  type="text"
                  placeholder="20 / 20"
                  aria-label="Visual acuity Snellen score"
                  class="w-full bg-transparent outline-none font-mono text-[16px] font-bold text-cabin-text"
                >
                <span class="font-mono text-[11.5px] text-cabin-muted shrink-0">Snellen</span>
              </div>
              <span v-if="validationErrors.visualAcuity" class="text-[10px] text-cabin-crit">
                {{ validationErrors.visualAcuity }}
              </span>
            </label>
          </div>

          <div class="flex flex-col gap-3.5">
            <div
              v-if="submitError"
              class="relative pl-5 pr-4 py-3.5 rounded-[4px] bg-cabin-crit/20 border border-cabin-crit flex flex-col gap-1 overflow-hidden"
            >
              <span class="absolute left-0 inset-y-2 w-1 bg-cabin-crit rounded-r" />
              <span class="text-[10.5px] font-bold tracking-[0.05em] uppercase text-cabin-text">
                EXAM SUBMISSION ERROR
              </span>
              <span class="text-[12px] text-cabin-ice">
                {{ submitError }}
              </span>
            </div>

            <div
              v-else
              class="relative pl-5 pr-4 py-3.5 rounded-[4px] border flex flex-col gap-1 overflow-hidden"
              :class="
                thresholdExceeded
                  ? 'bg-cabin-crit/16 border-cabin-crit/85'
                  : 'bg-cabin-inset border-cabin-card/75'
              "
            >
              <span
                class="absolute left-0 inset-y-2.5 w-1 rounded-r"
                :class="thresholdExceeded ? 'bg-cabin-crit' : 'bg-cabin-ok'"
              />
              <span
                class="text-[10.5px] font-bold tracking-[0.05em] uppercase"
                :class="thresholdExceeded ? 'text-cabin-text' : 'text-cabin-ok'"
              >
                {{ thresholdHeadline }}
              </span>
              <span class="text-[12.5px] font-semibold text-cabin-text">
                {{ thresholdDeltaText }}
              </span>
              <span v-if="submitResult" class="text-[11.5px] text-cabin-ok">
                Saved {{ submitResult.inserted_ids.length }} ocular metrics. Alerts triggered:
                {{ submitResult.alerts_created.length }}. Daily logs: {{ submitResult.streak.logs_completed }}.
              </span>
              <span v-else class="text-[11.5px] text-cabin-ice">
                Saving updates the Vision module trend and flags a Preventive Care advisory.
              </span>
            </div>

            <button
              type="submit"
              :disabled="isSubmitting"
              class="h-[52px] w-full px-5 rounded-[5px] bg-cabin-card hover:bg-cabin-card/85 border border-cabin-text/45 flex items-center justify-center gap-2.5 text-[13px] font-bold tracking-[0.03em] text-cabin-text cursor-pointer disabled:opacity-45 transition-colors"
            >
              <Icon name="spacescan:sans" class="w-4 h-4 text-cabin-text" />
              <span>{{ isSubmitting ? 'Saving Vision & Ocular Exam...' : 'Save Vision & Ocular Exam' }}</span>
            </button>
          </div>
        </form>
      </ShellHudWindow>

      <ShellHudWindow
        class="lg:col-span-5"
        title="PROBE ALIGNMENT & MEASUREMENT GUIDE"
        icon="reticle"
        tag-text="3.0 MM AXIAL"
      >
        <div class="h-full flex flex-col justify-between gap-4">
          <div class="p-4 rounded-[5px] bg-cabin-inset border border-cabin-card/75 flex flex-col justify-between gap-2">
            <span class="text-[10px] font-bold tracking-[0.05em] uppercase text-cabin-ok">
              AXIAL CALIPER TARGET · 3.0 MM BEHIND GLOBE
            </span>

            <div class="h-44 flex items-center justify-center">
              <svg viewBox="0 0 420 180" class="w-full h-40 max-w-[420px] text-cabin-text">
                <circle
                  cx="210"
                  cy="90"
                  r="72"
                  fill="none"
                  stroke="var(--color-status-ok)"
                  stroke-opacity="0.45"
                  stroke-width="1.2"
                  stroke-dasharray="5 4"
                />
                <circle
                  cx="210"
                  cy="90"
                  r="46"
                  fill="none"
                  stroke="currentColor"
                  stroke-opacity="0.32"
                  stroke-width="1.2"
                />
                <line
                  x1="110"
                  y1="90"
                  x2="310"
                  y2="90"
                  stroke="var(--color-navy-edge)"
                  stroke-opacity="0.65"
                  stroke-width="1.2"
                />
                <line
                  x1="210"
                  y1="10"
                  x2="210"
                  y2="170"
                  stroke="var(--color-navy-edge)"
                  stroke-opacity="0.65"
                  stroke-width="1.2"
                />
                <path
                  d="M164 90 C178 60, 242 60, 256 90 C242 120, 178 120, 164 90 Z"
                  fill="none"
                  stroke="currentColor"
                  stroke-opacity="0.85"
                  stroke-width="1.6"
                />
                <circle
                  cx="210"
                  cy="90"
                  r="14"
                  fill="none"
                  stroke="var(--color-status-ok)"
                  stroke-width="1.8"
                />
                <line
                  x1="256"
                  y1="56"
                  x2="256"
                  y2="124"
                  stroke="currentColor"
                  stroke-opacity="0.55"
                  stroke-dasharray="3 3"
                  stroke-width="1.2"
                />
                <line
                  x1="292"
                  y1="52"
                  x2="292"
                  y2="128"
                  stroke="var(--color-status-ok)"
                  stroke-width="2"
                />
                <line
                  x1="256"
                  y1="62"
                  x2="292"
                  y2="62"
                  stroke="var(--color-status-ok)"
                  stroke-dasharray="3 2"
                  stroke-width="1.3"
                />
                <text
                  x="258"
                  y="54"
                  fill="var(--color-status-ok)"
                  font-size="9.5"
                  font-family="JetBrains Mono, monospace"
                >
                  3.0 mm
                </text>
              </svg>
            </div>

            <p class="text-[11px] text-center text-cabin-ice">
              Align linear probe perpendicular to closed eyelid with neutral gaze
            </p>
          </div>

          <div class="flex flex-col gap-3">
            <div
              v-for="step in guideSteps"
              :key="step.code"
              class="relative pl-5 pr-4 py-3.5 rounded-[5px] bg-cabin-inset border border-cabin-card/70 flex flex-col gap-1.5 overflow-hidden"
            >
              <span
                class="absolute left-0 inset-y-2.5 w-1 rounded-r"
                :class="step.tone === 'ok' ? 'bg-cabin-ok' : 'bg-cabin-ice'"
              />
              <span
                class="text-[10.5px] font-bold tracking-[0.05em] uppercase"
                :class="step.tone === 'ok' ? 'text-cabin-ok' : 'text-cabin-ice'"
              >
                {{ step.code }}
              </span>
              <p class="text-[12.5px] text-cabin-text">
                {{ step.detail }}
              </p>
            </div>
          </div>
        </div>
      </ShellHudWindow>
    </div>
  </div>
</template>
