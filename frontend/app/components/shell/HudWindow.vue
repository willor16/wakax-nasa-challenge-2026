<script setup lang="ts">
withDefaults(
  defineProps<{
    title?: string
    subtitle?: string
    tagText?: string
    tagTone?: 'reference' | 'warn' | 'critical'
    icon?: string
  }>(),
  {
    title: undefined,
    subtitle: undefined,
    tagText: undefined,
    tagTone: 'reference',
    icon: undefined,
  },
)
</script>

<template>
  <section
    class="relative rounded-[6px] bg-cabin-card/28 border flex flex-col overflow-hidden"
    :style="{ borderColor: 'var(--window-frame-stroke)' }"
  >
    <span class="pointer-events-none absolute top-0 left-0 w-2 h-2 border-t-[1.4px] border-l-[1.4px] border-cabin-text/45" />
    <span class="pointer-events-none absolute top-0 right-0 w-2 h-2 border-t-[1.4px] border-r-[1.4px] border-cabin-text/45" />
    <span class="pointer-events-none absolute bottom-0 left-0 w-2 h-2 border-b-[1.4px] border-l-[1.4px] border-cabin-text/45" />
    <span class="pointer-events-none absolute bottom-0 right-0 w-2 h-2 border-b-[1.4px] border-r-[1.4px] border-cabin-text/45" />

    <header
      v-if="title"
      class="px-4 py-2.5 bg-cabin-card/58 border-b border-cabin-text/18 flex items-center justify-between gap-3"
    >
      <div class="flex items-center gap-2.5">
        <div
          v-if="icon"
          class="w-[22px] h-[22px] rounded-[4px] bg-cabin-inset border border-cabin-card/70 flex items-center justify-center"
        >
          <Icon :name="`spacescan:${icon}`" class="w-3.5 h-3.5 text-cabin-text" />
        </div>
        <div>
          <h2 class="text-[12.5px] font-bold tracking-[0.03em] uppercase text-cabin-text">
            {{ title }}
          </h2>
          <p v-if="subtitle" class="text-[10.5px] text-cabin-muted">
            {{ subtitle }}
          </p>
        </div>
      </div>

      <span
        v-if="tagText"
        class="px-3 h-[22px] rounded-full text-[9.8px] font-semibold tracking-[0.03em] inline-flex items-center gap-1.5 border"
        :class="{
          'bg-cabin-navy/42 border-cabin-navy-edge/70 text-cabin-text': tagTone === 'reference',
          'bg-cabin-navy/55 border-cabin-navy-edge/90 text-cabin-text': tagTone === 'warn',
          'bg-cabin-crit/25 border-cabin-crit/85 text-cabin-text': tagTone === 'critical',
        }"
      >
        <i v-if="tagTone === 'warn'" class="w-1.5 h-1.5 rounded-full bg-cabin-navy-edge" />
        {{ tagText }}
      </span>
    </header>

    <div class="p-5 flex-1">
      <slot />
    </div>
  </section>
</template>
