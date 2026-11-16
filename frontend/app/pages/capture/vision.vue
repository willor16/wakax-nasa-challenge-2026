<script setup lang="ts">
import SandraVisualBatteryModal from '~/components/vision/SandraVisualBatteryModal.vue'
import brainUrl from '~/assets/hologram/brain.svg'
import { apiErrorMessage } from '~/composables/useApi'
import { toNumber } from '~/composables/useCatalog'
import {
  buildSandraPayload,
  computeAmslerEyeSummary,
  computeConsolidatedSANS,
  countAnsweredSymptoms,
  EXAM_MILESTONES,
  hasAnySandraData,
  worstSnellenDenominator,
} from '~/utils/sandraVisualBattery'

usePageHeader({ title: 'Data Capture · Vision & Ocular Exam', status: { text: 'Ultrasound ready', tone: 'ok' } })
const { api } = useApi()
const { unread } = useMission()
const { load, numberRule, baselineHint, catalog, baselines } = useCatalog()
const loadError = ref<string | null>(null)
onMounted(() => load().catch((error) => { loadError.value = apiErrorMessage(error) }))

const form = reactive({ leftSheath: '', rightSheath: '', leftIop: '', rightIop: '', retina: '', acuity: '' })
const errors = ref<Record<string, string>>({})
const result = ref<{ tone: 'ok' | 'critical', title: string, text: string } | null>(null)
const busy = ref(false)
const batteryExpanded = ref(false)

const { session: sandraSession, resetBattery } = useSandraBattery()

const alertMm = computed(() => catalog.value.optic_sheath_right_mm?.critical_threshold ?? null)
const watchMm = computed(() => catalog.value.optic_sheath_right_mm?.nominal_max ?? null)

const batteryHasData = computed(() => hasAnySandraData(sandraSession.value))
const odAmsler = computed(() => computeAmslerEyeSummary(sandraSession.value.amslerGrid.OD, sandraSession.value.amslerAnswers.OD))
const osAmsler = computed(() => computeAmslerEyeSummary(sandraSession.value.amslerGrid.OS, sandraSession.value.amslerAnswers.OS))
const answeredSymptoms = computed(() => countAnsweredSymptoms(sandraSession.value.symptoms))
const batteryTriage = computed(() => computeConsolidatedSANS(sandraSession.value))

watch(() => sandraSession.value.acuity, (acuityMap) => {
  if (acuityMap.OD || acuityMap.OS || acuityMap.OU) {
    const worstDenom = worstSnellenDenominator(acuityMap)
    form.acuity = `20/${worstDenom}`
  }
}, { deep: true })

const detection = computed(() => {
  const entries = (['left', 'right'] as const).map((side) => {
    const value = toNumber(side === 'left' ? form.leftSheath : form.rightSheath)
    const base = baselines.value[`optic_sheath_${side}_mm`]?.mean_val
    return { side, value: value !== undefined && !Number.isNaN(value) ? value : null, base }
  }).filter(entry => entry.value !== null)
  if (!entries.length || alertMm.value === null) return null
  const worst = entries.reduce((a, b) => (b.value! > a.value! ? b : a))
  const delta = worst.base !== undefined ? worst.value! - worst.base : null
  const deltaText = delta === null ? '' : ` (${delta >= 0 ? '+' : ''}${delta.toFixed(1)} mm against baseline)`
  if (worst.value! >= alertMm.value) {
    return {
      tone: 'critical' as const,
      title: `Threshold detection · ${worst.side} optic sheath ${worst.value!.toFixed(1)} mm`,
      text: `Exceeds the ${alertMm.value} mm alert threshold${deltaText}. Saving flags a Preventive Care advisory.`,
    }
  }
  if (watchMm.value !== null && worst.value! > watchMm.value) {
    return {
      tone: 'critical' as const,
      title: `Above usual range · ${worst.side} optic sheath ${worst.value!.toFixed(1)} mm`,
      text: `Over the ${watchMm.value} mm usual limit${deltaText}. Saving adds it to the Vision trend.`,
    }
  }
  return {
    tone: 'ok' as const,
    title: 'Threshold detection · Within usual range',
    text: `Both values stay under ${watchMm.value} mm${deltaText}. Saving updates the Vision trend.`,
  }
})

async function save() {
  result.value = null
  const found: Record<string, string> = {}
  const items: { metric_key: string, value_num: number, payload_json?: Record<string, unknown> }[] = []
  const fields: [keyof typeof form, string, string][] = [
    ['leftSheath', 'optic_sheath_left_mm', 'Left optic nerve sheath'],
    ['rightSheath', 'optic_sheath_right_mm', 'Right optic nerve sheath'],
    ['leftIop', 'iop_left_mmhg', 'Left intraocular pressure'],
    ['rightIop', 'iop_right_mmhg', 'Right intraocular pressure'],
    ['retina', 'retinal_thickness_um', 'Retinal layer thickness'],
  ]
  const hasAnyInstrument = fields.some(([field]) => Boolean(form[field].trim()))
  const requireAllInstruments = !batteryHasData.value || hasAnyInstrument

  if (requireAllInstruments) {
    for (const [field, key, label] of fields) {
      if (batteryHasData.value && !form[field].trim()) continue
      const parsed = numberRule(key, label).safeParse(toNumber(form[field]))
      if (parsed.success) items.push({ metric_key: key, value_num: parsed.data })
      else found[field] = parsed.error.issues[0]!.message
    }
  }

  let acuityDenom: number | null = null
  if (form.acuity.trim()) {
    const match = form.acuity.replace(/\s/g, '').match(/^20\/(\d{1,3})$/)
    if (match) acuityDenom = Number(match[1])
    else found.acuity = 'Visual acuity: use the 20/20 format'
  }
  else if (batteryHasData.value) {
    acuityDenom = worstSnellenDenominator(sandraSession.value.acuity)
  }

  if (acuityDenom !== null) {
    const item: { metric_key: string, value_num: number, payload_json?: Record<string, unknown> } = {
      metric_key: 'visual_acuity_snellen',
      value_num: acuityDenom,
    }
    if (batteryHasData.value) item.payload_json = buildSandraPayload(sandraSession.value)
    items.push(item)
  }

  if (!items.length && !Object.keys(found).length) {
    found.form = 'Enter ultrasound values or complete at least one module in the Interactive Visual Battery.'
  }

  errors.value = found
  if (Object.keys(found).length) return
  busy.value = true
  try {
    const saved = await api<{ alerts_created: number[] }>('/measurements', { method: 'POST', body: { items } })
    unread.value += saved.alerts_created.length
    result.value = saved.alerts_created.length
      ? {
          tone: 'critical',
          title: `Exam saved · ${saved.alerts_created.length} advisory raised`,
          text: 'The physician will review this exam. Open Vision to inspect the updated evaluation.',
        }
      : {
          tone: 'ok',
          title: 'Exam saved · Ocular record updated',
          text: 'The Vision screen now shows your recorded measurements and visual battery.',
        }
    Object.assign(form, { leftSheath: '', rightSheath: '', leftIop: '', rightIop: '', retina: '', acuity: '' })
    resetBattery()
    batteryExpanded.value = false
  }
  catch (error) {
    errors.value = { form: apiErrorMessage(error) }
  }
  finally {
    busy.value = false
  }
}

async function saveFromModal() {
  if (!batteryHasData.value) {
    sandraSession.value.symptoms.q1_1_near.experienced = false
  }
  await save()
}

const steps = [
  { title: 'Gel Coupling', text: 'Apply sterile gel over the closed eyelid with zero pressure on the globe.' },
  { title: '3.0 mm Depth Marker', text: 'Set the axial caliper 3.0 mm behind the retina before freezing the frame.' },
  { title: 'Bilateral Verification', text: 'Record both left and right eyes in the same resting posture.' },
]
</script>

<template>
  <div class="page">
    <ShellCaptureTabs />
    <UiStateNote v-if="loadError" :error="loadError" @retry="() => reloadNuxtApp()" />
    <div v-else class="flex-1 min-h-0 flex gap-[18px]">
      <ShellHudWindow class="w-[54.6%] shrink-0" title="Ocular Ultrasound &amp; Visual Battery Entry" icon="sans" tag-text="FEEDS VISION" flush>
        <form class="flex-1 min-h-0 flex flex-col px-[23px] pt-[clamp(14px,2.5dvh,24px)] pb-[clamp(12px,2.1dvh,20px)]" novalidate @submit.prevent="save">
          <div class="grid grid-cols-2 gap-x-[19px] gap-y-[clamp(12px,3.2dvh,30px)]">
            <UiNumberField id="left-sheath" v-model="form.leftSheath" help-key="optic_sheath_left_mm" label="Left Optic Nerve Sheath" :hint="baselineHint('optic_sheath_left_mm').replace('Baseline', 'Personal baseline')" unit="mm" placeholder="e.g. 5.5" :error="errors.leftSheath" />
            <UiNumberField id="right-sheath" v-model="form.rightSheath" help-key="optic_sheath_right_mm" label="Right Optic Nerve Sheath" :hint="alertMm ? `Alert threshold ≥ ${alertMm} mm` : ''" unit="mm" placeholder="e.g. 5.9" :error="errors.rightSheath" />
            <UiNumberField id="left-iop" v-model="form.leftIop" help-key="iop_left_mmhg" label="Left Intraocular Pressure" :hint="baselineHint('iop_left_mmhg', 1, true)" unit="mmHg" placeholder="e.g. 15.8" :error="errors.leftIop" />
            <UiNumberField id="right-iop" v-model="form.rightIop" help-key="iop_right_mmhg" label="Right Intraocular Pressure" :hint="baselineHint('iop_right_mmhg', 1, true)" unit="mmHg" placeholder="e.g. 16.2" :error="errors.rightIop" />
            <UiNumberField id="retina" v-model="form.retina" help-key="retinal_thickness_um" label="Retinal Layer Thickness" :hint="baselineHint('retinal_thickness_um', 0, true)" unit="µm" placeholder="e.g. 104" inputmode="numeric" :error="errors.retina" />
            <UiNumberField id="acuity" v-model="form.acuity" help-key="visual_acuity_snellen" label="Visual Acuity (Auto or Manual)" hint="Populated from Landolt C or 4m chart" unit="Snellen" placeholder="20 / 20" inputmode="text" :error="errors.acuity" />
          </div>
          <div class="mt-auto pt-[10px] flex flex-col gap-[clamp(8px,1.5dvh,14px)]">
            <UiSaveResult v-if="result" :tone="result.tone" :title="result.title" :text="result.text" />
            <UiSaveResult v-else-if="errors.form" tone="critical" title="Not saved" :text="errors.form" />
            <UiSaveResult v-else-if="detection" :tone="detection.tone" :title="detection.title" :text="detection.text" />
            <UiSaveResult
              v-else-if="batteryHasData"
              :tone="batteryTriage.statusClass === 'critica' ? 'critical' : 'ok'"
              :title="`Visual Battery Ready · ${sandraSession.milestone}`"
              :text="`${batteryTriage.level} (Risk ${batteryTriage.score}/100). Save directly or pair with ultrasound values.`"
            />
            <UiSaveResult v-else tone="info" title="Threshold detection" text="Enter optic sheath values or launch the Interactive Visual Battery on the right." />
            <button type="submit" class="hud-button relative" :disabled="busy">
              <Icon name="spacescan:sans" class="w-[18px] h-[18px] absolute left-[22px]" />
              {{ busy ? 'Saving…' : 'Save Vision & Ocular Exam' }}
            </button>
          </div>
        </form>
      </ShellHudWindow>

      <ShellHudWindow class="flex-1 min-w-0" title="Interactive Visual Battery &amp; Probe Guide" icon="reticle" tag-text="SANS BATTERY" flush>
        <div class="flex-1 min-h-0 flex flex-col px-[19px] pt-[clamp(10px,1.6dvh,16px)] pb-[clamp(12px,1.8dvh,18px)] gap-[clamp(10px,1.5dvh,14px)] hud-scroll">
          <div class="tile-hi p-[14px] flex flex-col gap-[10px] shrink-0">
            <div class="flex items-center justify-between gap-[8px]">
              <div>
                <p class="text-[10px] font-bold tracking-[0.04em] uppercase text-cabin-ok">
                  In-Cabin Functional Assessment · Same Window
                </p>
                <p class="text-[14px] font-bold mt-[2px]">
                  Landolt C Acuity · 20×20 Amsler · SANS Symptoms
                </p>
              </div>
              <UiStatusPill :tone="batteryTriage.statusClass === 'critica' ? 'critical' : batteryTriage.statusClass === 'warn' ? 'watch' : 'ok'">
                {{ batteryTriage.triageLevel }}
              </UiStatusPill>
            </div>

            <div class="flex flex-wrap gap-[4px]">
              <button
                v-for="m in EXAM_MILESTONES"
                :key="m"
                type="button"
                class="focus-ring px-[8px] py-[3px] rounded-[3px] mono text-[10px] border transition"
                :class="sandraSession.milestone === m ? 'menu-item-active text-cabin-text' : 'border-cabin-line text-cabin-ice hover:text-cabin-text'"
                @click="sandraSession.milestone = m"
              >
                {{ m }}
              </button>
            </div>

            <div class="grid grid-cols-3 gap-[8px] text-[11px]">
              <div class="tile px-[10px] py-[8px]">
                <p class="label-caps">1 · Acuity</p>
                <p class="mono font-bold mt-[4px] text-cabin-text">
                  OD {{ sandraSession.acuity.OD?.snellen ?? '—' }} · OS {{ sandraSession.acuity.OS?.snellen ?? '—' }}
                </p>
              </div>
              <div class="tile px-[10px] py-[8px]">
                <p class="label-caps">2 · Amsler</p>
                <p class="mono font-bold mt-[4px]" :class="odAmsler.totalCells + osAmsler.totalCells > 0 ? 'text-cabin-crit' : 'text-cabin-ok'">
                  OD {{ odAmsler.totalCells }} · OS {{ osAmsler.totalCells }} cells
                </p>
              </div>
              <div class="tile px-[10px] py-[8px]">
                <p class="label-caps">3 · Symptoms</p>
                <p class="mono font-bold mt-[4px] text-cabin-text">
                  {{ answeredSymptoms }} / 13 answered
                </p>
              </div>
            </div>

            <div class="flex gap-[8px]">
              <button type="button" class="hud-button !h-[44px]" @click="batteryExpanded = true">
                <Icon name="spacescan:reticle" class="w-[16px] h-[16px]" />
                {{ batteryHasData ? 'Expand &amp; Resume Visual Battery' : 'Launch Fullscreen Visual Battery' }}
              </button>
            </div>
          </div>

          <div class="tile relative h-[clamp(140px,16dvh,170px)] shrink-0">
            <UiAiWatermark position="top-right" />
            <p class="absolute top-[12px] left-[14px] text-[10px] font-bold tracking-[0.04em] uppercase text-cabin-ok">
              Axial caliper target · 3.0 mm behind globe
            </p>
            <div class="absolute left-1/2 top-[28px] -translate-x-1/2 w-[112px] h-[112px]">
              <span class="absolute inset-0 rounded-full border-[1.3px] border-dashed border-cabin-ok/60" />
              <span class="absolute left-1/2 top-[-6px] bottom-[-6px] w-px bg-cabin-navy-edge" />
              <span class="absolute top-1/2 left-[-28px] right-[-28px] h-px bg-cabin-navy-edge" />
              <span class="absolute inset-[20px] rounded-full border border-cabin-text/30" />
              <img :src="brainUrl" alt="" class="absolute inset-[22px] w-[68px] h-[68px]">
            </div>
            <p class="absolute bottom-[10px] left-0 right-0 text-center text-[11px] text-cabin-ice">
              Align linear probe perpendicular to closed eyelid with neutral gaze
            </p>
          </div>

          <div class="grid grid-cols-3 gap-[8px] shrink-0">
            <div v-for="(step, index) in steps" :key="step.title" class="tile relative p-[10px] pl-[14px]">
              <span class="absolute left-0 top-[8px] bottom-[8px] w-[3px] rounded-full" :class="index < 2 ? 'bg-cabin-ok' : 'bg-cabin-navy-edge'" />
              <p class="text-[9.5px] font-bold tracking-[0.03em] uppercase" :class="index < 2 ? 'text-cabin-ok' : ''">0{{ index + 1 }} · {{ step.title }}</p>
              <p class="text-[11px] text-cabin-ice mt-[4px] leading-[1.35]">{{ step.text }}</p>
            </div>
          </div>
        </div>
      </ShellHudWindow>
    </div>

    <SandraVisualBatteryModal
      :expanded="batteryExpanded"
      :saving="busy"
      @minimize="batteryExpanded = false"
      @exit="batteryExpanded = false"
      @reset="resetBattery"
      @save-now="saveFromModal"
    />
  </div>
</template>
