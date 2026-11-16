<script setup lang="ts">
// Level 2 (after PIN): five health modules on a symmetric trapezoid with Profile raised at the centre.
const route = useRoute()
const { t } = useI18n()

const slots = [
  { to: '/vision', match: '/vision', icon: 'sans', label: 'nav.vision' },
  { to: '/sleep', match: '/sleep', icon: 'moon', label: 'nav.sleep' },
  { to: '/profile/personal', match: '/profile', icon: 'astronaut', label: 'nav.profile', main: true },
  { to: '/auscultation', match: '/auscultation', icon: 'stethoscope', label: 'nav.auscultation' },
  { to: '/guide', match: '/guide', icon: 'wiki', label: 'nav.guide' },
]
const isActive = (match: string) => route.path.startsWith(match)
</script>

<template>
  <nav class="relative shrink-0 w-full h-[72px]" :aria-label="t('nav.cockpitLabel')">
    <!-- The trapezoid keeps the 5-module design width on large displays and narrows on small ones. -->
    <div class="dock-trapezoid absolute left-1/2 -translate-x-1/2 bottom-0 h-[72px] w-[min(684px,calc(100%-120px))]" />
    <div class="absolute left-1/2 -translate-x-1/2 bottom-0 h-[72px] w-[min(636px,calc(100%-168px))] grid grid-cols-[1fr_1fr_1.45fr_1fr_1fr] items-end gap-[6px]">
      <NuxtLink
        v-for="slot in slots"
        :key="slot.to"
        :to="slot.to"
        class="focus-ring relative rounded-[4px] flex flex-col items-center justify-center border-[1.3px] min-w-0"
        :class="[
          slot.main
            ? 'h-[76px] -translate-y-[6px]'
            : 'h-[62px] mb-[6px] gap-[5px] text-[10.5px] whitespace-nowrap',
          isActive(slot.match)
            ? 'menu-item-active font-bold text-cabin-text'
            : slot.main
              ? 'bg-[var(--color-card-head)] border-cabin-text/45 text-cabin-text'
              : 'border-transparent text-cabin-ice/85 hover:text-cabin-text',
        ]"
        :aria-label="slot.main ? t(slot.label) : undefined"
        :title="slot.main ? t(slot.label) : undefined"
        :aria-current="isActive(slot.match) ? 'page' : undefined"
      >
        <Icon
          :name="`spacescan:${slot.icon}`"
          :size="slot.main ? 54 : 22"
          :class="slot.main ? 'w-[54px] h-[54px]' : 'w-[22px] h-[22px]'"
        />
        <span v-if="!slot.main">{{ t(slot.label) }}</span>
        <span
          v-if="isActive(slot.match)"
          class="absolute bottom-[2px] left-[24px] right-[24px] h-[2.5px] rounded-full bg-cabin-text/85"
        />
      </NuxtLink>
    </div>
  </nav>
</template>

<style scoped>
.dock-trapezoid {
  background: linear-gradient(180deg, var(--color-card-head) 0%, var(--color-card-fill) 100%);
  clip-path: polygon(2.6% 0, 97.4% 0, 100% 100%, 0 100%);
}
</style>
