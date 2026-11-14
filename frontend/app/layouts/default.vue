<script setup lang="ts">
const { isAuthenticated } = useSession()
const route = useRoute()

const publicRoutes = new Set(['/login', '/crew-overview', '/crew-streaks'])
const showAuthenticatedDock = computed(() => isAuthenticated.value && !publicRoutes.has(route.path))
</script>

<template>
  <div class="cockpit-canvas min-h-screen w-full flex flex-col justify-between overflow-x-hidden">
    <ShellTopTelemetryBar />

    <main class="flex-1 w-full max-w-[1568px] mx-auto p-[28px] flex flex-col gap-[18px]">
      <slot />
    </main>

    <ShellBottomCockpitDock v-if="showAuthenticatedDock" />
    <ShellPublicHierarchyBar v-else />
  </div>
</template>
