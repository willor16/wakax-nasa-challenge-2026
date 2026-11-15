<script setup lang="ts">
// 13 · Data Capture · Psych, Motor & Sleep: daily check-in, sleep window and reaction test.
import { z } from 'zod'
import { apiErrorMessage } from '~/composables/useApi'
import { ARENA_DURATION_MS } from '~/composables/useReactionArena'
import { formatDuration } from '~/utils/format'

const { api } = useApi()
const arena = useReactionArena()
usePageHeader(() => ({ title: 'Data Capture · Psych, Motor & Sleep',
  status: { text: arena.phase.value === 'waiting' || arena.phase.value === 'target' ? 'Test running' : 'Session active', tone: 'ok' } }))

const STATES = [
  { id: 'CALM', label: 'Calm' }, { id: 'FOCUSED', label: 'Focused' },
  { id: 'TIRED', label: 'Tired' }, { id: 'STRESSED', label: 'Stressed' },
] as const
const SCALES = [
  { key: 'mood', label: 'Overall Mood (1–5)' }, { key: 'stress', label: 'Perceived Stress (1–5)' },
  { key: 'isolation', label: 'Sense of Isolation (1–5)' }, { key: 'motivation', label: 'Mission Motivation (1–5)' },
] as const
type ScaleKey = typeof SCALES[number]['key']

const moodState = ref<string | null>(null)
const scales = reactive<Record<ScaleKey, number | null>>({ mood: null, stress: null, isolation: null, motivation: null })
const onset = ref('')
const wake = ref('')
const checkinMessage = ref<{ tone: 'ok' | 'critical', title: string, text: string } | null>(null)
const checkinBusy = ref(false)

const clock = z.string().regex(/^([01]\d|2[0-3]):[0-5]\d$/, 'Use the 24-hour HH:MM format')
const checkinSchema = z.object({
  mood: z.number({ invalid_type_error: 'Choose a value for every scale' }).int().min(1).max(5),
  stress: z.number({ invalid_type_error: 'Choose a value for every scale' }).int().min(1).max(5),
  isolation: z.number({ invalid_type_error: 'Choose a value for every scale' }).int().min(1).max(5),
  motivation: z.number({ invalid_type_error: 'Choose a value for every scale' }).int().min(1).max(5),
  sleep_onset_utc: clock.optional(),
  wake_utc: clock.optional(),
})

const asleepText = computed(() => {
  if (!clock.safeParse(onset.value).success || !clock.safeParse(wake.value).success) return ''
  const toMin = (t: string) => Number(t.slice(0, 2)) * 60 + Number(t.slice(3))
  const span = (toMin(wake.value) - toMin(onset.value) + 1440) % 1440
  return span ? `${formatDuration(span)} window` : ''
})

async function saveCheckin() {
  checkinMessage.value = null
  const body = {
    ...scales,
    mood_state: moodState.value ?? undefined,
    sleep_onset_utc: onset.value || undefined,
    wake_utc: wake.value || undefined,
  }
  if ((body.sleep_onset_utc === undefined) !== (body.wake_utc === undefined)) {
    checkinMessage.value = { tone: 'critical', title: 'Not saved', text: 'Enter both sleep onset and wake time, or neither.' }
    return
  }
  const parsed = checkinSchema.safeParse(body)
  if (!parsed.success) {
    checkinMessage.value = { tone: 'critical', title: 'Not saved', text: parsed.error.issues[0]!.message }
    return
  }
  checkinBusy.value = true
  try {
    const saved = await api<{ alert_id: number | null, sleep_session: { time_in_bed_min: number } | null, sleep_note_en?: string }>(
      '/psych/checkins', { method: 'POST', body })
    const sleepText = saved.sleep_session
      ? ` Sleep window of ${formatDuration(saved.sleep_session.time_in_bed_min)} sent to the Sleep module.`
      : saved.sleep_note_en ? ` ${saved.sleep_note_en}` : ''
    checkinMessage.value = saved.alert_id
      ? { tone: 'critical', title: 'Check-in saved · Support advised', text: `Your check-in raised a wellbeing advisory.${sleepText}` }
      : { tone: 'ok', title: 'Check-in saved', text: `Profile → Psychological is updated.${sleepText}` }
  }
  catch (error) {
    checkinMessage.value = { tone: 'critical', title: 'Not saved', text: apiErrorMessage(error) }
  }
  finally {
    checkinBusy.value = false
  }
}

const motorMessage = ref<{ tone: 'ok' | 'critical', title: string, text: string } | null>(null)
const motorBusy = ref(false)
async function saveMotor() {
  motorMessage.value = null
  if (arena.phase.value !== 'done' || !arena.times.value.length) {
    motorMessage.value = { tone: 'critical', title: 'Not saved', text: 'Complete a 2-minute test first.' }
    return
  }
  motorBusy.value = true
  try {
    const saved = await api<{ reaction_ms: number, accuracy_pct: number, alert_id: number | null }>('/cognitive/sessions', {
      method: 'POST',
      body: { reaction_times_ms: arena.times.value, false_starts: arena.falseStarts.value, duration_sec: ARENA_DURATION_MS / 1000 },
    })
    motorMessage.value = saved.alert_id
      ? { tone: 'critical', title: 'Session saved · Below target', text: 'Rest before demanding tasks; see Notifications.' }
      : { tone: 'ok', title: 'Session saved', text: `Mean ${Math.round(saved.reaction_ms)} ms · ${saved.accuracy_pct}% precision.` }
    arena.reset()
  }
  catch (error) {
    motorMessage.value = { tone: 'critical', title: 'Not saved', text: apiErrorMessage(error) }
  }
  finally {
    motorBusy.value = false
  }
}
const elapsedText = computed(() => {
  const s = Math.floor(arena.elapsedMs.value / 1000)
  return `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`
})
function onArenaKey(event: KeyboardEvent) {
  if (event.code === 'Space' || event.code === 'Enter') {
    event.preventDefault()
    arena.tap()
  }
}
</script>

<template>
  <div class="page">
    <ShellCaptureTabs />
    <div class="flex-1 min-h-0 flex gap-[18px]">
      <ShellHudWindow class="w-[740px]" title="Behavioral & Sleep Window Entry" icon="moon" tag-text="DAILY CHECK-IN" flush>
        <form class="flex-1 flex flex-col px-[23px] pt-[17px] pb-[20px]" novalidate @submit.prevent="saveCheckin">
          <p class="label-caps">Select current mood state</p>
          <div class="grid grid-cols-4 gap-[14px] mt-[10px]" role="radiogroup" aria-label="Current mood state">
            <button
v-for="state in STATES" :key="state.id" type="button" role="radio" :aria-checked="moodState === state.id"
                    class="focus-ring h-[40px] rounded-[4px] text-[12px] border-[1.3px]"
                    :class="moodState === state.id ? 'menu-item-active font-bold' : 'bg-cabin-tile border-cabin-line text-cabin-ice'"
                    @click="moodState = state.id">{{ state.label }}</button>
          </div>
          <div class="flex flex-col gap-[12px] mt-[18px]">
            <div v-for="scale in SCALES" :key="scale.key" class="tile h-[74px] px-[18px] flex items-center justify-between">
              <div>
                <p class="text-[13px] font-semibold">{{ scale.label }}</p>
                <p class="text-[11px] font-bold mt-[6px]" :class="scales[scale.key] ? 'text-cabin-ok' : 'text-cabin-dim'">
                  {{ scales[scale.key] ? `Selected: ${scales[scale.key]} / 5` : 'Not selected' }}
                </p>
              </div>
              <div class="flex gap-[10px]" role="radiogroup" :aria-label="scale.label">
                <button
v-for="n in 5" :key="n" type="button" role="radio" :aria-checked="scales[scale.key] === n"
                        class="focus-ring w-[44px] h-[40px] rounded-[4px] text-[13px] border-[1.3px]"
                        :class="scales[scale.key] === n ? 'menu-item-active font-bold' : 'border-cabin-edge/60 text-cabin-ice'"
                        @click="scales[scale.key] = n">{{ n }}</button>
              </div>
            </div>
          </div>
          <p class="label-caps mt-[22px]">Confirm last night sleep window (feeds sleep module)</p>
          <div class="grid grid-cols-2 gap-[19px] mt-[12px]">
            <div>
              <div class="flex justify-between mb-[8px]"><label for="onset" class="label-caps">Sleep onset (UTC)</label><span class="text-[9.5px] text-cabin-ice">Lights out</span></div>
              <div class="hud-field !h-[56px]"><input id="onset" v-model="onset" placeholder="22:18" inputmode="numeric" maxlength="5"><span class="text-[11px] font-bold text-cabin-ice">UTC</span></div>
            </div>
            <div>
              <div class="flex justify-between mb-[8px]"><label for="wake" class="label-caps">Wake time (UTC)</label><span class="text-[9.5px] text-cabin-ice">{{ asleepText }}</span></div>
              <div class="hud-field !h-[56px]"><input id="wake" v-model="wake" placeholder="05:54" inputmode="numeric" maxlength="5"><span class="text-[11px] font-bold text-cabin-ice">UTC</span></div>
            </div>
          </div>
          <div class="mt-auto flex flex-col gap-[14px]">
            <UiSaveResult v-if="checkinMessage" v-bind="checkinMessage" />
            <button type="submit" class="hud-button relative" :disabled="checkinBusy">
              <Icon name="spacescan:moon" class="w-[17px] h-[17px] absolute left-[22px]" />
              {{ checkinBusy ? 'Saving…' : 'Save Behavioral & Sleep Log' }}
            </button>
          </div>
        </form>
      </ShellHudWindow>

      <ShellHudWindow class="flex-1" title="Motor & Reaction Test Capture" icon="reticle" tag-text="2-MIN VIGILANCE" flush>
        <div class="flex-1 flex flex-col px-[23px] pt-[18px] pb-[20px]">
          <div
            class="tile-hi relative h-[304px] shrink-0 select-none focus-ring cursor-pointer"
            role="button"
            tabindex="0"
            :aria-label="arena.phase.value === 'target' ? 'Target on screen: tap now' : 'Reaction test area'"
            @pointerdown.prevent="arena.tap()"
            @keydown="onArenaKey"
          >
            <p class="absolute top-[18px] left-[18px] mono text-[10px]">
              TRIAL {{ arena.summary.value.trials + (arena.phase.value === 'target' ? 1 : 0) }} · ELAPSED {{ elapsedText }} / 02:00
            </p>
            <p class="absolute top-[18px] right-[18px] text-[10px] font-bold text-cabin-ok">
              {{ arena.phase.value === 'idle' ? 'PRESS START, THEN TAP THE GREEN TARGET' : arena.phase.value === 'done' ? 'TEST COMPLETE' : 'TAP GREEN STIMULUS IMMEDIATELY' }}
            </p>
            <span class="absolute left-[18px] right-[18px] top-1/2 h-px bg-cabin-navy-edge/50" />
            <span class="absolute top-[40px] bottom-[40px] left-1/2 w-px bg-cabin-navy-edge/50" />
            <span class="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-[190px] h-[190px] rounded-full border border-dashed border-cabin-navy-edge/70" />
            <span
              class="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-[120px] h-[120px] rounded-full flex items-center justify-center border-[2px] transition-colors"
              :class="arena.phase.value === 'target' ? 'border-cabin-ok bg-cabin-ok/25' : 'border-cabin-edge/40 bg-transparent'"
            >
              <span
class="w-[46px] h-[46px] rounded-full flex items-center justify-center text-[12px] font-bold border-[1.5px]"
                    :class="arena.phase.value === 'target' ? 'border-cabin-text bg-cabin-ok/40' : 'border-cabin-edge/40 text-cabin-dim'">TAP</span>
            </span>
            <p class="absolute bottom-[14px] left-0 right-0 text-center mono text-[11px]">
              Last Stimulus Latency: {{ arena.lastLatencyMs.value === null ? '—' : `${arena.lastLatencyMs.value} ms` }} · False Starts: {{ arena.falseStarts.value }}
            </p>
          </div>
          <div class="grid grid-cols-2 gap-[16px] mt-[18px] flex-1">
            <div class="tile relative px-[18px] flex flex-col justify-center">
              <span class="absolute top-0 left-0 right-0 h-[3px] bg-cabin-ok" />
              <p class="label-caps">Mean reaction time</p>
              <p class="text-[28px] font-bold mt-[14px]">{{ arena.summary.value.meanMs === null ? '—' : `${arena.summary.value.meanMs} ms` }}</p>
              <p class="text-[11px] text-cabin-ice mt-[12px]">Optimal threshold &lt; 300 ms</p>
            </div>
            <div class="tile relative px-[18px] flex flex-col justify-center">
              <span class="absolute top-0 left-0 right-0 h-[3px] bg-cabin-ok" />
              <p class="label-caps">Motor hit precision</p>
              <p class="text-[28px] font-bold mt-[14px]">{{ arena.summary.value.precisionPct === null ? '—' : `${arena.summary.value.precisionPct}%` }}</p>
              <p class="text-[11px] text-cabin-ice mt-[12px]">{{ arena.summary.value.valid }} / {{ arena.summary.value.trials }} valid responses</p>
            </div>
          </div>
          <UiSaveResult v-if="motorMessage" v-bind="motorMessage" class="mt-[14px]" />
          <div class="grid grid-cols-2 gap-[16px] mt-[16px]">
            <button type="button" class="hud-button relative" :disabled="arena.phase.value === 'waiting' || arena.phase.value === 'target'" @click="arena.start()">
              <Icon name="spacescan:reticle" class="w-[17px] h-[17px] absolute left-[20px]" />Start 2-Min Reaction Test
            </button>
            <button type="button" class="hud-button relative" :disabled="arena.phase.value !== 'done' || motorBusy" @click="saveMotor">
              <Icon name="spacescan:bolt" class="w-[17px] h-[17px] absolute left-[20px]" />{{ motorBusy ? 'Saving…' : 'Save Motor Session' }}
            </button>
          </div>
        </div>
      </ShellHudWindow>
    </div>
  </div>
</template>
