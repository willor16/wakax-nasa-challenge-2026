<script setup lang="ts">
import { z } from 'zod'
import AstroCowModal from '~/components/psych/AstroCowModal.vue'
import BehavioralMatrixModal from '~/components/psych/BehavioralMatrixModal.vue'
import NeuroFitModal from '~/components/psych/NeuroFitModal.vue'
import cowSpriteUrl from '~/assets/games/astrocow/cow-sprite.png'
import { apiErrorMessage } from '~/composables/useApi'
import { ARENA_DURATION_MS } from '~/composables/useReactionArena'
import type { AstroCowSummary } from '~/utils/astroCowTelemetry'
import { evaluateBehavioralMatrix } from '~/utils/behavioralMatrix20'
import { formatDuration } from '~/utils/format'
import { ACTIVE_SQUAD, SQUAD_SPRITES, type NeuroFitReport } from '~/utils/neuroFitEngine'

const { api } = useApi()
const { unread } = useMission()
const arena = useReactionArena()
const { state: gameState, resetMatrix } = usePsychGames()

usePageHeader(() => ({
  title: 'Data Capture · Psych, Motor & Sleep',
  status: {
    text: arena.phase.value === 'waiting' || arena.phase.value === 'target' ? 'Test running' : 'Session active',
    tone: 'ok',
  },
}))

const STATES = [
  { id: 'CALM', label: 'Calm' },
  { id: 'FOCUSED', label: 'Focused' },
  { id: 'TIRED', label: 'Tired' },
  { id: 'STRESSED', label: 'Stressed' },
] as const
const SCALES = [
  { key: 'mood', label: 'Overall Mood (1–5)' },
  { key: 'stress', label: 'Perceived Stress (1–5)' },
  { key: 'isolation', label: 'Sense of Isolation (1–5)' },
  { key: 'motivation', label: 'Mission Motivation (1–5)' },
] as const
type ScaleKey = typeof SCALES[number]['key']
const SCALE_HELP: Record<ScaleKey, string> = {
  mood: 'overall_mood',
  stress: 'stress_index',
  isolation: 'isolation',
  motivation: 'motivation',
}

const moodState = ref<string | null>(null)
const scales = reactive<Record<ScaleKey, number | null>>({
  mood: null,
  stress: null,
  isolation: null,
  motivation: null,
})
const onset = ref('')
const wake = ref('')
const checkinMessage = ref<{ tone: 'ok' | 'critical', title: string, text: string } | null>(null)
const checkinBusy = ref(false)

const matrixExpanded = ref(false)
const matrixSaving = ref(false)
const matrixSavedNote = ref<{ tone: 'ok' | 'critical', title: string, text: string } | null>(null)

const astrocowExpanded = ref(false)
const astrocowSaving = ref(false)
const astrocowSavedNote = ref<{ tone: 'ok' | 'critical', title: string, text: string } | null>(null)

const neurofitExpanded = ref(false)
const neurofitSaving = ref(false)
const neurofitSavedNote = ref<{ tone: 'ok' | 'critical', title: string, text: string } | null>(null)

type CaptureGameTab = 'reaction' | 'astrocow' | 'neurofit'
const activeGameTab = ref<CaptureGameTab>('reaction')

const matrixAnsweredCount = computed(() => gameState.value.matrixAnswers.filter(v => v !== null).length)
const matrixPreview = computed(() => {
  if (!gameState.value.matrixCompleted || gameState.value.matrixAnswers.some(v => v === null)) return null
  return evaluateBehavioralMatrix(gameState.value.matrixAnswers as number[])
})
const selectedCopilot = computed(() => SQUAD_SPRITES[gameState.value.neurofitCopilot])

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
    checkinMessage.value = {
      tone: 'critical',
      title: 'Not saved',
      text: 'Enter both sleep onset and wake time, or neither.',
    }
    return
  }
  const parsed = checkinSchema.safeParse(body)
  if (!parsed.success) {
    checkinMessage.value = { tone: 'critical', title: 'Not saved', text: parsed.error.issues[0]!.message }
    return
  }
  checkinBusy.value = true
  try {
    const saved = await api<{
      alert_id: number | null
      sleep_session: { time_in_bed_min: number } | null
      sleep_note_en?: string
    }>('/psych/checkins', { method: 'POST', body })
    if (saved.alert_id) unread.value += 1
    const sleepText = saved.sleep_session
      ? ` Sleep window of ${formatDuration(saved.sleep_session.time_in_bed_min)} sent to the Sleep module.`
      : saved.sleep_note_en ? ` ${saved.sleep_note_en}` : ''
    checkinMessage.value = saved.alert_id
      ? {
          tone: 'critical',
          title: 'Check-in saved · Support advised',
          text: `Your check-in raised a wellbeing advisory.${sleepText}`,
        }
      : {
          tone: 'ok',
          title: 'Check-in saved',
          text: `Profile → Psychological is updated.${sleepText}`,
        }
  }
  catch (error) {
    checkinMessage.value = { tone: 'critical', title: 'Not saved', text: apiErrorMessage(error) }
  }
  finally {
    checkinBusy.value = false
  }
}

async function saveMatrix(answers: number[]) {
  matrixSaving.value = true
  matrixSavedNote.value = null
  checkinMessage.value = null
  const hasSleep = clock.safeParse(onset.value).success && clock.safeParse(wake.value).success
  try {
    const saved = await api<{
      alert_id: number | null
      matrix_report: { total_load_score: number, readiness_status: string }
    }>('/psych/checkins', {
      method: 'POST',
      body: {
        assessment_type: 'BEHAVIORAL_MATRIX_20',
        item_responses: answers,
        sleep_onset_utc: hasSleep ? onset.value : undefined,
        wake_utc: hasSleep ? wake.value : undefined,
      },
    })
    if (saved.alert_id) unread.value += 1
    const rep = saved.matrix_report
    const note = saved.alert_id
      ? {
          tone: 'critical' as const,
          title: `Matrix saved · ${rep.readiness_status} (${rep.total_load_score}/80)`,
          text: 'Psychosocial load advisory logged to Notifications and Psychological Profile.',
        }
      : {
          tone: 'ok' as const,
          title: `Matrix saved · ${rep.readiness_status} (${rep.total_load_score}/80)`,
          text: '20-item assessment recorded and reflected on Profile → Psychological.',
        }
    matrixSavedNote.value = note
    checkinMessage.value = note
    resetMatrix()
    matrixExpanded.value = false
  }
  catch (error) {
    matrixSavedNote.value = { tone: 'critical', title: 'Not saved', text: apiErrorMessage(error) }
  }
  finally {
    matrixSaving.value = false
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
    const saved = await api<{ reaction_ms: number, accuracy_pct: number, alert_id: number | null }>(
      '/cognitive/sessions',
      {
        method: 'POST',
        body: {
          test_type: 'REACTION_ARENA',
          reaction_times_ms: arena.times.value,
          false_starts: arena.falseStarts.value,
          duration_sec: ARENA_DURATION_MS / 1000,
        },
      },
    )
    if (saved.alert_id) unread.value += 1
    motorMessage.value = saved.alert_id
      ? {
          tone: 'critical',
          title: 'Session saved · Below target',
          text: 'Rest before demanding tasks; see Notifications.',
        }
      : {
          tone: 'ok',
          title: 'Session saved',
          text: `Mean ${Math.round(saved.reaction_ms)} ms · ${saved.accuracy_pct}% precision.`,
        }
    arena.reset()
  }
  catch (error) {
    motorMessage.value = { tone: 'critical', title: 'Not saved', text: apiErrorMessage(error) }
  }
  finally {
    motorBusy.value = false
  }
}

async function saveAstroCow(summary: AstroCowSummary) {
  astrocowSaving.value = true
  astrocowSavedNote.value = null
  motorMessage.value = null
  try {
    const saved = await api<{ reaction_ms: number, accuracy_pct: number, alert_id: number | null }>(
      '/cognitive/sessions',
      {
        method: 'POST',
        body: {
          test_type: 'ASTROCOW_SIM',
          duration_sec: summary.duration_sec,
          astrocow: summary,
        },
      },
    )
    if (saved.alert_id) unread.value += 1
    const note = saved.alert_id
      ? {
          tone: 'critical' as const,
          title: 'AstroCow saved · Readiness alert raised',
          text: `Mean ${Math.round(saved.reaction_ms)} ms · ${saved.accuracy_pct}% precision. Review Notifications.`,
        }
      : {
          tone: 'ok' as const,
          title: 'AstroCow telemetry saved',
          text: `Mean ${Math.round(saved.reaction_ms)} ms · Recovery ${summary.recovery_time_sec} s · ${saved.accuracy_pct}% hit.`,
        }
    astrocowSavedNote.value = note
    motorMessage.value = note
    astrocowExpanded.value = false
  }
  catch (error) {
    astrocowSavedNote.value = { tone: 'critical', title: 'Not saved', text: apiErrorMessage(error) }
  }
  finally {
    astrocowSaving.value = false
  }
}

async function saveNeuroFit(report: NeuroFitReport) {
  neurofitSaving.value = true
  neurofitSavedNote.value = null
  motorMessage.value = null
  try {
    const saved = await api<{
      attention_score: number
      accuracy_pct: number
      alert_id: number | null
    }>('/cognitive/sessions', {
      method: 'POST',
      body: {
        test_type: 'NEUROFIT_LAB',
        duration_sec: report.duration_sec,
        neurofit: {
          copilot_id: report.copilot_id,
          duration_sec: report.duration_sec,
          total_score: report.total_score,
          ecg_index: report.ecg_index,
          stages: report.stages.map(st => ({
            key: st.key,
            title: st.title,
            cabCode: st.cabCode,
            cabName: st.cabName,
            score: st.score,
            accuracy: st.accuracy,
            correct_attempts: st.correct_attempts,
            error_attempts: st.error_attempts,
            total_attempts: st.total_attempts,
            avg_reaction_ms: st.avg_reaction_ms,
            level_reached: st.level_reached,
            duration_sec: st.duration_sec,
          })),
          cab_metrics: report.cab_metrics,
          diagnostic: report.diagnostic,
        },
      },
    })
    if (saved.alert_id) unread.value += 1
    const note = saved.alert_id
      ? {
          tone: 'critical' as const,
          title: `NeuroFit saved · Focus Alert (${Math.round(saved.attention_score)}/100)`,
          text: 'Cognitive focus advisory sent to Notifications and Psychological Profile.',
        }
      : {
          tone: 'ok' as const,
          title: `NeuroFit battery saved · Focus ${Math.round(saved.attention_score)}/100`,
          text: `Retention ${report.retention_pct}% · Attention ${report.sustained_attention_pct}% updated on Profile.`,
        }
    neurofitSavedNote.value = note
    motorMessage.value = note
    neurofitExpanded.value = false
  }
  catch (error) {
    neurofitSavedNote.value = { tone: 'critical', title: 'Not saved', text: apiErrorMessage(error) }
  }
  finally {
    neurofitSaving.value = false
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
      <ShellHudWindow class="w-[48.9%] shrink-0" title="Behavioral &amp; Sleep Window Entry" icon="moon" tag-text="DAILY CHECK-IN" flush>
        <form class="flex-1 min-h-0 flex flex-col px-[23px] pt-[clamp(8px,1.5dvh,14px)] pb-[clamp(10px,1.8dvh,18px)] hud-scroll" novalidate @submit.prevent="saveCheckin">
          <div class="tile-hi p-[10px] px-[14px] flex items-center justify-between gap-[10px] mb-[clamp(8px,1.3dvh,12px)] shrink-0">
            <div class="flex items-center gap-[10px] min-w-0">
              <img :src="cowSpriteUrl" alt="" class="w-[34px] h-[34px] shrink-0">
              <div class="min-w-0">
                <p class="text-[10px] font-bold tracking-[0.04em] uppercase text-cabin-ok">
                  20-Item Behavioral Matrix · Fullscreen
                </p>
                <p class="text-[11px] text-cabin-ice truncate">
                  <template v-if="matrixPreview">
                    Load {{ matrixPreview.totalLoad }}/80 ({{ matrixPreview.readinessStatus }}) ready to save
                  </template>
                  <template v-else-if="matrixAnsweredCount > 0">
                    In progress: {{ matrixAnsweredCount }} / 20 items answered
                  </template>
                  <template v-else>
                    5 subscales (Tension, Dejection, Anger, Fatigue, Isolation)
                  </template>
                </p>
              </div>
            </div>
            <button type="button" class="px-[12px] py-[7px] rounded-[4px] border border-cabin-ok bg-cabin-ok/15 mono text-[11px] font-bold text-cabin-ok shrink-0" @click="matrixExpanded = true">
              {{ matrixPreview ? 'Review Matrix' : matrixAnsweredCount > 0 ? 'Resume 20-Item' : 'Launch 20-Item Matrix' }}
            </button>
          </div>

          <p class="label-caps">Quick daily mood state</p>
          <div class="grid grid-cols-4 gap-[12px] mt-[8px]" role="radiogroup" aria-label="Current mood state">
            <button
              v-for="state in STATES"
              :key="state.id"
              type="button"
              role="radio"
              :aria-checked="moodState === state.id"
              class="focus-ring h-[clamp(32px,4.1dvh,42px)] rounded-[4px] text-[12px] border-[1.3px]"
              :class="moodState === state.id ? 'menu-item-active font-bold' : 'bg-cabin-tile border-cabin-line text-cabin-ice'"
              @click="moodState = state.id"
            >
              {{ state.label }}
            </button>
          </div>

          <div class="flex flex-col gap-[clamp(5px,1.1dvh,10px)] mt-[clamp(8px,1.5dvh,14px)]">
            <div v-for="scale in SCALES" :key="scale.key" class="tile h-[clamp(50px,6.8dvh,72px)] px-[16px] flex items-center justify-between gap-[10px]">
              <div class="min-w-0">
                <p class="text-[12.5px] font-semibold flex items-center gap-[6px]">{{ scale.label }}<UiParamHelp :metric-key="SCALE_HELP[scale.key]" /></p>
                <p class="text-[10.5px] font-bold mt-[3px]" :class="scales[scale.key] ? 'text-cabin-ok' : 'text-cabin-dim'">
                  {{ scales[scale.key] ? `Selected: ${scales[scale.key]} / 5` : 'Not selected' }}
                </p>
              </div>
              <div class="flex gap-[8px]" role="radiogroup" :aria-label="scale.label">
                <button
                  v-for="n in 5"
                  :key="n"
                  type="button"
                  role="radio"
                  :aria-checked="scales[scale.key] === n"
                  class="focus-ring w-[clamp(32px,2.7vw,42px)] h-[clamp(32px,4dvh,40px)] rounded-[4px] text-[12.5px] border-[1.3px]"
                  :class="scales[scale.key] === n ? 'menu-item-active font-bold' : 'border-cabin-edge/60 text-cabin-ice'"
                  @click="scales[scale.key] = n"
                >
                  {{ n }}
                </button>
              </div>
            </div>
          </div>

          <p class="label-caps mt-[clamp(8px,1.8dvh,16px)] flex items-center gap-[6px]">Confirm last night sleep window (feeds sleep module)<UiParamHelp metric-key="sleep_duration" /></p>
          <div class="grid grid-cols-2 gap-[16px] mt-[clamp(6px,1.1dvh,10px)]">
            <div>
              <div class="flex justify-between mb-[6px]"><label for="onset" class="label-caps">Sleep onset (UTC)</label><span class="text-[9.5px] text-cabin-ice">Lights out</span></div>
              <div class="hud-field !h-[clamp(40px,5.5dvh,54px)]"><input id="onset" v-model="onset" placeholder="22:18" inputmode="numeric" maxlength="5"><span class="text-[11px] font-bold text-cabin-ice">UTC</span></div>
            </div>
            <div>
              <div class="flex justify-between mb-[6px]"><label for="wake" class="label-caps">Wake time (UTC)</label><span class="text-[9.5px] text-cabin-ice">{{ asleepText }}</span></div>
              <div class="hud-field !h-[clamp(40px,5.5dvh,54px)]"><input id="wake" v-model="wake" placeholder="05:54" inputmode="numeric" maxlength="5"><span class="text-[11px] font-bold text-cabin-ice">UTC</span></div>
            </div>
          </div>

          <div class="mt-auto pt-[8px] flex flex-col gap-[clamp(6px,1.2dvh,12px)]">
            <UiSaveResult v-if="checkinMessage" v-bind="checkinMessage" />
            <button type="submit" class="hud-button relative" :disabled="checkinBusy">
              <Icon name="spacescan:moon" class="w-[17px] h-[17px] absolute left-[22px]" />
              {{ checkinBusy ? 'Saving…' : 'Save Behavioral & Sleep Log' }}
            </button>
          </div>
        </form>
      </ShellHudWindow>

      <ShellHudWindow class="flex-1 min-w-0" title="Sensorimotor &amp; Cognitive Capture" icon="reticle" tag-text="PSYCH &amp; MOTOR" flush>
        <div class="flex-1 min-h-0 flex flex-col px-[23px] pt-[clamp(8px,1.5dvh,14px)] pb-[clamp(10px,1.8dvh,18px)]">
          <div class="grid grid-cols-3 gap-[8px] mb-[12px] shrink-0">
            <button
              type="button"
              class="focus-ring py-[8px] px-[10px] rounded-[4px] border mono text-[11px] font-bold transition"
              :class="activeGameTab === 'reaction' ? 'menu-item-active text-cabin-text' : 'border-cabin-line text-cabin-ice hover:text-cabin-text'"
              @click="activeGameTab = 'reaction'"
            >
              1 · 2-Min Reaction
            </button>
            <button
              type="button"
              class="focus-ring py-[8px] px-[10px] rounded-[4px] border mono text-[11px] font-bold transition"
              :class="activeGameTab === 'astrocow' ? 'menu-item-active text-cabin-text' : 'border-cabin-line text-cabin-ice hover:text-cabin-text'"
              @click="activeGameTab = 'astrocow'"
            >
              2 · AST-01 AstroCow
            </button>
            <button
              type="button"
              class="focus-ring py-[8px] px-[10px] rounded-[4px] border mono text-[11px] font-bold transition"
              :class="activeGameTab === 'neurofit' ? 'menu-item-active text-cabin-text' : 'border-cabin-line text-cabin-ice hover:text-cabin-text'"
              @click="activeGameTab = 'neurofit'"
            >
              3 · NeuroFit 4-Stage
            </button>
          </div>

          <template v-if="activeGameTab === 'reaction'">
            <div
              class="tile-hi relative flex-[1.5] min-h-[190px] max-h-[360px] select-none focus-ring cursor-pointer"
              role="button"
              tabindex="0"
              :aria-label="arena.phase.value === 'target' ? 'Target on screen: tap now' : 'Reaction test area'"
              @pointerdown.prevent="arena.tap()"
              @keydown="onArenaKey"
            >
              <p class="absolute top-[16px] left-[18px] mono text-[10px]">
                TRIAL {{ arena.summary.value.trials + (arena.phase.value === 'target' ? 1 : 0) }} · ELAPSED {{ elapsedText }} / 02:00
              </p>
              <p class="absolute top-[16px] right-[18px] text-[10px] font-bold text-cabin-ok">
                {{ arena.phase.value === 'idle' ? 'PRESS START, THEN TAP THE GREEN TARGET' : arena.phase.value === 'done' ? 'TEST COMPLETE' : 'TAP GREEN STIMULUS IMMEDIATELY' }}
              </p>
              <span class="absolute left-[18px] right-[18px] top-1/2 h-px bg-cabin-navy-edge/50" />
              <span class="absolute top-[40px] bottom-[40px] left-1/2 w-px bg-cabin-navy-edge/50" />
              <span class="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-[180px] h-[180px] rounded-full border border-dashed border-cabin-navy-edge/70" />
              <span
                class="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-[112px] h-[112px] rounded-full flex items-center justify-center border-[2px] transition-colors"
                :class="arena.phase.value === 'target' ? 'border-cabin-ok bg-cabin-ok/25' : 'border-cabin-edge/40 bg-transparent'"
              >
                <span
                  class="w-[46px] h-[46px] rounded-full flex items-center justify-center text-[12px] font-bold border-[1.5px]"
                  :class="arena.phase.value === 'target' ? 'border-cabin-text bg-cabin-ok/40' : 'border-cabin-edge/40 text-cabin-dim'"
                >
                  TAP
                </span>
              </span>
              <p class="absolute bottom-[14px] left-0 right-0 text-center mono text-[11px]">
                Last Stimulus Latency: {{ arena.lastLatencyMs.value === null ? '—' : `${arena.lastLatencyMs.value} ms` }} · False Starts: {{ arena.falseStarts.value }}
              </p>
            </div>
            <div class="grid grid-cols-2 gap-[16px] mt-[clamp(8px,1.6dvh,16px)] flex-1 min-h-[88px]">
              <div class="tile relative px-[18px] flex flex-col justify-center">
                <span class="absolute top-0 left-0 right-0 h-[3px] bg-cabin-ok" />
                <p class="label-caps flex items-center gap-[6px]">Mean reaction time<UiParamHelp metric-key="reaction_time" /></p>
                <p class="text-[26px] font-bold mt-[clamp(6px,1.2dvh,12px)]">{{ arena.summary.value.meanMs === null ? '—' : `${arena.summary.value.meanMs} ms` }}</p>
                <p class="text-[11px] text-cabin-ice mt-[clamp(4px,1dvh,10px)]">Optimal threshold &lt; 300 ms</p>
              </div>
              <div class="tile relative px-[18px] flex flex-col justify-center">
                <span class="absolute top-0 left-0 right-0 h-[3px] bg-cabin-ok" />
                <p class="label-caps flex items-center gap-[6px]">Motor hit precision<UiParamHelp metric-key="motor_precision" /></p>
                <p class="text-[26px] font-bold mt-[clamp(6px,1.2dvh,12px)]">{{ arena.summary.value.precisionPct === null ? '—' : `${arena.summary.value.precisionPct}%` }}</p>
                <p class="text-[11px] text-cabin-ice mt-[clamp(4px,1dvh,10px)]">{{ arena.summary.value.valid }} / {{ arena.summary.value.trials }} valid responses</p>
              </div>
            </div>
            <UiSaveResult v-if="motorMessage" v-bind="motorMessage" class="mt-[10px]" />
            <div class="grid grid-cols-2 gap-[16px] mt-[clamp(8px,1.4dvh,14px)]">
              <button type="button" class="hud-button relative" :disabled="arena.phase.value === 'waiting' || arena.phase.value === 'target'" @click="arena.start()">
                <Icon name="spacescan:reticle" class="w-[17px] h-[17px] absolute left-[20px]" />Start 2-Min Reaction Test
              </button>
              <button type="button" class="hud-button relative" :disabled="arena.phase.value !== 'done' || motorBusy" @click="saveMotor">
                <Icon name="spacescan:bolt" class="w-[17px] h-[17px] absolute left-[20px]" />{{ motorBusy ? 'Saving…' : 'Save Motor Session' }}
              </button>
            </div>
          </template>

          <div v-else-if="activeGameTab === 'astrocow'" class="flex-1 min-h-0 flex flex-col gap-[12px] hud-scroll">
            <div class="tile-hi p-[18px] flex items-center gap-[16px]">
              <img :src="cowSpriteUrl" alt="AST-01 AstroCow" class="w-[64px] h-[64px] shrink-0">
              <div class="min-w-0 flex-1">
                <p class="label-caps text-cabin-ok">Dual-Task Sensorimotor Flight Simulator</p>
                <h3 class="text-[18px] font-bold mt-[2px]">AST-01 AstroCow · Stress Adaptation &amp; Motor Control</h3>
                <p class="text-[12px] text-cabin-ice mt-[4px]">
                  Steer through escalating orbital gates every 15s while locking timed beacon targets. Logs reaction latency, RT variability, T_recovery, omissions, errors after change, and motor precision.
                </p>
              </div>
            </div>

            <div class="grid grid-cols-3 gap-[10px]">
              <div class="tile p-[12px]"><p class="label-caps">Mean Latency</p><p class="mono text-[18px] font-bold mt-[4px]">{{ gameState.astrocowLast ? `${gameState.astrocowLast.mean_reaction_ms} ms` : '—' }}</p></div>
              <div class="tile p-[12px]"><p class="label-caps">Recovery T_rec</p><p class="mono text-[18px] font-bold mt-[4px]">{{ gameState.astrocowLast ? `${gameState.astrocowLast.recovery_time_sec} s` : '—' }}</p></div>
              <div class="tile p-[12px]"><p class="label-caps">RT Variability</p><p class="mono text-[18px] font-bold mt-[4px]">{{ gameState.astrocowLast ? `±${gameState.astrocowLast.rt_variability_ms} ms` : '—' }}</p></div>
              <div class="tile p-[12px]"><p class="label-caps">Motor Precision</p><p class="mono text-[18px] font-bold mt-[4px] text-cabin-ok">{{ gameState.astrocowLast ? `${gameState.astrocowLast.precision_pct}%` : '—' }}</p></div>
              <div class="tile p-[12px]"><p class="label-caps">Post-Change Err</p><p class="mono text-[18px] font-bold mt-[4px]">{{ gameState.astrocowLast ? gameState.astrocowLast.errors_after_change : '—' }}</p></div>
              <div class="tile p-[12px]"><p class="label-caps">Omitted Targets</p><p class="mono text-[18px] font-bold mt-[4px]">{{ gameState.astrocowLast ? gameState.astrocowLast.omitted_responses : '—' }}</p></div>
            </div>

            <UiSaveResult v-if="motorMessage" v-bind="motorMessage" />

            <div class="mt-auto grid gap-[12px]" :class="gameState.astrocowLast ? 'grid-cols-2' : 'grid-cols-1'">
              <button type="button" class="hud-button" @click="astrocowExpanded = true">
                <Icon name="spacescan:rocket" class="w-[17px] h-[17px]" />
                {{ gameState.astrocowLast ? 'Open / Fly AST-01 AstroCow' : 'Launch Fullscreen AST-01 AstroCow' }}
              </button>
              <button v-if="gameState.astrocowLast" type="button" class="hud-button" :disabled="astrocowSaving" @click="saveAstroCow(gameState.astrocowLast)">
                <Icon name="spacescan:bolt" class="w-[17px] h-[17px]" />
                {{ astrocowSaving ? 'Saving…' : 'Save Last Flight Telemetry' }}
              </button>
            </div>
          </div>

          <div v-else class="flex-1 min-h-0 flex flex-col gap-[12px] hud-scroll">
            <div class="tile-hi p-[16px] flex items-center gap-[14px]">
              <img :src="selectedCopilot.spriteUrl" :alt="selectedCopilot.name" class="w-[58px] h-[58px] shrink-0">
              <div class="min-w-0 flex-1">
                <p class="label-caps text-cabin-ok">4-Stage Neurocognitive Battery · Copilot {{ selectedCopilot.name }}</p>
                <h3 class="text-[18px] font-bold mt-[2px]">NeuroFit Lab · Memory, Inhibition, Reasoning &amp; Scan</h3>
                <p class="text-[12px] text-cabin-ice mt-[4px]">
                  Sequential stages measuring visuospatial retention, Stroop interference inhibition, route planning, visual scanning, and composite Focus Index.
                </p>
              </div>
              <div class="flex gap-[4px] shrink-0">
                <img v-for="m in ACTIVE_SQUAD" :key="m.id" :src="m.spriteUrl" :alt="m.name" class="w-[26px] h-[26px]">
              </div>
            </div>

            <div class="grid grid-cols-2 sm:grid-cols-4 gap-[10px]">
              <div class="tile p-[12px]"><p class="label-caps">Retention (CAB-ME)</p><p class="mono text-[18px] font-bold mt-[4px]">{{ gameState.neurofitLast ? `${gameState.neurofitLast.retention_pct}%` : '—' }}</p></div>
              <div class="tile p-[12px]"><p class="label-caps">Attention (CAB-AT)</p><p class="mono text-[18px] font-bold mt-[4px]">{{ gameState.neurofitLast ? `${gameState.neurofitLast.sustained_attention_pct}%` : '—' }}</p></div>
              <div class="tile p-[12px]"><p class="label-caps">Focus Index</p><p class="mono text-[18px] font-bold mt-[4px] text-cabin-ok">{{ gameState.neurofitLast ? `${gameState.neurofitLast.focus_index_score}/100` : '—' }}</p></div>
              <div class="tile p-[12px]"><p class="label-caps">Mean RT</p><p class="mono text-[18px] font-bold mt-[4px]">{{ gameState.neurofitLast ? `${gameState.neurofitLast.mean_reaction_ms} ms` : '—' }}</p></div>
            </div>

            <UiSaveResult v-if="motorMessage" v-bind="motorMessage" />

            <div class="mt-auto grid gap-[12px]" :class="gameState.neurofitLast ? 'grid-cols-2' : 'grid-cols-1'">
              <button type="button" class="hud-button" @click="neurofitExpanded = true">
                <Icon name="spacescan:reticle" class="w-[17px] h-[17px]" />
                {{ gameState.neurofitLast ? 'Open / Replay NeuroFit Battery' : 'Launch Fullscreen NeuroFit Battery' }}
              </button>
              <button v-if="gameState.neurofitLast" type="button" class="hud-button" :disabled="neurofitSaving" @click="saveNeuroFit(gameState.neurofitLast)">
                <Icon name="spacescan:bolt" class="w-[17px] h-[17px]" />
                {{ neurofitSaving ? 'Saving…' : 'Save Last NeuroFit Battery' }}
              </button>
            </div>
          </div>
        </div>
      </ShellHudWindow>
    </div>

    <BehavioralMatrixModal
      :expanded="matrixExpanded"
      :saving="matrixSaving"
      :saved-note="matrixSavedNote"
      @minimize="matrixExpanded = false"
      @exit="matrixExpanded = false"
      @save-matrix="saveMatrix"
    />

    <AstroCowModal
      :expanded="astrocowExpanded"
      :saving="astrocowSaving"
      :saved-note="astrocowSavedNote"
      @minimize="astrocowExpanded = false"
      @exit="astrocowExpanded = false"
      @save-session="saveAstroCow"
    />

    <NeuroFitModal
      :expanded="neurofitExpanded"
      :saving="neurofitSaving"
      :saved-note="neurofitSavedNote"
      @minimize="neurofitExpanded = false"
      @exit="neurofitExpanded = false"
      @save-session="saveNeuroFit"
    />
  </div>
</template>
