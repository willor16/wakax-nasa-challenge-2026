<script setup lang="ts">
// 12 · Data Capture · Vision & Ocular Exam.
import brainUrl from '~/assets/hologram/brain.svg'
import { apiErrorMessage } from '~/composables/useApi'
import { toNumber } from '~/composables/useCatalog'

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

const alertMm = computed(() => catalog.value.optic_sheath_right_mm?.critical_threshold ?? null)
const watchMm = computed(() => catalog.value.optic_sheath_right_mm?.nominal_max ?? null)

/** Live check of the sheath values typed so far against the alert threshold and baseline. */
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
    return { tone: 'critical' as const, title: `Threshold detection · ${worst.side} optic sheath ${worst.value!.toFixed(1)} mm`,
      text: `Exceeds the ${alertMm.value} mm alert threshold${deltaText}. Saving flags a Preventive Care advisory.` }
  }
  if (watchMm.value !== null && worst.value! > watchMm.value) {
    return { tone: 'critical' as const, title: `Above usual range · ${worst.side} optic sheath ${worst.value!.toFixed(1)} mm`,
      text: `Over the ${watchMm.value} mm usual limit${deltaText}. Saving adds it to the Vision trend.` }
  }
  return { tone: 'ok' as const, title: 'Threshold detection · Within usual range',
    text: `Both values stay under ${watchMm.value} mm${deltaText}. Saving updates the Vision trend.` }
})

async function save() {
  result.value = null
  const found: Record<string, string> = {}
  const items: { metric_key: string, value_num: number }[] = []
  const fields: [keyof typeof form, string, string][] = [
    ['leftSheath', 'optic_sheath_left_mm', 'Left optic nerve sheath'],
    ['rightSheath', 'optic_sheath_right_mm', 'Right optic nerve sheath'],
    ['leftIop', 'iop_left_mmhg', 'Left intraocular pressure'],
    ['rightIop', 'iop_right_mmhg', 'Right intraocular pressure'],
    ['retina', 'retinal_thickness_um', 'Retinal layer thickness'],
  ]
  for (const [field, key, label] of fields) {
    const parsed = numberRule(key, label).safeParse(toNumber(form[field]))
    if (parsed.success) items.push({ metric_key: key, value_num: parsed.data })
    else found[field] = parsed.error.issues[0]!.message
  }
  if (form.acuity.trim()) {
    const match = form.acuity.replace(/\s/g, '').match(/^20\/(\d{1,3})$/)
    if (match) items.push({ metric_key: 'visual_acuity_snellen', value_num: Number(match[1]) })
    else found.acuity = 'Visual acuity: use the 20/20 format'
  }
  errors.value = found
  if (Object.keys(found).length) return
  busy.value = true
  try {
    const saved = await api<{ alerts_created: number[] }>('/measurements', { method: 'POST', body: { items } })
    unread.value += saved.alerts_created.length
    result.value = saved.alerts_created.length
      ? { tone: 'critical', title: `Exam saved · ${saved.alerts_created.length} advisory raised`, text: 'The physician will review it. See Vision for the updated trend.' }
      : { tone: 'ok', title: 'Exam saved · Both eyes recorded', text: 'The Vision screen now shows this exam.' }
    Object.assign(form, { leftSheath: '', rightSheath: '', leftIop: '', rightIop: '', retina: '', acuity: '' })
  }
  catch (error) {
    errors.value = { form: apiErrorMessage(error) }
  }
  finally {
    busy.value = false
  }
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
      <ShellHudWindow class="w-[54.6%] shrink-0" title="Ocular Ultrasound & Tonometry Entry" icon="sans" tag-text="FEEDS VISION" flush>
        <form class="flex-1 min-h-0 flex flex-col px-[23px] pt-[clamp(14px,3dvh,28px)] pb-[clamp(12px,2.1dvh,20px)]" novalidate @submit.prevent="save">
          <div class="grid grid-cols-2 gap-x-[19px] gap-y-[clamp(14px,4dvh,38px)]">
            <UiNumberField id="left-sheath" v-model="form.leftSheath" help-key="optic_sheath_left_mm" label="Left Optic Nerve Sheath" :hint="baselineHint('optic_sheath_left_mm').replace('Baseline', 'Personal baseline')" unit="mm" placeholder="e.g. 5.5" :error="errors.leftSheath" />
            <UiNumberField id="right-sheath" v-model="form.rightSheath" help-key="optic_sheath_right_mm" label="Right Optic Nerve Sheath" :hint="alertMm ? `Alert threshold ≥ ${alertMm} mm` : ''" unit="mm" placeholder="e.g. 5.9" :error="errors.rightSheath" />
            <UiNumberField id="left-iop" v-model="form.leftIop" help-key="iop_left_mmhg" label="Left Intraocular Pressure" :hint="baselineHint('iop_left_mmhg', 1, true)" unit="mmHg" placeholder="e.g. 15.8" :error="errors.leftIop" />
            <UiNumberField id="right-iop" v-model="form.rightIop" help-key="iop_right_mmhg" label="Right Intraocular Pressure" :hint="baselineHint('iop_right_mmhg', 1, true)" unit="mmHg" placeholder="e.g. 16.2" :error="errors.rightIop" />
            <UiNumberField id="retina" v-model="form.retina" help-key="retinal_thickness_um" label="Retinal Layer Thickness" :hint="baselineHint('retinal_thickness_um', 0, true)" unit="µm" placeholder="e.g. 104" inputmode="numeric" :error="errors.retina" />
            <UiNumberField id="acuity" v-model="form.acuity" help-key="visual_acuity_snellen" label="Visual Acuity (Both Eyes)" hint="4-meter cabin chart" unit="Snellen" placeholder="20 / 20" inputmode="text" :error="errors.acuity" />
          </div>
          <div class="mt-auto pt-[10px] flex flex-col gap-[clamp(10px,1.7dvh,16px)]">
            <UiSaveResult v-if="result" :tone="result.tone" :title="result.title" :text="result.text" />
            <UiSaveResult v-else-if="errors.form" tone="critical" title="Not saved" :text="errors.form" />
            <UiSaveResult v-else-if="detection" :tone="detection.tone" :title="detection.title" :text="detection.text" />
            <UiSaveResult v-else tone="info" title="Threshold detection" text="Enter both optic nerve sheath values to compare them with your baseline." />
            <button type="submit" class="hud-button relative" :disabled="busy">
              <Icon name="spacescan:sans" class="w-[18px] h-[18px] absolute left-[22px]" />
              {{ busy ? 'Saving…' : 'Save Vision & Ocular Exam' }}
            </button>
          </div>
        </form>
      </ShellHudWindow>

      <ShellHudWindow class="flex-1 min-w-0" title="Probe Alignment & Measurement Guide" icon="reticle" tag-text="3.0 MM AXIAL" flush>
        <div class="flex-1 min-h-0 flex flex-col px-[19px] pt-[clamp(10px,1.9dvh,18px)] pb-[clamp(12px,2.1dvh,20px)] gap-[clamp(10px,1.9dvh,18px)]">
          <div class="tile-hi relative h-[clamp(190px,21.5dvh,230px)] shrink-0">
            <UiAiWatermark position="top-right" />
            <p class="absolute top-[18px] left-[16px] text-[10px] font-bold tracking-[0.04em] uppercase text-cabin-ok">Axial caliper target · 3.0 mm behind globe</p>
            <div class="absolute left-1/2 top-[30px] -translate-x-1/2 w-[160px] h-[160px]">
              <span class="absolute inset-0 rounded-full border-[1.3px] border-dashed border-cabin-ok/60" />
              <span class="absolute left-1/2 top-[-10px] bottom-[-10px] w-px bg-cabin-navy-edge" />
              <span class="absolute top-1/2 left-[-40px] right-[-40px] h-px bg-cabin-navy-edge" />
              <span class="absolute inset-[30px] rounded-full border border-cabin-text/30" />
              <img :src="brainUrl" alt="" class="absolute inset-[32px] w-[96px] h-[96px]">
            </div>
            <p class="absolute bottom-[14px] left-0 right-0 text-center text-[11.5px]">Align linear probe perpendicular to closed eyelid with neutral gaze</p>
          </div>
          <div v-for="(step, index) in steps" :key="step.title" class="tile relative flex-1 min-h-0 pl-[22px] pr-[18px] flex flex-col justify-center">
            <span class="absolute left-0 top-[12px] bottom-[12px] w-[3px] rounded-full" :class="index < 2 ? 'bg-cabin-ok' : 'bg-cabin-navy-edge'" />
            <p class="text-[10.5px] font-bold tracking-[0.03em] uppercase" :class="index < 2 ? 'text-cabin-ok' : ''">0{{ index + 1 }} · {{ step.title }}</p>
            <p class="text-[12.5px] mt-[clamp(6px,1.5dvh,14px)]">{{ step.text }}</p>
          </div>
        </div>
      </ShellHudWindow>
    </div>
  </div>
</template>
