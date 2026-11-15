<script setup lang="ts">
// 36 px sub-bar of tabs or filters (Profile, Sleep, Capture, Notifications), built on
// accessible tab primitives. Tabs either navigate (``to``) or update the bound value.
import { TabsList, TabsRoot, TabsTrigger } from 'reka-ui'

export interface SubnavTab { id: string, label: string, to?: string }

const props = defineProps<{ tabs: SubnavTab[], tabWidth?: number, label: string }>()
const active = defineModel<string>({ required: true })

async function select(value: string | number) {
  const tab = props.tabs.find(item => item.id === value)
  if (!tab) return
  active.value = tab.id
  if (tab.to) await navigateTo(tab.to)
}
</script>

<template>
  <div class="h-[37px] shrink-0 flex items-center gap-[8px]">
    <TabsRoot :model-value="active" @update:model-value="select">
      <TabsList class="flex items-center gap-[8px]" :aria-label="label">
        <TabsTrigger
          v-for="tab in tabs"
          :key="tab.id"
          :value="tab.id"
          class="focus-ring relative h-[37px] rounded-[4px] text-[11.5px] font-semibold border-[1.3px] cursor-pointer"
          :class="[
            active === tab.id
              ? 'menu-item-active font-bold text-cabin-text'
              : 'bg-cabin-tile border-cabin-line text-cabin-ice/90 hover:text-cabin-text',
            tabWidth === 0 ? 'px-[46px]' : '',
          ]"
          :style="tabWidth === 0 ? undefined : { width: `${tabWidth ?? 186}px` }"
        >
          {{ tab.label }}
          <span v-if="active === tab.id" class="absolute bottom-[1px] left-[30px] right-[30px] h-[2.5px] rounded-full bg-cabin-text/85" />
        </TabsTrigger>
      </TabsList>
    </TabsRoot>
    <div class="ml-auto flex items-center gap-[10px]">
      <slot />
    </div>
  </div>
</template>
