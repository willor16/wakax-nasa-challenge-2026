<script setup lang="ts">
import { TabsList, TabsRoot, TabsTrigger } from 'reka-ui'

withDefaults(
  defineProps<{
    badgeText?: string
    badgeTone?: 'reference' | 'warn' | 'critical'
    showStageFilter?: boolean
  }>(),
  {
    badgeText: 'READ ONLY',
    badgeTone: 'reference',
    showStageFilter: true,
  },
)

const selectedStage = defineModel<'ALL' | 'LAUNCH' | 'MISSION' | 'RETURN'>('selectedStage', {
  default: 'ALL',
})

const route = useRoute()
const router = useRouter()

const tabs = [
  { id: '/profile/personal', label: 'Personal Data' },
  { id: '/profile/psychological', label: 'Psychological' },
  { id: '/profile/physical', label: 'Physical' },
]

const stageFilters: Array<{ value: 'ALL' | 'LAUNCH' | 'MISSION' | 'RETURN', label: string }> = [
  { value: 'ALL', label: 'ACTIVE' },
  { value: 'LAUNCH', label: 'LAUNCH' },
  { value: 'MISSION', label: 'MISSION' },
  { value: 'RETURN', label: 'RETURN' },
]

const activeTab = computed({
  get: () => route.path,
  set: async (nextPath: string) => {
    if (nextPath !== route.path) {
      await router.push(nextPath)
    }
  },
})
</script>

<template>
  <div class="flex flex-wrap items-center justify-between gap-3 min-h-[36px]">
    <TabsRoot v-model="activeTab">
      <TabsList class="flex flex-wrap items-center gap-2">
        <TabsTrigger
          v-for="tab in tabs"
          :key="tab.id"
          :value="tab.id"
          class="relative h-9 px-6 rounded-[4px] text-[11.5px] border transition-colors cursor-pointer"
          :class="
            activeTab === tab.id
              ? 'menu-item-active font-bold text-cabin-text'
              : 'bg-cabin-inset border-cabin-card/60 text-cabin-muted hover:text-cabin-text font-semibold'
          "
        >
          {{ tab.label }}
          <span
            v-if="activeTab === tab.id"
            class="pointer-events-none absolute bottom-0 inset-x-4 h-[2.5px] rounded-full bg-cabin-text/80"
          />
        </TabsTrigger>
      </TabsList>
    </TabsRoot>

    <div class="flex flex-wrap items-center gap-2.5">
      <div
        v-if="showStageFilter"
        class="h-8 p-0.5 rounded-[4px] bg-cabin-inset border border-cabin-card/65 inline-flex items-center gap-1"
        role="group"
        aria-label="Read-only mission stage comparison"
      >
        <span class="px-2 text-[9.5px] font-bold tracking-[0.06em] uppercase text-cabin-muted">
          Baseline View
        </span>
        <button
          v-for="filter in stageFilters"
          :key="filter.value"
          type="button"
          class="h-6 px-2.5 rounded-[3px] font-mono text-[10px] tracking-[0.05em] uppercase transition-colors cursor-pointer"
          :class="
            selectedStage === filter.value
              ? 'menu-item-active font-bold text-cabin-text'
              : 'text-cabin-muted hover:text-cabin-text font-semibold border border-transparent'
          "
          @click="selectedStage = filter.value"
        >
          {{ filter.label }}
        </button>
      </div>

      <span
        class="px-3.5 h-7 rounded-full border text-[10px] font-bold tracking-[0.05em] uppercase text-cabin-text inline-flex items-center gap-1.5"
        :class="{
          'bg-cabin-navy/42 border-cabin-navy-edge/75': badgeTone === 'reference',
          'bg-cabin-navy/60 border-cabin-navy-edge': badgeTone === 'warn',
          'bg-cabin-crit/25 border-cabin-crit/85': badgeTone === 'critical',
        }"
      >
        <span
          class="w-1.5 h-1.5 rounded-full"
          :class="{
            'bg-cabin-ok': badgeTone === 'reference',
            'bg-cabin-navy-edge': badgeTone === 'warn',
            'bg-cabin-crit': badgeTone === 'critical',
          }"
        />
        {{ badgeText }}
      </span>
    </div>
  </div>
</template>
