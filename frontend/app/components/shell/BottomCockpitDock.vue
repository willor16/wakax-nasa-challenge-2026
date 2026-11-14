<script setup lang="ts">
const route = useRoute()
const router = useRouter()
const { activeCrew, signOut } = useSession()

const dockModules = [
  { to: '/vision', match: '/vision', labelKey: 'nav.dock.vision', icon: 'sans', center: false },
  { to: '/sleep', match: '/sleep', labelKey: 'nav.dock.sleep', icon: 'moon', center: false },
  { to: '/auscultation', match: '/auscultation', labelKey: 'nav.dock.auscultation', icon: 'stethoscope', center: false },
  { to: '/profile/personal', match: '/profile', labelKey: 'nav.dock.profile', icon: 'profile', center: true },
  { to: '/capture/auscultation', match: '/capture', labelKey: 'nav.dock.capture', icon: 'capture', center: false },
  { to: '/guide', match: '/guide', labelKey: 'nav.dock.guide', icon: 'wiki', center: false },
  { to: '/comms', match: '/comms', labelKey: 'nav.dock.comms', icon: 'earth', center: false },
]

function isActive(matchPrefix: string): boolean {
  return route.path === matchPrefix || route.path.startsWith(`${matchPrefix}/`)
}

async function handleSignOut() {
  signOut()
  await router.push('/login')
}
</script>

<template>
  <nav
    aria-label="Authenticated cockpit dock"
    class="h-[72px] px-7 bg-cabin-bg/90 border-t border-cabin-card/60 flex items-center justify-between gap-4 shrink-0"
  >
    <!-- Active crew badge (left) -->
    <div class="h-11 px-3.5 rounded-[6px] bg-cabin-inset border border-cabin-card/70 flex items-center gap-2.5 min-w-[175px]">
      <span class="w-2 h-2 rounded-full bg-cabin-ok shrink-0" />
      <div class="leading-tight">
        <div class="font-mono text-[10.5px] font-bold text-cabin-muted">
          {{ activeCrew?.code ?? 'ID·01' }}
        </div>
        <div class="text-[11.5px] font-bold tracking-[0.03em] text-cabin-text truncate">
          {{ activeCrew?.shortName ?? 'E. VARGAS' }}
        </div>
      </div>
    </div>

    <!-- Symmetrical 7-module trapezoid with Profile elevated at slot 4 -->
    <div class="flex items-end gap-2">
      <NuxtLink
        v-for="mod in dockModules"
        :key="mod.to"
        :to="mod.to"
        class="rounded-t-[8px] rounded-b-[4px] border flex flex-col items-center justify-center gap-1 transition-all"
        :class="[
          mod.center ? 'w-[192px] h-[56px] -translate-y-[8px]' : 'w-[138px] h-[48px]',
          isActive(mod.match)
            ? 'menu-item-active text-cabin-text'
            : 'bg-cabin-card/28 border-cabin-card/70 text-cabin-muted hover:text-cabin-text hover:bg-cabin-card/42',
        ]"
      >
        <Icon :name="`spacescan:${mod.icon}`" :class="mod.center ? 'w-4 h-4' : 'w-3.5 h-3.5'" />
        <span
          class="font-bold tracking-[0.04em] uppercase"
          :class="mod.center ? 'text-[11.5px]' : 'text-[10.5px]'"
        >
          {{ $t(mod.labelKey) }}
        </span>
      </NuxtLink>
    </div>

    <!-- Sign Out button (right) -->
    <button
      type="button"
      class="h-10 px-5 rounded-[6px] bg-cabin-card hover:bg-cabin-card/85 border border-cabin-text/20 text-[11.5px] font-bold tracking-[0.04em] uppercase text-cabin-text transition-colors min-w-[130px] cursor-pointer"
      @click="handleSignOut"
    >
      {{ $t('nav.dock.signOut') }}
    </button>
  </nav>
</template>
