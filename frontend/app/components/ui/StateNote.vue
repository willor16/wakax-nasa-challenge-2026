<script setup lang="ts">
// Loading, empty and error message for a window body. Never shows stand-in numbers.
defineProps<{ loading?: boolean, error?: string | null, empty?: string }>()
defineEmits<{ retry: [] }>()
</script>

<template>
  <div class="flex-1 flex flex-col items-center justify-center gap-[10px] text-center px-6" role="status">
    <template v-if="loading">
      <span class="w-[22px] h-[22px] rounded-full border-2 border-cabin-edge border-t-cabin-text animate-spin" />
      <p class="text-[12px] text-cabin-ice">Loading…</p>
    </template>
    <template v-else-if="error">
      <Icon name="spacescan:alert" class="w-[22px] h-[22px] text-cabin-crit" />
      <p class="text-[12.5px] max-w-[420px]">{{ error }}</p>
      <button type="button" class="hud-button !w-[150px] !h-[34px] !text-[11.5px]" @click="$emit('retry')">
        Try Again
      </button>
    </template>
    <template v-else>
      <p class="text-[12.5px] text-cabin-ice max-w-[420px]">{{ empty }}</p>
      <slot />
    </template>
  </div>
</template>
