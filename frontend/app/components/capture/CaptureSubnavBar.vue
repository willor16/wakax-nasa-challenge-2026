<script setup lang="ts">
import { TabsList, TabsRoot, TabsTrigger } from 'reka-ui'

const route = useRoute()
const router = useRouter()

const tabs = [
  { id: '/capture/auscultation', label: 'Auscultation Audio' },
  { id: '/capture/physical', label: 'Physical & Labs' },
  { id: '/capture/vision', label: 'Vision & Ocular' },
  { id: '/capture/psych-sleep', label: 'Psych, Motor & Sleep' },
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
  <TabsRoot v-model="activeTab" class="mb-4">
    <TabsList class="flex flex-wrap items-center gap-2">
      <TabsTrigger
        v-for="tab in tabs"
        :key="tab.id"
        :value="tab.id"
        class="h-9 px-5 rounded-[4px] text-[11.2px] font-semibold border transition-colors cursor-pointer bg-cabin-inset border-cabin-card/60 text-cabin-muted hover:text-cabin-text data-[state=active]:menu-item-active data-[state=active]:font-bold data-[state=active]:text-cabin-text"
      >
        {{ tab.label }}
      </TabsTrigger>
    </TabsList>
  </TabsRoot>
</template>
