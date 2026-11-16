<script setup lang="ts">
const route = useRoute()
const { t } = useI18n()
const tabs = [
  { id: 'auscultation', label: t('captureTabs.auscultation'), to: '/capture/auscultation' },
  { id: 'physical', label: t('captureTabs.physical'), to: '/capture/physical' },
  { id: 'vision', label: t('captureTabs.vision'), to: '/capture/vision' },
  { id: 'psych-sleep', label: t('captureTabs.psychSleep'), to: '/capture/psych-sleep' },
]
const active = ref(route.path.split('/').at(-1) ?? 'auscultation')
</script>

<template>
  <ShellSubnavTabs v-model="active" :tabs="tabs" :tab-width="0" :label="t('captureTabs.label')">
    <div class="h-[30px] w-[268px] rounded-full menu-item-active flex items-center justify-center text-[9.5px] font-bold tracking-[0.03em]">
      {{ t('captureTabs.feeds') }}
    </div>
  </ShellSubnavTabs>
</template>
