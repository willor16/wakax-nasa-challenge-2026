<script setup lang="ts">
// Outcome box under a Capture form: what was saved and any advisory it raised.
defineProps<{ tone: 'ok' | 'critical' | 'info', title: string, text: string }>()
</script>

<template>
  <div
class="relative rounded-[5px] border-[1.2px] h-[78px] shrink-0 pl-[24px] pr-[18px] flex flex-col justify-center"
       :class="tone === 'critical' ? 'border-cabin-crit/85 bg-[var(--color-crit-soft)]' : 'border-cabin-line bg-cabin-tile'"
       role="status">
    <span v-if="tone === 'critical'" class="absolute left-0 top-[10px] bottom-[10px] w-[3px] rounded-full bg-cabin-crit" />
    <p class="text-[10px] font-bold tracking-[0.04em] uppercase" :class="tone === 'ok' ? 'text-cabin-ok' : ''">{{ title }}</p>
    <p class="text-[12.5px] mt-[9px]">{{ text }}</p>
  </div>
</template>
