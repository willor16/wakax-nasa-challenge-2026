<script setup lang="ts">
// 10 · Data Capture · Auscultation Audio: 30-second heart and lung recordings.
import VChart from 'vue-echarts'
import { apiErrorMessage } from '~/composables/useApi'
import { envelopeOption } from '~/utils/charts'
import { RECORD_SECONDS } from '~/utils/audio'

const { api } = useApi()
const { cabin } = useMission()
const noise = computed(() => cabin.value?.noise_dba ?? null)
const noiseLimit = computed(() => cabin.value?.limits.noise_dba_max ?? 55)
const tooLoud = computed(() => noise.value !== null && noise.value >= noiseLimit.value)

usePageHeader(() => ({
  title: 'Data Capture · Auscultation Audio',
  status: noise.value === null
    ? { text: 'Cabin noise unknown', tone: 'neutral' }
    : { text: `${tooLoud.value ? 'Cabin too loud' : 'Cabin quiet'} · ${Math.round(noise.value)} dBA`, tone: tooLoud.value ? 'critical' : 'ok' },
}))

const CARDIAC = [
  { id: 'aortic', label: 'Aortic · 2nd R', pickup: 'Aortic (2nd right intercostal space)' },
  { id: 'pulmonic', label: 'Pulmonic · 2nd L', pickup: 'Pulmonic (2nd left intercostal space)' },
  { id: 'tricuspid', label: 'Tricuspid · 4th L', pickup: 'Tricuspid (4th left intercostal space)' },
  { id: 'mitral', label: 'Mitral Apex', pickup: 'Mitral apex (5th intercostal space)' },
] as const
const PULMONARY = [
  { id: 'upper_left', label: 'Upper Left', pickup: 'Upper left anterior zone' },
  { id: 'upper_right', label: 'Upper Right', pickup: 'Upper right anterior zone' },
  { id: 'lower_left', label: 'Lower Left', pickup: 'Lower left posterior zone' },
  { id: 'lower_right', label: 'Lower Right', pickup: 'Lower right posterior zone' },
] as const

const progress = ref<{ CARDIAC: string[], PULMONARY: string[] }>({ CARDIAC: [], PULMONARY: [] })
async function loadProgress() {
  try {
    progress.value = await api('/auscultation/progress')
  }
  catch {
    // Progress is informative only; recording still works without it.
  }
}
onMounted(loadProgress)

interface Panel {
  organ: 'CARDIAC' | 'PULMONARY'
  sites: typeof CARDIAC | typeof PULMONARY
  site: Ref<string>
  recorder: ReturnType<typeof useAuscultationRecorder>
  result: Ref<null | { rate_per_min: number | null, rhythm_label: string, signal_quality_pct: number, regularity_pct: number }>
  error: Ref<string | null>
}
function panel(organ: 'CARDIAC' | 'PULMONARY', sites: typeof CARDIAC | typeof PULMONARY): Panel {
  return { organ, sites, site: ref(sites[3]!.id), recorder: useAuscultationRecorder(organ), result: ref(null), error: ref(null) }
}
const panels = [panel('CARDIAC', CARDIAC), panel('PULMONARY', PULMONARY)]

function pickSite(p: Panel, id: string) {
  if (p.recorder.state.value === 'recording' || p.recorder.state.value === 'starting') return
  p.site.value = id
  p.result.value = null
  p.error.value = null
}
async function toggle(p: Panel) {
  p.error.value = null
  p.result.value = null
  if (p.recorder.state.value === 'recording' || p.recorder.state.value === 'starting') await p.recorder.stop()
  else await p.recorder.start()
}
async function save(p: Panel) {
  const take = p.recorder.captured.value
  if (!take || noise.value === null) return
  p.recorder.state.value = 'saving'
  p.error.value = null
  const form = new FormData()
  form.append('organ_type', p.organ)
  form.append('anatomical_site', p.site.value)
  form.append('cabin_noise_dba', String(noise.value))
  form.append('sha256_hex', take.sha256)
  form.append('audio_file', new Blob([take.wav], { type: 'audio/wav' }), `${p.organ.toLowerCase()}-${p.site.value}.wav`)
  try {
    p.result.value = await api('/auscultation/samples', { method: 'POST', body: form })
    p.recorder.state.value = 'saved'
    p.recorder.captured.value = null
    await loadProgress()
  }
  catch (error) {
    p.recorder.state.value = 'captured'
    p.error.value = apiErrorMessage(error, 'The recording could not be saved.')
  }
}

function statusLine(p: Panel): string {
  const s = p.recorder.state.value
  const time = `00:${String(p.recorder.seconds.value).padStart(2, '0')} / 00:${RECORD_SECONDS} SEC`
  if (s === 'recording') return `● RECORDING ${p.organ} AUDIO · ${time}`
  if (s === 'starting') return 'STARTING STETHOSCOPE…'
  if (s === 'captured') return `● SAMPLE CAPTURED · 00:${RECORD_SECONDS} / 00:${RECORD_SECONDS} SEC`
  if (s === 'saving') return 'SAVING SAMPLE…'
  if (s === 'saved') return '● SAMPLE SAVED'
  return `READY · 00:00 / 00:${RECORD_SECONDS} SEC`
}
function progressLine(p: Panel): string {
  const done = progress.value[p.organ]
  return p.sites.map((site) => {
    const name = site.label.split(' · ')[0]!.replace(' Apex', '')
    if (p.recorder.state.value === 'recording' && p.site.value === site.id) return `${name}: ${p.recorder.seconds.value}s / ${RECORD_SECONDS}s`
    return `${name}: ${done.includes(site.id) ? `Saved (${RECORD_SECONDS}s)` : p.site.value === site.id ? 'Ready' : 'Queued'}`
  }).join(' · ')
}
const liveChart = (p: Panel) => (p.recorder.envelope.value.length > 4
  ? envelopeOption(p.recorder.envelope.value, p.organ === 'CARDIAC' ? 'cardiac' : 'pulmonary') : null)
</script>

<template>
  <div class="page">
    <ShellCaptureTabs />
    <div class="flex-1 min-h-0 flex gap-[18px]">
      <ShellHudWindow
v-for="p in panels" :key="p.organ" class="flex-1" flush
                      :title="p.organ === 'CARDIAC' ? 'Cardiac Audio Recording' : 'Pulmonary Audio Recording'"
                      :icon="p.organ === 'CARDIAC' ? 'heart' : 'stethoscope'"
                      :tag-text="p.organ === 'CARDIAC' ? 'HEART · 30S' : 'LUNGS · 30S'">
        <div class="flex-1 flex flex-col px-[19px] pt-[16px] pb-[20px]">
          <p class="label-caps">{{ p.organ === 'CARDIAC' ? 'Select cardiac valve placement' : 'Select bilateral lung zone' }}</p>
          <div class="grid grid-cols-4 gap-[9px] mt-[10px]" role="radiogroup" :aria-label="p.organ === 'CARDIAC' ? 'Valve placement' : 'Lung zone'">
            <button
v-for="site in p.sites" :key="site.id" type="button" role="radio" :aria-checked="p.site.value === site.id"
                    class="focus-ring h-[38px] rounded-[4px] text-[11.5px] border-[1.3px]"
                    :class="p.site.value === site.id ? 'menu-item-active font-bold' : 'bg-cabin-tile border-cabin-line text-cabin-ice'"
                    @click="pickSite(p, site.id)">{{ site.label }}</button>
          </div>

          <div class="tile-hi h-[162px] shrink-0 mt-[16px] flex items-center px-[24px] gap-[26px]">
            <UiHoloFigure :figure="p.organ === 'CARDIAC' ? 'heart' : 'lungs'" :size="108" :label="p.organ === 'CARDIAC' ? 'Heart' : 'Lungs'" />
            <div class="min-w-0 flex-1">
              <p class="text-[10px] font-bold tracking-[0.04em] uppercase text-cabin-ok truncate">
                {{ p.organ === 'CARDIAC' ? 'Digital stethoscope' : 'Pulmonary pickup' }} · {{ p.sites.find(s => s.id === p.site.value)?.pickup }}
              </p>
              <p class="text-[15px] font-bold mt-[10px]">
                <template v-if="p.result.value">
                  {{ p.organ === 'CARDIAC' ? 'Heart Rate' : 'Breathing Rate' }}:
                  {{ p.result.value.rate_per_min ?? '—' }} {{ p.organ === 'CARDIAC' ? 'bpm' : 'rpm' }} · Signal {{ p.result.value.signal_quality_pct }}%
                </template>
                <template v-else>{{ p.organ === 'CARDIAC' ? 'Place the chest piece and hold still' : 'Breathe slowly through the mouth' }}</template>
              </p>
              <p class="text-[12px] mt-[8px]" :class="tooLoud ? 'text-cabin-text' : 'text-cabin-ice'">
                Cabin Noise: {{ noise === null ? 'unknown' : `${Math.round(noise)} dBA` }} ({{ tooLoud ? 'above' : 'below' }} {{ noiseLimit }} dBA acoustic limit)
              </p>
              <div class="flex items-center gap-[12px] mt-[12px]">
                <span class="label-caps !text-[9px]">{{ p.organ === 'CARDIAC' ? 'Input gain' : 'Airflow gain' }}</span>
                <UiProgressBar
class="flex-1" thick :pct="p.recorder.inputDb.value === null ? 0 : Math.max(0, 100 + p.recorder.inputDb.value * 1.6)"
                               :tone="p.organ === 'CARDIAC' ? 'ok' : 'watch'" />
                <span class="mono text-[10px] w-[52px] text-right" :class="p.organ === 'CARDIAC' ? 'text-cabin-ok' : ''">
                  {{ p.recorder.inputDb.value === null ? '—' : `${p.recorder.inputDb.value} dB` }}
                </span>
              </div>
            </div>
          </div>

          <div class="tile relative flex-1 mt-[16px] min-h-0">
            <p
class="absolute top-[14px] left-[18px] mono text-[10.5px] z-10"
               :class="p.recorder.state.value === 'recording' ? '' : p.recorder.state.value === 'captured' || p.recorder.state.value === 'saved' ? 'text-cabin-ok' : 'text-cabin-ice'">
              {{ statusLine(p) }}
            </p>
            <p v-if="p.result.value" class="absolute top-[14px] right-[18px] mono text-[10.5px] text-cabin-ok z-10 uppercase">{{ p.result.value.rhythm_label }}</p>
            <ClientOnly>
              <VChart
v-if="liveChart(p)" :option="liveChart(p)!" theme="spacescan-hud" autoresize class="absolute inset-x-0 top-[34px] bottom-[22px]"
                      :aria-label="`${p.organ.toLowerCase()} sound level`" />
            </ClientOnly>
            <p v-if="!liveChart(p)" class="absolute inset-0 flex items-center justify-center text-[12px] text-cabin-ice px-8 text-center">
              The live sound trace appears here while recording.
            </p>
            <div class="absolute left-[18px] right-[18px] bottom-[12px]">
              <UiProgressBar :pct="(p.recorder.seconds.value / RECORD_SECONDS) * 100" thick />
            </div>
          </div>

          <div class="tile h-[74px] shrink-0 mt-[14px] px-[18px] flex flex-col justify-center">
            <p class="label-caps">{{ p.organ === 'CARDIAC' ? 'Cardiac' : 'Pulmonary' }} recording progress</p>
            <p class="text-[11.5px] font-semibold mt-[9px] truncate">{{ progressLine(p) }}</p>
          </div>
          <p
v-if="p.recorder.message.value || p.error.value || (tooLoud && p.recorder.state.value === 'idle')"
             class="text-[11px] mt-[8px] flex items-center gap-[6px]" role="alert">
            <Icon name="spacescan:alert" class="w-[12px] h-[12px] text-cabin-crit shrink-0" />
            {{ p.error.value ?? p.recorder.message.value ?? `The cabin is too loud for a clinical recording. Wait until it is below ${noiseLimit} dBA.` }}
          </p>
          <div class="grid grid-cols-2 gap-[16px] mt-[14px]">
            <button
type="button" class="hud-button relative"
                    :disabled="tooLoud || noise === null || p.recorder.busyElsewhere.value || p.recorder.state.value === 'saving'"
                    @click="toggle(p)">
              <Icon name="spacescan:mic" class="w-[17px] h-[17px] absolute left-[20px]" />
              {{ p.recorder.state.value === 'recording' || p.recorder.state.value === 'starting' ? 'Stop Recording' : p.organ === 'CARDIAC' ? 'Record / Stop Heart Audio' : 'Record Pulmonary Audio' }}
            </button>
            <button type="button" class="hud-button relative" :disabled="p.recorder.state.value !== 'captured'" @click="save(p)">
              <Icon name="spacescan:play" class="w-[15px] h-[15px] absolute left-[20px]" />
              {{ p.recorder.state.value === 'saving' ? 'Saving…' : p.organ === 'CARDIAC' ? 'Save Cardiac Recording' : 'Save Lung Recording' }}
            </button>
          </div>
        </div>
      </ShellHudWindow>
    </div>
  </div>
</template>
