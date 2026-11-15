<script setup lang="ts">
import { TabsList, TabsRoot, TabsTrigger } from 'reka-ui'

withDefaults(
  defineProps<{
    showStageSelector?: boolean
  }>(),
  {
    showStageSelector: false,
  },
)

const missionStage = defineModel<'LAUNCH' | 'MISSION' | 'RETURN'>('missionStage', {
  default: 'MISSION',
})

const route = useRoute()
const router = useRouter()

const tabs = [
  { id: '/capture/auscultation', label: 'Auscultation Audio' },
  { id: '/capture/physical', label: 'Physical & Labs' },
  { id: '/capture/vision', label: 'Vision & Ocular' },
  { id: '/capture/psych-sleep', label: 'Psych, Motor & Sleep' },
]

const stages: Array<'LAUNCH' | 'MISSION' | 'RETURN'> = ['LAUNCH', 'MISSION', 'RETURN']

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
          class="relative h-9 px-5 rounded-[4px] text-[11.2px] border transition-colors cursor-pointer"
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
        v-if="showStageSelector"
        class="h-8 p-0.5 rounded-[4px] bg-cabin-inset border border-cabin-card/65 inline-flex items-center gap-1"
        role="group"
        aria-label="Mission stage selector"
      >
        <span class="px-2 text-[9.5px] font-bold tracking-[0.06em] uppercase text-cabin-muted">
          Stage
        </span>
        <button
          v-for="stage in stages"
          :key="stage"
          type="button"
          class="h-6 px-2.5 rounded-[3px] font-mono text-[10px] tracking-[0.05em] uppercase transition-colors cursor-pointer"
          :class="
            missionStage === stage
              ? 'menu-item-active font-bold text-cabin-text'
              : 'text-cabin-muted hover:text-cabin-text font-semibold border border-transparent'
          "
          @click="missionStage = stage"
        >
          {{ stage }}
        </button>
      </div>

      <span
        class="px-3.5 h-7 rounded-full bg-cabin-navy/42 border border-cabin-navy-edge/75 text-[10px] font-bold tracking-[0.05em] uppercase text-cabin-text inline-flex items-center"
      >
        DATA CAPTURE · FEEDS ALL MODULES
      </span>
    </div>
  </div>
</template>
