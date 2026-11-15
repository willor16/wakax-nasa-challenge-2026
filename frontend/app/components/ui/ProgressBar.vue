<script setup lang="ts">
import type { Tone } from '~/utils/format'

withDefaults(defineProps<{ pct: number, tone?: Tone, thick?: boolean }>(), { tone: 'ok' })
</script>

<template>
  <div class="w-full rounded-full bg-cabin-track overflow-hidden" :class="thick ? 'h-[5px]' : 'h-[3.5px]'">
    <div
      class="h-full rounded-full"
      :class="{
        'bg-cabin-ok': tone === 'ok',
        'bg-cabin-navy-edge': tone === 'watch',
        'bg-cabin-crit': tone === 'critical',
        'bg-cabin-dim': tone === 'neutral',
      }"
      :style="{ width: `${Math.min(100, Math.max(0, pct))}%` }"
    />
  </div>
</template>
