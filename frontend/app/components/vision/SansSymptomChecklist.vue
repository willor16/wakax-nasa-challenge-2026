<script setup lang="ts">
import { visionAudio } from '~/utils/visionAudio'
import {
  calculateSymptomRisk,
  countAnsweredSymptoms,
  type AmslerCorrelation,
  type QuestionnaireData,
} from '~/utils/sandraVisualBattery'

const props = defineProps<{
  amslerCorrelation: AmslerCorrelation
}>()

const emit = defineEmits<{
  'module-completed': [payload: { module: 'questionnaire', data: QuestionnaireData }]
}>()

const { session } = useSandraBattery()
const form = computed(() => session.value.symptoms)

type BlockId = 'focal' | 'quality' | 'neuro' | 'surface'
type QuestionKey = keyof SymptomAnswers

const BLOCKS: { id: BlockId, shortTitle: string, title: string }[] = [
  { id: 'focal', shortTitle: '1. Focal Distance', title: 'Acuity & Focal Distance' },
  { id: 'quality', shortTitle: '2. Visual Quality', title: 'Quality & Stability' },
  { id: 'neuro', shortTitle: '3. Neuro-Ophthalmic', title: 'Neuro-Ophthalmic Signs' },
  { id: 'surface', shortTitle: '4. Ocular Surface', title: 'Cabin Ocular Surface' },
]

const BLOCK_QUESTIONS: Record<BlockId, QuestionKey[]> = {
  focal: ['q1_1_near', 'q1_2_intermediate', 'q1_3_distance', 'q1_4_glasses'],
  quality: ['q2_1_fluctuations', 'q2_2_dimLight', 'q2_3_metamorphopsia', 'q2_4_depth'],
  neuro: ['q3_1_diplopia', 'q3_2_transientLoss', 'q3_3_headache', 'q3_4_phosphenes'],
  surface: ['q4_1_dryEye'],
}

const QUESTION_BADGES: Record<QuestionKey, string> = {
  q1_1_near: '1.1',
  q1_2_intermediate: '1.2',
  q1_3_distance: '1.3',
  q1_4_glasses: '1.4',
  q2_1_fluctuations: '2.1',
  q2_2_dimLight: '2.2',
  q2_3_metamorphopsia: '2.3',
  q2_4_depth: '2.4',
  q3_1_diplopia: '3.1',
  q3_2_transientLoss: '3.2',
  q3_3_headache: '3.3',
  q3_4_phosphenes: '3.4',
  q4_1_dryEye: '4.1',
}

const TVL_TRIGGERS = [
  'Postural change / Head tilt',
  'Valsalva maneuver / Straining',
  'Exercise on cycle / resistive unit',
  'Spontaneous / No trigger',
]

const HEADACHE_LOCATIONS = [
  'Retro-ocular (Behind the globes)',
  'Frontal',
  'Holocranial (Entire head)',
  'Occipital / Neck',
]

const DROP_USAGE_OPTIONS = [
  'None used',
  '1 to 2 drops/day',
  '3 to 5 drops/day',
  'More than 5 drops/day (Intensive)',
]

const currentBlockIndex = ref(0)
const currentQuestionIndex = ref(0)
const isTransitioning = ref(false)
let autoAdvanceTimer: ReturnType<typeof setTimeout> | null = null

const currentBlock = computed(() => BLOCKS[currentBlockIndex.value]!)
const currentBlockQuestions = computed(() => BLOCK_QUESTIONS[currentBlock.value.id] ?? [])
const currentQuestionKey = computed<QuestionKey>(() => currentBlockQuestions.value[currentQuestionIndex.value] ?? 'q1_1_near')
const isLastQuestionInBlock = computed(() => currentQuestionIndex.value >= currentBlockQuestions.value.length - 1)
const completedQuestionsCount = computed(() => countAnsweredSymptoms(form.value))

function isQuestionAnswered(key: QuestionKey): boolean {
  if (key === 'q1_4_glasses') return form.value.q1_4_glasses.used !== null
  return form.value[key].experienced !== null
}

function getBlockStatus(blockId: BlockId): 'complete' | 'partial' | 'empty' {
  const keys = BLOCK_QUESTIONS[blockId]
  if (keys.every(isQuestionAnswered)) return 'complete'
  if (keys.some(isQuestionAnswered)) return 'partial'
  return 'empty'
}

function getBlockStatusLabel(blockId: BlockId): string {
  const status = getBlockStatus(blockId)
  if (status === 'complete') return 'Completed'
  if (status === 'partial') return 'In progress'
  return 'Pending'
}

const isCurrentBlockComplete = computed(() => getBlockStatus(currentBlock.value.id) === 'complete')
const isCurrentQuestionYes = computed(() => {
  const k = currentQuestionKey.value
  if (k === 'q1_4_glasses') return form.value.q1_4_glasses.used === true
  return form.value[k].experienced === true
})

function selectBlock(idx: number) {
  visionAudio.playClick()
  currentBlockIndex.value = idx
  const qList = BLOCK_QUESTIONS[BLOCKS[idx]!.id]
  const firstUnanswered = qList.findIndex(k => !isQuestionAnswered(k))
  currentQuestionIndex.value = firstUnanswered !== -1 ? firstUnanswered : 0
}

function selectQuestion(idx: number) {
  visionAudio.playClick()
  currentQuestionIndex.value = idx
}

function prevQuestion() {
  if (currentQuestionIndex.value > 0) {
    visionAudio.playClick()
    currentQuestionIndex.value--
  }
}

function nextQuestion() {
  if (currentQuestionIndex.value < currentBlockQuestions.value.length - 1) {
    visionAudio.playClick()
    currentQuestionIndex.value++
  }
}

function scheduleAdvance(delayMs: number) {
  if (currentQuestionIndex.value < currentBlockQuestions.value.length - 1) {
    isTransitioning.value = true
    if (autoAdvanceTimer) clearTimeout(autoAdvanceTimer)
    autoAdvanceTimer = setTimeout(() => {
      currentQuestionIndex.value++
      isTransitioning.value = false
    }, delayMs)
  }
  else if (getBlockStatus(currentBlock.value.id) === 'complete') {
    visionAudio.playSuccess()
  }
}

function handleAnswerNo(key: QuestionKey, subKey: 'experienced' | 'used' = 'experienced') {
  visionAudio.playClick()
  if (key === 'q1_4_glasses' && subKey === 'used') form.value.q1_4_glasses.used = false
  else if (key !== 'q1_4_glasses') form.value[key].experienced = false
  scheduleAdvance(260)
}

function handleAnswerYes(key: QuestionKey, subKey: 'experienced' | 'used' = 'experienced') {
  visionAudio.playClick()
  if (key === 'q1_4_glasses' && subKey === 'used') form.value.q1_4_glasses.used = true
  else if (key !== 'q1_4_glasses') form.value[key].experienced = true
}

function confirmAndAdvanceQuestion() {
  visionAudio.playClick()
  scheduleAdvance(200)
}

function nextBlock() {
  if (currentBlockIndex.value < BLOCKS.length - 1) {
    visionAudio.playSuccess()
    selectBlock(currentBlockIndex.value + 1)
  }
}

function prevBlock() {
  if (currentBlockIndex.value > 0) {
    visionAudio.playClick()
    selectBlock(currentBlockIndex.value - 1)
  }
}

function submitQuestionnaire() {
  visionAudio.playComplete()
  const scoreObj = calculateSymptomRisk(form.value)
  emit('module-completed', {
    module: 'questionnaire',
    data: {
      answers: form.value,
      score: scoreObj.riskScore,
      level: scoreObj.riskLevel,
      statusClass: scoreObj.statusClass,
      answeredCount: completedQuestionsCount.value,
      timestamp: new Date().toISOString(),
    },
  })
}

watch(() => props.amslerCorrelation, (newVal) => {
  if (newVal.hasMetamorphopsia && form.value.q2_3_metamorphopsia.experienced === null) {
    form.value.q2_3_metamorphopsia.experienced = true
    form.value.q2_3_metamorphopsia.eye = newVal.affectedEye !== 'None' ? newVal.affectedEye : 'Both'
  }
}, { immediate: true, deep: true })

onBeforeUnmount(() => {
  if (autoAdvanceTimer) clearTimeout(autoAdvanceTimer)
})
</script>

<template>
  <div class="glass-card questionnaire-module">
    <div class="card-header">
      <div class="card-title-group">
        <div class="brand-icon">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
            <polyline points="14 2 14 8 20 8" />
            <line x1="16" y1="13" x2="8" y2="13" />
            <line x1="16" y1="17" x2="8" y2="17" />
          </svg>
        </div>
        <div>
          <h2>Module 3: SANS Visual Symptom Questionnaire</h2>
          <span class="card-badge">SPACEFLIGHT EPIDEMIOLOGICAL SURVEILLANCE · 4 CLINICAL BLOCKS</span>
        </div>
      </div>
      <div class="header-actions">
        <span class="hud-caption">PROGRESS</span>
        <div class="progress-pill">
          <span class="pill-number">{{ completedQuestionsCount }} / 13</span>
        </div>
      </div>
    </div>

    <div class="blocks-navigation">
      <button
        v-for="(block, idx) in BLOCKS"
        :key="block.id"
        type="button"
        :class="['block-nav-btn', currentBlockIndex === idx ? 'active' : '']"
        @click="selectBlock(idx)"
      >
        <span class="block-idx">{{ idx + 1 }}</span>
        <div class="block-btn-content">
          <span class="block-btn-title">{{ block.shortTitle }}</span>
          <span class="block-btn-status" :class="getBlockStatus(block.id)">{{ getBlockStatusLabel(block.id) }}</span>
        </div>
      </button>
    </div>

    <div class="active-block-container">
      <div class="question-stepper-bar">
        <div class="stepper-info">
          <span class="stepper-tag">BLOCK {{ currentBlockIndex + 1 }} OF 4 · {{ currentBlock.title }}</span>
          <span class="stepper-progress">Question {{ currentQuestionIndex + 1 }} of {{ currentBlockQuestions.length }} in this block</span>
        </div>
        <div class="stepper-pills">
          <button
            v-for="(qKey, qIdx) in currentBlockQuestions"
            :key="qKey"
            type="button"
            :class="['stepper-pill-btn', currentQuestionIndex === qIdx ? 'active' : '', isQuestionAnswered(qKey) ? 'answered' : '']"
            @click="selectQuestion(qIdx)"
          >
            <span>{{ QUESTION_BADGES[qKey] }}</span>
            <span v-if="isQuestionAnswered(qKey)" class="pill-check">✓</span>
          </button>
        </div>
      </div>

      <div :class="['active-question-card', isTransitioning ? 'fade-transition' : '']">
        <div v-if="currentQuestionKey === 'q1_1_near'">
          <div class="q-header">
            <span class="q-badge">1.1</span>
            <h4>Have you noticed changes in near vision (reading logs, handheld screens)?</h4>
          </div>
          <div class="boolean-toggle">
            <button type="button" :class="['choice-btn', form.q1_1_near.experienced === false ? 'selected-ok' : '']" @click="handleAnswerNo('q1_1_near')">No (No changes)</button>
            <button type="button" :class="['choice-btn', form.q1_1_near.experienced === true ? 'selected-warn' : '']" @click="handleAnswerYes('q1_1_near')">Yes (Changes present)</button>
          </div>
          <div v-if="form.q1_1_near.experienced" class="sub-parameters-grid">
            <div class="param-box">
              <label>Affected Eye:</label>
              <div class="mini-choice-row">
                <button v-for="eye in ['OD', 'OS', 'Both']" :key="eye" type="button" :class="['mini-btn', form.q1_1_near.eye === eye ? 'active' : '']" @click="form.q1_1_near.eye = eye">{{ eye }}</button>
              </div>
            </div>
            <div class="param-box">
              <label>Severity (1 to 5): <strong>{{ form.q1_1_near.severity }}</strong></label>
              <input v-model.number="form.q1_1_near.severity" type="range" min="1" max="5">
            </div>
          </div>
        </div>

        <div v-else-if="currentQuestionKey === 'q1_2_intermediate'">
          <div class="q-header">
            <span class="q-badge">1.2</span>
            <h4>Have you noticed changes in intermediate vision (control panels, cockpit consoles)?</h4>
          </div>
          <div class="boolean-toggle">
            <button type="button" :class="['choice-btn', form.q1_2_intermediate.experienced === false ? 'selected-ok' : '']" @click="handleAnswerNo('q1_2_intermediate')">No (No changes)</button>
            <button type="button" :class="['choice-btn', form.q1_2_intermediate.experienced === true ? 'selected-warn' : '']" @click="handleAnswerYes('q1_2_intermediate')">Yes (Changes present)</button>
          </div>
          <div v-if="form.q1_2_intermediate.experienced" class="sub-parameters-grid">
            <div class="param-box">
              <label>Affected Eye:</label>
              <div class="mini-choice-row">
                <button v-for="eye in ['OD', 'OS', 'Both']" :key="eye" type="button" :class="['mini-btn', form.q1_2_intermediate.eye === eye ? 'active' : '']" @click="form.q1_2_intermediate.eye = eye">{{ eye }}</button>
              </div>
            </div>
            <div class="param-box">
              <label>Severity (1 to 5): <strong>{{ form.q1_2_intermediate.severity }}</strong></label>
              <input v-model.number="form.q1_2_intermediate.severity" type="range" min="1" max="5">
            </div>
          </div>
        </div>

        <div v-else-if="currentQuestionKey === 'q1_3_distance'">
          <div class="q-header">
            <span class="q-badge">1.3</span>
            <h4>Have you noticed changes in distance vision (cupola view, exterior maneuvers)?</h4>
          </div>
          <div class="boolean-toggle">
            <button type="button" :class="['choice-btn', form.q1_3_distance.experienced === false ? 'selected-ok' : '']" @click="handleAnswerNo('q1_3_distance')">No (No changes)</button>
            <button type="button" :class="['choice-btn', form.q1_3_distance.experienced === true ? 'selected-warn' : '']" @click="handleAnswerYes('q1_3_distance')">Yes (Changes present)</button>
          </div>
          <div v-if="form.q1_3_distance.experienced" class="sub-parameters-grid">
            <div class="param-box">
              <label>Affected Eye:</label>
              <div class="mini-choice-row">
                <button v-for="eye in ['OD', 'OS', 'Both']" :key="eye" type="button" :class="['mini-btn', form.q1_3_distance.eye === eye ? 'active' : '']" @click="form.q1_3_distance.eye = eye">{{ eye }}</button>
              </div>
            </div>
            <div class="param-box">
              <label>Severity (1 to 5): <strong>{{ form.q1_3_distance.severity }}</strong></label>
              <input v-model.number="form.q1_3_distance.severity" type="range" min="1" max="5">
            </div>
          </div>
        </div>

        <div v-else-if="currentQuestionKey === 'q1_4_glasses'">
          <div class="q-header">
            <span class="q-badge">1.4</span>
            <h4>Have you needed to use or step up your Space Anticipation Glasses prescription?</h4>
          </div>
          <div class="boolean-toggle">
            <button type="button" :class="['choice-btn', form.q1_4_glasses.used === false ? 'selected-ok' : '']" @click="handleAnswerNo('q1_4_glasses', 'used')">No (Not required)</button>
            <button type="button" :class="['choice-btn', form.q1_4_glasses.used === true ? 'selected-warn' : '']" @click="handleAnswerYes('q1_4_glasses', 'used')">Yes (Using prescription)</button>
          </div>
          <div v-if="form.q1_4_glasses.used" class="sub-parameters-grid">
            <div class="param-box full-width">
              <label>Diopter Power Used:</label>
              <div class="mini-choice-row">
                <button v-for="p in ['+0.75 D', '+1.00 D', '+1.50 D', '+2.00 D', '+2.50 D', '+3.00 D']" :key="p" type="button" :class="['mini-btn', form.q1_4_glasses.power === p ? 'active' : '']" @click="form.q1_4_glasses.power = p">{{ p }}</button>
              </div>
            </div>
          </div>
        </div>

        <div v-else-if="currentQuestionKey === 'q2_1_fluctuations'">
          <div class="q-header">
            <span class="q-badge">2.1</span>
            <h4>Do you experience daily visual acuity fluctuations or shifts across rest cycles?</h4>
          </div>
          <div class="boolean-toggle">
            <button type="button" :class="['choice-btn', form.q2_1_fluctuations.experienced === false ? 'selected-ok' : '']" @click="handleAnswerNo('q2_1_fluctuations')">No (Stable acuity)</button>
            <button type="button" :class="['choice-btn', form.q2_1_fluctuations.experienced === true ? 'selected-warn' : '']" @click="handleAnswerYes('q2_1_fluctuations')">Yes (Fluctuations present)</button>
          </div>
          <div v-if="form.q2_1_fluctuations.experienced" class="sub-parameters-grid">
            <div class="param-box">
              <label>Frequency:</label>
              <div class="mini-choice-row">
                <button v-for="f in ['Occasional', 'Frequent', 'Constant']" :key="f" type="button" :class="['mini-btn', form.q2_1_fluctuations.frequency === f ? 'active' : '']" @click="form.q2_1_fluctuations.frequency = f">{{ f }}</button>
              </div>
            </div>
            <div class="param-box">
              <label>Severity (1 to 5): <strong>{{ form.q2_1_fluctuations.severity }}</strong></label>
              <input v-model.number="form.q2_1_fluctuations.severity" type="range" min="1" max="5">
            </div>
          </div>
        </div>

        <div v-else-if="currentQuestionKey === 'q2_2_dimLight'">
          <div class="q-header">
            <span class="q-badge">2.2</span>
            <h4>Do you have difficulty seeing in dim light or low-contrast environments?</h4>
          </div>
          <div class="boolean-toggle">
            <button type="button" :class="['choice-btn', form.q2_2_dimLight.experienced === false ? 'selected-ok' : '']" @click="handleAnswerNo('q2_2_dimLight')">No (Normal contrast)</button>
            <button type="button" :class="['choice-btn', form.q2_2_dimLight.experienced === true ? 'selected-warn' : '']" @click="handleAnswerYes('q2_2_dimLight')">Yes (Dim-light difficulty)</button>
          </div>
          <div v-if="form.q2_2_dimLight.experienced" class="sub-parameters-grid">
            <div class="param-box full-width">
              <label>Deficit Severity (1 to 5): <strong>{{ form.q2_2_dimLight.severity }}</strong></label>
              <input v-model.number="form.q2_2_dimLight.severity" type="range" min="1" max="5">
            </div>
          </div>
        </div>

        <div v-else-if="currentQuestionKey === 'q2_3_metamorphopsia'">
          <div class="q-header">
            <span class="q-badge">2.3</span>
            <h4>Do you perceive wavy distortion in straight lines or objects (metamorphopsia)?</h4>
          </div>
          <div class="boolean-toggle">
            <button type="button" :class="['choice-btn', form.q2_3_metamorphopsia.experienced === false ? 'selected-ok' : '']" @click="handleAnswerNo('q2_3_metamorphopsia')">No (Straight lines normal)</button>
            <button type="button" :class="['choice-btn', form.q2_3_metamorphopsia.experienced === true ? 'selected-critica' : '']" @click="handleAnswerYes('q2_3_metamorphopsia')">Yes (Distortion present)</button>
          </div>
          <div v-if="form.q2_3_metamorphopsia.experienced" class="sub-parameters-grid">
            <div class="param-box">
              <label>Affected Eye:</label>
              <div class="mini-choice-row">
                <button v-for="eye in ['OD', 'OS', 'Both']" :key="eye" type="button" :class="['mini-btn', form.q2_3_metamorphopsia.eye === eye ? 'active' : '']" @click="form.q2_3_metamorphopsia.eye = eye">{{ eye }}</button>
              </div>
            </div>
            <div class="param-box">
              <label>Module 2 (Amsler Grid) Correlation:</label>
              <div v-if="amslerCorrelation.hasMetamorphopsia">
                <span class="badge-status warn">CORRELATION CONFIRMED</span>
                <p class="mt-[4px] text-[12px] text-cabin-ice">Amsler mapping detected active distortion in eye: {{ amslerCorrelation.affectedEye }}.</p>
              </div>
              <div v-else>
                <span class="badge-status ok">NO PRIOR AMSLER FINDING</span>
                <p class="mt-[4px] text-[12px] text-cabin-ice">Cross-check objectively in Module 2 Amsler Grid.</p>
              </div>
            </div>
          </div>
        </div>

        <div v-else-if="currentQuestionKey === 'q2_4_depth'">
          <div class="q-header">
            <span class="q-badge">2.4</span>
            <h4>Have you noticed alterations in depth perception (stereopsis)?</h4>
          </div>
          <div class="boolean-toggle">
            <button type="button" :class="['choice-btn', form.q2_4_depth.experienced === false ? 'selected-ok' : '']" @click="handleAnswerNo('q2_4_depth')">No (Stereopsis intact)</button>
            <button type="button" :class="['choice-btn', form.q2_4_depth.experienced === true ? 'selected-warn' : '']" @click="handleAnswerYes('q2_4_depth')">Yes (Depth deficit)</button>
          </div>
          <div v-if="form.q2_4_depth.experienced" class="sub-parameters-grid">
            <div class="param-box full-width">
              <label>Operational impact on docking or payload handling?</label>
              <div class="mini-choice-row">
                <button type="button" :class="['mini-btn', form.q2_4_depth.operationalImpact === false ? 'active' : '']" @click="form.q2_4_depth.operationalImpact = false">No operational impact</button>
                <button type="button" :class="['mini-btn', form.q2_4_depth.operationalImpact === true ? 'active-critica' : '']" @click="form.q2_4_depth.operationalImpact = true">Yes (Critical task risk)</button>
              </div>
            </div>
          </div>
        </div>

        <div v-else-if="currentQuestionKey === 'q3_1_diplopia'">
          <div class="q-header">
            <span class="q-badge">3.1</span>
            <h4>Have you experienced double vision (diplopia)?</h4>
          </div>
          <div class="boolean-toggle">
            <button type="button" :class="['choice-btn', form.q3_1_diplopia.experienced === false ? 'selected-ok' : '']" @click="handleAnswerNo('q3_1_diplopia')">No (Single binocular vision)</button>
            <button type="button" :class="['choice-btn', form.q3_1_diplopia.experienced === true ? 'selected-critica' : '']" @click="handleAnswerYes('q3_1_diplopia')">Yes (Medical Alert: Diplopia)</button>
          </div>
          <div v-if="form.q3_1_diplopia.experienced" class="sub-parameters-grid">
            <div class="param-box full-width">
              <label>Diplopia Pattern:</label>
              <div class="mini-choice-row">
                <button type="button" :class="['mini-btn', form.q3_1_diplopia.type === 'Intermittent' ? 'active' : '']" @click="form.q3_1_diplopia.type = 'Intermittent'">Intermittent</button>
                <button type="button" :class="['mini-btn', form.q3_1_diplopia.type === 'Constant' ? 'active-critica' : '']" @click="form.q3_1_diplopia.type = 'Constant'">Constant (Severe)</button>
              </div>
            </div>
          </div>
        </div>

        <div v-else-if="currentQuestionKey === 'q3_2_transientLoss'">
          <div class="q-header">
            <span class="q-badge">3.2</span>
            <h4>Have you experienced dimming or transient vision loss episodes (TVL)?</h4>
          </div>
          <div class="boolean-toggle">
            <button type="button" :class="['choice-btn', form.q3_2_transientLoss.experienced === false ? 'selected-ok' : '']" @click="handleAnswerNo('q3_2_transientLoss')">No (No transient dimming)</button>
            <button type="button" :class="['choice-btn', form.q3_2_transientLoss.experienced === true ? 'selected-critica' : '']" @click="handleAnswerYes('q3_2_transientLoss')">Yes (Alert: Transient Loss)</button>
          </div>
          <div v-if="form.q3_2_transientLoss.experienced" class="sub-parameters-grid">
            <div class="param-box">
              <label>Typical Episode Duration:</label>
              <div class="mini-choice-row">
                <button v-for="d in ['< 30 seconds', '30s – 2 minutes', '> 2 minutes']" :key="d" type="button" :class="['mini-btn', form.q3_2_transientLoss.duration === d ? 'active' : '']" @click="form.q3_2_transientLoss.duration = d">{{ d }}</button>
              </div>
            </div>
            <div class="param-box">
              <label>Primary Trigger:</label>
              <div class="mini-choice-row">
                <button v-for="tr in TVL_TRIGGERS" :key="tr" type="button" :class="['mini-btn', form.q3_2_transientLoss.trigger === tr ? 'active' : '']" @click="form.q3_2_transientLoss.trigger = tr">{{ tr }}</button>
              </div>
            </div>
          </div>
        </div>

        <div v-else-if="currentQuestionKey === 'q3_3_headache'">
          <div class="q-header">
            <span class="q-badge">3.3</span>
            <h4>Do you have headaches or retro-ocular pressure behind the eyes?</h4>
          </div>
          <div class="boolean-toggle">
            <button type="button" :class="['choice-btn', form.q3_3_headache.experienced === false ? 'selected-ok' : '']" @click="handleAnswerNo('q3_3_headache')">No (No headache or pressure)</button>
            <button type="button" :class="['choice-btn', form.q3_3_headache.experienced === true ? 'selected-warn' : '']" @click="handleAnswerYes('q3_3_headache')">Yes (Headache / Pressure)</button>
          </div>
          <div v-if="form.q3_3_headache.experienced" class="sub-parameters-grid">
            <div class="param-box">
              <label>Intensity (VAS 1 to 10): <strong>{{ form.q3_3_headache.intensity }}</strong></label>
              <input v-model.number="form.q3_3_headache.intensity" type="range" min="1" max="10">
            </div>
            <div class="param-box">
              <label>Primary Location:</label>
              <div class="mini-choice-row">
                <button v-for="loc in HEADACHE_LOCATIONS" :key="loc" type="button" :class="['mini-btn', form.q3_3_headache.location === loc ? 'active' : '']" @click="form.q3_3_headache.location = loc">{{ loc }}</button>
              </div>
            </div>
          </div>
        </div>

        <div v-else-if="currentQuestionKey === 'q3_4_phosphenes'">
          <div class="q-header">
            <span class="q-badge">3.4</span>
            <h4>Do you perceive light flashes (phosphenes) at rest with eyes closed?</h4>
          </div>
          <div class="boolean-toggle">
            <button type="button" :class="['choice-btn', form.q3_4_phosphenes.experienced === false ? 'selected-ok' : '']" @click="handleAnswerNo('q3_4_phosphenes')">No (No phosphenes)</button>
            <button type="button" :class="['choice-btn', form.q3_4_phosphenes.experienced === true ? 'selected-warn' : '']" @click="handleAnswerYes('q3_4_phosphenes')">Yes (Resting phosphenes)</button>
          </div>
          <div v-if="form.q3_4_phosphenes.experienced" class="sub-parameters-grid">
            <div class="param-box full-width">
              <label>Occurrence Frequency:</label>
              <div class="mini-choice-row">
                <button v-for="freq in ['Rare (1-2 per week)', 'Frequent (daily)', 'Continuous / Troublesome']" :key="freq" type="button" :class="['mini-btn', form.q3_4_phosphenes.frequency === freq ? 'active' : '']" @click="form.q3_4_phosphenes.frequency = freq">{{ freq }}</button>
              </div>
            </div>
          </div>
        </div>

        <div v-else>
          <div class="q-header">
            <span class="q-badge">4.1</span>
            <h4>Do you experience dry eyes, irritation, burning, or foreign-body sensation?</h4>
          </div>
          <div class="boolean-toggle">
            <button type="button" :class="['choice-btn', form.q4_1_dryEye.experienced === false ? 'selected-ok' : '']" @click="handleAnswerNo('q4_1_dryEye')">No (Healthy ocular surface)</button>
            <button type="button" :class="['choice-btn', form.q4_1_dryEye.experienced === true ? 'selected-warn' : '']" @click="handleAnswerYes('q4_1_dryEye')">Yes (Dryness / Irritation)</button>
          </div>
          <div v-if="form.q4_1_dryEye.experienced" class="sub-parameters-grid">
            <div class="param-box">
              <label>More Affected Eye:</label>
              <div class="mini-choice-row">
                <button v-for="eye in ['OD', 'OS', 'Both']" :key="eye" type="button" :class="['mini-btn', form.q4_1_dryEye.eye === eye ? 'active' : '']" @click="form.q4_1_dryEye.eye = eye">{{ eye }}</button>
              </div>
            </div>
            <div class="param-box">
              <label>Artificial Tears / Lubricant Use:</label>
              <div class="mini-choice-row">
                <button v-for="drop in DROP_USAGE_OPTIONS" :key="drop" type="button" :class="['mini-btn', form.q4_1_dryEye.dropsUsage === drop ? 'active' : '']" @click="form.q4_1_dryEye.dropsUsage = drop">{{ drop }}</button>
              </div>
            </div>
          </div>
        </div>

        <div v-if="isCurrentQuestionYes" class="sub-confirm-bar">
          <button type="button" class="btn-advance" @click="confirmAndAdvanceQuestion">
            {{ isLastQuestionInBlock ? 'Record Parameters & Complete Block ✓' : 'Save Parameters & Next Question →' }}
          </button>
        </div>

        <div class="question-inblock-nav">
          <button type="button" class="btn btn-ghost" :disabled="currentQuestionIndex === 0" @click="prevQuestion">
            ← Previous Question
          </button>
          <div class="spacer" />
          <button v-if="!isLastQuestionInBlock" type="button" class="btn btn-ghost" @click="nextQuestion">
            Next Question →
          </button>
        </div>
      </div>

      <div v-if="isCurrentBlockComplete" class="block-completion-alert">
        <div class="alert-icon-ring">✓</div>
        <div class="flex-1 min-w-0">
          <h4 class="text-[15px] font-bold">Block {{ currentBlockIndex + 1 }} Completed</h4>
          <p class="text-[12.5px] text-cabin-ice">All items in {{ currentBlock.title }} are recorded.</p>
        </div>
        <button v-if="currentBlockIndex < BLOCKS.length - 1" type="button" class="btn btn-primary" @click="nextBlock">
          Continue to {{ BLOCKS[currentBlockIndex + 1]!.shortTitle }} →
        </button>
      </div>

      <div class="block-footer-nav">
        <button v-if="currentBlockIndex > 0" type="button" class="btn btn-ghost" @click="prevBlock">
          ← Previous Block
        </button>
        <div class="spacer" />
        <button
          v-if="currentBlockIndex < BLOCKS.length - 1"
          type="button"
          :class="['btn', isCurrentBlockComplete ? 'btn-primary' : 'btn-ghost']"
          @click="nextBlock"
        >
          Next Block →
        </button>
        <button
          v-else
          type="button"
          :class="['btn', isCurrentBlockComplete ? 'btn-ok' : 'btn-primary']"
          @click="submitQuestionnaire"
        >
          Consolidate SANS Clinical Assessment
        </button>
      </div>
    </div>
  </div>
</template>
