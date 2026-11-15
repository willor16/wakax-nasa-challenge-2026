<script setup lang="ts">
// Universal window: smoked-glass card, precision corner marks, header with icon and tag.
withDefaults(defineProps<{
  title?: string
  tagText?: string
  tagTone?: 'reference' | 'warn' | 'critical'
  icon?: string
  critical?: boolean
  flush?: boolean
}>(), {
  title: undefined,
  tagText: undefined,
  tagTone: 'reference',
  icon: undefined,
})
</script>

<template>
  <section
    class="relative rounded-[6px] bg-[var(--color-card-fill)] border flex flex-col min-h-0 min-w-0"
    :style="{ borderColor: critical ? 'var(--color-crit-edge)' : 'var(--window-frame-stroke)' }"
    :aria-label="title"
  >
    <span class="corner top-0 left-0 border-t-[1.4px] border-l-[1.4px]" />
    <span class="corner top-0 right-0 border-t-[1.4px] border-r-[1.4px]" />
    <span class="corner bottom-0 left-0 border-b-[1.4px] border-l-[1.4px]" />
    <span class="corner bottom-0 right-0 border-b-[1.4px] border-r-[1.4px]" />

    <header
      v-if="title || $slots.header"
      class="h-[40px] shrink-0 px-[12px] bg-[var(--color-card-head)] border-b border-[var(--color-text-line)] flex items-center justify-between gap-3 rounded-t-[5px]"
    >
      <slot name="header">
        <div class="flex items-center gap-[10px] min-w-0">
          <div
            v-if="icon"
            class="w-[22px] h-[22px] shrink-0 rounded-[4px] bg-cabin-tile border border-cabin-edge/70 flex items-center justify-center"
          >
            <Icon :name="`spacescan:${icon}`" class="w-[13px] h-[13px]" />
          </div>
          <h2 class="text-[13px] font-bold tracking-[0.02em] uppercase truncate">{{ title }}</h2>
        </div>
      </slot>
      <UiStatusPill v-if="tagText" :tone="tagTone === 'critical' ? 'critical' : 'reference'" :dot="tagTone === 'warn'">
        {{ tagText }}
      </UiStatusPill>
    </header>

    <div class="flex-1 min-h-0 flex flex-col" :class="flush ? '' : 'p-[18px]'">
      <slot />
    </div>
  </section>
</template>

<style scoped>
.corner {
  position: absolute;
  width: 8px;
  height: 8px;
  pointer-events: none;
  border-color: var(--color-text-corner);
}
</style>
