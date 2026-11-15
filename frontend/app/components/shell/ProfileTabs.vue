<script setup lang="ts">
const route = useRoute()
const { isOperator } = useSession()
const { t } = useI18n()
const tabs = [
  { id: 'personal', label: t('profileTabs.personal'), to: '/profile/personal' },
  { id: 'psychological', label: t('profileTabs.psychological'), to: '/profile/psychological' },
  { id: 'physical', label: t('profileTabs.physical'), to: '/profile/physical' },
  { id: 'streak', label: t('profileTabs.streak'), to: '/profile/streak' },
]
const active = ref(route.path.split('/').at(-1) ?? 'personal')
const onAdmin = computed(() => route.path === '/crew-management')
</script>

<template>
  <ShellSubnavTabs v-model="active" :tabs="tabs" :label="t('profileTabs.label')">
    <NuxtLink
v-if="isOperator" to="/crew-management"
              class="focus-ring h-[37px] px-[26px] rounded-[4px] text-[11.5px] font-semibold border-[1.3px] flex items-center gap-[8px]"
              :class="onAdmin ? 'menu-item-active font-bold' : 'bg-cabin-tile border-cabin-line text-cabin-ice/90 hover:text-cabin-text'">
      <Icon name="spacescan:shield" class="w-[14px] h-[14px]" />Crew Administration
    </NuxtLink>
    <slot />
  </ShellSubnavTabs>
</template>
