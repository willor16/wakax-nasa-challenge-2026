<script setup lang="ts">
// Holographic artwork from the design file with a status ring. The artwork was generated
// with AI tools, so it carries the general "AI Used" mark. Whole-body figures follow the
// crew member's sex: the female figures are derived from the same artwork (narrower
// shoulders and waist, wider hips, shoulder-length hair).
import bodyUrl from '~/assets/hologram/body_small.svg'
import bodyScanUrl from '~/assets/hologram/body_scan.svg'
import bodyScanFemaleUrl from '~/assets/hologram/body_scan_f.svg'
import bodyFemaleUrl from '~/assets/hologram/body_small_f.svg'
import brainUrl from '~/assets/hologram/brain.svg'
import heartUrl from '~/assets/hologram/heart.svg'
import lungsUrl from '~/assets/hologram/lungs.svg'
import type { Tone } from '~/utils/format'

const props = withDefaults(defineProps<{
  figure: 'body' | 'body-scan' | 'heart' | 'lungs' | 'brain'
  tone?: Tone
  /** Pixels, or any CSS length such as ``clamp(72px, 14dvh, 168px)`` for windows that resize. */
  size?: number | string
  label: string
  watermark?: boolean
  /** ``F`` draws the female body; anything else the male one. Organs are the same for both. */
  sex?: 'F' | 'M' | string | null
}>(), { tone: 'ok', size: 104, watermark: true, sex: null })

const sources = { 'body': bodyUrl, 'body-scan': bodyScanUrl, 'heart': heartUrl, 'lungs': lungsUrl, 'brain': brainUrl }
const female = { 'body': bodyFemaleUrl, 'body-scan': bodyScanFemaleUrl } as Record<string, string>
const src = computed(() => (props.sex === 'F' ? female[props.figure] : undefined) ?? sources[props.figure])
const box = computed(() => (typeof props.size === 'number' ? `${props.size}px` : props.size))
const ring = computed(() => props.figure === 'body' || props.figure === 'brain')
</script>

<template>
  <div
    class="relative shrink-0 rounded-full"
    :class="figure === 'body-scan' ? 'hologram-shell' : ''"
    :style="{ width: box, height: box }"
    role="img"
    :aria-label="label"
  >
    <img :src="src" alt="" class="absolute inset-0 w-full h-full">
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
    <UiAiWatermark v-if="watermark" :position="figure === 'body-scan' ? 'bottom-center' : 'below'" />
  </div>
</template>
