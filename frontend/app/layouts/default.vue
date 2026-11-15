<script setup lang="ts">
// The cockpit is drawn on a fixed 1568 x 940 canvas (the design size) and scaled
// as one piece, so every display in the cabin shows the same proportions.
const { isAuthenticated } = useSession()
const route = useRoute()
useMissionFeed()

const DESIGN_WIDTH = 1568
const DESIGN_HEIGHT = 940
const PUBLIC_PATHS = new Set(['/login', '/crew-overview', '/crew-streaks'])

const scale = ref(1)
function fit() {
  scale.value = Math.min(window.innerWidth / DESIGN_WIDTH, window.innerHeight / DESIGN_HEIGHT)
}
onMounted(() => {
  fit()
  window.addEventListener('resize', fit)
})
onBeforeUnmount(() => window.removeEventListener('resize', fit))

const showDock = computed(() => isAuthenticated.value && !PUBLIC_PATHS.has(route.path))
</script>

<template>
  <div class="cockpit-stage">
    <div class="cockpit-canvas" :style="{ transform: `scale(${scale})` }">
      <ShellTopTelemetryBar :authenticated="showDock" />
      <main class="absolute left-0 right-0 top-[56px] bottom-[74px] px-[28px] pt-[10px] pb-[14px] flex flex-col gap-[12px] overflow-clip">
        <slot />
      </main>
      <ShellBottomCockpitDock v-if="showDock" />
      <ShellPublicHierarchyBar v-else />
    </div>
  </div>
</template>
