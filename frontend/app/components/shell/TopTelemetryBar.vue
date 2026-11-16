<script setup lang="ts">
import logoUrl from '~/assets/hologram/logo.svg'

defineProps<{ authenticated: boolean }>()

const header = usePageHeader()
const { clockText, unread, mission } = useMission()
const { logout } = useSession()
const route = useRoute()
const { t } = useI18n()

const onNotifications = computed(() => route.path === '/notifications')

// The physician's patient switch: every results screen follows the chosen patient; capture
// screens keep recording for the physician.
const { isPhysician, activePatientId, patients, setActivePatient, crew } = useSession()
const { api } = useApi()
async function loadPatients() {
  if (!isPhysician.value) return
  try {
    patients.value = await api<PatientSummary[]>('/crew/patients')
  }
  catch {
    // Keep the last list; the next refresh corrects it.
  }
}
let patientTimer: ReturnType<typeof setInterval> | null = null
onMounted(() => {
  void loadPatients()
  patientTimer = setInterval(() => void loadPatients(), 30_000)
})
onBeforeUnmount(() => {
  if (patientTimer) clearInterval(patientTimer)
})
watch(isPhysician, () => void loadPatients())
const { signature } = useDataSync()
watch(signature(['alerts']), () => void loadPatients())
const onCapture = computed(() => route.path.startsWith('/capture'))
const onComms = computed(() => route.path.startsWith('/comms'))
const lastRoute = useState<string>('last-route-before-notifications', () => '/profile/personal')

watch(
  () => route.fullPath,
  (fullPath) => {
    if (route.path !== '/notifications' && route.path !== '/login') {
      lastRoute.value = fullPath
    }
  },
  { immediate: true },
)

async function toggleNotifications() {
  if (onNotifications.value) {
    await navigateTo(lastRoute.value || '/profile/personal')
  }
  else {
    await navigateTo('/notifications')
  }
}

async function signOut() {
  logout()
  await navigateTo('/login')
}
</script>

<template>
  <header
    class="relative shrink-0 w-full h-[56px] flex items-center px-[18px] border-b border-cabin-edge/40 bg-[var(--color-header-bg)]"
  >
    <img :src="logoUrl" alt="" class="w-[34px] h-[36px] shrink-0">
    <div class="ml-[8px] leading-tight w-[104px] shrink-0">
      <p class="text-[15.5px] font-bold tracking-[0.01em]">{{ t('brand.name') }}</p>
      <p class="text-[9.5px] font-semibold text-cabin-ice tracking-[0.04em]">{{ mission?.mission_code ?? '' }}</p>
    </div>

    <template v-if="header.title">
      <span class="w-px h-[30px] bg-cabin-text/20 mx-[18px]" />
      <div class="leading-tight min-w-0" :class="!authenticated ? '' : isPhysician && patients.length && !onCapture ? 'max-w-[calc(50%-527px)]' : 'max-w-[calc(50%-295px)]'">
        <h1 class="text-[15.5px] font-semibold truncate">{{ header.title }}</h1>
        <p v-if="header.subtitle" class="text-[9.5px] font-semibold text-cabin-ice tracking-[0.04em] uppercase">
          {{ header.subtitle }}
        </p>
      </div>
    </template>

    <div
      v-if="authenticated && isPhysician && patients.length"
      class="ml-[22px] flex items-center gap-[6px] shrink-0" role="group" aria-label="Patient view"
    >
      <!-- Compact chips (code only) so the switch fits beside the centred Capture button. -->
      <span v-if="onCapture" class="text-[8.5px] font-semibold text-cabin-muted tracking-[0.06em] mr-[4px] leading-tight">
        RECORDING<br>FOR YOU
      </span>
      <template v-if="!onCapture">
        <button
          v-for="p in patients" :key="p.id" type="button"
          class="focus-ring relative h-[28px] px-[8px] rounded-[4px] text-[10px] font-bold border-[1.3px] whitespace-nowrap"
          :class="p.id === activePatientId ? 'menu-item-active' : 'bg-cabin-tile border-cabin-line text-cabin-ice'"
          :aria-pressed="p.id === activePatientId"
          :aria-label="`Show ${p.full_name}${p.id === crew?.id ? ' (you)' : ''}${p.open_critical ? `, ${p.open_critical} critical advisories` : p.open_alerts ? `, ${p.open_alerts} advisories` : ''}`"
          :title="p.full_name"
          @click="setActivePatient(p.id)"
        >
          <span class="mono">{{ p.code }}</span>
          <i
            v-if="p.open_critical || p.open_alerts"
            class="absolute -top-[3px] -right-[3px] w-[7px] h-[7px] rounded-full"
            :class="p.open_critical ? 'bg-cabin-crit' : 'bg-cabin-navy-edge'"
          />
        </button>
      </template>
    </div>

    <NuxtLink
      v-if="authenticated"
      to="/capture/auscultation"
      class="focus-ring capture-header-btn absolute left-1/2 -translate-x-1/2 top-0 z-20 h-[63px] px-[20px] pb-[4px] flex items-center gap-[10px] text-[13px] font-extrabold tracking-[0.05em] uppercase text-cabin-text"
      :class="onCapture ? 'is-active' : ''"
      :aria-current="onCapture ? 'page' : undefined"
    >
      <span class="capture-plus-relief w-[36px] h-[36px] rounded-[7px] flex items-center justify-center shrink-0">
        <svg viewBox="0 0 24 24" class="w-[24px] h-[24px]" fill="none" stroke="currentColor" stroke-width="3.6" stroke-linecap="round" aria-hidden="true">
          <path d="M12 5v14M5 12h14" />
        </svg>
      </span>
      <span>{{ t('nav.capture') }}</span>
    </NuxtLink>

    <div class="ml-auto flex items-center gap-[12px]">
      <div class="leading-tight" :class="header.status || authenticated ? 'pl-[16px] border-l border-cabin-text/20' : ''">
        <p v-if="header.status || authenticated" class="text-[8.5px] font-semibold text-cabin-muted tracking-[0.06em]">
          {{ t('header.missionClock') }}
        </p>
        <p class="mono text-[11.5px] font-medium tracking-[0.04em]" aria-live="off">{{ clockText }}</p>
      </div>

      <template v-if="authenticated">
        <button
          type="button"
          class="focus-ring relative h-[40px] w-[40px] rounded-[5px] flex items-center justify-center border-[1.4px] cursor-pointer shrink-0"
          :class="[
            unread > 0 ? 'border-cabin-crit/85' : 'border-cabin-navy-edge/80',
            onNotifications ? 'menu-item-active text-cabin-text' : 'bg-cabin-tile text-cabin-text hover:border-cabin-text/60',
          ]"
          :aria-label="onNotifications ? t('header.notificationsClose') : t('header.notificationsLabel', { count: unread })"
          :aria-pressed="onNotifications"
          @click="toggleNotifications"
        >
          <span class="relative inline-flex items-center justify-center">
            <Icon name="spacescan:bell" class="w-[20px] h-[20px]" />
            <span
              v-if="unread > 0"
              class="absolute -top-[6px] -right-[7px] min-w-[16px] h-[16px] px-[4px] rounded-full bg-cabin-crit text-cabin-text text-[9.5px] font-bold leading-none flex items-center justify-center border border-[var(--color-header-bg)]"
            >
              {{ unread > 99 ? '99+' : unread }}
            </span>
          </span>
        </button>

        <NuxtLink
          to="/comms"
          class="focus-ring shrink-0"
          :class="onComms
            ? 'h-[40px] px-[14px] rounded-[4px] flex items-center justify-center gap-[8px] text-[11.5px] font-bold menu-item-active text-cabin-text'
            : 'hud-button !w-auto !h-[40px] px-[14px] !text-[11.5px]'"
          :aria-current="onComms ? 'page' : undefined"
        >
          <Icon name="spacescan:satellite" class="w-[15px] h-[15px] shrink-0" />
          <span>{{ t('nav.comms') }}</span>
        </NuxtLink>

        <button
          type="button"
          class="hud-button !w-auto !h-[40px] px-[16px] !text-[11.5px] shrink-0"
          @click="signOut"
        >
          <Icon name="spacescan:lock" class="w-[14px] h-[14px] shrink-0" />
          <span>{{ t('nav.signOut') }}</span>
        </button>
      </template>

      <div
        v-else-if="header.status"
        class="ml-[2px] h-[30px] w-[200px] rounded-full flex items-center px-[12px] text-[10.5px] font-bold tracking-[0.03em] border-[1.4px]"
        :class="{
          'bg-cabin-ok/15 border-cabin-ok/80': header.status.tone === 'ok',
          'bg-cabin-crit/30 border-cabin-crit/85': header.status.tone === 'critical',
          'bg-cabin-navy/50 border-cabin-navy-edge/80': header.status.tone === 'neutral',
        }"
        role="status"
      >
        <i
          class="w-[7px] h-[7px] rounded-full shrink-0"
          :class="{
            'bg-cabin-ok': header.status.tone === 'ok',
            'bg-cabin-crit': header.status.tone === 'critical',
            'bg-cabin-navy-edge': header.status.tone === 'neutral',
          }"
        />
        <span class="flex-1 text-center truncate uppercase">{{ header.status.text }}</span>
      </div>
    </div>
  </header>
</template>
