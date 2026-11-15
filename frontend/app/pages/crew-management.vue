<script setup lang="ts">
interface CrewRecord {
  id: string
  code: string
  full_name: string
  role: 'ASTRONAUT' | 'PILOT' | 'OPERATOR' | 'PHYSICIAN'
  age: number | null
  sex: 'F' | 'M' | 'X' | null
  blood_type: string | null
  height_cm: number | null
  is_active: number
  failed_attempts: number
}

interface BaselineRecord {
  metric_key: string
  display_name_en: string
  unit: string
  mean_val: number
  std_dev: number
  sample_count: number
}

const { activeCrew, authHeaders } = useSession()

const roster = ref<CrewRecord[]>([])
const baselines = ref<BaselineRecord[]>([])
const selectedCrewId = ref('ID-01')
const feedbackMessage = ref('')
const errorMessage = ref('')
const isBusy = ref(false)

const newCrew = reactive({
  id: 'ID-05',
  code: 'ID·05',
  full_name: '',
  role: 'ASTRONAUT' as CrewRecord['role'],
  pin: '',
  age: 33,
  sex: 'F' as 'F' | 'M' | 'X',
  blood_type: 'O+',
  height_cm: 170,
})

const isOperator = computed(() => activeCrew.value?.role === 'OPERATOR')

async function loadRoster() {
  if (!isOperator.value) return
  try {
    roster.value = await $fetch<CrewRecord[]>('/api/v1/crew', { headers: authHeaders() })
  }
  catch {
    errorMessage.value = 'Unable to load crew administration roster.'
  }
}

async function loadBaselines(crewId: string) {
  selectedCrewId.value = crewId
  try {
    baselines.value = await $fetch<BaselineRecord[]>(`/api/v1/crew/${crewId}/baselines`)
  }
  catch {
    baselines.value = []
  }
}

async function createMember() {
  feedbackMessage.value = ''
  errorMessage.value = ''
  isBusy.value = true
  try {
    await $fetch('/api/v1/crew', {
      method: 'POST',
      headers: authHeaders(),
      body: newCrew,
    })
    feedbackMessage.value = `Created profile ${newCrew.code}.`
    newCrew.full_name = ''
    newCrew.pin = ''
    await loadRoster()
  }
  catch (err: unknown) {
    const detail = (err as { data?: { detail?: string } })?.data?.detail
    errorMessage.value = detail || 'Unable to create crew profile.'
  }
  finally {
    isBusy.value = false
  }
}

async function toggleActive(member: CrewRecord) {
  feedbackMessage.value = ''
  errorMessage.value = ''
  try {
    await $fetch(`/api/v1/crew/${member.id}`, {
      method: 'PATCH',
      headers: authHeaders(),
      body: { is_active: member.is_active === 0, unlock_account: true },
    })
    await loadRoster()
  }
  catch {
    errorMessage.value = 'Unable to update crew member status.'
  }
}

async function recomputeBaselines(crewId: string) {
  feedbackMessage.value = ''
  errorMessage.value = ''
  try {
    const res = await $fetch<{ updated_count: number }>(`/api/v1/crew/${crewId}/baselines/recompute`, {
      method: 'POST',
      headers: authHeaders(),
    })
    feedbackMessage.value = `Recomputed ${res.updated_count} pre-flight baselines for ${crewId}.`
    await loadBaselines(crewId)
  }
  catch {
    errorMessage.value = 'Unable to recompute pre-flight baselines.'
  }
}

onMounted(async () => {
  await loadRoster()
  await loadBaselines(selectedCrewId.value)
})
</script>

<template>
  <div class="grid grid-cols-1 lg:grid-cols-12 gap-[18px] flex-1">
    <ShellHudWindow
      class="lg:col-span-7"
      title="Crew Roster & Access Administration"
      subtitle="Operator management for onboard crew profiles and pre-flight baselines"
      icon="profile"
      tag-text="OPERATOR ONLY"
    >
      <p
        v-if="!isOperator"
        class="px-4 py-3 rounded-[6px] bg-cabin-crit/20 border border-cabin-crit text-[12px] text-cabin-text"
      >
        Sign in with an Operator profile to create, edit, or deactivate crew members.
      </p>

      <template v-else>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-2.5 mb-4">
          <div
            v-for="member in roster"
            :key="member.id"
            class="p-3 rounded-[6px] bg-cabin-inset border border-cabin-card/70 flex items-center justify-between gap-2"
          >
            <div>
              <div class="font-mono text-[10.5px] text-cabin-muted">
                {{ member.code }} · {{ member.role }}
              </div>
              <div class="text-[13px] font-bold text-cabin-text">{{ member.full_name }}</div>
            </div>
            <div class="flex items-center gap-1.5">
              <button
                type="button"
                class="px-2.5 h-7 rounded-[4px] bg-cabin-navy/45 border border-cabin-navy-edge/80 text-[10px] font-bold uppercase text-cabin-text cursor-pointer"
                @click="recomputeBaselines(member.id)"
              >
                Baselines
              </button>
              <button
                type="button"
                class="px-2.5 h-7 rounded-[4px] border text-[10px] font-bold uppercase cursor-pointer"
                :class="member.is_active ? 'bg-cabin-card/45 border-cabin-card text-cabin-text' : 'bg-cabin-crit/25 border-cabin-crit text-cabin-text'"
                @click="toggleActive(member)"
              >
                {{ member.is_active ? 'Active' : 'Inactive' }}
              </button>
            </div>
          </div>
        </div>

        <form class="p-4 rounded-[6px] bg-cabin-inset border border-cabin-card/65 grid grid-cols-2 md:grid-cols-3 gap-3" @submit.prevent="createMember">
          <input v-model="newCrew.id" type="text" placeholder="ID-05" class="h-9 px-3 rounded-[4px] bg-cabin-bg border border-cabin-card/80 font-mono text-[12px] text-cabin-text">
          <input v-model="newCrew.code" type="text" placeholder="ID·05" class="h-9 px-3 rounded-[4px] bg-cabin-bg border border-cabin-card/80 font-mono text-[12px] text-cabin-text">
          <input v-model="newCrew.full_name" type="text" placeholder="Full Name" class="h-9 px-3 rounded-[4px] bg-cabin-bg border border-cabin-card/80 text-[12px] text-cabin-text">
          <select v-model="newCrew.role" class="h-9 px-3 rounded-[4px] bg-cabin-bg border border-cabin-card/80 text-[12px] text-cabin-text">
            <option value="ASTRONAUT">ASTRONAUT</option>
            <option value="PILOT">PILOT</option>
            <option value="OPERATOR">OPERATOR</option>
            <option value="PHYSICIAN">PHYSICIAN</option>
          </select>
          <input v-model="newCrew.pin" type="password" maxlength="4" placeholder="4-digit PIN" class="h-9 px-3 rounded-[4px] bg-cabin-bg border border-cabin-card/80 font-mono text-[12px] text-cabin-text">
          <button type="submit" :disabled="isBusy" class="h-9 px-4 rounded-[4px] bg-cabin-card hover:bg-cabin-card/85 text-[11px] font-bold uppercase text-cabin-text cursor-pointer">
            Add Crew Member
          </button>
        </form>

        <p v-if="feedbackMessage" class="mt-3 text-[11.5px] text-cabin-ok">{{ feedbackMessage }}</p>
        <p v-if="errorMessage" class="mt-3 text-[11.5px] text-cabin-crit">{{ errorMessage }}</p>
      </template>
    </ShellHudWindow>

    <ShellHudWindow
      class="lg:col-span-5"
      title="Pre-Flight Personal Baselines"
      subtitle="Reference mean and deviation computed from Launch stage"
      icon="vitruvian"
      :tag-text="selectedCrewId"
    >
      <div class="max-h-[420px] overflow-y-auto flex flex-col gap-2">
        <div
          v-for="item in baselines"
          :key="item.metric_key"
          class="px-3 py-2 rounded-[4px] bg-cabin-inset border border-cabin-card/55 flex items-center justify-between text-[11.5px]"
        >
          <span class="text-cabin-text">{{ item.display_name_en }}</span>
          <span class="font-mono text-cabin-ok">
            {{ item.mean_val }} ± {{ item.std_dev }} {{ item.unit }}
          </span>
        </div>
      </div>
    </ShellHudWindow>
  </div>
</template>
