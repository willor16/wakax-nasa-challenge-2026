<script setup lang="ts">
import { TabsList, TabsRoot, TabsTrigger } from 'reka-ui'
import type { SleepPeriodFilter } from '~/composables/useSleep'

const props = withDefaults(
  defineProps<{
    lastNightLabel?: string
    restWindowBadge?: string
    scoreBadge?: string
    qualityTone?: 'reference' | 'warn' | 'critical'
  }>(),
  {
    lastNightLabel: 'Last Night (D45)',
    restWindowBadge: 'REST WINDOW · 22:18 – 05:54 UTC',
    scoreBadge: 'SCORE 84 · OPTIMAL',
    qualityTone: 'reference',
  },
)

const selectedPeriod = defineModel<SleepPeriodFilter>('selectedPeriod', {
  default: 'last_night',
})

const tabs = computed<Array<{ id: SleepPeriodFilter, label: string }>>(() => [
  { id: 'last_night', label: props.lastNightLabel },
  { id: '7d', label: 'Last 7 Days' },
  { id: '14d', label: 'Last 14 Days' },
  { id: '30d', label: 'Last 30 Days' },
])
</script>

<template>
  <div class="flex flex-wrap items-center justify-between gap-3 min-h-[36px]">
    <TabsRoot v-model="selectedPeriod">
      <TabsList class="flex flex-wrap items-center gap-2">
        <TabsTrigger
          v-for="tab in tabs"
          :key="tab.id"
          :value="tab.id"
          class="relative h-9 px-5 rounded-[4px] text-[11.5px] border transition-colors cursor-pointer"
          :class="
            selectedPeriod === tab.id
              ? 'menu-item-active font-bold text-cabin-text'
              : 'bg-cabin-inset border-cabin-card/60 text-cabin-muted hover:text-cabin-text font-semibold'
          "
        >
          {{ tab.label }}
          <span
            v-if="selectedPeriod === tab.id"
            class="pointer-events-none absolute bottom-0 inset-x-4 h-[2.5px] rounded-full bg-cabin-text/80"
          />
        </TabsTrigger>
      </TabsList>
    </TabsRoot>

    <div class="flex flex-wrap items-center gap-2.5">
      <span
        class="px-3.5 h-7 rounded-full border border-cabin-card/75 bg-cabin-inset font-mono text-[10px] font-semibold tracking-[0.05em] uppercase text-cabin-ice inline-flex items-center"
      >
        {{ restWindowBadge }}
      </span>

      <span
        class="px-3.5 h-7 rounded-full border text-[10px] font-bold tracking-[0.05em] uppercase text-cabin-text inline-flex items-center gap-1.5"
        :class="{
          'bg-cabin-navy/42 border-cabin-navy-edge/75': qualityTone === 'reference',
          'bg-cabin-navy/60 border-cabin-navy-edge': qualityTone === 'warn',
          'bg-cabin-crit/25 border-cabin-crit/85': qualityTone === 'critical',
        }"
      >
        <span
          class="w-1.5 h-1.5 rounded-full"
          :class="{
            'bg-cabin-ok': qualityTone === 'reference',
            'bg-cabin-navy-edge': qualityTone === 'warn',
            'bg-cabin-crit': qualityTone === 'critical',
          }"
        />
        {{ scoreBadge }}
      </span>
    </div>
  </div>
</template>
