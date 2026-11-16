<script setup lang="ts">
import {
  ACTIVE_SQUAD,
  buildNeuroFitReport,
  CAMPAIGN_STAGES,
  ENDING_SPRITES,
  SQUAD_SPRITES,
  type NeuroFitReport,
  type NeuroFitStageResult,
  type SquadId,
  type StageKey,
} from '~/utils/neuroFitEngine'
import { psychAudio } from '~/utils/psychAudio'

const props = defineProps<{
  expanded: boolean
  saving?: boolean
  savedNote?: { tone: 'ok' | 'critical', title: string, text: string } | null
}>()

const emit = defineEmits<{
  minimize: []
  exit: []
  'save-session': [report: NeuroFitReport]
}>()

const { state, resetNeurofit } = usePsychGames()

type OverlayView = 'dashboard' | 'briefing' | 'stage' | 'interlude' | 'summary'
const view = ref<OverlayView>('dashboard')
const currentStageIndex = ref(0)
const isMuted = ref(psychAudio.muted)

const stageResults = ref<NeuroFitStageResult[]>([])
const finalReport = ref<NeuroFitReport | null>(state.value.neurofitLast)

const hudLevel = ref(1)
const hudScore = ref(0)
const hudTimeLeft = ref(30)
const hudTimed = ref(true)
const hudInstruction = ref('Ready to begin assessment.')
const hudTone = ref<'info' | 'ok' | 'critical'>('info')
const hudLead = ref<SquadId>('tamalito')

const seqGridSize = ref(6)
const seqOrder = ref<number[]>([])
const seqPlayerStep = ref(0)
const seqIsShowing = ref(true)
const litTile = ref<number | null>(null)
const seqWrongShake = ref(false)

const stroopWord = ref<'OPTIMAL' | 'CRITICAL' | 'NOMINAL'>('OPTIMAL')
const stroopColorTone = ref<'ok' | 'crit' | 'nom'>('ok')
const stroopCrewId = ref<SquadId>('chipilin')
const stroopIsMatch = ref(true)
const stroopShake = ref(false)
const stroopStreak = ref(0)

const expGridSize = ref(5)
const expShipPos = ref({ r: 0, c: 0 })
const expGoalPos = ref({ r: 4, c: 4 })
const expObstacles = ref<string[]>([])
const expRescues = ref<{ key: string, memberId: SquadId }[]>([])
const expRescuedKeys = ref<string[]>([])
const expCommands = ref<('UP' | 'DOWN' | 'LEFT' | 'RIGHT')[]>([])
const expExecuting = ref(false)
const expRound = ref(1)

const scanDim = ref(3)
const scanTargetId = ref<SquadId>('misi')
const scanCells = ref<{ memberId: SquadId, isTarget: boolean }[]>([])
const scanStreak = ref(0)

let timerInterval: ReturnType<typeof setInterval> | null = null
let activeTimeouts: ReturnType<typeof setTimeout>[] = []
let stageStartedAt = 0
let lastActionTime = 0
let reactionTimes: number[] = []
let correctAttempts = 0
let errorAttempts = 0
let totalAttempts = 0

const activeStage = computed(() => CAMPAIGN_STAGES[currentStageIndex.value]!)
const selectedCopilot = computed(() => SQUAD_SPRITES[state.value.neurofitCopilot])
const globalIndex = computed(() => {
  const vals = Object.values(state.value.neurofitCabMetrics)
  return vals.length ? Math.round(vals.reduce((a, b) => a + b.score, 0) / vals.length) : 428
})

const endingTier = computed(() => {
  const acc = finalReport.value?.overall_accuracy_pct ?? 0
  if (acc >= 80) return 'ok'
  if (acc >= 50) return 'warn'
  return 'crit'
})

function clearTimers() {
  if (timerInterval) {
    clearInterval(timerInterval)
    timerInterval = null
  }
  activeTimeouts.forEach(t => clearTimeout(t))
  activeTimeouts = []
}

function addTimeout(fn: () => void, ms: number) {
  const id = setTimeout(fn, ms)
  activeTimeouts.push(id)
}

function setBanner(text: string, tone: 'info' | 'ok' | 'critical', lead?: SquadId) {
  hudInstruction.value = text
  hudTone.value = tone
  if (lead) hudLead.value = lead
}

function selectCopilot(id: SquadId) {
  psychAudio.playClick()
  state.value.neurofitCopilot = id
}

function toggleAudio() {
  isMuted.value = psychAudio.toggleMute()
}

function handleResetAll() {
  clearTimers()
  resetNeurofit()
  stageResults.value = []
  finalReport.value = null
  view.value = 'dashboard'
}

function startFullSequenceMission() {
  psychAudio.playLevelUp()
  clearTimers()
  stageResults.value = []
  finalReport.value = null
  currentStageIndex.value = 0
  view.value = 'briefing'
}

function abortToDashboard() {
  clearTimers()
  psychAudio.playClick()
  view.value = 'dashboard'
}

function startCountdown(stageIndex: number) {
  if (timerInterval) clearInterval(timerInterval)
  timerInterval = setInterval(() => {
    if (!props.expanded || view.value !== 'stage') return
    hudTimeLeft.value--
    if (hudTimeLeft.value <= 0) {
      completeStage(stageIndex)
    }
  }, 1000)
}

function beginActiveStage(stageIndex: number) {
  clearTimers()
  currentStageIndex.value = stageIndex
  const meta = CAMPAIGN_STAGES[stageIndex]!
  const lvlKey = meta.key as StageKey
  hudLevel.value = state.value.neurofitLevels[lvlKey]
  hudScore.value = 0
  stageStartedAt = Date.now()
  lastActionTime = Date.now()
  reactionTimes = []
  correctAttempts = 0
  errorAttempts = 0
  totalAttempts = 0
  view.value = 'stage'

  if (meta.key === 'sequence') {
    hudTimed.value = true
    hudTimeLeft.value = 30
    startSequenceRound()
    startCountdown(0)
  }
  else if (meta.key === 'bee') {
    hudTimed.value = true
    hudTimeLeft.value = 30
    stroopStreak.value = 0
    setBanner('Verify whether the badge color matches its meaning.', 'info', 'chipilin')
    renderStroopCard()
    startCountdown(1)
  }
  else if (meta.key === 'explorer') {
    hudTimed.value = false
    expRound.value = 1
    generateExplorerBoard()
  }
  else if (meta.key === 'scan') {
    hudTimed.value = true
    hudTimeLeft.value = 30
    scanStreak.value = 0
    renderScanBoard()
    startCountdown(3)
  }
}

const SEQUENCE_TONES = [261.63, 293.66, 329.63, 392.0, 440.0, 523.25, 587.33, 659.25, 783.99]

function flashTile(idx: number, durationMs = 400) {
  litTile.value = idx
  psychAudio.playTone(SEQUENCE_TONES[idx % SEQUENCE_TONES.length], durationMs / 1000, 'sine', 0.12)
  addTimeout(() => {
    if (litTile.value === idx) litTile.value = null
  }, durationMs)
}

function startSequenceRound() {
  const totalTiles = hudLevel.value >= 3 ? 9 : 6
  seqGridSize.value = totalTiles
  const seqLen = Math.min(8, 2 + hudLevel.value)
  seqOrder.value = Array.from({ length: seqLen }, () => Math.floor(Math.random() * totalTiles))
  seqPlayerStep.value = 0
  seqIsShowing.value = true
  setBanner(`Watch the signal sequence (${seqLen} tones)…`, 'info', 'tamalito')

  const pace = Math.max(360, 640 - hudLevel.value * 35)
  seqOrder.value.forEach((tileIdx, step) => {
    addTimeout(() => {
      if (view.value !== 'stage') return
      flashTile(tileIdx, pace * 0.65)
      if (step === seqOrder.value.length - 1) {
        addTimeout(() => {
          seqIsShowing.value = false
          lastActionTime = Date.now()
          setBanner('Your turn! Tap squad tiles in the exact order.', 'info', 'tamalito')
        }, pace * 0.78)
      }
    }, 400 + step * pace)
  })
}

function handleSeqTileClick(idx: number) {
  if (seqIsShowing.value || view.value !== 'stage') return
  const now = Date.now()
  reactionTimes.push(Math.min(8000, Math.max(120, now - lastActionTime)))
  lastActionTime = now
  flashTile(idx, 220)
  totalAttempts++

  const expected = seqOrder.value[seqPlayerStep.value]
  if (idx === expected) {
    correctAttempts++
    seqPlayerStep.value++
    if (seqPlayerStep.value === seqOrder.value.length) {
      seqIsShowing.value = true
      hudScore.value += 30 * hudLevel.value
      hudLevel.value++
      psychAudio.playSuccess()
      setBanner('Sequence synchronized! Increasing complexity…', 'ok', 'tamalito')
      addTimeout(startSequenceRound, 750)
    }
  }
  else {
    errorAttempts++
    seqIsShowing.value = true
    seqWrongShake.value = true
    addTimeout(() => { seqWrongShake.value = false }, 350)
    psychAudio.playError()
    if (hudLevel.value > 1) hudLevel.value--
    setBanner('Out-of-order signal! Recalibrating sequence…', 'critical', 'tamalito')
    addTimeout(startSequenceRound, 850)
  }
}

function renderStroopCard() {
  const states: { tone: 'ok' | 'crit' | 'nom', word: 'OPTIMAL' | 'CRITICAL' | 'NOMINAL' }[] = [
    { tone: 'ok', word: 'OPTIMAL' },
    { tone: 'crit', word: 'CRITICAL' },
    { tone: 'nom', word: 'NOMINAL' },
  ]
  const crew = ACTIVE_SQUAD[Math.floor(Math.random() * ACTIVE_SQUAD.length)]!
  const badge = states[Math.floor(Math.random() * states.length)]!
  const isMatch = Math.random() < 0.5
  let word = badge.word
  if (!isMatch) {
    const others = states.filter(s => s.tone !== badge.tone)
    word = others[Math.floor(Math.random() * others.length)]!.word
  }
  stroopCrewId.value = crew.id
  stroopColorTone.value = badge.tone
  stroopWord.value = word
  stroopIsMatch.value = isMatch
  lastActionTime = Date.now()
}

function answerStroop(saysMatch: boolean) {
  if (view.value !== 'stage') return
  const rt = Math.min(8000, Math.max(120, Date.now() - lastActionTime))
  reactionTimes.push(rt)
  totalAttempts++
  if (saysMatch === stroopIsMatch.value) {
    correctAttempts++
    stroopStreak.value++
    hudScore.value += 20 + hudLevel.value * 5
    psychAudio.playSuccess()
    if (stroopStreak.value % 4 === 0) hudLevel.value++
    setBanner(`Verified in ${rt} ms! Streak ${stroopStreak.value}.`, 'ok', 'chipilin')
    renderStroopCard()
  }
  else {
    errorAttempts++
    stroopStreak.value = 0
    hudScore.value = Math.max(0, hudScore.value - 15)
    psychAudio.playError()
    stroopShake.value = true
    setBanner('Stroop interference! Check the frame & color, not the decoy word.', 'critical', 'chipilin')
    addTimeout(() => {
      stroopShake.value = false
      renderStroopCard()
    }, 300)
  }
}

function generateExplorerBoard() {
  const size = hudLevel.value >= 3 ? 6 : 5
  expGridSize.value = size
  expShipPos.value = { r: 0, c: 0 }
  expGoalPos.value = { r: size - 1, c: size - 1 }
  expCommands.value = []
  expExecuting.value = false
  expRescuedKeys.value = []

  let r = 0
  let c = 0
  const visited = new Set(['0,0'])
  const path: { r: number, c: number }[] = [{ r: 0, c: 0 }]
  while (r < size - 1 || c < size - 1) {
    const moves: { r: number, c: number }[] = []
    if (r < size - 1) moves.push({ r: r + 1, c })
    if (c < size - 1) moves.push({ r, c: c + 1 })
    if (r > 0 && Math.random() < 0.2 && !visited.has(`${r - 1},${c}`)) moves.push({ r: r - 1, c })
    if (c > 0 && Math.random() < 0.2 && !visited.has(`${r},${c - 1}`)) moves.push({ r, c: c - 1 })
    const next = moves[Math.floor(Math.random() * moves.length)]!
    r = next.r
    c = next.c
    visited.add(`${r},${c}`)
    path.push({ r, c })
  }

  const rescues: { key: string, memberId: SquadId }[] = []
  if (path.length > 3) {
    const p1 = path[Math.floor(path.length * 0.4)]!
    rescues.push({ key: `${p1.r},${p1.c}`, memberId: 'kuoki' })
  }
  if (path.length > 5) {
    const p2 = path[Math.floor(path.length * 0.72)]!
    const key2 = `${p2.r},${p2.c}`
    if (!rescues.some(x => x.key === key2)) rescues.push({ key: key2, memberId: 'misi' })
  }
  expRescues.value = rescues

  const obs: string[] = []
  const maxObs = Math.min(size * 2, 3 + hudLevel.value * 2)
  for (let rr = 0; rr < size; rr++) {
    for (let cc = 0; cc < size; cc++) {
      const k = `${rr},${cc}`
      if (!visited.has(k) && obs.length < maxObs && Math.random() < 0.55) obs.push(k)
    }
  }
  expObstacles.value = obs
  lastActionTime = Date.now()
  setBanner(`Sector ${expRound.value}/2: Plot route to rescue crewmates and reach GOAL.`, 'info', 'wakax')
}

function addExpCmd(dir: 'UP' | 'DOWN' | 'LEFT' | 'RIGHT') {
  if (expExecuting.value || expCommands.value.length >= 16) return
  psychAudio.playClick()
  expCommands.value.push(dir)
}

function clearExpCmds() {
  if (expExecuting.value) return
  psychAudio.playClick()
  expCommands.value = []
}

function runExpPlan() {
  if (expExecuting.value || expCommands.value.length === 0) return
  expExecuting.value = true
  totalAttempts++
  reactionTimes.push(Math.min(15000, Math.max(300, Date.now() - lastActionTime)))

  const curr = { r: 0, c: 0 }
  const rescued = new Set<string>()
  const cmds = [...expCommands.value]

  cmds.forEach((cmd, idx) => {
    addTimeout(() => {
      if (view.value !== 'stage') return
      if (cmd === 'UP') curr.r--
      if (cmd === 'DOWN') curr.r++
      if (cmd === 'LEFT') curr.c--
      if (cmd === 'RIGHT') curr.c++

      const key = `${curr.r},${curr.c}`
      const out = curr.r < 0 || curr.r >= expGridSize.value || curr.c < 0 || curr.c >= expGridSize.value
      const hitObs = expObstacles.value.includes(key)
      if (out || hitObs) {
        psychAudio.playError()
        errorAttempts++
        setBanner('Critical deviation! Avoid red ALERT zones and recalculate.', 'critical', 'wakax')
        expExecuting.value = false
        expCommands.value = []
        expShipPos.value = { r: 0, c: 0 }
        expRescuedKeys.value = []
        lastActionTime = Date.now()
        return
      }
      psychAudio.playTone(440 + idx * 35, 0.1, 'sine', 0.08)
      expShipPos.value = { ...curr }
      if (expRescues.value.some(x => x.key === key)) rescued.add(key)
      expRescuedKeys.value = [...rescued]

      if (idx === cmds.length - 1) {
        const atGoal = curr.r === expGoalPos.value.r && curr.c === expGoalPos.value.c
        const allRescued = rescued.size === expRescues.value.length
        if (atGoal && allRescued) {
          psychAudio.playSuccess()
          correctAttempts++
          hudScore.value += 60 + hudLevel.value * 15
          hudLevel.value++
          setBanner('Crew rescued and nominal landing at GOAL!', 'ok', 'wakax')
          addTimeout(() => {
            if (expRound.value >= 2) completeStage(2)
            else {
              expRound.value++
              generateExplorerBoard()
            }
          }, 800)
        }
        else {
          psychAudio.playError()
          errorAttempts++
          setBanner(!atGoal ? 'Did not reach the GOAL beacon.' : 'Missed rescuing a crewmate along the path.', 'critical', 'wakax')
          expExecuting.value = false
          expCommands.value = []
          expShipPos.value = { r: 0, c: 0 }
          expRescuedKeys.value = []
          lastActionTime = Date.now()
        }
      }
    }, (idx + 1) * 260)
  })
}

function renderScanBoard() {
  const dim = hudLevel.value >= 4 ? 5 : (hudLevel.value >= 2 ? 4 : 3)
  scanDim.value = dim
  const total = dim * dim
  const target = ACTIVE_SQUAD[Math.floor(Math.random() * ACTIVE_SQUAD.length)]!
  scanTargetId.value = target.id
  const distractors = ACTIVE_SQUAD.filter(m => m.id !== target.id)
  const targetIdx = Math.floor(Math.random() * total)
  scanCells.value = Array.from({ length: total }, (_, idx) => ({
    memberId: idx === targetIdx ? target.id : distractors[Math.floor(Math.random() * distractors.length)]!.id,
    isTarget: idx === targetIdx,
  }))
  lastActionTime = Date.now()
  setBanner(`Locate ${target.name} in the sensor matrix!`, 'info', 'misi')
}

function handleScanClick(isTarget: boolean) {
  if (view.value !== 'stage') return
  const rt = Math.min(8000, Math.max(120, Date.now() - lastActionTime))
  reactionTimes.push(rt)
  totalAttempts++
  if (isTarget) {
    correctAttempts++
    scanStreak.value++
    hudScore.value += 18 + hudLevel.value * 6
    if (scanStreak.value % 4 === 0) hudLevel.value++
    psychAudio.playSuccess()
    renderScanBoard()
  }
  else {
    errorAttempts++
    scanStreak.value = 0
    hudScore.value = Math.max(0, hudScore.value - 12)
    psychAudio.playError()
    setBanner('Wrong signal! Scan with precision.', 'critical', 'kuoki')
  }
}

function completeStage(stageIndex: number) {
  clearTimers()
  const meta = CAMPAIGN_STAGES[stageIndex]!
  const durationSec = Math.max(1, Math.round((Date.now() - stageStartedAt) / 1000))
  const accuracy = totalAttempts > 0 ? Math.round((correctAttempts / totalAttempts) * 100) : 0
  const avgRt = reactionTimes.length > 0
    ? Math.round(reactionTimes.reduce((a, b) => a + b, 0) / reactionTimes.length)
    : 0

  state.value.neurofitLevels[meta.key] = hudLevel.value
  const factor = totalAttempts > 0 ? Math.max(0.15, (hudScore.value / 110) * (accuracy / 100)) : 0
  const gains: Record<string, number> = {}
  Object.entries(meta.weights).forEach(([k, w]) => {
    const delta = factor > 0 ? Math.max(2, Math.round(factor * (w ?? 0) * 15)) : 0
    const metric = state.value.neurofitCabMetrics[k]
    if (metric) {
      metric.score = Math.min(800, metric.score + delta)
      gains[k] = delta
    }
  })

  stageResults.value.push({
    key: meta.key,
    title: meta.title,
    cabCode: meta.cabCode,
    cabName: meta.cabName,
    score: hudScore.value,
    accuracy,
    correct_attempts: correctAttempts,
    error_attempts: errorAttempts,
    total_attempts: totalAttempts,
    avg_reaction_ms: avgRt,
    level_reached: hudLevel.value,
    duration_sec: durationSec,
    leadCharId: meta.lead,
    gains,
  })

  if (stageIndex < CAMPAIGN_STAGES.length - 1) {
    psychAudio.playSuccess()
    view.value = 'interlude'
  }
  else {
    const report = buildNeuroFitReport(
      stageResults.value,
      state.value.neurofitCopilot,
      JSON.parse(JSON.stringify(state.value.neurofitCabMetrics)),
    )
    finalReport.value = report
    state.value.neurofitLast = report
    if (report.overall_accuracy_pct >= 80) psychAudio.playLevelUp()
    else if (report.overall_accuracy_pct >= 50) psychAudio.playSuccess()
    else psychAudio.playError()
    view.value = 'summary'
  }
}

function advanceFromInterlude() {
  psychAudio.playClick()
  currentStageIndex.value++
  view.value = 'briefing'
}

const lastStageResult = computed(() => stageResults.value.at(-1) ?? null)

function explorerDirArrow(cmd: 'UP' | 'DOWN' | 'LEFT' | 'RIGHT') {
  return { UP: '↑', DOWN: '↓', LEFT: '←', RIGHT: '→' }[cmd]
}

function handleMinimize() {
  clearTimers()
  emit('minimize')
}

function handleExit() {
  clearTimers()
  emit('exit')
}

watch(() => props.expanded, (open) => {
  if (open && view.value === 'stage' && hudTimed.value && !timerInterval && hudTimeLeft.value > 0) {
    startCountdown(currentStageIndex.value)
  }
  else if (!open) {
    clearTimers()
  }
})

onBeforeUnmount(() => clearTimers())
</script>

<template>
  <Teleport v-if="expanded" to="body">
    <div class="psych-battery-overlay" role="dialog" aria-modal="true" aria-label="NeuroFit Lab Cognitive Battery">
      <header class="psych-overlay-header">
        <div class="max-w-[1280px] mx-auto flex flex-wrap items-center justify-between gap-[12px]">
          <div class="flex items-center gap-[12px]">
            <img :src="selectedCopilot.spriteUrl" :alt="selectedCopilot.name" class="w-[38px] h-[38px]">
            <div>
              <p class="label-caps text-cabin-ok">NeuroFit Lab · 4-Stage Cognitive Battery</p>
              <p class="text-[14px] font-bold">Copilot: {{ selectedCopilot.name }} · Composite Index {{ globalIndex }} / 800</p>
            </div>
          </div>

          <div class="flex flex-wrap items-center gap-[8px]">
            <button type="button" class="px-[10px] py-[6px] rounded-[4px] border border-cabin-line mono text-[11px] text-cabin-ice" @click="toggleAudio">
              {{ isMuted ? 'MUTED' : 'AUDIO HUD' }}
            </button>
            <button type="button" class="px-[12px] py-[6px] rounded-[4px] border border-cabin-line text-[12px] text-cabin-ice hover:text-cabin-text" @click="handleMinimize">
              Minimize
            </button>
            <button type="button" class="px-[12px] py-[6px] rounded-[4px] border border-cabin-crit/60 bg-cabin-crit/15 text-[12px] font-bold text-cabin-crit" @click="handleExit">
              Exit
            </button>
          </div>
        </div>
      </header>

      <div class="psych-overlay-scroll hud-scroll">
        <div class="max-w-[1100px] mx-auto">
          <div v-if="view === 'dashboard'" class="grid grid-cols-1 lg:grid-cols-12 gap-[16px]">
            <div class="lg:col-span-5 tile-hi p-[18px] flex flex-col justify-between gap-[12px]">
              <div>
                <span class="px-[10px] py-[3px] rounded-full border border-cabin-line mono text-[10.5px] font-bold text-cabin-ok">
                  4 STAGES · CAB &amp; CAT SEQUENCE
                </span>
                <h2 class="text-[20px] font-bold mt-[10px]">Full Cognitive Assessment Sequence</h2>
                <p class="text-[12.5px] text-cabin-ice mt-[8px] leading-[1.5]">
                  Complete four consecutive stages: 1. Sequence Factory (Memory), 2. Color Squad (Inhibition),
                  3. Space Explorer (Spatial Planning), and 4. Rapid Scan (Visual Perception).
                </p>
                <div class="flex flex-wrap gap-[6px] mt-[12px]">
                  <span v-for="st in CAMPAIGN_STAGES" :key="st.key" class="px-[8px] py-[3px] rounded-[4px] border border-cabin-line mono text-[10.5px] text-cabin-ice">
                    {{ st.cabCode }} · {{ st.shortTitle }}
                  </span>
                </div>
              </div>

              <div class="flex flex-col gap-[8px]">
                <button type="button" class="hud-button" @click="startFullSequenceMission">
                  Start 4-Stage Sequence Mission
                </button>
                <button type="button" class="px-[12px] py-[8px] rounded-[6px] border border-cabin-line mono text-[11px] text-cabin-ice" @click="handleResetAll">
                  Reset Battery Baseline
                </button>
              </div>
            </div>

            <div class="lg:col-span-7 flex flex-col gap-[14px]">
              <div class="tile p-[16px]">
                <p class="label-caps text-cabin-ok">Select Astronaut Copilot</p>
                <p class="text-[12px] text-cabin-ice mt-[4px]">"{{ selectedCopilot.quote }}" — {{ selectedCopilot.name }}</p>
                <div class="grid grid-cols-5 gap-[8px] mt-[12px]">
                  <button
                    v-for="member in ACTIVE_SQUAD"
                    :key="member.id"
                    type="button"
                    class="p-[8px] rounded-[8px] border flex flex-col items-center gap-[4px] transition"
                    :class="state.neurofitCopilot === member.id ? 'menu-item-active border-cabin-ok' : 'border-cabin-line hover:border-cabin-text/50'"
                    @click="selectCopilot(member.id)"
                  >
                    <img :src="member.spriteUrl" :alt="member.name" class="w-[42px] h-[42px] mascot-float">
                    <span class="text-[11px] font-bold">{{ member.name }}</span>
                  </button>
                </div>
              </div>

              <div class="tile p-[16px] grid grid-cols-2 sm:grid-cols-4 gap-[10px]">
                <div v-for="(metric, k) in state.neurofitCabMetrics" :key="k" class="tile-hi p-[10px]">
                  <span class="mono text-[10px] font-bold text-cabin-ok">{{ metric.code }}</span>
                  <p class="text-[12px] font-bold mt-[4px]">{{ metric.label }}</p>
                  <p class="mono text-[16px] font-bold mt-[4px]">{{ metric.score }} <span class="text-[10px] text-cabin-ice">/ 800</span></p>
                </div>
              </div>
            </div>
          </div>

          <div v-else-if="view === 'briefing'" class="max-w-[680px] mx-auto tile-hi p-[22px] flex flex-col gap-[14px]">
            <div class="flex items-center justify-between">
              <span class="mono text-[11px] font-bold text-cabin-ok">STAGE {{ currentStageIndex + 1 }} OF {{ CAMPAIGN_STAGES.length }}</span>
              <span class="px-[8px] py-[2px] rounded-[4px] border border-cabin-line mono text-[11px]">{{ activeStage.cabCode }} · {{ activeStage.cabName }}</span>
            </div>
            <div class="flex items-center gap-[14px]">
              <img :src="SQUAD_SPRITES[activeStage.lead].spriteUrl" :alt="SQUAD_SPRITES[activeStage.lead].name" class="w-[56px] h-[56px] mascot-float">
              <div>
                <p class="mono text-[10.5px] text-cabin-ice">{{ activeStage.catName }}</p>
                <h3 class="text-[20px] font-bold">{{ activeStage.title }}</h3>
                <p class="text-[12px] text-cabin-ice">Supervisor: {{ SQUAD_SPRITES[activeStage.lead].name }}</p>
              </div>
            </div>
            <div class="tile p-[12px] text-[12.5px] leading-[1.5]">
              <p class="label-caps text-cabin-ok">Objective</p>
              <p class="mt-[4px]">{{ activeStage.briefing.objective }}</p>
            </div>
            <div class="tile p-[12px] text-[12.5px] leading-[1.5]">
              <p class="label-caps text-cabin-ok">Controls</p>
              <p class="mt-[4px]">{{ activeStage.briefing.controls }}</p>
            </div>
            <div class="tile p-[12px] text-[12.5px] leading-[1.5]">
              <p class="label-caps text-cabin-ice">Rules</p>
              <p class="mt-[4px]">{{ activeStage.briefing.rules }}</p>
            </div>
            <div class="flex justify-between pt-[6px]">
              <button type="button" class="px-[14px] py-[9px] rounded-[6px] border border-cabin-line text-[12px]" @click="abortToDashboard">
                Back to Hub
              </button>
              <button type="button" class="px-[18px] py-[9px] rounded-[6px] border border-cabin-ok bg-cabin-ok/20 font-bold text-cabin-ok text-[13px]" @click="beginActiveStage(currentStageIndex)">
                Start Stage {{ currentStageIndex + 1 }}
              </button>
            </div>
          </div>

          <div v-else-if="view === 'stage'" class="max-w-[780px] mx-auto tile-hi overflow-hidden">
            <div class="px-[18px] py-[12px] border-b border-cabin-line flex flex-wrap items-center justify-between gap-[10px]">
              <div>
                <h3 class="text-[16px] font-bold">{{ activeStage.title }}</h3>
                <p class="mono text-[11px] text-cabin-ice">{{ activeStage.cabCode }} · {{ activeStage.cabName }}</p>
              </div>
              <div class="flex items-center gap-[14px] mono">
                <span>LVL {{ hudLevel }}</span>
                <span class="text-cabin-ok font-bold">{{ hudScore }} PTS</span>
                <span v-if="hudTimed" class="font-bold" :class="hudTimeLeft <= 8 ? 'text-cabin-crit' : 'text-cabin-text'">{{ hudTimeLeft }}s</span>
                <button type="button" class="px-[10px] py-[4px] rounded-[4px] border border-cabin-line text-[11px]" @click="abortToDashboard">
                  Abort Stage
                </button>
              </div>
            </div>

            <div class="px-[18px] py-[10px] border-b flex items-center gap-[12px]" :class="hudTone === 'ok' ? 'border-cabin-ok/60 bg-cabin-ok/10' : hudTone === 'critical' ? 'border-cabin-crit bg-cabin-crit/15' : 'border-cabin-line bg-cabin-inset'">
              <img :src="SQUAD_SPRITES[hudLead].spriteUrl" :alt="hudLead" class="w-[36px] h-[36px]">
              <p class="text-[13px] font-semibold">{{ SQUAD_SPRITES[hudLead].name }}: {{ hudInstruction }}</p>
            </div>

            <div class="p-[22px] min-h-[340px] flex items-center justify-center">
              <div v-if="activeStage.key === 'sequence'" class="grid grid-cols-3 gap-[12px] w-full max-w-[380px]" :class="{ 'animate-shake': seqWrongShake }">
                <button
                  v-for="idx in seqGridSize"
                  :key="idx - 1"
                  type="button"
                  class="tile p-[12px] rounded-[12px] flex flex-col items-center gap-[4px] transition"
                  :class="{ 'tile-lit': litTile === idx - 1 }"
                  @click="handleSeqTileClick(idx - 1)"
                >
                  <img :src="ACTIVE_SQUAD[(idx - 1) % ACTIVE_SQUAD.length]!.spriteUrl" :alt="ACTIVE_SQUAD[(idx - 1) % ACTIVE_SQUAD.length]!.name" class="w-[52px] h-[52px]">
                  <span class="text-[11px] font-bold">{{ ACTIVE_SQUAD[(idx - 1) % ACTIVE_SQUAD.length]!.name }}</span>
                </button>
              </div>

              <div v-else-if="activeStage.key === 'bee'" class="w-full max-w-[440px] flex flex-col items-center gap-[18px]" :class="{ 'animate-shake': stroopShake }">
                <div class="tile w-full p-[22px] rounded-[14px] flex flex-col items-center gap-[14px] text-center">
                  <span class="mono text-[11px] text-cabin-ice">Telemetry Check · {{ SQUAD_SPRITES[stroopCrewId].name }}</span>
                  <img :src="SQUAD_SPRITES[stroopCrewId].spriteUrl" :alt="stroopCrewId" class="w-[72px] h-[72px] mascot-float">
                  <div
                    class="px-[22px] py-[10px] rounded-[10px] border-2 mono text-[26px] font-extrabold tracking-[0.06em]"
                    :class="stroopColorTone === 'ok' ? 'border-cabin-ok text-cabin-ok bg-cabin-ok/15' : stroopColorTone === 'crit' ? 'border-cabin-crit text-cabin-crit bg-cabin-crit/15' : 'border-cabin-text text-cabin-text bg-cabin-inset'"
                  >
                    {{ stroopWord }}
                  </div>
                  <p class="text-[11.5px] text-cabin-ice">Does frame color match the word? (GREEN=OPTIMAL, RED=CRITICAL, CREAM=NOMINAL)</p>
                </div>
                <div class="grid grid-cols-2 gap-[12px] w-full">
                  <button type="button" class="py-[12px] rounded-[10px] border border-cabin-crit bg-cabin-crit/15 font-bold text-cabin-crit" @click="answerStroop(false)">
                    DECOY (Mismatch)
                  </button>
                  <button type="button" class="py-[12px] rounded-[10px] border border-cabin-ok bg-cabin-ok/20 font-bold text-cabin-ok" @click="answerStroop(true)">
                    MATCH
                  </button>
                </div>
              </div>

              <div v-else-if="activeStage.key === 'explorer'" class="w-full max-w-[440px] flex flex-col items-center gap-[14px]">
                <div class="grid gap-[6px] w-full max-w-[310px]" :class="expGridSize === 6 ? 'grid-cols-6' : 'grid-cols-5'">
                  <template v-for="r in expGridSize" :key="'r' + r">
                    <div
                      v-for="c in expGridSize"
                      :key="`${r - 1},${c - 1}`"
                      class="aspect-square rounded-[8px] border flex items-center justify-center"
                      :class="expObstacles.includes(`${r - 1},${c - 1}`) ? 'border-cabin-crit bg-cabin-crit/20' : (expShipPos.r === r - 1 && expShipPos.c === c - 1) ? 'menu-item-active border-cabin-text' : (expGoalPos.r === r - 1 && expGoalPos.c === c - 1) ? 'border-cabin-ok bg-cabin-ok/20' : 'border-cabin-line bg-cabin-inset'"
                    >
                      <span v-if="expObstacles.includes(`${r - 1},${c - 1}`)" class="mono text-[9px] font-bold text-cabin-crit">ALERT</span>
                      <img v-else-if="expShipPos.r === r - 1 && expShipPos.c === c - 1" :src="SQUAD_SPRITES.wakax.spriteUrl" alt="Wakax" class="w-[32px] h-[32px]">
                      <span v-else-if="expGoalPos.r === r - 1 && expGoalPos.c === c - 1" class="mono text-[9.5px] font-bold text-cabin-ok">GOAL</span>
                      <img
                        v-else-if="expRescues.find(x => x.key === `${r - 1},${c - 1}` && !expRescuedKeys.includes(x.key))"
                        :src="SQUAD_SPRITES[expRescues.find(x => x.key === `${r - 1},${c - 1}`)!.memberId].spriteUrl"
                        alt="Crew rescue"
                        class="w-[28px] h-[28px] mascot-float"
                      >
                    </div>
                  </template>
                </div>

                <div class="tile w-full min-h-[42px] p-[8px] flex flex-wrap items-center gap-[6px]">
                  <span v-if="expCommands.length === 0" class="text-[11.5px] text-cabin-ice mx-auto">Queue Wakax’s flight path…</span>
                  <span v-for="(cmd, i) in expCommands" :key="i" class="px-[8px] py-[2px] rounded-[4px] border border-cabin-line mono text-[12px] font-bold">
                    {{ explorerDirArrow(cmd) }}
                  </span>
                </div>

                <div class="flex flex-wrap items-center justify-center gap-[8px]">
                  <button type="button" class="px-[14px] py-[9px] rounded-[8px] border border-cabin-line mono font-bold" @click="addExpCmd('LEFT')">←</button>
                  <button type="button" class="px-[14px] py-[9px] rounded-[8px] border border-cabin-line mono font-bold" @click="addExpCmd('UP')">↑</button>
                  <button type="button" class="px-[14px] py-[9px] rounded-[8px] border border-cabin-line mono font-bold" @click="addExpCmd('DOWN')">↓</button>
                  <button type="button" class="px-[14px] py-[9px] rounded-[8px] border border-cabin-line mono font-bold" @click="addExpCmd('RIGHT')">→</button>
                  <button type="button" class="px-[12px] py-[9px] rounded-[8px] border border-cabin-crit text-cabin-crit text-[12px] font-bold" @click="clearExpCmds">Clear</button>
                  <button type="button" class="px-[16px] py-[9px] rounded-[8px] border border-cabin-ok bg-cabin-ok/20 text-cabin-ok text-[12.5px] font-bold" :disabled="expExecuting || expCommands.length === 0" @click="runExpPlan">Launch</button>
                </div>
              </div>

              <div v-else-if="activeStage.key === 'scan'" class="w-full max-w-[400px] flex flex-col items-center gap-[14px]">
                <div class="tile px-[14px] py-[8px] flex items-center gap-[10px] border-cabin-ok">
                  <span class="label-caps">Target:</span>
                  <img :src="SQUAD_SPRITES[scanTargetId].spriteUrl" :alt="scanTargetId" class="w-[34px] h-[34px]">
                  <span class="text-[13px] font-bold text-cabin-ok">{{ SQUAD_SPRITES[scanTargetId].name }}</span>
                </div>
                <div class="grid gap-[8px] w-full max-w-[330px]" :class="scanDim === 5 ? 'grid-cols-5' : scanDim === 4 ? 'grid-cols-4' : 'grid-cols-3'">
                  <button
                    v-for="(cell, idx) in scanCells"
                    :key="idx"
                    type="button"
                    class="tile aspect-square rounded-[10px] p-[6px] flex items-center justify-center hover:border-cabin-text"
                    @click="handleScanClick(cell.isTarget)"
                  >
                    <img :src="SQUAD_SPRITES[cell.memberId].spriteUrl" :alt="cell.memberId" class="w-[40px] h-[40px]">
                  </button>
                </div>
              </div>
            </div>
          </div>

          <div v-else-if="view === 'interlude' && lastStageResult" class="max-w-[540px] mx-auto tile-hi p-[22px] text-center flex flex-col items-center gap-[14px]">
            <span class="mono text-[11px] font-bold text-cabin-ok">STAGE {{ stageResults.length }} OF {{ CAMPAIGN_STAGES.length }} COMPLETE</span>
            <img :src="SQUAD_SPRITES[lastStageResult.leadCharId].spriteUrl" :alt="lastStageResult.title" class="w-[68px] h-[68px] mascot-float">
            <h3 class="text-[19px] font-bold">{{ lastStageResult.title }} · Evaluated</h3>
            <div class="grid grid-cols-2 sm:grid-cols-4 gap-[8px] w-full">
              <div class="tile p-[10px]"><p class="label-caps">Score</p><p class="mono font-bold mt-[4px]">{{ lastStageResult.score }}</p></div>
              <div class="tile p-[10px]"><p class="label-caps">Accuracy</p><p class="mono font-bold mt-[4px] text-cabin-ok">{{ lastStageResult.accuracy }}%</p></div>
              <div class="tile p-[10px]"><p class="label-caps">Hits / Err</p><p class="mono font-bold mt-[4px]">{{ lastStageResult.correct_attempts }}/{{ lastStageResult.error_attempts }}</p></div>
              <div class="tile p-[10px]"><p class="label-caps">Avg RT</p><p class="mono font-bold mt-[4px]">{{ lastStageResult.avg_reaction_ms || '—' }} ms</p></div>
            </div>
            <button type="button" class="hud-button" @click="advanceFromInterlude">
              View Stage {{ stageResults.length + 1 }} Briefing
            </button>
          </div>

          <div v-else-if="view === 'summary' && finalReport" class="tile-hi p-[22px] flex flex-col gap-[16px]">
            <div class="flex flex-wrap items-center justify-between gap-[10px]">
              <div>
                <p class="label-caps text-cabin-ok">Cognitive Assessment Report · Complete</p>
                <h3 class="text-[20px] font-bold">Focus Index {{ finalReport.focus_index_score }} / 100 · ECG {{ finalReport.ecg_index }} / 800</h3>
              </div>
              <UiStatusPill :tone="endingTier === 'ok' ? 'ok' : endingTier === 'warn' ? 'watch' : 'critical'">
                {{ finalReport.overall_accuracy_pct }}% ACCURACY
              </UiStatusPill>
            </div>

            <div class="tile p-[14px] flex items-center justify-center gap-[10px]">
              <template v-if="endingTier === 'ok'">
                <img v-for="m in ACTIVE_SQUAD" :key="m.id" :src="m.spriteUrl" :alt="m.name" class="w-[44px] h-[44px] mascot-float">
                <img :src="SQUAD_SPRITES.tayuyo.spriteUrl" alt="Tayuyo" class="w-[58px] h-[58px] mascot-float">
                <img :src="ENDING_SPRITES.cakeUrl" alt="Space cake reward" class="w-[54px] h-[54px] mascot-float">
              </template>
              <template v-else-if="endingTier === 'warn'">
                <img :src="SQUAD_SPRITES.tayuyo.spriteUrl" alt="Tayuyo" class="w-[58px] h-[58px]">
                <img :src="ENDING_SPRITES.asteroidGrazeUrl" alt="Asteroid graze" class="w-[48px] h-[48px]">
                <p class="text-[12.5px] text-cabin-ice">Orbital Graze · Reach 80% accuracy for full optimal clearance.</p>
              </template>
              <template v-else>
                <img :src="SQUAD_SPRITES.tayuyo.spriteUrl" alt="Tayuyo" class="w-[58px] h-[58px]">
                <img :src="ENDING_SPRITES.asteroidImpactUrl" alt="Asteroid impact" class="w-[48px] h-[48px]">
                <p class="text-[12.5px] text-cabin-crit">Impact Alert · Rest and recalibrate attention before duty shifts.</p>
              </template>
            </div>

            <div class="grid grid-cols-2 sm:grid-cols-5 gap-[10px]">
              <div class="tile p-[10px]"><p class="label-caps">Retention (CAB-ME)</p><p class="mono text-[17px] font-bold mt-[4px]">{{ finalReport.retention_pct }}%</p></div>
              <div class="tile p-[10px]"><p class="label-caps">Attention (CAB-AT)</p><p class="mono text-[17px] font-bold mt-[4px]">{{ finalReport.sustained_attention_pct }}%</p></div>
              <div class="tile p-[10px]"><p class="label-caps">Reasoning (CAB-RS)</p><p class="mono text-[17px] font-bold mt-[4px]">{{ finalReport.spatial_reasoning_pct }}%</p></div>
              <div class="tile p-[10px]"><p class="label-caps">Perception (CAB-PC)</p><p class="mono text-[17px] font-bold mt-[4px]">{{ finalReport.visual_perception_pct }}%</p></div>
              <div class="tile p-[10px]"><p class="label-caps">Mean Latency</p><p class="mono text-[17px] font-bold mt-[4px]">{{ finalReport.mean_reaction_ms }} ms</p></div>
            </div>

            <div class="tile p-[12px] text-[12.5px] leading-[1.5]">
              <p>{{ finalReport.diagnostic.narrative }}</p>
              <p class="mono text-[11px] text-cabin-ok mt-[6px]">Strongest: {{ finalReport.diagnostic.strengthLabel }}</p>
              <p class="mono text-[11px] text-cabin-ice">Watch Area: {{ finalReport.diagnostic.weaknessLabel }}</p>
            </div>

            <UiSaveResult v-if="savedNote" :tone="savedNote.tone" :title="savedNote.title" :text="savedNote.text" />

            <div class="flex flex-wrap justify-between gap-[10px]">
              <button type="button" class="px-[16px] py-[10px] rounded-[6px] border border-cabin-line mono text-[12px]" @click="startFullSequenceMission">
                Replay Full Assessment (4/4)
              </button>
              <button type="button" class="px-[18px] py-[10px] rounded-[6px] border border-cabin-ok bg-cabin-ok/20 font-bold text-cabin-ok mono text-[12px]" :disabled="saving" @click="emit('save-session', finalReport)">
                {{ saving ? 'Saving…' : 'Save Cognitive Battery' }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>
