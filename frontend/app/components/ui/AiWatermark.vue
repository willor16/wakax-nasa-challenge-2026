<script setup lang="ts">
// Quiet corner mark on places where assisted analysis or generated artwork was used.
// It names no engine; the wording is always the plain English "AI Used".
withDefaults(defineProps<{
  position?: 'top-right' | 'bottom-right' | 'bottom-left' | 'top-left' | 'bottom-center' | 'below' | 'inline'
}>(), { position: 'bottom-right' })

const { t } = useI18n()
</script>

<template>
  <span
    class="pointer-events-none select-none mono text-[9px] uppercase tracking-[0.08em] text-cabin-muted/45 whitespace-nowrap"
    :class="{
      'absolute top-[6px] right-[8px]': position === 'top-right',
      'absolute bottom-[6px] right-[8px]': position === 'bottom-right',
      'absolute bottom-[6px] left-[8px]': position === 'bottom-left',
      'absolute top-[6px] left-[8px]': position === 'top-left',
      'absolute bottom-[2px] left-1/2 -translate-x-1/2': position === 'bottom-center',
      'absolute top-full mt-[1px] left-1/2 -translate-x-1/2': position === 'below',
      'inline-block': position === 'inline',
    }"
    data-ai-watermark
  >{{ t('ai.used') }}</span>
</template>
