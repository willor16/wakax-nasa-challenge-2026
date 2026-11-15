<script setup lang="ts">
import { ocularCaptureSchema } from '~/schemas/capture'

interface IngestionResponse {
  inserted_ids: number[]
  alerts_created: number[]
  streak: {
    logs_completed: number
  }
}

const { activeCrew, authHeaders, refreshMissionStatus } = useSession()

const form = reactive({
  missionStage: 'MISSION' as 'LAUNCH' | 'MISSION' | 'RETURN',
  leftOpticSheathMm: 4.5,
  rightOpticSheathMm: 4.6,
  leftIopMmhg: 15,
  rightIopMmhg: 16,
  retinalThicknessUm: 108,
  visualAcuity: '20/20',
})

const validationErrors = ref<Record<string, string>>({})
const isSubmitting = ref(false)
const submitResult = ref<IngestionResponse | null>(null)
const submitError = ref('')

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
    const d = parsed.data
    const ocularContext = {
      retinal_thickness_um: d.retinalThicknessUm,
      visual_acuity: d.visualAcuity,
    }
    const res = await $fetch<IngestionResponse>('/api/v1/measurements', {
      method: 'POST',
      headers: authHeaders(),
      body: {
        crew_id: crewId,
        mission_stage: d.missionStage,
        source_type: 'MANUAL',
        items: [
          { metric_key: 'optic_sheath_left_mm', value_num: d.leftOpticSheathMm, payload_json: ocularContext },
          { metric_key: 'optic_sheath_right_mm', value_num: d.rightOpticSheathMm, payload_json: ocularContext },
          { metric_key: 'iop_left_mmhg', value_num: d.leftIopMmhg },
          { metric_key: 'iop_right_mmhg', value_num: d.rightIopMmhg },
        ],
      },
    })
    submitResult.value = res
    await refreshMissionStatus()
  }
  catch (err: unknown) {
    const detail = (err as { data?: { detail?: string } })?.data?.detail
    submitError.value = detail || 'Unable to save ocular examination.'
  }
  finally {
    isSubmitting.value = false
  }
}
</script>

<template>
  <ShellHudWindow
    class="flex-1"
    title="Capture · Vision & Ocular"
    subtitle="Bilateral optic nerve sheath, intraocular pressure, and acuity log"
    icon="reticle"
    tag-text="DATA CAPTURE"
  >
    <CaptureSubnavBar />

    <form class="grid grid-cols-1 lg:grid-cols-12 gap-4" @submit.prevent="handleSubmit">
      <div class="lg:col-span-5 p-4 rounded-[6px] bg-cabin-inset border border-cabin-card/65 flex flex-col gap-3">
        <div class="text-[11px] font-bold uppercase tracking-[0.05em] text-cabin-text">
          Bilateral Optic Nerve Sheath & Tonometry
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

        <div class="grid grid-cols-2 gap-3">
          <label class="flex flex-col gap-1">
            <span class="text-[10.5px] text-cabin-muted">Left ONSD (mm)</span>
            <input
              v-model.number="form.leftOpticSheathMm"
              type="number"
              step="0.1"
              class="h-9 px-3 rounded-[4px] bg-cabin-bg border border-cabin-card/80 font-mono text-[12.5px] text-cabin-text"
            >
            <span v-if="validationErrors.leftOpticSheathMm" class="text-[10px] text-cabin-crit">
              {{ validationErrors.leftOpticSheathMm }}
            </span>
          </label>

          <label class="flex flex-col gap-1">
            <span class="text-[10.5px] text-cabin-muted">Right ONSD (mm)</span>
            <input
              v-model.number="form.rightOpticSheathMm"
              type="number"
              step="0.1"
              class="h-9 px-3 rounded-[4px] bg-cabin-bg border border-cabin-card/80 font-mono text-[12.5px] text-cabin-text"
            >
            <span v-if="validationErrors.rightOpticSheathMm" class="text-[10px] text-cabin-crit">
              {{ validationErrors.rightOpticSheathMm }}
            </span>
          </label>

          <label class="flex flex-col gap-1">
            <span class="text-[10.5px] text-cabin-muted">Left IOP (mmHg)</span>
            <input
              v-model.number="form.leftIopMmhg"
              type="number"
              step="0.5"
              class="h-9 px-3 rounded-[4px] bg-cabin-bg border border-cabin-card/80 font-mono text-[12.5px] text-cabin-text"
            >
            <span v-if="validationErrors.leftIopMmhg" class="text-[10px] text-cabin-crit">
              {{ validationErrors.leftIopMmhg }}
            </span>
          </label>

          <label class="flex flex-col gap-1">
            <span class="text-[10.5px] text-cabin-muted">Right IOP (mmHg)</span>
            <input
              v-model.number="form.rightIopMmhg"
              type="number"
              step="0.5"
              class="h-9 px-3 rounded-[4px] bg-cabin-bg border border-cabin-card/80 font-mono text-[12.5px] text-cabin-text"
            >
            <span v-if="validationErrors.rightIopMmhg" class="text-[10px] text-cabin-crit">
              {{ validationErrors.rightIopMmhg }}
            </span>
          </label>
        </div>

        <div class="grid grid-cols-2 gap-3">
          <label class="flex flex-col gap-1">
            <span class="text-[10.5px] text-cabin-muted">Retinal Thickness (um)</span>
            <input
              v-model.number="form.retinalThicknessUm"
              type="number"
              step="1"
              class="h-9 px-3 rounded-[4px] bg-cabin-bg border border-cabin-card/80 font-mono text-[12.5px] text-cabin-text"
            >
            <span v-if="validationErrors.retinalThicknessUm" class="text-[10px] text-cabin-crit">
              {{ validationErrors.retinalThicknessUm }}
            </span>
          </label>

          <label class="flex flex-col gap-1">
            <span class="text-[10.5px] text-cabin-muted">Visual Acuity (Snellen)</span>
            <input
              v-model="form.visualAcuity"
              type="text"
              placeholder="20/20"
              class="h-9 px-3 rounded-[4px] bg-cabin-bg border border-cabin-card/80 font-mono text-[12.5px] text-cabin-text"
            >
            <span v-if="validationErrors.visualAcuity" class="text-[10px] text-cabin-crit">
              {{ validationErrors.visualAcuity }}
            </span>
          </label>
        </div>
      </div>

      <div class="lg:col-span-7 p-4 rounded-[6px] bg-cabin-inset border border-cabin-card/65 flex flex-col justify-between gap-4">
        <div class="flex items-center justify-between">
          <div>
            <div class="text-[11px] font-bold uppercase tracking-[0.05em] text-cabin-text">
              3.0 mm Axial Ultrasound Alignment Guide
            </div>
            <p class="text-[11px] text-cabin-muted">
              Position caliper 3.0 mm posterior to the retina globe boundary before recording width.
            </p>
          </div>
          <span class="font-mono text-[11px] px-2.5 py-1 rounded-full bg-cabin-navy/45 border border-cabin-navy-edge/80 text-cabin-text">
            AXIAL 3.0 MM
          </span>
        </div>

        <div class="h-44 rounded-[6px] bg-cabin-bg/85 border border-cabin-card/55 flex items-center justify-center">
          <svg viewBox="0 0 360 140" class="w-full h-36 max-w-[360px] text-cabin-text">
            <circle cx="110" cy="70" r="46" fill="none" stroke="currentColor" stroke-opacity="0.7" stroke-width="1.6" />
            <path d="M156 54 L310 50 M156 86 L310 90" stroke="currentColor" stroke-opacity="0.55" stroke-width="1.5" />
            <line x1="156" y1="20" x2="156" y2="120" stroke="var(--color-navy-edge)" stroke-dasharray="4 3" stroke-width="1.4" />
            <line x1="216" y1="26" x2="216" y2="114" stroke="var(--color-status-ok)" stroke-width="2" />
            <line x1="156" y1="70" x2="216" y2="70" stroke="var(--color-status-ok)" stroke-dasharray="3 3" stroke-width="1.4" />
            <text x="166" y="64" fill="var(--color-status-ok)" font-size="10" font-family="JetBrains Mono, monospace">3.0 mm</text>
            <text x="224" y="42" fill="currentColor" font-size="10" font-family="JetBrains Mono, monospace">ONSD</text>
          </svg>
        </div>

        <div class="flex flex-col gap-2.5">
          <button
            type="submit"
            :disabled="isSubmitting"
            class="h-11 px-6 rounded-[6px] bg-cabin-card hover:bg-cabin-card/85 border border-cabin-text/25 text-[12px] font-bold uppercase tracking-[0.05em] text-cabin-text cursor-pointer disabled:opacity-45"
          >
            {{ isSubmitting ? 'Saving Examination...' : 'Save Ocular Examination' }}
          </button>

          <p
            v-if="submitResult"
            class="px-3 py-2 rounded-[4px] bg-cabin-navy/45 border border-cabin-ok/70 text-[11px] text-cabin-text"
          >
            Saved {{ submitResult.inserted_ids.length }} ocular metrics. Alerts triggered:
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
