<script setup lang="ts">
import AcuityChartTest from '~/components/vision/AcuityChartTest.vue'
import AmslerGridTest from '~/components/vision/AmslerGridTest.vue'
import SansSymptomChecklist from '~/components/vision/SansSymptomChecklist.vue'
import { visionAudio } from '~/utils/visionAudio'
import {
  buildSandraPayload,
  computeAmslerEyeSummary,
  computeConsolidatedSANS,
  countAnsweredSymptoms,
  EXAM_MILESTONES,
  hasAnySandraData,
  type AcuityEyeResult,
  type AmslerCorrelation,
  type EyeSide,
  type SandraSessionState,
} from '~/utils/sandraVisualBattery'

const props = defineProps<{
  expanded: boolean
  saving?: boolean
}>()

const emit = defineEmits<{
  minimize: []
  exit: []
  'save-now': []
  reset: []
}>()

const { session } = useSandraBattery()

type BatteryTab = 'menu' | 'acuity' | 'symptoms' | 'amsler'

const activeTab = ref<BatteryTab>('menu')
const showCalibrationModal = ref(false)
const showReportModal = ref(false)
const isMuted = ref(visionAudio.muted)
const cardPixelWidth = ref(Math.round(85.60 * session.value.pxPerMm))

const currentPxPerMm = computed(() => cardPixelWidth.value / 85.60)
const odAmslerSummary = computed(() => computeAmslerEyeSummary(session.value.amslerGrid.OD, session.value.amslerAnswers.OD))
const osAmslerSummary = computed(() => computeAmslerEyeSummary(session.value.amslerGrid.OS, session.value.amslerAnswers.OS))
const answeredSymptomCount = computed(() => countAnsweredSymptoms(session.value.symptoms))
const overallSANS = computed(() => computeConsolidatedSANS(session.value))
const reportPreview = computed(() => buildSandraPayload(session.value).sandra_test)
const canSave = computed(() => hasAnySandraData(session.value))

const amslerCorrelationData = computed<AmslerCorrelation>(() => {
  const od = odAmslerSummary.value
  const os = osAmslerSummary.value
  const hasODMeta = od.hasMetamorphopsia
  const hasOSMeta = os.hasMetamorphopsia
  return {
    hasMetamorphopsia: hasODMeta || hasOSMeta,
    affectedEye: (hasODMeta && hasOSMeta) ? 'Both' : (hasODMeta ? 'OD' : (hasOSMeta ? 'OS' : 'None')),
    odSeverity: od,
    osSeverity: os,
  }
})

const globalSANSStatus = computed(() => {
  const s = overallSANS.value
  if (s.statusClass === 'critica') return { label: 'SANS ALERT', statusClass: 'status-critica' }
  if (s.statusClass === 'warn') return { label: 'OBSERVATION', statusClass: 'status-warn' }
  return { label: 'NOMINAL', statusClass: 'status-ok' }
})

function selectTab(tab: BatteryTab) {
  visionAudio.playClick()
  activeTab.value = tab
}

function toggleAudio() {
  isMuted.value = visionAudio.toggleMute()
}

function setPreset(px: number) {
  visionAudio.playClick()
  cardPixelWidth.value = px
}

function openCalibration() {
  visionAudio.playClick()
  cardPixelWidth.value = Math.round(85.60 * session.value.pxPerMm)
  showCalibrationModal.value = true
}

function saveCalibration() {
  visionAudio.playSuccess()
  session.value.pxPerMm = currentPxPerMm.value
  showCalibrationModal.value = false
}

function handleUpdateEyeResult(payload: { eye: EyeSide, result: AcuityEyeResult }) {
  session.value.acuity[payload.eye] = payload.result
}

function handleModuleCompleted(payload: { module: string, data: unknown }) {
  if (payload.module === 'acuity') {
    visionAudio.playSuccess()
    activeTab.value = 'menu'
  }
  else if (payload.module === 'amsler') {
    visionAudio.playSuccess()
    session.value.amslerSummary = {
      OD: odAmslerSummary.value,
      OS: osAmslerSummary.value,
      answers: session.value.amslerAnswers,
      gridData: session.value.amslerGrid,
    }
    activeTab.value = 'menu'
  }
  else if (payload.module === 'questionnaire') {
    session.value.questionnaire = payload.data as SandraSessionState['questionnaire']
    showReportModal.value = true
  }
}

function applyAndMinimize() {
  visionAudio.playComplete()
  showReportModal.value = false
  emit('minimize')
}

function saveExamNow() {
  visionAudio.playComplete()
  showReportModal.value = false
  emit('save-now')
}

function printReport() {
  visionAudio.playClick()
  if (typeof window !== 'undefined') window.print()
}

function handleKeydown(event: KeyboardEvent) {
  if (!props.expanded || event.key !== 'Escape') return
  if (showCalibrationModal.value) {
    showCalibrationModal.value = false
    return
  }
  if (showReportModal.value) {
    showReportModal.value = false
    return
  }
  emit('minimize')
}

onMounted(() => {
  if (typeof document !== 'undefined') document.addEventListener('keydown', handleKeydown)
})

onBeforeUnmount(() => {
  if (typeof document !== 'undefined') document.removeEventListener('keydown', handleKeydown)
})
</script>

<template>
  <Teleport v-if="expanded" to="body">
    <div class="sandra-battery-overlay" role="dialog" aria-modal="true" aria-label="SANS Interactive Visual Battery">
      <header class="app-header">
        <div class="header-container">
          <div class="brand-badge">
            <div class="brand-icon">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="10" />
                <path d="m4.93 4.93 4.24 4.24" />
                <path d="m14.83 9.17 4.24-4.24" />
                <path d="m14.83 14.83 4.24 4.24" />
                <path d="m9.17 14.83-4.24 4.24" />
                <circle cx="12" cy="12" r="4" />
              </svg>
            </div>
            <div>
              <p class="text-[13px] font-bold tracking-[0.05em] uppercase text-cabin-text">
                Integrated Visual &amp; Macular Assessment
              </p>
              <div class="flex flex-wrap gap-[4px] mt-[4px]">
                <button
                  v-for="m in EXAM_MILESTONES"
                  :key="m"
                  type="button"
                  class="px-[8px] py-[2px] rounded-[3px] mono text-[10px] border transition"
                  :class="session.milestone === m ? 'menu-item-active text-cabin-text' : 'border-cabin-line text-cabin-muted hover:text-cabin-text'"
                  @click="session.milestone = m; visionAudio.playClick()"
                >
                  {{ m }}
                </button>
              </div>
            </div>
          </div>

          <div class="header-metrics">
            <div class="hud-item">
              <span class="hud-label">SANS STATUS</span>
              <span :class="['hud-value', globalSANSStatus.statusClass]">{{ globalSANSStatus.label }}</span>
            </div>
            <button type="button" class="btn btn-ghost sound-toggle-btn" @click="toggleAudio">
              {{ isMuted ? 'MUTED' : 'AUDIO HUD' }}
            </button>
            <button type="button" class="btn btn-primary" @click="showReportModal = true">
              Clinical Report
            </button>
            <button type="button" class="btn btn-ghost" title="Minimize while keeping progress" @click="emit('minimize')">
              Minimize
            </button>
            <button type="button" class="btn btn-critica" title="Exit to Ocular Capture" @click="emit('exit')">
              Exit
            </button>
          </div>
        </div>
      </header>

      <div class="px-[24px] pt-[10px] shrink-0">
        <div class="max-w-[1240px] mx-auto flex flex-wrap items-center gap-[8px]">
          <button
            type="button"
            class="px-[12px] py-[6px] rounded-[4px] mono text-[11px] font-semibold border transition"
            :class="activeTab === 'menu' ? 'menu-item-active text-cabin-text' : 'border-cabin-line text-cabin-ice hover:text-cabin-text'"
            @click="selectTab('menu')"
          >
            Module Menu
          </button>
          <button
            type="button"
            class="px-[12px] py-[6px] rounded-[4px] mono text-[11px] font-semibold border transition"
            :class="activeTab === 'acuity' ? 'menu-item-active text-cabin-text' : 'border-cabin-line text-cabin-ice hover:text-cabin-text'"
            @click="selectTab('acuity')"
          >
            1 · Visual Acuity
          </button>
          <button
            type="button"
            class="px-[12px] py-[6px] rounded-[4px] mono text-[11px] font-semibold border transition"
            :class="activeTab === 'amsler' ? 'menu-item-active text-cabin-text' : 'border-cabin-line text-cabin-ice hover:text-cabin-text'"
            @click="selectTab('amsler')"
          >
            2 · Amsler Grid
          </button>
          <button
            type="button"
            class="px-[12px] py-[6px] rounded-[4px] mono text-[11px] font-semibold border transition"
            :class="activeTab === 'symptoms' ? 'menu-item-active text-cabin-text' : 'border-cabin-line text-cabin-ice hover:text-cabin-text'"
            @click="selectTab('symptoms')"
          >
            3 · Symptom Questionnaire ({{ answeredSymptomCount }}/13)
          </button>
        </div>
      </div>

      <main class="sandra-main-scroll hud-scroll">
        <div class="main-viewport">
          <div v-show="activeTab === 'menu'" class="modules-menu-view">
            <div class="glass-card menu-selection-card">
              <div class="menu-selection-list">
                <button type="button" class="menu-module-item" @click="selectTab('acuity')">
                  <span class="module-item-indicator">
                    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <circle cx="12" cy="12" r="3" />
                      <path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z" />
                    </svg>
                  </span>
                  <div class="flex-1 min-w-0">
                    <span class="module-item-title block">Visual Acuity (Landolt C)</span>
                    <span class="mono text-[11px] text-cabin-ice">
                      OD: {{ session.acuity.OD?.snellen ?? 'Pending' }} · OS: {{ session.acuity.OS?.snellen ?? 'Pending' }}
                    </span>
                  </div>
                  <span class="module-item-chevron">→</span>
                </button>

                <button type="button" class="menu-module-item" @click="selectTab('amsler')">
                  <span class="module-item-indicator">
                    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <rect x="3" y="3" width="18" height="18" rx="2" />
                      <line x1="3" y1="9" x2="21" y2="9" />
                      <line x1="3" y1="15" x2="21" y2="15" />
                      <line x1="9" y1="3" x2="9" y2="21" />
                      <line x1="15" y1="3" x2="15" y2="21" />
                    </svg>
                  </span>
                  <div class="flex-1 min-w-0">
                    <span class="module-item-title block">Amsler Grid (Macular Distortion)</span>
                    <span class="mono text-[11px] text-cabin-ice">
                      OD: {{ odAmslerSummary.totalCells }} cells · OS: {{ osAmslerSummary.totalCells }} cells
                    </span>
                  </div>
                  <span class="module-item-chevron">→</span>
                </button>

                <button type="button" class="menu-module-item" @click="selectTab('symptoms')">
                  <span class="module-item-indicator">
                    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                      <polyline points="14 2 14 8 20 8" />
                      <line x1="16" y1="13" x2="8" y2="13" />
                      <line x1="16" y1="17" x2="8" y2="17" />
                    </svg>
                  </span>
                  <div class="flex-1 min-w-0">
                    <span class="module-item-title block">Symptoms Questionnaire</span>
                    <span class="mono text-[11px] text-cabin-ice">
                      {{ answeredSymptomCount }} / 13 questions answered
                    </span>
                  </div>
                  <span class="module-item-chevron">→</span>
                </button>
              </div>

              <div class="mt-[18px] pt-[14px] border-t border-cabin-line flex flex-wrap items-center justify-between gap-[10px]">
                <button type="button" class="btn btn-ghost" @click="emit('reset')">
                  Reset Session
                </button>
                <div class="flex items-center gap-[8px] flex-wrap">
                  <span v-if="!canSave" class="mono text-[11px] text-cabin-muted">
                    Complete at least one module to enable saving
                  </span>
                  <button type="button" class="btn btn-primary" @click="showReportModal = true">
                    Review Summary &amp; Apply
                  </button>
                  <button type="button" class="btn btn-ok" :disabled="saving || !canSave" @click="emit('save-now')">
                    {{ saving ? 'Saving…' : 'Save Exam Now' }}
                  </button>
                </div>
              </div>
            </div>
          </div>

          <AcuityChartTest
            v-show="activeTab === 'acuity'"
            :px-per-mm="session.pxPerMm"
            :results="session.acuity"
            :active-input="expanded && activeTab === 'acuity' && !showCalibrationModal && !showReportModal"
            @open-calibration="openCalibration"
            @update-eye-result="handleUpdateEyeResult"
            @module-completed="handleModuleCompleted"
          />

          <AmslerGridTest
            v-show="activeTab === 'amsler'"
            @module-completed="handleModuleCompleted"
          />

          <SansSymptomChecklist
            v-show="activeTab === 'symptoms'"
            :amsler-correlation="amslerCorrelationData"
            @module-completed="handleModuleCompleted"
          />
        </div>
      </main>

      <div v-if="showCalibrationModal" class="modal-backdrop" @click.self="showCalibrationModal = false">
        <div class="modal-content calibration-modal">
          <div class="card-header">
            <div class="card-title-group">
              <div>
                <h3>Screen Scale Calibration (Optometry)</h3>
                <span class="card-badge">STANDARD REFERENCE ID-1 CARD (85.60 mm)</span>
              </div>
            </div>
            <button type="button" class="btn btn-ghost" @click="showCalibrationModal = false">✕</button>
          </div>
          <p class="text-[13px] text-cabin-ice leading-[1.5]">
            To match the angular aperture of Landolt C optotypes to 5 arcminutes at arm distance, hold a standard card
            (85.6 mm wide) against the display and align the rectangle below using the slider.
          </p>
          <div class="card-visual-wrapper">
            <div class="card-visual" :style="{ width: `${cardPixelWidth}px` }">
              <div class="card-chip" />
              <div class="card-visual-text">CALIBRATION CARD (85.6 mm)</div>
              <div class="card-visual-px">{{ Math.round(cardPixelWidth) }} px ({{ currentPxPerMm.toFixed(2) }} px/mm)</div>
            </div>
          </div>
          <div>
            <label class="block mono text-[12px] text-cabin-muted mb-[6px]">Adjust Screen Card Width (px):</label>
            <input v-model.number="cardPixelWidth" type="range" min="200" max="500" step="1">
          </div>
          <div class="presets-row">
            <button type="button" class="btn btn-ghost" @click="setPreset(320)">Laptop 13" - 15"</button>
            <button type="button" class="btn btn-ghost" @click="setPreset(350)">Cabin Monitor 24"</button>
            <button type="button" class="btn btn-ghost" @click="setPreset(380)">Crew Tablet 10"</button>
          </div>
          <div class="modal-footer">
            <button type="button" class="btn btn-ghost" @click="showCalibrationModal = false">Cancel</button>
            <button type="button" class="btn btn-ok" @click="saveCalibration">Save Calibration</button>
          </div>
        </div>
      </div>

      <div v-if="showReportModal" class="modal-backdrop" @click.self="showReportModal = false">
        <div class="modal-content">
          <div class="card-header">
            <div class="card-title-group">
              <div>
                <h3>Aerospace SANS Clinical Summary</h3>
                <span class="card-badge">{{ session.milestone }} · MULTIMODAL OCULAR CONSOLIDATION</span>
              </div>
            </div>
            <button type="button" class="btn btn-ghost" @click="showReportModal = false">✕</button>
          </div>

          <div :class="['triage-banner', overallSANS.statusClass]">
            <div class="flex flex-wrap items-center justify-between gap-[8px] mb-[6px]">
              <span class="mono text-[11px] text-cabin-muted">CONSOLIDATED ASSESSMENT</span>
              <div class="flex items-center gap-[10px]">
                <span class="badge-status" :class="overallSANS.statusClass">{{ overallSANS.level }}</span>
                <span class="mono text-[13px] font-bold">Risk Score: {{ overallSANS.score }} / 100</span>
              </div>
            </div>
            <p class="text-[13px] text-cabin-text">{{ overallSANS.directive }}</p>
          </div>

          <div class="report-section">
            <h4 class="text-[13px] font-bold uppercase mb-[10px]">1 · Snellen Visual Acuity (OD / OS)</h4>
            <div class="grid-2">
              <div class="report-subcard">
                <span class="mono text-[11px] text-cabin-muted">Right Eye (OD)</span>
                <template v-if="session.acuity.OD">
                  <span class="mono text-[20px] font-extrabold">{{ session.acuity.OD.snellen }}</span>
                  <span class="mono text-[11px] text-cabin-ice">Decimal {{ session.acuity.OD.decimal }} · LogMAR {{ session.acuity.OD.logMar }}</span>
                  <span class="badge-status self-start mt-[4px]" :class="session.acuity.OD.statusClass">{{ session.acuity.OD.statusLabel }}</span>
                </template>
                <span v-else class="text-[12px] text-cabin-dim italic">Not evaluated in this session</span>
              </div>
              <div class="report-subcard">
                <span class="mono text-[11px] text-cabin-muted">Left Eye (OS)</span>
                <template v-if="session.acuity.OS">
                  <span class="mono text-[20px] font-extrabold">{{ session.acuity.OS.snellen }}</span>
                  <span class="mono text-[11px] text-cabin-ice">Decimal {{ session.acuity.OS.decimal }} · LogMAR {{ session.acuity.OS.logMar }}</span>
                  <span class="badge-status self-start mt-[4px]" :class="session.acuity.OS.statusClass">{{ session.acuity.OS.statusLabel }}</span>
                </template>
                <span v-else class="text-[12px] text-cabin-dim italic">Not evaluated in this session</span>
              </div>
            </div>
          </div>

          <div class="report-section">
            <h4 class="text-[13px] font-bold uppercase mb-[10px]">2 · Amsler Grid (Metamorphopsia &amp; Scotomas)</h4>
            <div class="grid-2">
              <div class="report-subcard">
                <span class="mono text-[11px] text-cabin-muted">Amsler OD (Right Eye)</span>
                <span class="mono text-[19px] font-extrabold">{{ odAmslerSummary.affectedPercent }}%</span>
                <span class="mono text-[11px] text-cabin-ice">Altered cells: {{ odAmslerSummary.totalCells }} / 400</span>
                <span class="badge-status self-start mt-[4px]" :class="odAmslerSummary.status">
                  {{ odAmslerSummary.hasScotoma ? 'SCOTOMA' : (odAmslerSummary.hasMetamorphopsia ? 'METAMORPHOPSIA' : 'NOMINAL') }}
                </span>
              </div>
              <div class="report-subcard">
                <span class="mono text-[11px] text-cabin-muted">Amsler OS (Left Eye)</span>
                <span class="mono text-[19px] font-extrabold">{{ osAmslerSummary.affectedPercent }}%</span>
                <span class="mono text-[11px] text-cabin-ice">Altered cells: {{ osAmslerSummary.totalCells }} / 400</span>
                <span class="badge-status self-start mt-[4px]" :class="osAmslerSummary.status">
                  {{ osAmslerSummary.hasScotoma ? 'SCOTOMA' : (osAmslerSummary.hasMetamorphopsia ? 'METAMORPHOPSIA' : 'NOMINAL') }}
                </span>
              </div>
            </div>
          </div>

          <div class="report-section">
            <h4 class="text-[13px] font-bold uppercase mb-[10px]">3 · SANS Epidemiological Summary</h4>
            <div>
              <div v-for="row in reportPreview.symptoms.summary_rows" :key="row.label" class="table-row">
                <span class="text-cabin-ice">{{ row.label }}</span>
                <span class="mono font-semibold" :class="row.critical ? 'text-cabin-crit' : 'text-cabin-text'">{{ row.value }}</span>
              </div>
            </div>
          </div>

          <div class="report-section">
            <h4 class="text-[13px] font-bold uppercase mb-[8px]">Clinical Directives &amp; Countermeasures</h4>
            <ul class="medical-recommendations-list">
              <li v-for="(rec, idx) in overallSANS.recommendations" :key="idx">{{ rec }}</li>
            </ul>
          </div>

          <div class="modal-footer">
            <button type="button" class="btn btn-ghost" @click="printReport">Print Log</button>
            <button type="button" class="btn btn-primary" @click="applyAndMinimize">Apply &amp; Minimize to Form</button>
            <button type="button" class="btn btn-ok" :disabled="saving || !canSave" @click="saveExamNow">
              {{ saving ? 'Saving…' : 'Save Exam Now' }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>
