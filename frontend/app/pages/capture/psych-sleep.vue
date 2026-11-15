<script setup lang="ts">
import { psychCheckinSchema } from '~/schemas/mind'
import { ARENA_PLANNED_TRIALS, formatClock, sleepDuration } from '~/utils/mind'

type MoodState = 'CALM' | 'FOCUSED' | 'TIRED' | 'STRESSED'
type ScaleKey = 'mood' | 'stress' | 'isolation' | 'motivation'

const { authHeaders, isAuthenticated } = useSession()
const arena = useReactionArena()

const moodStates: MoodState[] = ['CALM', 'FOCUSED', 'TIRED', 'STRESSED']
const scaleKeys: ScaleKey[] = ['mood', 'stress', 'isolation', 'motivation']

const form = reactive({
  moodState: 'CALM' as MoodState,
  mood: 4,
  stress: 2,
  isolation: 1,
  motivation: 5,
  sleepOnsetUtc: '22:00',
  wakeUtc: '06:00',
})
const formErrors = ref<Record<string, string>>({})
const saving = ref(false)
const savedIndex = ref<number | null>(null)
const saveError = ref(false)

const savingMotor = ref(false)
const motorSaved = ref(false)
const motorError = ref(false)

const asleep = computed(() => sleepDuration(form.sleepOnsetUtc, form.wakeUtc))
const lastLatency = computed(() =>
  arena.lastLatencyMs.value === null ? '--' : `${arena.lastLatencyMs.value} ms`,
)

async function saveCheckin() {
  formErrors.value = {}
  savedIndex.value = null
  saveError.value = false
  const parsed = psychCheckinSchema.safeParse(form)
  if (!parsed.success) {
    for (const issue of parsed.error.issues) {
      formErrors.value[String(issue.path[0])] = issue.message
    }
    return
  }
  saving.value = true
  try {
    const d = parsed.data
    const res = await $fetch<{ wellbeing_index: number }>('/api/v1/psych/checkins', {
      method: 'POST',
      headers: authHeaders(),
      body: {
        mood_state: d.moodState,
        mood: d.mood,
        stress: d.stress,
        isolation: d.isolation,
        motivation: d.motivation,
        sleep_onset_utc: d.sleepOnsetUtc,
        wake_utc: d.wakeUtc,
      },
    })
    savedIndex.value = res.wellbeing_index
  }
  catch {
    saveError.value = true
  }
  finally {
    saving.value = false
  }
}

function startArena() {
  motorSaved.value = false
  motorError.value = false
  arena.start()
}

async function saveMotor() {
  if (arena.phase.value !== 'done' || arena.times.value.length === 0) return
  savingMotor.value = true
  motorError.value = false
  try {
    await $fetch('/api/v1/cognitive/sessions', {
      method: 'POST',
      headers: authHeaders(),
      body: {
        reaction_times_ms: arena.times.value,
        false_starts: arena.falseStarts.value,
        duration_sec: 120,
      },
    })
    motorSaved.value = true
  }
  catch {
    motorError.value = true
  }
  finally {
    savingMotor.value = false
  }
}

onMounted(() => {
  if (!isAuthenticated.value) void navigateTo('/login')
})
</script>

<template>
  <div class="flex flex-col gap-[18px] flex-1">
    <div class="flex items-start justify-between gap-3">
      <CaptureSubnavBar />
      <span class="h-8 px-4 rounded-full border bg-cabin-navy/42 border-cabin-navy-edge/80 text-[10.5px] font-bold tracking-[0.05em] inline-flex items-center">
        {{ $t('mind.capture.feeds') }}
      </span>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-2 gap-[18px] flex-1">
      <ShellHudWindow
        :title="$t('mind.capture.entry')"
        icon="moon"
        :tag-text="$t('mind.capture.dailyCheckIn')"
      >
        <form
          class="flex flex-col gap-3 h-full"
          @submit.prevent="saveCheckin"
        >
          <span class="text-[9.8px] font-bold tracking-[0.06em] text-cabin-muted">
            {{ $t('mind.capture.moodState') }}
          </span>
          <div class="grid grid-cols-4 gap-2">
            <button
              v-for="state in moodStates"
              :key="state"
              type="button"
              class="h-9 rounded-[4px] border text-[11.5px] font-semibold"
              :class="form.moodState === state ? 'menu-item-active text-cabin-text' : 'bg-cabin-inset border-cabin-card/60 text-cabin-muted hover:text-cabin-text'"
              :aria-pressed="form.moodState === state"
              @click="form.moodState = state"
            >
              {{ $t(`mind.capture.states.${state}`) }}
            </button>
          </div>

          <div
            v-for="key in scaleKeys"
            :key="key"
            class="rounded-[4px] border border-cabin-card/55 bg-cabin-inset px-4 py-2.5 flex items-center justify-between gap-3"
          >
            <span class="flex flex-col">
              <span class="text-[12px] font-bold text-cabin-text">{{ $t(`mind.capture.scales.${key}`) }}</span>
              <span class="text-[10px] text-cabin-ok">{{ $t('mind.capture.selected', { value: form[key] }) }}</span>
            </span>
            <span
              class="flex gap-2"
              role="radiogroup"
              :aria-label="$t(`mind.capture.scales.${key}`)"
            >
              <button
                v-for="n in 5"
                :key="n"
                type="button"
                role="radio"
                :aria-checked="form[key] === n"
                class="w-9 h-9 rounded-[4px] border text-[12px] font-semibold"
                :class="form[key] === n ? 'menu-item-active text-cabin-text' : 'bg-cabin-inset border-cabin-card/60 text-cabin-muted hover:text-cabin-text'"
                @click="form[key] = n"
              >
                {{ n }}
              </button>
            </span>
          </div>

          <span class="mt-1 text-[9.8px] font-bold tracking-[0.06em] text-cabin-muted">
            {{ $t('mind.capture.sleepWindow') }}
          </span>
          <div class="grid grid-cols-2 gap-3">
            <label class="flex flex-col gap-1">
              <span class="flex justify-between text-[9.8px] font-bold tracking-[0.05em] text-cabin-muted">
                {{ $t('mind.capture.sleepOnset') }}
                <span class="font-normal">{{ $t('mind.capture.lightsOut') }}</span>
              </span>
              <span class="relative">
                <input
                  v-model="form.sleepOnsetUtc"
                  type="text"
                  inputmode="numeric"
                  maxlength="5"
                  placeholder="22:18"
                  class="w-full h-11 rounded-[4px] border border-cabin-card/60 bg-cabin-inset px-3 font-mono text-[15px] text-cabin-text"
                >
                <span class="absolute right-3 top-1/2 -translate-y-1/2 text-[10px] font-bold text-cabin-muted">UTC</span>
              </span>
              <span
                v-if="formErrors.sleepOnsetUtc"
                class="text-[10.5px] text-cabin-crit"
              >{{ formErrors.sleepOnsetUtc }}</span>
            </label>
            <label class="flex flex-col gap-1">
              <span class="flex justify-between text-[9.8px] font-bold tracking-[0.05em] text-cabin-muted">
                {{ $t('mind.capture.wakeTime') }}
                <span class="font-mono font-normal">{{ asleep }}</span>
              </span>
              <span class="relative">
                <input
                  v-model="form.wakeUtc"
                  type="text"
                  inputmode="numeric"
                  maxlength="5"
                  placeholder="22:18"
                  class="w-full h-11 rounded-[4px] border border-cabin-text/60 bg-cabin-inset px-3 font-mono text-[15px] text-cabin-text"
                >
                <span class="absolute right-3 top-1/2 -translate-y-1/2 text-[10px] font-bold text-cabin-muted">UTC</span>
              </span>
              <span
                v-if="formErrors.wakeUtc"
                class="text-[10.5px] text-cabin-crit"
              >{{ formErrors.wakeUtc }}</span>
            </label>
          </div>

          <p
            v-if="savedIndex !== null"
            class="text-[11.5px] text-cabin-ok"
          >
            {{ $t('mind.capture.saved', { index: savedIndex }) }}
          </p>
          <p
            v-if="saveError"
            class="text-[11.5px] text-cabin-crit"
          >
            {{ $t('mind.capture.saveError') }}
          </p>

          <button
            type="submit"
            class="mt-auto h-11 rounded-[4px] border border-cabin-text/70 bg-cabin-card/60 text-[12.5px] font-semibold text-cabin-text inline-flex items-center justify-center gap-2 hover:bg-cabin-card disabled:opacity-60"
            :disabled="saving"
          >
            <Icon
              name="spacescan:moon"
              class="w-4 h-4"
            />
            {{ saving ? $t('mind.capture.saving') : $t('mind.capture.saveLog') }}
          </button>
        </form>
      </ShellHudWindow>

      <ShellHudWindow
        :title="$t('mind.capture.motor')"
        icon="reticle"
        :tag-text="$t('mind.capture.vigilance')"
      >
        <div class="flex flex-col gap-3 h-full">
          <div class="relative rounded-[4px] border border-cabin-card bg-cabin-inset h-[250px] select-none">
            <span class="absolute top-3 left-3 font-mono text-[10px] text-cabin-muted">
              {{ $t('mind.capture.trial', { n: arena.summary.value.trials, total: ARENA_PLANNED_TRIALS, elapsed: formatClock(arena.elapsedMs.value) }) }}
            </span>
            <span class="absolute top-3 right-3 text-[10px] font-bold text-cabin-ok">
              {{ $t('mind.capture.tapGreen') }}
            </span>
            <span class="pointer-events-none absolute left-1/2 top-[22px] bottom-[34px] w-px bg-cabin-navy-edge/40" />
            <span class="pointer-events-none absolute top-1/2 left-6 right-6 h-px bg-cabin-navy-edge/40" />
            <button
              type="button"
              class="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-24 h-24 rounded-full border-2 flex items-center justify-center transition-colors"
              :class="arena.phase.value === 'target' ? 'border-cabin-ok bg-cabin-ok/25' : 'border-cabin-card bg-cabin-card/15'"
              :disabled="arena.phase.value === 'idle' || arena.phase.value === 'done'"
              @pointerdown.prevent="arena.tap()"
            >
              <span
                class="w-12 h-12 rounded-full border text-[11px] font-bold inline-flex items-center justify-center"
                :class="arena.phase.value === 'target' ? 'border-cabin-ok text-cabin-text' : 'border-cabin-card text-cabin-muted'"
              >
                {{
                  arena.phase.value === 'target' ? $t('mind.capture.tap')
                  : arena.phase.value === 'waiting' ? $t('mind.capture.wait')
                    : arena.phase.value === 'done' ? $t('mind.capture.done') : $t('mind.capture.ready')
                }}
              </span>
            </button>
            <span class="absolute bottom-3 inset-x-0 text-center font-mono text-[10.5px] text-cabin-text">
              {{ $t('mind.capture.lastLatency', { ms: lastLatency, count: arena.summary.value.falseStarts }) }}
            </span>
          </div>

          <div class="grid grid-cols-2 gap-3">
            <div class="rounded-[4px] border border-cabin-card/55 border-t-[3px] border-t-cabin-ok bg-cabin-inset px-4 py-3">
              <span class="text-[9.8px] font-bold tracking-[0.06em] text-cabin-muted">{{ $t('mind.capture.meanReaction') }}</span>
              <p class="text-[24px] font-bold text-cabin-text">
                {{ arena.summary.value.meanMs || '--' }} <span class="text-[14px]">ms</span>
              </p>
              <span class="text-[10.5px] text-cabin-muted">{{ $t('mind.capture.optimal') }}</span>
            </div>
            <div class="rounded-[4px] border border-cabin-card/55 border-t-[3px] border-t-cabin-ok bg-cabin-inset px-4 py-3">
              <span class="text-[9.8px] font-bold tracking-[0.06em] text-cabin-muted">{{ $t('mind.capture.precision') }}</span>
              <p class="text-[24px] font-bold text-cabin-text">
                {{ arena.summary.value.trials ? `${arena.summary.value.precisionPct}%` : '--' }}
              </p>
              <span class="text-[10.5px] text-cabin-muted">
                {{ $t('mind.capture.validResponses', { valid: arena.summary.value.valid, total: arena.summary.value.trials + arena.summary.value.falseStarts }) }}
              </span>
            </div>
          </div>

          <p
            v-if="motorSaved"
            class="text-[11.5px] text-cabin-ok"
          >
            {{ $t('mind.capture.motorSaved') }}
          </p>
          <p
            v-if="motorError"
            class="text-[11.5px] text-cabin-crit"
          >
            {{ $t('mind.capture.motorError') }}
          </p>

          <div class="mt-auto grid grid-cols-2 gap-3">
            <button
              type="button"
              class="h-11 rounded-[4px] border border-cabin-card bg-cabin-card/60 text-[12px] font-semibold text-cabin-text inline-flex items-center justify-center gap-2 hover:bg-cabin-card disabled:opacity-60"
              :disabled="arena.phase.value === 'waiting' || arena.phase.value === 'target'"
              @click="startArena"
            >
              <Icon
                name="spacescan:reticle"
                class="w-4 h-4"
              />
              {{ arena.phase.value === 'done' ? $t('mind.capture.restart') : $t('mind.capture.start') }}
            </button>
            <button
              type="button"
              class="h-11 rounded-[4px] border border-cabin-text/70 bg-cabin-card/40 text-[12px] font-semibold text-cabin-text inline-flex items-center justify-center gap-2 hover:bg-cabin-card/70 disabled:opacity-60"
              :disabled="arena.phase.value !== 'done' || savingMotor || motorSaved"
              @click="saveMotor"
            >
              <Icon
                name="spacescan:flame"
                class="w-4 h-4"
              />
              {{ $t('mind.capture.saveMotor') }}
            </button>
          </div>
        </div>
      </ShellHudWindow>
    </div>
  </div>
</template>
