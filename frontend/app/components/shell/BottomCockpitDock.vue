<script setup lang="ts">
// Level 2 (after PIN): seven modules on a symmetric trapezoid with Profile raised at the centre.
const route = useRoute()
const { crew, logout } = useSession()
const { t } = useI18n()

const slots = [
  { to: '/vision', match: '/vision', icon: 'sans', label: 'nav.vision' },
  { to: '/sleep', match: '/sleep', icon: 'moon', label: 'nav.sleep' },
  { to: '/auscultation', match: '/auscultation', icon: 'stethoscope', label: 'nav.auscultation' },
  { to: '/profile/personal', match: '/profile', icon: 'profile', label: 'nav.profile', main: true },
  { to: '/capture/auscultation', match: '/capture', icon: 'capture', label: 'nav.capture' },
  { to: '/guide', match: '/guide', icon: 'wiki', label: 'nav.guide' },
  { to: '/comms', match: '/comms', icon: 'earth', label: 'nav.comms' },
]
const isActive = (match: string) => route.path.startsWith(match)

async function signOut() {
  logout()
  await navigateTo('/login')
}
</script>

<template>
  <nav class="relative shrink-0 w-full h-[72px]" :aria-label="t('nav.cockpitLabel')">
    <div class="absolute left-[24px] bottom-[12px] w-[211px] h-[46px] tile-hi flex items-center px-[20px] gap-[14px]">
      <Icon name="spacescan:profile" class="w-[16px] h-[16px] shrink-0" />
      <span class="flex-1 text-center text-[10.5px] font-bold tracking-[0.03em] truncate">
        {{ crew?.code }} · {{ crew?.short_name }}
      </span>
    </div>

    <!-- The trapezoid keeps the design width on large displays and narrows on small ones. -->
    <div class="dock-trapezoid absolute left-1/2 -translate-x-1/2 bottom-0 h-[72px] w-[min(1104px,calc(100%-464px))]" />
    <div class="absolute left-1/2 -translate-x-1/2 bottom-0 h-[72px] w-[min(1056px,calc(100%-512px))] flex items-end justify-between gap-[6px]">
      <NuxtLink
        v-for="slot in slots"
        :key="slot.to"
        :to="slot.to"
        class="focus-ring relative rounded-[4px] flex flex-col items-center justify-center border-[1.3px]"
        :class="[
          slot.main
            ? 'flex-[1.39] max-w-[172px] min-w-0 h-[76px] -translate-y-[6px] gap-[6px] text-[12.5px] font-bold'
            : 'flex-1 max-w-[124px] min-w-0 h-[62px] mb-[6px] gap-[7px] text-[10.5px] whitespace-nowrap',
          isActive(slot.match)
            ? 'menu-item-active font-bold text-cabin-text'
            : slot.main
              ? 'bg-[var(--color-card-head)] border-cabin-text/45 text-cabin-text'
              : 'border-transparent text-cabin-ice/85 hover:text-cabin-text',
        ]"
        :aria-current="isActive(slot.match) ? 'page' : undefined"
      >
        <Icon :name="`spacescan:${slot.icon}`" :class="slot.main ? 'w-[22px] h-[22px]' : 'w-[18px] h-[18px]'" />
        {{ t(slot.label) }}
        <span
          v-if="isActive(slot.match)"
          class="absolute bottom-[1px] left-[24px] right-[24px] h-[2.5px] rounded-full bg-cabin-text/85"
        />
      </NuxtLink>
    </div>

    <button
      type="button"
      class="hud-button absolute right-[25px] bottom-[12px] !w-[210px] !h-[46px] !text-[11.5px]"
      @click="signOut"
    >
      <Icon name="spacescan:lock" class="w-[15px] h-[15px] absolute left-[24px]" />
      {{ t('nav.signOut') }}
    </button>
  </nav>
</template>

<style scoped>
.dock-trapezoid {
  background: linear-gradient(180deg, var(--color-card-head) 0%, var(--color-card-fill) 100%);
  clip-path: polygon(2.6% 0, 97.4% 0, 100% 100%, 0 100%);
}
</style>
