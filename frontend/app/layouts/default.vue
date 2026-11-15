<script setup lang="ts">
// The cockpit fills the whole display (100vw x 100dvh): a 56px top bar, the working area
// and the 72px bottom dock. Windows inside each screen share the space with proportional
// columns, so the same layout reads well from 1366 x 768 cabin tablets to 2560 x 1440 walls.
const { isAuthenticated } = useSession()
const route = useRoute()
useMissionFeed()

const PUBLIC_PATHS = new Set(['/login', '/crew-overview', '/crew-streaks'])

const showDock = computed(() => isAuthenticated.value && !PUBLIC_PATHS.has(route.path))
</script>

<template>
  <div class="cockpit-stage">
    <div class="cockpit-canvas">
      <ShellTopTelemetryBar :authenticated="showDock" />
      <main class="flex-1 min-h-0 w-full px-[28px] pt-[10px] pb-[14px] flex flex-col gap-[14px] overflow-hidden">
        <slot />
      </main>
      <ShellBottomCockpitDock v-if="showDock" />
      <ShellPublicHierarchyBar v-else />
    </div>
  </div>
</template>
