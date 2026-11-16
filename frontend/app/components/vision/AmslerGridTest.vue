<script setup lang="ts">
import { visionAudio } from '~/utils/visionAudio'
import {
  computeAmslerEyeSummary,
  type AmslerPerceptualAnswers,
  type AmslerReportData,
  type AmslerTool,
  type BinaryEye,
} from '~/utils/sandraVisualBattery'

const emit = defineEmits<{
  'module-completed': [payload: { module: 'amsler', data: AmslerReportData }]
}>()

const { session } = useSandraBattery()

const activeEye = ref<BinaryEye>('OD')
const currentTool = ref<AmslerTool | 'eraser'>('metamorphopsia')
const isDrawing = ref(false)
const simulationMode = ref(false)
const timerSeconds = ref(30)
const timerRunning = ref(false)
const timerFinished = ref(false)
let timerInterval: ReturnType<typeof setInterval> | null = null

const currentEyeGrid = computed(() => session.value.amslerGrid[activeEye.value])
const currentExam = computed(() => session.value.amslerAnswers[activeEye.value])

const currentEyeSeverity = computed(() => {
  const summary = computeAmslerEyeSummary(currentEyeGrid.value, currentExam.value)
  if (summary.status === 'critica') {
    return {
      label: 'CRITICAL / SANS ALERT',
      statusClass: summary.status,
      affectedPercent: summary.affectedPercent,
      totalCells: summary.totalCells,
      clinicalNote: 'Central scotoma or significant macular field defect indicated. Urgent retinal OCT and flight surgeon review recommended.',
    }
  }
  if (summary.status === 'warn') {
    return {
      label: 'OBSERVATION / MILD',
      statusClass: summary.status,
      affectedPercent: summary.affectedPercent,
      totalCells: summary.totalCells,
      clinicalNote: 'Metamorphopsia or discrete paracentral distortion detected. Consistent with early choroidal folds from cephalad fluid shift.',
    }
  }
  return {
    label: 'NOMINAL / OPTIMAL',
    statusClass: summary.status,
    affectedPercent: 0,
    totalCells: 0,
    clinicalNote: 'Symmetric and sharp macular grid pattern. No evidence of central scotoma or metamorphopsia in this eye.',
  }
})

function resetFixationTimer(silent = false) {
  if (!silent) visionAudio.playClick()
  if (timerInterval) {
    clearInterval(timerInterval)
    timerInterval = null
  }
  timerSeconds.value = 30
  timerRunning.value = false
  timerFinished.value = false
}

function startFixationTimer() {
  if (timerRunning.value) return
  visionAudio.playClick()
  timerSeconds.value = 30
  timerRunning.value = true
  timerFinished.value = false
  if (timerInterval) clearInterval(timerInterval)
  timerInterval = setInterval(() => {
    if (timerSeconds.value > 1) {
      timerSeconds.value--
    }
    else {
      timerSeconds.value = 0
      timerRunning.value = false
      timerFinished.value = true
      if (timerInterval) {
        clearInterval(timerInterval)
        timerInterval = null
      }
      visionAudio.playWarning()
    }
  }, 1000)
}

function switchEye(eye: BinaryEye) {
  visionAudio.playClick()
  activeEye.value = eye
  resetFixationTimer(true)
}

function toggleEye() {
  switchEye(activeEye.value === 'OD' ? 'OS' : 'OD')
}

function setTool(tool: AmslerTool | 'eraser') {
  visionAudio.playClick()
  currentTool.value = tool
}

function clearCurrentGrid() {
  visionAudio.playWarning()
  session.value.amslerGrid[activeEye.value] = {}
}

function setQuestionAnswer<K extends keyof AmslerPerceptualAnswers>(key: K, value: boolean) {
  visionAudio.playClick()
  currentExam.value[key] = value
}

function toggleSimulation() {
  simulationMode.value = !simulationMode.value
  if (simulationMode.value) visionAudio.playWarning()
  else visionAudio.playClick()
}

function getCellCoords(event: MouseEvent | TouchEvent) {
  const target = event.currentTarget as Element | null
  const svg = target?.closest('svg')
  if (!svg) return null
  const rect = svg.getBoundingClientRect()
  const clientX = 'touches' in event && event.touches[0]
    ? event.touches[0].clientX
    : (event as MouseEvent).clientX
  const clientY = 'touches' in event && event.touches[0]
    ? event.touches[0].clientY
    : (event as MouseEvent).clientY
  const x = Math.max(0, Math.min(399, (clientX - rect.left) * (400 / rect.width)))
  const y = Math.max(0, Math.min(399, (clientY - rect.top) * (400 / rect.height)))
  return { col: Math.floor(x / 20), row: Math.floor(y / 20) }
}

function applyDrawing(event: MouseEvent | TouchEvent) {
  const coords = getCellCoords(event)
  if (!coords) return
  const key = `${coords.row}_${coords.col}`
  const targetGrid = session.value.amslerGrid[activeEye.value]
  if (currentTool.value === 'eraser') {
    if (targetGrid[key]) {
      session.value.amslerGrid[activeEye.value] = Object.fromEntries(
        Object.entries(targetGrid).filter(([k]) => k !== key),
      )
    }
  }
  else {
    targetGrid[key] = { row: coords.row, col: coords.col, type: currentTool.value }
    if (currentTool.value === 'metamorphopsia' && currentExam.value.hasWavyLines === null) {
      currentExam.value.hasWavyLines = true
    }
    if (currentTool.value === 'scotoma' && currentExam.value.hasBlankSpots === null) {
      currentExam.value.hasBlankSpots = true
    }
  }
}

function startDrawing(event: MouseEvent) {
  isDrawing.value = true
  applyDrawing(event)
}

function draw(event: MouseEvent) {
  if (isDrawing.value) applyDrawing(event)
}

function stopDrawing() {
  isDrawing.value = false
}

function handleTouchStart(event: TouchEvent) {
  isDrawing.value = true
  applyDrawing(event)
}

function handleTouchMove(event: TouchEvent) {
  if (isDrawing.value) applyDrawing(event)
}

function saveAmslerEvaluation() {
  visionAudio.playComplete()
  emit('module-completed', {
    module: 'amsler',
    data: {
      OD: computeAmslerEyeSummary(session.value.amslerGrid.OD, session.value.amslerAnswers.OD),
      OS: computeAmslerEyeSummary(session.value.amslerGrid.OS, session.value.amslerAnswers.OS),
      answers: session.value.amslerAnswers,
      gridData: session.value.amslerGrid,
    },
  })
}

onBeforeUnmount(() => {
  if (timerInterval) {
    clearInterval(timerInterval)
    timerInterval = null
  }
})
</script>

<template>
  <div class="glass-card amsler-module">
    <div class="card-header">
      <div class="card-title-group">
        <div class="brand-icon">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <rect x="3" y="3" width="18" height="18" rx="2" />
            <line x1="3" y1="9" x2="21" y2="9" />
            <line x1="3" y1="15" x2="21" y2="15" />
            <line x1="9" y1="3" x2="9" y2="21" />
            <line x1="15" y1="3" x2="15" y2="21" />
            <circle cx="12" cy="12" r="1.5" fill="currentColor" />
          </svg>
        </div>
        <div>
          <h2>Module 2: Amsler Grid (Macular SANS Evaluation)</h2>
          <span class="card-badge">METAMORPHOPSIA &amp; SCOTOMA MAPPING · CENTRAL RETINAL PROTOCOL</span>
        </div>
      </div>
      <div class="header-actions">
        <button type="button" :class="['btn', simulationMode ? 'btn-critica' : 'btn-ghost']" @click="toggleSimulation">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M2 12h20M2 12a10 10 0 0 1 20 0M2 12a10 10 0 0 0 20 0" />
          </svg>
          {{ simulationMode ? 'Disable Simulation' : 'Simulate Choroidal Folds' }}
        </button>
      </div>
    </div>

    <div class="amsler-controls-bar">
      <div class="control-group">
        <span class="control-label">Eye Tested:</span>
        <div class="eye-toggle-btn-group">
          <button type="button" :class="['btn-toggle', activeEye === 'OD' ? 'active' : '']" @click="switchEye('OD')">OD (Right Eye)</button>
          <button type="button" :class="['btn-toggle', activeEye === 'OS' ? 'active' : '']" @click="switchEye('OS')">OS (Left Eye)</button>
        </div>
      </div>
      <div class="control-group">
        <span class="control-label">Mapping Tool:</span>
        <div class="tool-btn-group">
          <button type="button" :class="['tool-btn', currentTool === 'metamorphopsia' ? 'active-warn' : '']" @click="setTool('metamorphopsia')">
            <span class="tool-dot warn" /> Metamorphopsia
          </button>
          <button type="button" :class="['tool-btn', currentTool === 'scotoma' ? 'active-critica' : '']" @click="setTool('scotoma')">
            <span class="tool-dot critica" /> Scotoma
          </button>
          <button type="button" :class="['tool-btn', currentTool === 'eraser' ? 'active' : '']" @click="setTool('eraser')">Eraser</button>
          <button type="button" class="tool-btn" @click="clearCurrentGrid">Clear Grid</button>
        </div>
      </div>
    </div>

    <div class="amsler-workspace-layout">
      <div class="grid-canvas-container">
        <div class="grid-helper-text">
          Focus on the central dot with one eye occluded. Paint any wavy lines or blank zones directly onto the grid.
        </div>

        <div class="amsler-timer-bar" :class="{ 'timer-state-green': timerRunning, 'timer-state-red': timerFinished }">
          <div class="timer-display-group">
            <div class="timer-info">
              <span class="timer-title">Fixation Timer (30s)</span>
              <span v-if="timerRunning" class="timer-status-text running">Fixation active: keep gaze on center dot...</span>
              <span v-else-if="timerFinished" class="timer-status-text alert">Time elapsed (30s)! Record visual findings.</span>
              <span v-else class="timer-status-text">Fixate on the central dot for 30s.</span>
            </div>
          </div>
          <div class="timer-controls-group">
            <div class="timer-countdown-badge" :class="{ 'countdown-running': timerRunning, 'countdown-finished': timerFinished }">
              {{ timerSeconds }}s
            </div>
            <button v-if="!timerRunning && !timerFinished" type="button" class="timer-btn btn-ok" @click="startFixationTimer">
              Start (30s)
            </button>
            <button v-else-if="timerRunning" type="button" class="timer-btn btn-ghost" @click="resetFixationTimer()">
              Reset
            </button>
            <button v-else type="button" class="timer-btn btn-critica" @click="startFixationTimer">
              Repeat (30s)
            </button>
          </div>
        </div>

        <div class="timer-progress-track">
          <div class="timer-progress-fill" :class="{ 'bg-ok': timerRunning, 'bg-critica': timerFinished }" :style="{ width: `${(timerSeconds / 30) * 100}%` }" />
        </div>

        <div class="amsler-frame" :class="{ 'simulated-sans': simulationMode }">
          <svg
            class="amsler-svg"
            viewBox="0 0 400 400"
            @mousedown="startDrawing"
            @mousemove="draw"
            @mouseup="stopDrawing"
            @mouseleave="stopDrawing"
            @touchstart.passive="handleTouchStart"
            @touchmove.prevent="handleTouchMove"
            @touchend="stopDrawing"
          >
            <rect width="400" height="400" class="svg-bg" />
            <g class="grid-lines" :class="{ 'warped-lines': simulationMode }">
              <line v-for="i in 21" :key="'h-' + i" x1="0" :y1="(i - 1) * 20" x2="400" :y2="(i - 1) * 20" class="svg-grid-line" />
              <line v-for="i in 21" :key="'v-' + i" :x1="(i - 1) * 20" y1="0" :x2="(i - 1) * 20" y2="400" class="svg-grid-line" />
            </g>
            <g>
              <rect
                v-for="(cell, key) in currentEyeGrid"
                :key="key"
                :x="cell.col * 20"
                :y="cell.row * 20"
                width="20"
                height="20"
                :class="['mapped-rect', cell.type]"
              />
            </g>
            <circle cx="200" cy="200" r="5" class="center-fixation-dot" />
            <circle cx="200" cy="200" r="1.5" class="center-inner-dot" />
          </svg>
        </div>

        <div class="amsler-legend">
          <div class="legend-item"><span class="legend-swatch ok" /> Nominal Grid</div>
          <div class="legend-item"><span class="legend-swatch warn" /> Metamorphopsia (Wavy)</div>
          <div class="legend-item"><span class="legend-swatch critica" /> Scotoma (Blank Spot)</div>
        </div>
      </div>

      <div>
        <div class="questions-card">
          <h3>Direct Perceptual Assessment</h3>
          <p class="questions-subtitle">Answer while maintaining gaze on the central fixation dot:</p>

          <div class="question-item">
            <span class="q-num">1</span>
            <div class="q-content">
              <p class="q-title">Can you clearly see the central fixation dot?</p>
              <div class="q-options">
                <button type="button" :class="['btn-choice', currentExam.seeCenter === true ? 'selected-ok' : '']" @click="setQuestionAnswer('seeCenter', true)">Yes (Nominal)</button>
                <button type="button" :class="['btn-choice', currentExam.seeCenter === false ? 'selected-critica' : '']" @click="setQuestionAnswer('seeCenter', false)">No (Central Scotoma)</button>
              </div>
            </div>
          </div>

          <div class="question-item">
            <span class="q-num">2</span>
            <div class="q-content">
              <p class="q-title">Are all four corners and outer borders of the grid visible?</p>
              <div class="q-options">
                <button type="button" :class="['btn-choice', currentExam.seeCorners === true ? 'selected-ok' : '']" @click="setQuestionAnswer('seeCorners', true)">Yes (Complete)</button>
                <button type="button" :class="['btn-choice', currentExam.seeCorners === false ? 'selected-critica' : '']" @click="setQuestionAnswer('seeCorners', false)">No (Field Defect)</button>
              </div>
            </div>
          </div>

          <div class="question-item">
            <span class="q-num">3</span>
            <div class="q-content">
              <p class="q-title">Do you perceive wavy, curved, or distorted grid lines?</p>
              <div class="q-options">
                <button type="button" :class="['btn-choice', currentExam.hasWavyLines === false ? 'selected-ok' : '']" @click="setQuestionAnswer('hasWavyLines', false)">No (Straight Lines)</button>
                <button type="button" :class="['btn-choice', currentExam.hasWavyLines === true ? 'selected-warn' : '']" @click="setQuestionAnswer('hasWavyLines', true)">Yes (Metamorphopsia)</button>
              </div>
            </div>
          </div>

          <div class="question-item">
            <span class="q-num">4</span>
            <div class="q-content">
              <p class="q-title">Do you notice blurry areas, holes, spots, or broken lines?</p>
              <div class="q-options">
                <button type="button" :class="['btn-choice', currentExam.hasBlankSpots === false ? 'selected-ok' : '']" @click="setQuestionAnswer('hasBlankSpots', false)">No (Continuous)</button>
                <button type="button" :class="['btn-choice', currentExam.hasBlankSpots === true ? 'selected-critica' : '']" @click="setQuestionAnswer('hasBlankSpots', true)">Yes (Scotoma)</button>
              </div>
            </div>
          </div>

          <div :class="['amsler-score-box', currentEyeSeverity.statusClass]">
            <div class="score-header">
              <span class="score-title">MACULAR DISTORTION INDEX ({{ activeEye }}):</span>
              <span class="badge-status" :class="currentEyeSeverity.statusClass">{{ currentEyeSeverity.label }}</span>
            </div>
            <div class="score-stats">
              <span>Affected Area: <strong>{{ currentEyeSeverity.affectedPercent }}%</strong></span>
              <span>Marked Cells: <strong>{{ currentEyeSeverity.totalCells }}</strong></span>
              <span>Central Involvement: <strong>{{ currentExam.seeCenter === false ? 'DETECTED' : 'NEGATIVE' }}</strong></span>
            </div>
            <p class="score-desc">{{ currentEyeSeverity.clinicalNote }}</p>
          </div>

          <div class="amsler-actions">
            <button type="button" class="btn btn-ghost" @click="toggleEye">
              {{ activeEye === 'OD' ? 'Switch to Left Eye (OS)' : 'Return to Right Eye (OD)' }}
            </button>
            <button type="button" class="btn btn-ok" @click="saveAmslerEvaluation">
              Save &amp; Select Next Module
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
