<script setup lang="ts">
// Level 1 (no PIN): Sign In · Crew Overview · Crew Streaks.
const route = useRoute()
const { t } = useI18n()
const tabs = [
  { to: '/login', icon: 'lock', label: 'nav.signIn' },
  { to: '/crew-overview', icon: 'vitruvian', label: 'nav.crewOverview' },
  { to: '/crew-streaks', icon: 'flame', label: 'nav.crewStreaks' },
]
</script>

<template>
  <nav class="absolute bottom-0 left-0 right-0 h-[74px] flex justify-center" :aria-label="t('nav.publicLabel')">
    <div class="dock-trapezoid w-[690px] h-full flex items-end justify-center gap-[24px] px-[52px] pb-[6px]">
      <NuxtLink
        v-for="tab in tabs"
        :key="tab.to"
        :to="tab.to"
        class="focus-ring relative w-[180px] h-[62px] rounded-[4px] flex flex-col items-center justify-center gap-[5px] text-[11px] border-[1.3px] border-transparent"
        :class="route.path === tab.to ? 'menu-item-active font-bold text-cabin-text' : 'text-cabin-ice/85 hover:text-cabin-text'"
        :aria-current="route.path === tab.to ? 'page' : undefined"
      >
        <Icon :name="`spacescan:${tab.icon}`" class="w-[18px] h-[18px]" />
        {{ t(tab.label) }}
        <span v-if="route.path === tab.to" class="absolute bottom-[1px] left-[26px] right-[26px] h-[2.5px] rounded-full bg-cabin-text/85" />
      </NuxtLink>
    </div>
  </nav>
</template>

<style scoped>
.dock-trapezoid {
  background: linear-gradient(180deg, var(--color-card-head) 0%, var(--color-card-fill) 100%);
  clip-path: polygon(5% 0, 95% 0, 100% 100%, 0 100%);
}
</style>
