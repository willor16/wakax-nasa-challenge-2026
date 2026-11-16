<script setup lang="ts">
import cowSpriteUrl from '~/assets/games/astrocow/cow-sprite.png'
import {
  evaluateBehavioralMatrix,
  MATRIX_ITEMS,
  MATRIX_SCALE_OPTIONS,
} from '~/utils/behavioralMatrix20'
import { psychAudio } from '~/utils/psychAudio'

const props = defineProps<{
  expanded: boolean
  saving?: boolean
  savedNote?: { tone: 'ok' | 'critical', title: string, text: string } | null
}>()

const emit = defineEmits<{
  minimize: []
  exit: []
  'save-matrix': [answers: number[]]
}>()

const { state, resetMatrix } = usePsychGames()

interface SpatialPod {
  val: number
  label: string
  desc: string
  leftPct: number
  topPct: number
}

const pods = ref<SpatialPod[]>([])
const hoveredVal = ref<number | null>(null)

const currentItem = computed(() => MATRIX_ITEMS[state.value.matrixCurrentIdx] ?? MATRIX_ITEMS[0]!)
const answeredCount = computed(() => state.value.matrixAnswers.filter(v => v !== null).length)
const progressPct = computed(() => Math.round((answeredCount.value / 20) * 100))

const report = computed(() => {
  if (!state.value.matrixCompleted || state.value.matrixAnswers.some(v => v === null)) return null
  return evaluateBehavioralMatrix(state.value.matrixAnswers as number[])
})

function shuffleLayout() {
  const zones = [
    { xMin: 4, xMax: 23, yMin: 6, yMax: 30 },
    { xMin: 66, xMax: 80, yMin: 6, yMax: 30 },
    { xMin: 36, xMax: 52, yMin: 26, yMax: 52 },
    { xMin: 6, xMax: 26, yMin: 56, yMax: 72 },
    { xMin: 64, xMax: 80, yMin: 56, yMax: 72 },
  ]
  for (let i = zones.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1))
    ;[zones[i], zones[j]] = [zones[j]!, zones[i]!]
  }
  const opts = [...MATRIX_SCALE_OPTIONS]
  for (let i = opts.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1))
    ;[opts[i], opts[j]] = [opts[j]!, opts[i]!]
  }
  pods.value = opts.map((opt, idx) => {
    const z = zones[idx]!
    return {
      val: opt.val,
      label: opt.label,
      desc: opt.desc,
      leftPct: Math.round(z.xMin + Math.random() * (z.xMax - z.xMin)),
      topPct: Math.round(z.yMin + Math.random() * (z.yMax - z.yMin)),
    }
  })
  hoveredVal.value = pods.value[0]?.val ?? null
}

function selectRating(val: number) {
  psychAudio.playClick()
  state.value.matrixAnswers[state.value.matrixCurrentIdx] = val
  if (state.value.matrixCurrentIdx < 19) {
    state.value.matrixCurrentIdx++
    shuffleLayout()
  }
  else {
    psychAudio.playSuccess()
    state.value.matrixCompleted = true
  }
}

function prevItem() {
  if (state.value.matrixCurrentIdx > 0) {
    psychAudio.playClick()
    state.value.matrixCurrentIdx--
    shuffleLayout()
  }
}

function startOver() {
  psychAudio.playClick()
  resetMatrix()
  shuffleLayout()
}

watch(() => props.expanded, (open) => {
  if (open && pods.value.length === 0) shuffleLayout()
})

onMounted(() => {
  shuffleLayout()
})
</script>

<template>
  <Teleport v-if="expanded" to="body">
    <div class="psych-battery-overlay" role="dialog" aria-modal="true" aria-label="20-Item Behavioral and Social Dynamics Matrix">
      <header class="psych-overlay-header">
        <div class="max-w-[1160px] mx-auto flex flex-wrap items-center justify-between gap-[12px]">
          <div class="flex items-center gap-[10px]">
            <span class="px-[8px] py-[3px] rounded-[4px] border border-cabin-line menu-item-active mono text-[10.5px] font-bold">
              SPACEFLIGHT BHP · IWS
            </span>
            <div>
              <p class="text-[14px] font-bold">Mood, Affect &amp; Social Dynamics Matrix (20 Items)</p>
              <p class="mono text-[10.5px] text-cabin-ice">HFBP-EM &amp; APA DSM-5-TR Cross-Walk · {{ answeredCount }}/20 answered ({{ progressPct }}%)</p>
            </div>
          </div>

          <div class="flex items-center gap-[10px]">
            <div class="hidden sm:block w-[140px] h-[7px] rounded-full bg-cabin-bg border border-cabin-line overflow-hidden">
              <div class="h-full bg-cabin-ok transition-all" :style="{ width: `${progressPct}%` }" />
            </div>
            <button type="button" class="px-[12px] py-[6px] rounded-[4px] border border-cabin-line text-[12px] text-cabin-ice hover:text-cabin-text" @click="emit('minimize')">
              Minimize
            </button>
            <button type="button" class="px-[12px] py-[6px] rounded-[4px] border border-cabin-crit/60 bg-cabin-crit/15 text-[12px] font-bold text-cabin-crit" @click="emit('exit')">
              Exit
            </button>
          </div>
        </div>
      </header>

      <div class="psych-overlay-scroll hud-scroll">
        <div v-if="!state.matrixCompleted" class="max-w-[1060px] mx-auto flex flex-col gap-[14px]">
          <div class="tile-hi p-[18px] text-center">
            <div class="flex flex-wrap items-center justify-center gap-[8px]">
              <span class="px-[8px] py-[2px] rounded-[4px] border border-cabin-line mono text-[10.5px] font-bold text-cabin-ok">
                ITEM {{ currentItem.id }} OF 20
              </span>
              <span class="px-[8px] py-[2px] rounded-[4px] border border-cabin-line mono text-[10.5px] text-cabin-ice">
                {{ currentItem.block }}
              </span>
              <span class="px-[8px] py-[2px] rounded-[4px] border border-cabin-line mono text-[10.5px]">
                {{ currentItem.construct }}
              </span>
            </div>
            <p class="text-[32px] font-extrabold mt-[10px] tracking-[0.02em]">{{ currentItem.en }}</p>
            <p class="text-[12.5px] text-cabin-ice mt-[4px]">
              Rate how strongly you experience this state <strong>right now</strong>.
            </p>
          </div>

          <div class="spatial-deck-area">
            <button
              v-for="pod in pods"
              :key="pod.val"
              type="button"
              class="spatial-option-pod"
              :class="{ selected: state.matrixAnswers[state.matrixCurrentIdx] === pod.val }"
              :style="{ left: `${pod.leftPct}%`, top: `${pod.topPct}%` }"
              @mouseenter="hoveredVal = pod.val"
              @focus="hoveredVal = pod.val"
              @click="selectRating(pod.val)"
            >
              <img
                v-if="hoveredVal === pod.val"
                :src="cowSpriteUrl"
                alt="Dr. Moo assistant"
                class="w-[54px] h-[54px] absolute -top-[34px] -right-[14px] mascot-float pointer-events-none"
              >
              <span class="mono text-[26px] font-extrabold leading-none">{{ pod.val }}</span>
              <span class="text-[13px] font-bold mt-[4px]">{{ pod.label }}</span>
              <span class="mono text-[10px] text-cabin-ice uppercase mt-[2px]">{{ pod.desc }}</span>
            </button>
          </div>

          <div class="flex flex-wrap items-center justify-between gap-[10px]">
            <button
              type="button"
              class="px-[14px] py-[8px] rounded-[6px] border border-cabin-line text-[12px] font-bold"
              :class="state.matrixCurrentIdx === 0 ? 'opacity-40 pointer-events-none' : ''"
              @click="prevItem"
            >
              ← Previous Item
            </button>
            <span class="mono text-[11px] text-cabin-ice">Select a spatial pod to log and advance</span>
            <button type="button" class="px-[14px] py-[8px] rounded-[6px] border border-cabin-line text-[12px] text-cabin-ice" @click="startOver">
              Reset Session
            </button>
          </div>
        </div>

        <div v-else-if="report" class="max-w-[1060px] mx-auto flex flex-col gap-[16px]">
          <div class="tile-hi p-[18px] flex flex-col gap-[14px]">
            <div class="flex flex-wrap items-center justify-between gap-[10px]">
              <div class="flex items-center gap-[14px]">
                <img :src="cowSpriteUrl" alt="Dr. Moo" class="w-[62px] h-[62px] mascot-float">
                <div>
                  <span class="label-caps text-cabin-ok">Crew Wellness Debrief</span>
                  <h3 class="text-[18px] font-bold mt-[2px]">{{ report.heading }}</h3>
                  <p class="text-[12.5px] text-cabin-ice mt-[4px]">{{ report.body }}</p>
                </div>
              </div>
              <UiStatusPill :tone="report.tone">
                {{ report.readinessStatus }}
              </UiStatusPill>
            </div>

            <div class="grid grid-cols-1 md:grid-cols-3 gap-[10px]">
              <div class="tile p-[12px]">
                <p class="text-[12px] font-bold">Autonomic Regulation</p>
                <p class="text-[11px] text-cabin-ice mt-[4px]">5 cycles of slow diaphragmatic breathing (4s in, 4s hold, 6s out).</p>
              </div>
              <div class="tile p-[12px]">
                <p class="text-[12px] font-bold">Crew Connection</p>
                <p class="text-[11px] text-cabin-ice mt-[4px]">Shared galley break or crew check-in to reinforce social cohesion.</p>
              </div>
              <div class="tile p-[12px]">
                <p class="text-[12px] font-bold">Sensory Decompression</p>
                <p class="text-[11px] text-cabin-ice mt-[4px]">10-minute visual rest window away from cabin display glare.</p>
              </div>
            </div>
          </div>

          <div class="tile p-[18px] flex flex-col gap-[14px]">
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-[12px]">
              <div class="tile-hi p-[14px]">
                <p class="label-caps">Operational Flight Status</p>
                <p class="text-[20px] font-extrabold mt-[4px]" :class="report.tone === 'critical' ? 'text-cabin-crit' : report.tone === 'ok' ? 'text-cabin-ok' : 'text-cabin-text'">
                  {{ report.readinessStatus }}
                </p>
                <p class="text-[11.5px] text-cabin-ice mt-[2px]">{{ report.readinessBadge }}</p>
              </div>
              <div class="tile-hi p-[14px]">
                <p class="label-caps">Global Psychosocial Load</p>
                <p class="mono text-[20px] font-extrabold mt-[4px]">{{ report.totalLoad }} / 80 pts <span class="text-[12px] text-cabin-ice">(Mean {{ report.meanLoad.toFixed(2) }})</span></p>
                <p class="text-[11.5px] text-cabin-ice mt-[2px]">{{ report.rangeDescriptor }}</p>
              </div>
            </div>

            <div class="grid grid-cols-2 sm:grid-cols-5 gap-[10px]">
              <div v-for="sub in report.subscales" :key="sub.code" class="tile p-[10px]">
                <p class="mono text-[10.5px] font-bold text-cabin-ok">{{ sub.code }} · SUBSCALE</p>
                <p class="text-[12px] font-bold mt-[2px]">{{ sub.label }}</p>
                <p class="mono text-[16px] font-bold mt-[6px]">{{ sub.score }} / 16</p>
                <p class="mono text-[10px] mt-[2px]" :class="sub.tone === 'critical' ? 'text-cabin-crit' : sub.tone === 'ok' ? 'text-cabin-ok' : 'text-cabin-ice'">
                  {{ sub.apaLabel }}
                </p>
              </div>
            </div>

            <div class="grid grid-cols-1 sm:grid-cols-2 gap-[12px]">
              <div class="tile p-[12px]">
                <p class="label-caps text-cabin-ok">APA DSM-5-TR GAD Cross-Walk</p>
                <p class="mono text-[14px] font-bold mt-[4px]">Mean {{ report.gadMean.toFixed(2) }} / 4.00 ({{ report.gadScaled40 }}/40 Eq.) · {{ report.gadLabel }}</p>
              </div>
              <div class="tile p-[12px]">
                <p class="label-caps text-cabin-ok">APA DSM-5-TR PHQ-9 Cross-Walk</p>
                <p class="mono text-[14px] font-bold mt-[4px]">{{ report.phq9Eq }} / 27 Eq. · {{ report.phq9Category }}</p>
              </div>
            </div>

            <div class="tile-hi p-[12px] text-[12px] leading-[1.45]">
              <strong>Flight Director Directive:</strong> {{ report.directiveText }}
            </div>

            <UiSaveResult v-if="savedNote" :tone="savedNote.tone" :title="savedNote.title" :text="savedNote.text" />

            <div class="flex flex-wrap justify-between gap-[10px]">
              <button type="button" class="px-[16px] py-[10px] rounded-[6px] border border-cabin-line mono text-[12px]" @click="startOver">
                Start New Assessment
              </button>
              <button type="button" class="px-[18px] py-[10px] rounded-[6px] border border-cabin-ok bg-cabin-ok/20 font-bold text-cabin-ok mono text-[12px]" :disabled="saving" @click="emit('save-matrix', state.matrixAnswers as number[])">
                {{ saving ? 'Saving…' : 'Save Behavioral Matrix' }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>
