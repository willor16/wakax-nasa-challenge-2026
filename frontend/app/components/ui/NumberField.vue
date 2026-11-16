<script setup lang="ts">
// Labelled numeric entry for Capture forms (label + hint above, unit inside the field).
// ``notice`` shows the live admission check under the field: critical = non-admissible
// (saving is blocked), watch = admissible but outside the normal range.
defineProps<{ label: string, hint?: string, unit?: string, placeholder?: string, error?: string | null
  inputmode?: 'decimal' | 'numeric' | 'text', id: string
  /** Parameter key for the "?" help button next to the label. */
  helpKey?: string
  notice?: { tone: 'critical' | 'watch', text: string } | null }>()
const model = defineModel<string>({ required: true })
</script>

<template>
  <div>
    <div class="flex items-baseline justify-between gap-2 mb-[8px]">
      <span class="flex items-center gap-[6px] min-w-0">
        <label :for="id" class="label-caps">{{ label }}</label>
        <UiParamHelp v-if="helpKey" :metric-key="helpKey" />
      </span>
      <span v-if="hint" class="text-[9.5px] text-cabin-ice truncate">{{ hint }}</span>
    </div>
    <div
      class="hud-field" :data-invalid="error || notice?.tone === 'critical' ? 'true' : undefined"
      :class="notice?.tone === 'watch' && !error ? '!border-cabin-navy-edge' : ''">
      <input
:id="id" v-model="model" :inputmode="inputmode ?? 'decimal'" :placeholder="placeholder" autocomplete="off"
             :aria-invalid="error || notice?.tone === 'critical' ? 'true' : undefined"
             :aria-describedby="error ? `${id}-error` : notice ? `${id}-notice` : undefined">
      <span v-if="unit" class="text-[11px] font-bold text-cabin-ice">{{ unit }}</span>
    </div>
    <p v-if="error" :id="`${id}-error`" class="text-[10px] mt-[4px] text-cabin-text" role="alert">{{ error }}</p>
    <p
v-else-if="notice" :id="`${id}-notice`" class="text-[10px] mt-[4px] leading-[1.35] flex items-start gap-[6px]"
       :class="notice.tone === 'critical' ? 'text-cabin-text' : 'text-cabin-ice'" role="status" aria-live="polite">
      <i class="mt-[3px] w-[6px] h-[6px] shrink-0 rounded-full" :class="notice.tone === 'critical' ? 'bg-cabin-crit' : 'bg-cabin-navy-edge'" />
      {{ notice.text }}
    </p>
  </div>
</template>
