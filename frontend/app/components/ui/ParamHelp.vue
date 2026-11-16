<script setup lang="ts">
// Small "?" button next to a parameter name. Hovering previews a card that explains what the
// parameter measures, how to read it and its mission impact, with the usual range and (when
// signed in) the crew member's own baseline. A click or Enter / Space pins it open; Esc, a
// click elsewhere, scrolling or resizing closes it.
//
// The card is positioned once when it opens (fixed, teleported to the page body) and never
// tracks its anchor: the cockpit windows resize with the display, and a card that kept
// re-measuring its anchor inside resizing windows could lock the page in a layout loop.

const props = defineProps<{ metricKey: string }>()

const { t } = useI18n()
const { entries, load } = useParamHelp()
const { isAuthenticated, crew, activePatient } = useSession()
const { api } = useApi()
const route = useRoute()
// Whose ranges to show: capture screens record for the signed-in crew member; results
// screens show the patient being viewed (the physician may be looking at someone else).
const subject = computed(() => (route.path.startsWith('/capture') ? crew.value : activePatient.value))

const CARD_WIDTH = 320
const MARGIN = 16

const open = ref(false)
const pinned = ref(false)
const trigger = ref<HTMLButtonElement | null>(null)
const card = ref<HTMLElement | null>(null)
const position = ref<{ left: number, top?: number, bottom?: number }>({ left: 0, top: 0 })
const cardId = `param-help-${useId()}`
let hoverTimer: ReturnType<typeof setTimeout> | null = null

const help = computed(() => entries.value[props.metricKey] ?? null)
const baseline = useState<Record<string, { mean_val: number }>>('param-help-baselines', () => ({}))
const baselineFor = useState('param-help-baselines-for', () => '')

// Ranges that differ by sex show the range of the person on screen.
const sexRange = computed(() => {
  const sex = subject.value?.sex === 'X' ? null : subject.value?.sex
  const range = sex ? help.value?.by_sex?.[sex] : undefined
  return range && range.nominal_min != null && range.nominal_max != null ? { sex, ...range } : null
})
const normalLabel = computed(() => (sexRange.value
  ? `${t('help.normal')} (${sexRange.value.sex === 'F' ? 'female' : 'male'})`
  : t('help.normal')))
const normalText = computed(() => {
  const item = help.value
  if (!item) return null
  const low = sexRange.value?.nominal_min ?? item.nominal_min
  const high = sexRange.value?.nominal_max ?? item.nominal_max
  if (low == null || high == null) return null
  return `${low}–${high} ${item.unit}`
})
const personalText = computed(() => {
  const base = baseline.value[props.metricKey]
  if (!base || !help.value) return null
  const digits = Math.abs(base.mean_val) < 10 ? 2 : 1
  return `${base.mean_val.toFixed(digits)} ${help.value.unit}`
})

async function prepare() {
  await load()
  const id = subject.value?.id
  if (!isAuthenticated.value || !id || baselineFor.value === id) return
  baselineFor.value = id
  try {
    const rows = await api<{ metric_key: string, mean_val: number }[]>(`/crew/${id}/baselines`)
    baseline.value = Object.fromEntries(rows.map(row => [row.metric_key, row]))
  }
  catch {
    baselineFor.value = ''
  }
}

/** Place the card below the button (or above when there is no room), inside the display. */
function place() {
  const box = trigger.value?.getBoundingClientRect()
  if (!box) return
  const left = Math.min(Math.max(MARGIN, box.left - 8), window.innerWidth - CARD_WIDTH - MARGIN)
  const below = window.innerHeight - box.bottom
  position.value = below >= 240 || below >= box.top
    ? { left, top: box.bottom + 6 }
    : { left, bottom: window.innerHeight - box.top + 6 }
}

function show(pin: boolean) {
  if (hoverTimer) clearTimeout(hoverTimer)
  if (!open.value) place()
  pinned.value = pinned.value || pin
  open.value = true
  void prepare()
}
function close() {
  if (hoverTimer) clearTimeout(hoverTimer)
  open.value = false
  pinned.value = false
}
function toggle() {
  if (open.value && pinned.value) close()
  else show(true)
}
function hoverIn() {
  if (hoverTimer) clearTimeout(hoverTimer)
  hoverTimer = setTimeout(() => show(false), 250)
}
function hoverOut() {
  if (hoverTimer) clearTimeout(hoverTimer)
  if (pinned.value) return
  hoverTimer = setTimeout(close, 200)
}

function onKey(event: KeyboardEvent) {
  if (event.key === 'Escape' && open.value) {
    close()
    trigger.value?.focus()
  }
}
function onPointerDown(event: PointerEvent) {
  const target = event.target as Node | null
  if (!target || trigger.value?.contains(target) || card.value?.contains(target)) return
  close()
}

watch(open, (value) => {
  if (!import.meta.client) return
  if (value) {
    document.addEventListener('keydown', onKey)
    document.addEventListener('pointerdown', onPointerDown, true)
    window.addEventListener('resize', close)
    window.addEventListener('scroll', close, true)
  }
  else {
    document.removeEventListener('keydown', onKey)
    document.removeEventListener('pointerdown', onPointerDown, true)
    window.removeEventListener('resize', close)
    window.removeEventListener('scroll', close, true)
  }
})
onMounted(() => void load())
onBeforeUnmount(() => {
  if (hoverTimer) clearTimeout(hoverTimer)
  open.value = false
})
</script>

<template>
  <button
    ref="trigger"
    type="button"
    class="focus-ring param-help-trigger inline-flex shrink-0 items-center justify-center w-[15px] h-[15px] rounded-full border border-cabin-edge/80 bg-cabin-tile text-cabin-ice text-[9.5px] font-bold leading-none normal-case tracking-normal hover:border-cabin-text hover:text-cabin-text"
    :aria-label="t('help.open', { name: help?.label_en ?? metricKey.replaceAll('_', ' ') })"
    :aria-expanded="open"
    :aria-controls="open ? cardId : undefined"
    @pointerenter="hoverIn"
    @pointerleave="hoverOut"
    @click.stop.prevent="toggle"
  >
    ?
  </button>
  <Teleport v-if="open" to="body">
    <div
      :id="cardId"
      ref="card"
      role="dialog"
      :aria-label="help?.label_en ?? metricKey"
      class="param-help-card fixed z-50 w-[320px] rounded-[6px] border border-cabin-edge bg-cabin-bg px-[16px] py-[14px] text-cabin-text normal-case tracking-normal text-left font-normal"
      :style="{
        left: `${position.left}px`,
        top: position.top === undefined ? undefined : `${position.top}px`,
        bottom: position.bottom === undefined ? undefined : `${position.bottom}px`,
      }"
      @pointerenter="hoverIn"
      @pointerleave="hoverOut"
    >
      <template v-if="help">
        <p class="text-[13px] font-bold">{{ help.label_en }}</p>
        <dl class="mt-[8px] flex flex-col gap-[8px] text-[11.5px] leading-[1.55]">
          <div>
            <dt class="label-caps !text-[9px]">{{ t('help.measures') }}</dt>
            <dd class="text-cabin-ice mt-[2px]">{{ help.summary_en }}</dd>
          </div>
          <div>
            <dt class="label-caps !text-[9px]">{{ t('help.reading') }}</dt>
            <dd class="text-cabin-ice mt-[2px]">{{ help.interpretation_en }}</dd>
          </div>
          <div>
            <dt class="label-caps !text-[9px]">{{ t('help.impact') }}</dt>
            <dd class="text-cabin-ice mt-[2px]">{{ help.operational_impact_en }}</dd>
          </div>
        </dl>
        <div v-if="normalText || personalText" class="mt-[10px] pt-[8px] border-t border-cabin-line flex flex-wrap gap-x-[16px] gap-y-[4px] text-[11px]">
          <p v-if="normalText"><span class="text-cabin-muted">{{ normalLabel }}:</span> <span class="mono">{{ normalText }}</span></p>
          <p v-if="personalText"><span class="text-cabin-muted">{{ t('help.personal') }}:</span> <span class="mono">{{ personalText }}</span></p>
        </div>
      </template>
      <p v-else class="text-[11.5px] text-cabin-ice">Loading…</p>
    </div>
  </Teleport>
</template>
