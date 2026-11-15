<script setup lang="ts">
// Small rounded label. Reference pills are navy; only critical states turn red.
withDefaults(defineProps<{
  tone?: 'reference' | 'ok' | 'watch' | 'critical' | 'neutral'
  dot?: boolean
  size?: 'sm' | 'md'
}>(), { tone: 'reference', size: 'md' })
</script>

<template>
  <span
    class="inline-flex items-center justify-center gap-[6px] rounded-full font-bold tracking-[0.03em] border-[1.2px] whitespace-nowrap shrink-0"
    :class="[
      size === 'sm' ? 'h-[20px] px-[12px] text-[9px]' : 'h-[23px] px-[14px] text-[9.8px]',
      tone === 'critical'
        ? 'bg-cabin-crit/25 border-cabin-crit/85 text-cabin-text'
        : 'bg-[var(--color-pill-fill)] border-[var(--color-pill-edge)] text-cabin-text',
    ]"
  >
    <i v-if="dot || tone === 'watch'" class="w-[6px] h-[6px] rounded-full bg-cabin-navy-edge" />
    <slot />
  </span>
</template>
