<script setup lang="ts">
// Labelled numeric entry for Capture forms (label + hint above, unit inside the field).
defineProps<{ label: string, hint?: string, unit?: string, placeholder?: string, error?: string | null
  inputmode?: 'decimal' | 'numeric' | 'text', id: string }>()
const model = defineModel<string>({ required: true })
</script>

<template>
  <div>
    <div class="flex items-baseline justify-between gap-2 mb-[8px]">
      <label :for="id" class="label-caps">{{ label }}</label>
      <span v-if="hint" class="text-[9.5px] text-cabin-ice truncate">{{ hint }}</span>
    </div>
    <div class="hud-field" :data-invalid="error ? 'true' : undefined">
      <input
:id="id" v-model="model" :inputmode="inputmode ?? 'decimal'" :placeholder="placeholder" autocomplete="off"
             :aria-invalid="error ? 'true' : undefined" :aria-describedby="error ? `${id}-error` : undefined">
      <span v-if="unit" class="text-[11px] font-bold text-cabin-ice">{{ unit }}</span>
    </div>
    <p v-if="error" :id="`${id}-error`" class="text-[10px] mt-[4px] text-cabin-text" role="alert">{{ error }}</p>
  </div>
</template>
