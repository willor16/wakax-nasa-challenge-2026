<script setup lang="ts">
// Holographic artwork from the design file with a status ring and the scan sweep.
import bodyUrl from '~/assets/hologram/body_small.svg'
import bodyScanUrl from '~/assets/hologram/body_scan.svg'
import brainUrl from '~/assets/hologram/brain.svg'
import heartUrl from '~/assets/hologram/heart.svg'
import lungsUrl from '~/assets/hologram/lungs.svg'
import type { Tone } from '~/utils/format'

const props = withDefaults(defineProps<{
  figure: 'body' | 'body-scan' | 'heart' | 'lungs' | 'brain'
  tone?: Tone
  size?: number
  label: string
}>(), { tone: 'ok', size: 104 })

const sources = { 'body': bodyUrl, 'body-scan': bodyScanUrl, 'heart': heartUrl, 'lungs': lungsUrl, 'brain': brainUrl }
const ring = computed(() => props.figure === 'body' || props.figure === 'brain')
</script>

<template>
  <div
    class="relative shrink-0 rounded-full"
    :class="figure === 'body-scan' ? 'hologram-shell hologram-scanline' : ''"
    :style="{ width: `${size}px`, height: `${size}px` }"
    role="img"
    :aria-label="label"
  >
    <img :src="sources[figure]" alt="" class="absolute inset-0 w-full h-full">
    <span
      v-if="ring"
      class="absolute rounded-full border-[1.3px] border-dashed"
      :class="{
        'border-cabin-ok/60': tone === 'ok',
        'border-cabin-navy-edge': tone === 'watch',
        'border-cabin-crit/70': tone === 'critical',
        'border-cabin-dim/60': tone === 'neutral',
      }"
      :style="{ inset: figure === 'body' ? '11%' : '1%' }"
    />
  </div>
</template>
