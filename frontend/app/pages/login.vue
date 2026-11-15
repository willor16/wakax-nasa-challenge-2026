<script setup lang="ts">
interface CrewProfileSummary {
  id: string
  code: string
  full_name: string
  short_name: string
  role: 'ASTRONAUT' | 'PILOT' | 'OPERATOR' | 'PHYSICIAN'
  status: 'Optimal' | 'Nominal' | 'Attention' | 'Critical'
  unread_alerts: number
  is_locked: boolean
  locked_until_utc: string | null
}

const router = useRouter()
const { signInWithPin, refreshMissionStatus } = useSession()

const crewRoster = ref<CrewProfileSummary[]>([])
const selectedId = ref('ID-01')
const pinDigits = ref('')
const isSubmitting = ref(false)
const errorMessage = ref('')

async function loadProfiles() {
  try {
    crewRoster.value = await $fetch<CrewProfileSummary[]>('/api/v1/crew/profiles')
    if (crewRoster.value.length > 0 && !crewRoster.value.some(c => c.id === selectedId.value)) {
      selectedId.value = crewRoster.value[0]!.id
    }
  }
  catch {
    errorMessage.value = 'Unable to reach onboard health service.'
  }
}

async function submitPin() {
  if (pinDigits.value.length !== 4 || isSubmitting.value) return
  isSubmitting.value = true
  errorMessage.value = ''
  try {
    await signInWithPin(selectedId.value, pinDigits.value)
    await router.push('/profile/personal')
  }
  catch (err: unknown) {
    const detail = (err as { data?: { detail?: string } })?.data?.detail
    errorMessage.value = detail || 'Authentication failed. Verify PIN and retry.'
    pinDigits.value = ''
    await loadProfiles()
  }
  finally {
    isSubmitting.value = false
  }
}

function statusColorClass(status: CrewProfileSummary['status']): string {
  if (status === 'Critical') return 'text-cabin-crit'
  if (status === 'Attention') return 'text-cabin-ice'
  return 'text-cabin-ok'
}

onMounted(async () => {
  await Promise.all([loadProfiles(), refreshMissionStatus()])
})
</script>

<template>
  <div class="grid grid-cols-1 lg:grid-cols-12 gap-[18px] flex-1">
    <ShellHudWindow
      class="lg:col-span-7"
      title="Crew Member Sign In"
      subtitle="Select profile and enter 4-digit access PIN"
      icon="lock"
      tag-text="CABIN TERMINAL"
    >
      <div class="grid grid-cols-2 gap-3 mb-5">
        <button
          v-for="member in crewRoster"
          :key="member.id"
          type="button"
          class="p-3.5 rounded-[6px] border text-left transition-colors cursor-pointer"
          :class="
            selectedId === member.id
              ? 'menu-item-active text-cabin-text'
              : 'bg-cabin-inset border-cabin-card/65 text-cabin-muted hover:text-cabin-text'
          "
          @click="selectedId = member.id; errorMessage = ''"
        >
          <div class="flex items-center justify-between">
            <span class="font-mono text-[11px] font-bold text-cabin-muted">{{ member.code }}</span>
            <span
              class="text-[10px] font-semibold uppercase tracking-[0.04em]"
              :class="statusColorClass(member.status)"
            >
              {{ member.is_locked ? 'Locked' : member.status }}
            </span>
          </div>
          <div class="mt-1 text-[13.5px] font-bold text-cabin-text">
            {{ member.full_name }}
          </div>
          <div class="text-[10.5px] tracking-[0.04em] uppercase text-cabin-muted">
            {{ member.role }}
          </div>
        </button>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-2 gap-4 items-start">
        <AuthPinPad4Digits
          v-model="pinDigits"
          :disabled="isSubmitting || crewRoster.length === 0"
          @submit="submitPin"
        />

        <div class="flex flex-col gap-3">
          <div class="p-3.5 rounded-[6px] bg-cabin-inset border border-cabin-card/65 text-[11.5px] text-cabin-muted">
            <div class="font-bold uppercase tracking-[0.04em] text-cabin-text mb-1">
              Keyboard or Pad Entry
            </div>
            <input
              v-model="pinDigits"
              type="password"
              inputmode="numeric"
              maxlength="4"
              placeholder="4-digit PIN"
              class="mt-1 w-full h-10 px-3 rounded-[4px] bg-cabin-bg/75 border border-cabin-card/80 font-mono text-[14px] tracking-[0.25em] text-cabin-text focus:outline-none focus:border-cabin-navy-edge"
              @keyup.enter="submitPin"
            >
          </div>

          <button
            type="button"
            class="h-11 px-6 rounded-[6px] bg-cabin-card hover:bg-cabin-card/85 border border-cabin-text/25 text-[12px] font-bold uppercase tracking-[0.05em] text-cabin-text cursor-pointer disabled:opacity-45"
            :disabled="pinDigits.length !== 4 || isSubmitting"
            @click="submitPin"
          >
            {{ isSubmitting ? 'Verifying...' : 'Unlock Profile' }}
          </button>

          <p
            v-if="errorMessage"
            class="px-3 py-2 rounded-[4px] bg-cabin-crit/20 border border-cabin-crit/80 text-[11.5px] font-semibold text-cabin-text"
          >
            {{ errorMessage }}
          </p>
        </div>
      </div>
    </ShellHudWindow>

    <ShellHudWindow
      class="lg:col-span-5"
      title="Public Crew Views"
      subtitle="Read-only mission telemetry without PIN"
      icon="shield"
      tag-text="READ ONLY"
    >
      <div class="flex flex-col gap-3">
        <NuxtLink
          to="/crew-overview"
          class="p-4 rounded-[6px] bg-cabin-inset border border-cabin-card/70 hover:bg-cabin-card/30 transition-colors flex items-center justify-between"
        >
          <div>
            <div class="text-[13px] font-bold text-cabin-text">Crew Overview</div>
            <div class="text-[11px] text-cabin-muted">Group readiness, vital snapshot, and cabin atmosphere</div>
          </div>
          <Icon name="spacescan:shield" class="w-5 h-5 text-cabin-text" />
        </NuxtLink>

        <NuxtLink
          to="/crew-streaks"
          class="p-4 rounded-[6px] bg-cabin-inset border border-cabin-card/70 hover:bg-cabin-card/30 transition-colors flex items-center justify-between"
        >
          <div>
            <div class="text-[13px] font-bold text-cabin-text">Crew Streaks</div>
            <div class="text-[11px] text-cabin-muted">Daily logging consistency and 7-day compliance</div>
          </div>
          <Icon name="spacescan:flame" class="w-5 h-5 text-cabin-text" />
        </NuxtLink>
      </div>
    </ShellHudWindow>
  </div>
</template>
