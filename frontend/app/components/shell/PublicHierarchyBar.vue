<script setup lang="ts">
const route = useRoute()

const publicTabs = [
  { to: '/login', labelKey: 'nav.public.signIn', icon: 'lock' },
  { to: '/crew-overview', labelKey: 'nav.public.crewOverview', icon: 'shield' },
  { to: '/crew-streaks', labelKey: 'nav.public.crewStreaks', icon: 'flame' },
]
</script>

<template>
  <nav
    aria-label="Public cabin navigation"
    class="h-[68px] px-7 bg-cabin-bg/88 border-t border-cabin-card/55 flex items-center justify-center shrink-0"
  >
    <div class="flex items-center gap-3">
      <NuxtLink
        v-for="tab in publicTabs"
        :key="tab.to"
        :to="tab.to"
        class="h-10 px-6 rounded-[6px] border flex items-center gap-2.5 text-[12px] font-bold tracking-[0.03em] uppercase transition-colors"
        :class="
          route.path === tab.to
            ? 'menu-item-active text-cabin-text'
            : 'bg-cabin-card/30 border-cabin-card/70 text-cabin-muted hover:text-cabin-text'
        "
      >
        <Icon :name="`spacescan:${tab.icon}`" class="w-4 h-4" />
        <span>{{ $t(tab.labelKey) }}</span>
      </NuxtLink>
    </div>
  </nav>
</template>
