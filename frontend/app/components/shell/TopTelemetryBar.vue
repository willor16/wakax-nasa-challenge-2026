<script setup lang="ts">
import logoUrl from '~/assets/hologram/logo.svg'

defineProps<{ authenticated: boolean }>()

const header = usePageHeader()
const { clockText, unread, mission } = useMission()
const route = useRoute()
const { t } = useI18n()
const onNotifications = computed(() => route.path === '/notifications')
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
      <div class="leading-tight min-w-0">
        <h1 class="text-[15.5px] font-semibold truncate">{{ header.title }}</h1>
        <p v-if="header.subtitle" class="text-[9.5px] font-semibold text-cabin-ice tracking-[0.04em] uppercase">
          {{ header.subtitle }}
        </p>
      </div>
    </template>

    <div class="ml-auto flex items-center">
      <div class="leading-tight" :class="header.status || authenticated ? 'pl-[16px] border-l border-cabin-text/20' : ''">
        <p v-if="header.status || authenticated" class="text-[8.5px] font-semibold text-cabin-muted tracking-[0.06em]">
          {{ t('header.missionClock') }}
        </p>
        <p class="mono text-[11.5px] font-medium tracking-[0.04em]" aria-live="off">{{ clockText }}</p>
      </div>

      <NuxtLink
        v-if="authenticated"
        to="/notifications"
        class="focus-ring ml-[58px] h-[30px] w-[160px] rounded-full flex items-center justify-center gap-[10px] text-[11.5px] font-semibold border-[1.4px]"
        :class="[
          unread > 0 ? 'border-cabin-crit/85' : 'border-cabin-navy-edge/80',
          onNotifications ? 'bg-cabin-navy/60' : 'bg-cabin-tile',
        ]"
        :aria-label="t('header.notificationsLabel', { count: unread })"
      >
        <span class="relative">
          <Icon name="spacescan:bell" class="w-[15px] h-[15px]" />
          <i v-if="unread > 0" class="absolute -top-[3px] -right-[3px] w-[6px] h-[6px] rounded-full bg-cabin-crit" />
        </span>
        {{ t('header.notifications', { count: unread }) }}
      </NuxtLink>

      <div
        v-if="header.status"
        class="ml-[14px] h-[30px] w-[200px] rounded-full flex items-center px-[12px] text-[10.5px] font-bold tracking-[0.03em] border-[1.4px]"
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
