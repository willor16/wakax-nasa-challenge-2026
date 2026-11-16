<script setup lang="ts">
// 01 · Sign In: pick a crew profile and enter the 4-digit PIN. Public views need no sign-in.
import { apiErrorMessage } from '~/composables/useApi'
import { crewTone } from '~/utils/format'

interface CrewProfile {
  id: string
  code: string
  full_name: string
  title_en: string
  sex: 'F' | 'M' | null
  status: string
  is_locked: boolean
}

usePageHeader({ title: '' })
const { api } = useApi()
const { login, isAuthenticated } = useSession()

const { data: profiles, loading, error, refresh } = useResource(() => api<CrewProfile[]>('/crew/profiles'))
const selectedId = ref<string | null>(null)
const pin = ref('')
const busy = ref(false)
const failure = ref<string | null>(null)
const pinInput = ref<HTMLInputElement | null>(null)

const selected = computed(() => profiles.value?.find(p => p.id === selectedId.value) ?? null)
const JUDGE_PINS: Record<string, string> = {
  'ID-01': '1042',
  'ID-02': '2084',
  'ID-03': '3190',
  'ID-04': '4275',
}
const judgeNotes = computed(() =>
  (profiles.value ?? [])
    .filter(p => JUDGE_PINS[p.id])
    .map(p => ({ profile: p, pin: JUDGE_PINS[p.id]! })),
)
watch(profiles, (list) => {
  if (list?.length && !selectedId.value) selectedId.value = list[0]!.id
})

function choose(profile: CrewProfile) {
  selectedId.value = profile.id
  pin.value = ''
  failure.value = null
  pinInput.value?.focus()
}

function onPinInput(event: Event) {
  const input = event.target as HTMLInputElement
  pin.value = input.value.replace(/\D/g, '').slice(0, 4)
  input.value = pin.value
  failure.value = null
}

async function signIn() {
  if (!selected.value || pin.value.length !== 4 || busy.value) return
  busy.value = true
  failure.value = null
  try {
    await login(selected.value.id, pin.value)
    await navigateTo('/profile/personal')
  }
  catch (reason) {
    failure.value = apiErrorMessage(reason, 'Sign-in failed. Please try again.')
    pin.value = ''
    if (pinInput.value) pinInput.value.value = ''
    void refresh(true)
    pinInput.value?.focus()
  }
  finally {
    busy.value = false
  }
}

onMounted(() => {
  if (isAuthenticated.value) void navigateTo('/profile/personal')
})
</script>

<template>
  <div class="flex-1 min-h-0 flex flex-col items-center justify-center">
    <h1 class="text-[21px] font-bold">Select Crew Profile</h1>

    <UiStateNote
v-if="loading || error || !profiles?.length" :loading="loading" :error="error"
                 empty="No crew profiles are set up yet." class="!flex-none h-[clamp(210px,27.3dvh,300px)] mt-[clamp(10px,2.1dvh,20px)]" @retry="refresh()" />
    <div v-else class="mt-[clamp(10px,2.1dvh,20px)] flex gap-[21px]" role="radiogroup" aria-label="Crew profile">
      <button
        v-for="profile in profiles"
        :key="profile.id"
        type="button"
        role="radio"
        :aria-checked="profile.id === selectedId"
        class="focus-ring relative w-[clamp(210px,16.5vw,300px)] h-[clamp(210px,27.3dvh,300px)] rounded-[5px] flex flex-col items-center cursor-pointer border-[1.4px]"
        :class="profile.id === selectedId
          ? 'bg-[var(--color-card-head)] border-cabin-text/85'
          : 'bg-[var(--color-card-fill)] border-cabin-line hover:border-cabin-edge'"
        @click="choose(profile)"
      >
        <span class="absolute top-[14px] left-[16px] mono text-[10px] text-cabin-ice tracking-[0.06em]">{{ profile.code }}</span>
        <UiStatusPill
          class="absolute top-[10px] right-[12px] min-w-[84px]"
          :tone="profile.id !== selectedId && crewTone(profile.status) === 'critical' ? 'critical' : 'reference'"
        >
          {{ profile.is_locked ? 'LOCKED' : profile.id === selectedId ? 'SELECTED' : profile.status.toUpperCase() }}
        </UiStatusPill>
        <UiHoloFigure
figure="body" :sex="profile.sex" :tone="crewTone(profile.status)" size="clamp(80px, 11dvh, 124px)" class="mt-[clamp(44px,7dvh,72px)]"
                      :label="`${profile.full_name}: ${profile.status}`" />
        <span class="mt-[clamp(14px,2.1dvh,22px)] text-[15px] font-bold">{{ profile.full_name }}</span>
        <span class="mt-[5px] text-[11.5px] text-cabin-ice">{{ profile.title_en }}</span>
      </button>
    </div>

    <ShellHudWindow class="w-[500px] max-w-full h-[clamp(206px,24.7dvh,240px)] shrink-0 mt-[clamp(12px,2.4dvh,23px)]" flush>
      <template #header>
        <div class="flex items-center gap-[10px] min-w-0">
          <div class="w-[22px] h-[22px] rounded-[4px] bg-cabin-tile border border-cabin-edge/70 flex items-center justify-center">
            <Icon name="spacescan:lock" class="w-[13px] h-[13px]" />
          </div>
          <h2 class="text-[13px] font-bold tracking-[0.02em] uppercase truncate">
            Enter PIN<template v-if="selected"> · {{ selected.full_name }}</template>
          </h2>
        </div>
        <UiStatusPill>4-DIGIT PIN</UiStatusPill>
      </template>
      <form class="flex-1 flex flex-col items-center" @submit.prevent="signIn">
        <label class="relative mt-[clamp(14px,2.8dvh,26px)] flex gap-[18px] cursor-text">
          <span class="sr-only">4-digit PIN for {{ selected?.full_name }}</span>
          <input
            ref="pinInput"
            type="password"
            inputmode="numeric"
            autocomplete="off"
            maxlength="4"
            class="absolute inset-0 opacity-0 cursor-text"
            :disabled="!selected || selected.is_locked || busy"
            @input="onPinInput"
          >
          <span
            v-for="index in 4"
            :key="index"
            class="w-[64px] h-[60px] rounded-[5px] flex items-center justify-center border-[1.3px]"
            :class="index - 1 === Math.min(pin.length, 3) && pin.length < 4 || (pin.length === 4 && index === 4)
              ? 'bg-[var(--color-bg-top)] border-cabin-text/85'
              : 'bg-cabin-tile border-cabin-edge/70'"
          >
            <i v-if="pin.length >= index" class="w-[10px] h-[10px] rounded-full bg-cabin-text" />
          </span>
        </label>
        <button
type="submit" class="hud-button !w-[416px] !h-[52px] mt-[clamp(14px,3dvh,28px)] relative"
                :disabled="!selected || selected.is_locked || pin.length !== 4 || busy">
          <Icon name="spacescan:lock" class="w-[15px] h-[15px] absolute left-[20px]" />
          {{ busy ? 'Signing In…' : 'Sign In' }}
        </button>
        <p class="h-[18px] mt-[6px] text-[11px] text-cabin-text" :class="failure ? '' : 'invisible'" role="alert">
          <Icon name="spacescan:alert" class="w-[11px] h-[11px] text-cabin-crit align-[-1px]" /> {{ failure }}
        </p>
      </form>
    </ShellHudWindow>

    <aside
      v-if="judgeNotes.length"
      aria-label="Judge access note"
      class="tile mt-[clamp(10px,1.8dvh,16px)] w-[clamp(500px,68vw,960px)] max-w-full px-[16px] py-[10px] shrink-0"
    >
      <div class="flex items-center justify-between gap-[10px] mb-[7px]">
        <p class="label-caps flex items-center gap-[6px]">
          <Icon name="spacescan:shield" class="w-[12px] h-[12px] text-cabin-ok shrink-0" />
          Judge Note · Crew Access PINs
        </p>
        <span class="text-[10px] text-cabin-ice">Select a profile above and enter its 4-digit PIN</span>
      </div>
      <div class="grid grid-cols-2 lg:grid-cols-4 gap-[8px]">
        <button
          v-for="item in judgeNotes"
          :key="item.profile.id"
          type="button"
          class="focus-ring px-[10px] py-[6px] rounded-[4px] border text-left flex items-center justify-between gap-[8px] cursor-pointer"
          :class="item.profile.id === selectedId
            ? 'menu-item-active border-cabin-edge text-cabin-text'
            : 'bg-cabin-tile border-cabin-line text-cabin-ice hover:border-cabin-edge hover:text-cabin-text'"
          @click="choose(item.profile)"
        >
          <span class="min-w-0 truncate text-[11px]">
            <strong class="font-semibold text-cabin-text">{{ item.profile.full_name }}</strong>
            <span class="text-cabin-ice"> · {{ item.profile.title_en }}</span>
          </span>
          <span class="mono text-[11.5px] font-bold text-cabin-ok shrink-0">{{ item.pin }}</span>
        </button>
      </div>
    </aside>
  </div>
</template>
