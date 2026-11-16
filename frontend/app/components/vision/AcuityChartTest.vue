<script setup lang="ts">
import { visionAudio } from '~/utils/visionAudio'
import type { AcuityEyeResult, AcuityResultsMap, BatteryStatusClass, EyeSide } from '~/utils/sandraVisualBattery'

const props = withDefaults(defineProps<{
  pxPerMm?: number
  results: AcuityResultsMap
  activeInput?: boolean
}>(), { pxPerMm: 3.78, activeInput: false })

const emit = defineEmits<{
  'open-calibration': []
  'update-eye-result': [payload: { eye: EyeSide, result: AcuityEyeResult }]
  'module-completed': [payload: { module: 'acuity', data: AcuityResultsMap }]
}>()

type Direction = 'up' | 'right' | 'down' | 'left'

const LEVELS = [
  { snellen: '20/200', decimal: '0.10', logMar: '1.00', baseMm: 14.5 },
  { snellen: '20/100', decimal: '0.20', logMar: '0.70', baseMm: 7.25 },
  { snellen: '20/60', decimal: '0.33', logMar: '0.48', baseMm: 4.35 },
  { snellen: '20/40', decimal: '0.50', logMar: '0.30', baseMm: 2.90 },
  { snellen: '20/30', decimal: '0.67', logMar: '0.18', baseMm: 2.18 },
  { snellen: '20/25', decimal: '0.80', logMar: '0.10', baseMm: 1.81 },
  { snellen: '20/20', decimal: '1.00', logMar: '0.00', baseMm: 1.45 },
  { snellen: '20/15', decimal: '1.33', logMar: '-0.12', baseMm: 1.09 },
] as const

const TRIALS_PER_LEVEL = 3
const MAX_TIME_PER_ROUND = 6.0

const gameState = ref<'idle' | 'playing' | 'finished'>('idle')
const currentEye = ref<EyeSide>('OD')
const currentLevelIdx = ref(0)
const currentTrialInLevel = ref(1)
const correctInLevel = ref(0)
const currentOrientation = ref<Direction>('up')
const streak = ref(0)
const timeLeft = ref(MAX_TIME_PER_ROUND)
const flashSuccess = ref(false)
const flashError = ref(false)
const responseTimes = ref<number[]>([])
let timerInterval: ReturnType<typeof setInterval> | null = null
let trialStartTime = 0

const finalResult = ref({
  snellen: '20/20',
  decimal: '1.00',
  logMar: '0.00',
  avgResponseTime: '1.20',
})

const currentLevelData = computed(() => LEVELS[currentLevelIdx.value] ?? LEVELS[LEVELS.length - 1]!)

const optotypeStyle = computed(() => {
  const basePixels = Math.max(16, currentLevelData.value.baseMm * props.pxPerMm * 2.2)
  const rotations: Record<Direction, string> = { up: '270deg', right: '0deg', down: '90deg', left: '180deg' }
  const strokePx = Math.max(3, Math.round(basePixels / 5))
  return {
    width: `${basePixels}px`,
    height: `${basePixels}px`,
    borderWidth: `${strokePx}px`,
    transform: `rotate(${rotations[currentOrientation.value]})`,
  }
})

const resultTier = computed(() => {
  const dec = Number.parseFloat(finalResult.value.decimal)
  if (dec >= 1.0) {
    return {
      label: 'NOMINAL / OPTIMAL',
      statusClass: 'ok' as BatteryStatusClass,
      description: 'Central visual acuity within optimal flight crew range without signs of macular compromise.',
    }
  }
  if (dec >= 0.5) {
    return {
      label: 'OBSERVATION / MILD SHIFT',
      statusClass: 'warn' as BatteryStatusClass,
      description: 'Mild reduction in visual acuity, consistent with early microgravity hyperopic shift. Correlate with Amsler Grid.',
    }
  }
  return {
    label: 'SANS ALERT / CRITICAL',
    statusClass: 'critica' as BatteryStatusClass,
    description: 'Significant decline in central visual acuity. Possible optic disc edema or choroidal folds. Notify crew physician.',
  }
})

function stopTimer() {
  if (timerInterval) {
    clearInterval(timerInterval)
    timerInterval = null
  }
}

function startTimer() {
  stopTimer()
  const interval = 100
  timerInterval = setInterval(() => {
    timeLeft.value -= interval / 1000
    if (timeLeft.value <= 0) {
      timeLeft.value = 0
      submitAnswer(null)
    }
  }, interval)
}

function nextRound() {
  const directions: Direction[] = ['up', 'right', 'down', 'left']
  const available = directions.filter(d => d !== currentOrientation.value)
  currentOrientation.value = available[Math.floor(Math.random() * available.length)]!
  timeLeft.value = MAX_TIME_PER_ROUND
  trialStartTime = performance.now()
  startTimer()
}

function startTest() {
  visionAudio.playClick()
  gameState.value = 'playing'
  currentLevelIdx.value = 0
  currentTrialInLevel.value = 1
  correctInLevel.value = 0
  streak.value = 0
  responseTimes.value = []
  nextRound()
}

function finishTest(achievedLevel: (typeof LEVELS)[number]) {
  visionAudio.playComplete()
  gameState.value = 'finished'
  const avgTime = responseTimes.value.length
    ? (responseTimes.value.reduce((a, b) => a + b, 0) / responseTimes.value.length).toFixed(2)
    : '1.00'

  finalResult.value = {
    snellen: achievedLevel.snellen,
    decimal: achievedLevel.decimal,
    logMar: achievedLevel.logMar,
    avgResponseTime: avgTime,
  }

  const dec = Number.parseFloat(achievedLevel.decimal)
  let statusClass: BatteryStatusClass = 'ok'
  let statusLabel = 'NOMINAL'
  if (dec < 0.5) {
    statusClass = 'critica'
    statusLabel = 'CRITICAL'
  }
  else if (dec < 1.0) {
    statusClass = 'warn'
    statusLabel = 'OBSERVATION'
  }

  emit('update-eye-result', {
    eye: currentEye.value,
    result: {
      ...finalResult.value,
      statusClass,
      statusLabel,
    },
  })
}

function submitAnswer(direction: Direction | null) {
  stopTimer()
  const reactionTime = (performance.now() - trialStartTime) / 1000
  responseTimes.value.push(reactionTime)
  const isCorrect = direction === currentOrientation.value

  if (isCorrect) {
    visionAudio.playSuccess()
    correctInLevel.value++
    streak.value++
    flashSuccess.value = true
    setTimeout(() => {
      flashSuccess.value = false
    }, 250)
  }
  else {
    visionAudio.playError()
    streak.value = 0
    flashError.value = true
    setTimeout(() => {
      flashError.value = false
    }, 350)
  }

  if (currentTrialInLevel.value < TRIALS_PER_LEVEL) {
    currentTrialInLevel.value++
    nextRound()
  }
  else {
    const passedLevel = correctInLevel.value >= 2
    if (passedLevel && currentLevelIdx.value < LEVELS.length - 1) {
      currentLevelIdx.value++
      currentTrialInLevel.value = 1
      correctInLevel.value = 0
      nextRound()
    }
    else {
      const finalLevel = passedLevel
        ? LEVELS[currentLevelIdx.value]!
        : LEVELS[Math.max(0, currentLevelIdx.value - 1)]!
      finishTest(finalLevel)
    }
  }
}

function resetToOtherEye() {
  visionAudio.playClick()
  if (currentEye.value === 'OD') currentEye.value = 'OS'
  else if (currentEye.value === 'OS') currentEye.value = 'OU'
  else currentEye.value = 'OD'
  gameState.value = 'idle'
}

function abortTest() {
  visionAudio.playWarning()
  stopTimer()
  gameState.value = 'idle'
}

function handleKeydown(e: KeyboardEvent) {
  if (!props.activeInput || gameState.value !== 'playing' || e.repeat) return
  if (e.key === 'ArrowUp') {
    e.preventDefault()
    submitAnswer('up')
  }
  else if (e.key === 'ArrowRight') {
    e.preventDefault()
    submitAnswer('right')
  }
  else if (e.key === 'ArrowDown') {
    e.preventDefault()
    submitAnswer('down')
  }
  else if (e.key === 'ArrowLeft') {
    e.preventDefault()
    submitAnswer('left')
  }
}

onMounted(() => {
  if (typeof window !== 'undefined') window.addEventListener('keydown', handleKeydown)
})

onBeforeUnmount(() => {
  if (typeof window !== 'undefined') window.removeEventListener('keydown', handleKeydown)
  stopTimer()
})

watch(() => props.activeInput, (active) => {
  if (!active && gameState.value === 'playing') stopTimer()
  else if (active && gameState.value === 'playing') startTimer()
})
</script>

<template>
  <div class="glass-card visual-acuity-module">
    <div class="card-header">
      <div class="card-title-group">
        <div class="brand-icon">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z" />
            <circle cx="12" cy="12" r="3" />
          </svg>
        </div>
        <div>
          <h2>Module 1: Visual Acuity Exam</h2>
          <span class="card-badge">LANDOLT C OPTOTYPE PROTOCOL · CENTRAL OCULAR FIELD</span>
        </div>
      </div>
      <div class="header-actions">
        <button type="button" class="btn btn-ghost" @click="emit('open-calibration')">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <rect x="2" y="5" width="20" height="14" rx="2" />
            <line x1="2" y1="10" x2="22" y2="10" />
          </svg>
          Calibrate Screen
        </button>
      </div>
    </div>

    <div v-if="gameState === 'idle'" class="test-setup-pane">
      <div class="instruction-box">
        <h3>Clinical & Ambient Instructions</h3>
        <p>
          This assessment uses standardized <strong>Landolt C</strong> ring optotypes.
          Indicate the opening direction of the ring using the arrow keys or the on-screen directional pad.
        </p>
        <ul class="setup-checklist">
          <li><strong>Recommended distance:</strong> 60 cm to 1 meter from display (arm length).</li>
          <li><strong>Lighting:</strong> Nominal cabin illumination with zero direct glare.</li>
          <li><strong>Correction:</strong> Wear Space Anticipation Glasses or corrective lenses if prescribed.</li>
        </ul>
      </div>

      <div class="eye-selector-group">
        <span class="selector-label">Select Eye to Evaluate:</span>
        <div class="eye-buttons">
          <button type="button" :class="['btn', 'eye-btn', currentEye === 'OD' ? 'active' : 'btn-ghost']" @click="currentEye = 'OD'">
            <span class="eye-tag">OD</span> Right Eye (Occlude OS)
          </button>
          <button type="button" :class="['btn', 'eye-btn', currentEye === 'OS' ? 'active' : 'btn-ghost']" @click="currentEye = 'OS'">
            <span class="eye-tag">OS</span> Left Eye (Occlude OD)
          </button>
          <button type="button" :class="['btn', 'eye-btn', currentEye === 'OU' ? 'active' : 'btn-ghost']" @click="currentEye = 'OU'">
            <span class="eye-tag">OU</span> Binocular (Both Eyes)
          </button>
        </div>
      </div>

      <div class="start-action-row">
        <button type="button" class="btn btn-ok start-test-btn" @click="startTest">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polygon points="5 3 19 12 5 21 5 3" />
          </svg>
          START ACUITY EVALUATION
        </button>
      </div>
    </div>

    <div v-else-if="gameState === 'playing'" class="test-active-pane">
      <div class="game-hud">
        <div class="hud-box">
          <span class="hud-caption">EYE UNDER TEST</span>
          <span class="hud-value">{{ currentEye === 'OD' ? 'RIGHT EYE' : (currentEye === 'OS' ? 'LEFT EYE' : 'BINOCULAR') }}</span>
        </div>
        <div class="hud-box">
          <span class="hud-caption">SNELLEN LEVEL</span>
          <span class="hud-value">{{ currentLevelData.snellen }} ({{ currentLevelData.decimal }})</span>
        </div>
        <div class="hud-box">
          <span class="hud-caption">STREAK / COMBO</span>
          <span class="hud-value status-ok">x{{ streak }} ★</span>
        </div>
        <div class="hud-box">
          <span class="hud-caption">TIME LIMIT</span>
          <span :class="['hud-value', timeLeft <= 2 ? 'status-critica' : '']">{{ timeLeft.toFixed(1) }}s</span>
        </div>
      </div>

      <div class="timer-bar-container">
        <div class="timer-bar" :style="{ width: `${(timeLeft / MAX_TIME_PER_ROUND) * 100}%` }" />
      </div>

      <div class="optotype-stage" :class="{ 'flash-success': flashSuccess, 'flash-error': flashError }">
        <div class="landolt-ring" :style="optotypeStyle" role="img" aria-label="Landolt C optotype" />
      </div>

      <p class="optotype-instruction">
        Use keyboard arrow keys or on-screen directional pads matching the ring opening:
      </p>

      <div class="dpad-controller">
        <div class="dpad-row">
          <button type="button" class="dpad-btn" @click="submitAnswer('up')">
            <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
              <line x1="12" y1="19" x2="12" y2="5" />
              <polyline points="5 12 12 5 19 12" />
            </svg>
            <span class="btn-subtext">UP (↑)</span>
          </button>
        </div>
        <div class="dpad-row dpad-horizontal">
          <button type="button" class="dpad-btn" @click="submitAnswer('left')">
            <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
              <line x1="19" y1="12" x2="5" y2="12" />
              <polyline points="12 19 5 12 12 5" />
            </svg>
            <span class="btn-subtext">LEFT (←)</span>
          </button>
          <div class="dpad-center-hub">
            <span>{{ currentTrialInLevel }} / {{ TRIALS_PER_LEVEL }}</span>
          </div>
          <button type="button" class="dpad-btn" @click="submitAnswer('right')">
            <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
              <line x1="5" y1="12" x2="19" y2="12" />
              <polyline points="12 5 19 12 12 19" />
            </svg>
            <span class="btn-subtext">RIGHT (→)</span>
          </button>
        </div>
        <div class="dpad-row">
          <button type="button" class="dpad-btn" @click="submitAnswer('down')">
            <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
              <line x1="12" y1="5" x2="12" y2="19" />
              <polyline points="19 12 12 19 5 12" />
            </svg>
            <span class="btn-subtext">DOWN (↓)</span>
          </button>
        </div>
      </div>

      <div class="test-footer-actions">
        <button type="button" class="btn btn-ghost" @click="abortTest">Cancel Exam</button>
      </div>
    </div>

    <div v-else class="test-results-pane">
      <div :class="['result-summary-card', resultTier.statusClass]">
        <div class="result-status-header">
          <div class="badge-status" :class="resultTier.statusClass">
            STATUS {{ resultTier.label }}
          </div>
          <span class="eye-examined-tag">EYE: {{ currentEye }}</span>
        </div>

        <div class="result-metrics-grid">
          <div class="result-metric">
            <span class="metric-label">SNELLEN ACUITY</span>
            <span class="metric-huge">{{ finalResult.snellen }}</span>
          </div>
          <div class="result-metric">
            <span class="metric-label">DECIMAL SCORE</span>
            <span class="metric-val">{{ finalResult.decimal }}</span>
          </div>
          <div class="result-metric">
            <span class="metric-label">LOGMAR SCALE</span>
            <span class="metric-val">{{ finalResult.logMar }}</span>
          </div>
          <div class="result-metric">
            <span class="metric-label">AVG RESPONSE</span>
            <span class="metric-val">{{ finalResult.avgResponseTime }}s</span>
          </div>
        </div>

        <div class="result-diagnostic-text">
          <p>{{ resultTier.description }}</p>
        </div>
      </div>

      <div class="eyes-summary-row">
        <div class="eye-record-card">
          <h4>Right Eye (OD)</h4>
          <p v-if="results.OD" class="recorded-val">
            <span>Snellen: <strong>{{ results.OD.snellen }}</strong> ({{ results.OD.decimal }})</span>
            <span class="badge-status" :class="results.OD.statusClass">{{ results.OD.statusLabel }}</span>
          </p>
          <p v-else class="unrecorded-val">Pending evaluation</p>
        </div>
        <div class="eye-record-card">
          <h4>Left Eye (OS)</h4>
          <p v-if="results.OS" class="recorded-val">
            <span>Snellen: <strong>{{ results.OS.snellen }}</strong> ({{ results.OS.decimal }})</span>
            <span class="badge-status" :class="results.OS.statusClass">{{ results.OS.statusLabel }}</span>
          </p>
          <p v-else class="unrecorded-val">Pending evaluation</p>
        </div>
      </div>

      <div class="result-actions">
        <button type="button" class="btn btn-primary" @click="resetToOtherEye">
          {{ currentEye === 'OD' ? 'Evaluate Left Eye (OS)' : 'Repeat / Switch Eye' }}
        </button>
        <button type="button" class="btn btn-ok" @click="emit('module-completed', { module: 'acuity', data: results })">
          Save &amp; Select Next Module
        </button>
      </div>
    </div>
  </div>
</template>
