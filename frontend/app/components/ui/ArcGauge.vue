<script setup lang="ts">
// 270-degree dial with a label, a large value and a caption in the centre.
import VChart from 'vue-echarts'
import type { GaugeTone } from '~/utils/charts'
import { arcGaugeOption } from '~/utils/charts'

const props = withDefaults(defineProps<{
  fraction: number
  tone?: GaugeTone
  label: string
  value: string
  caption?: string
  /** Pixels, or any CSS length (``clamp(...)``) for windows that resize. */
  size?: number | string
  valueSize?: number
}>(), { tone: 'ok', caption: undefined, size: 104, valueSize: 21 })

const box = computed(() => (typeof props.size === 'number' ? `${props.size}px` : props.size))
const option = computed(() => arcGaugeOption(props.fraction, props.tone))
</script>

<template>
  <div
    class="relative shrink-0"
    :style="{ width: box, height: box }"
    role="img"
    :aria-label="`${label}: ${value}${caption ? `, ${caption}` : ''}`"
  >
    <ClientOnly>
      <VChart :option="option" theme="spacescan-hud" autoresize class="absolute inset-0" />
    </ClientOnly>
    <div class="absolute inset-0 flex flex-col items-center justify-center text-center leading-tight pointer-events-none">
      <span class="text-[8.5px] font-bold tracking-[0.04em] uppercase text-cabin-ice">{{ label }}</span>
      <span class="font-bold" :style="{ fontSize: `${valueSize}px` }">{{ value }}</span>
      <span v-if="caption" class="text-[9.5px] text-cabin-ice">{{ caption }}</span>
    </div>
  </div>
</template>
