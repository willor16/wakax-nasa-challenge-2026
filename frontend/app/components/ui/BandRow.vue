<script setup lang="ts">
// Results row: name and reference on the left, value and status pill on the right, and a
// track with the reference band (navy) and the current value (dot). Read-only.
import type { StatusCode } from '~/utils/format'
import { scalePct, toneOf } from '~/utils/format'

const props = defineProps<{
  label: string
  reference?: string
  valueText: string
  unit?: string
  status: StatusCode
  statusText: string
  value?: number | null
  scaleMin?: number | null
  scaleMax?: number | null
  bandLow?: number | null
  bandHigh?: number | null
  /** Parameter key for the "?" help button next to the name. */
  helpKey?: string
}>()

const hasScale = computed(() => props.scaleMin != null && props.scaleMax != null && props.scaleMax > props.scaleMin)
const band = computed(() => {
  if (!hasScale.value || props.bandLow == null || props.bandHigh == null) return null
  const left = scalePct(props.bandLow, props.scaleMin!, props.scaleMax!)
  const right = scalePct(props.bandHigh, props.scaleMin!, props.scaleMax!)
  return { left: `${left}%`, width: `${Math.max(2, right - left)}%` }
})
const marker = computed(() => (hasScale.value && props.value != null
  ? `${scalePct(props.value, props.scaleMin!, props.scaleMax!)}%`
  : null))
const tone = computed(() => toneOf(props.status))
</script>

<template>
  <div>
    <div class="flex items-start justify-between gap-3">
      <div class="min-w-0">
        <p class="text-[13px] font-semibold leading-tight flex items-center gap-[6px] min-w-0">
          <span class="truncate">{{ label }}</span>
          <UiParamHelp v-if="helpKey" :metric-key="helpKey" />
        </p>
        <p v-if="reference" class="text-[9.8px] text-cabin-ice mt-[3px] truncate">{{ reference }}</p>
      </div>
      <div class="flex items-center gap-[14px] shrink-0">
        <p class="font-bold text-[20px] leading-none">
          {{ valueText }}<span v-if="unit" class="text-[10.5px] font-normal text-cabin-ice ml-[6px]">{{ unit }}</span>
        </p>
        <UiStatusPill :tone="tone === 'critical' ? 'critical' : tone === 'watch' ? 'watch' : 'reference'" class="min-w-[62px]">
          {{ statusText }}
        </UiStatusPill>
      </div>
    </div>
    <div class="relative h-[10px] mt-[10px]" aria-hidden="true">
      <div class="absolute left-0 right-0 top-[3.5px] h-[3px] rounded-full bg-cabin-track" />
      <div
        v-if="band"
        class="absolute top-[1px] h-[8px] rounded-full bg-[var(--color-band-fill)] border border-cabin-navy-edge/70"
        :style="band"
      />
      <i
        v-if="marker"
        class="absolute top-[1px] w-[8px] h-[8px] -ml-[4px] rounded-full border border-cabin-bg"
        :class="{
          'bg-cabin-ok': tone === 'ok',
          'bg-cabin-navy-edge': tone === 'watch',
          'bg-cabin-crit': tone === 'critical',
          'bg-cabin-dim': tone === 'neutral',
        }"
        :style="{ left: marker }"
      />
    </div>
  </div>
</template>
