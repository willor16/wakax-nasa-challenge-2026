<script setup lang="ts">
const { isAuthenticated, cabinMode, unreadAlerts } = useSession()
const route = useRoute()

const utcClock = ref('')
let clockTimer: ReturnType<typeof setInterval> | null = null

function updateClock() {
  const now = new Date()
  utcClock.value = now.toISOString().slice(11, 19) + ' UTC'
}

onMounted(() => {
  updateClock()
  clockTimer = setInterval(updateClock, 1000)
})

onUnmounted(() => {
  if (clockTimer) clearInterval(clockTimer)
})
</script>

<template>
  <header class="h-[56px] px-7 bg-cabin-bg/86 border-b border-cabin-card/55 flex items-center justify-between gap-4 shrink-0">
    <div class="flex items-center gap-3">
      <div class="w-7 h-7 rounded-[4px] bg-cabin-card/35 border border-cabin-card/80 flex items-center justify-center">
        <Icon name="spacescan:rocket" class="w-4 h-4 text-cabin-text" />
      </div>
      <div class="flex items-baseline gap-2.5">
        <span class="text-[14px] font-bold tracking-[0.06em] uppercase text-cabin-text">
          {{ $t('brand.title') }}
        </span>
        <span class="font-mono text-[11px] font-semibold tracking-[0.08em] text-cabin-muted">
          {{ $t('brand.mission') }}
        </span>
      </div>
    </div>

    <div class="flex items-center gap-4">
      <div class="px-3.5 h-8 rounded-[4px] bg-cabin-inset border border-cabin-card/60 flex items-center gap-2.5">
        <span class="text-[10px] font-semibold tracking-[0.06em] uppercase text-cabin-muted">
          {{ $t('header.missionClock') }}
        </span>
        <span class="font-mono text-[12.5px] font-bold text-cabin-text">
          {{ utcClock || '00:00:00 UTC' }}
        </span>
      </div>

      <NuxtLink
        v-if="isAuthenticated"
        to="/notifications"
        class="h-8 px-3.5 rounded-[4px] border flex items-center gap-2 text-[11.5px] font-semibold transition-colors"
        :class="
          route.path === '/notifications'
            ? 'menu-item-active text-cabin-text'
            : 'bg-cabin-inset border-cabin-card/65 text-cabin-text hover:bg-cabin-card/35'
        "
      >
        <Icon name="spacescan:bell" class="w-3.5 h-3.5 text-cabin-text" />
        <span>{{ $t('header.notifications') }}</span>
        <span
          class="font-mono text-[10.5px] font-bold px-1.5 py-0.5 rounded-full"
          :class="unreadAlerts > 0 ? 'bg-cabin-crit/85 text-cabin-text' : 'bg-cabin-navy/55 text-cabin-text'"
        >
          {{ unreadAlerts }}
        </span>
      </NuxtLink>

      <div
        class="h-8 px-3.5 rounded-full border flex items-center gap-2 text-[10.8px] font-bold tracking-[0.05em] uppercase"
        :class="
          cabinMode === 'critical'
            ? 'bg-cabin-crit/25 border-cabin-crit text-cabin-text'
            : 'bg-cabin-navy/42 border-cabin-navy-edge/80 text-cabin-text'
        "
      >
        <span
          class="w-2 h-2 rounded-full"
          :class="cabinMode === 'critical' ? 'bg-cabin-crit' : 'bg-cabin-ok'"
        />
        <span>{{ cabinMode === 'critical' ? $t('header.cabinCritical') : $t('header.cabinNominal') }}</span>
      </div>
    </div>
  </header>
</template>
