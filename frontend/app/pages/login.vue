<script setup lang="ts">
const router = useRouter()
const { signInMock } = useSession()

const crewRoster = [
  { id: 'ID-01', code: 'ID·01', fullName: 'Elena Vargas', shortName: 'E. VARGAS', role: 'PILOT' as const, status: 'Attention' },
  { id: 'ID-02', code: 'ID·02', fullName: 'Marcus Vance', shortName: 'M. VANCE', role: 'OPERATOR' as const, status: 'Optimal' },
  { id: 'ID-03', code: 'ID·03', fullName: 'Amara Okafor', shortName: 'A. OKAFOR', role: 'PHYSICIAN' as const, status: 'Optimal' },
  { id: 'ID-04', code: 'ID·04', fullName: 'Kenji Sato', shortName: 'K. SATO', role: 'ASTRONAUT' as const, status: 'Nominal' },
]

const selectedId = ref('ID-01')
const pinDigits = ref('')

async function submitPin() {
  if (pinDigits.value.length !== 4) return
  const chosen = crewRoster.find(c => c.id === selectedId.value)
  signInMock(chosen)
  await router.push('/profile/personal')
}
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
          @click="selectedId = member.id"
        >
          <div class="flex items-center justify-between">
            <span class="font-mono text-[11px] font-bold text-cabin-muted">{{ member.code }}</span>
            <span class="text-[10px] font-semibold uppercase tracking-[0.04em] text-cabin-ok">
              {{ member.status }}
            </span>
          </div>
          <div class="mt-1 text-[13.5px] font-bold text-cabin-text">
            {{ member.fullName }}
          </div>
          <div class="text-[10.5px] tracking-[0.04em] uppercase text-cabin-muted">
            {{ member.role }}
          </div>
        </button>
      </div>

      <div class="flex items-center gap-3">
        <input
          v-model="pinDigits"
          type="password"
          inputmode="numeric"
          maxlength="4"
          placeholder="4-digit PIN"
          class="h-11 px-4 rounded-[6px] bg-cabin-inset border border-cabin-card/80 font-mono text-[15px] tracking-[0.28em] text-cabin-text focus:outline-none focus:border-cabin-navy-edge w-48"
        >
        <button
          type="button"
          class="h-11 px-6 rounded-[6px] bg-cabin-card hover:bg-cabin-card/85 border border-cabin-text/25 text-[12px] font-bold uppercase tracking-[0.05em] text-cabin-text cursor-pointer disabled:opacity-45"
          :disabled="pinDigits.length !== 4"
          @click="submitPin"
        >
          Unlock Profile
        </button>
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
