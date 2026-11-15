<script setup lang="ts">
const model = defineModel<string>({ default: '' })

defineProps<{
  disabled?: boolean
}>()

const emit = defineEmits<{
  submit: []
}>()

const keypadDigits = ['1', '2', '3', '4', '5', '6', '7', '8', '9']

function appendDigit(digit: string) {
  if (model.value.length >= 4) return
  model.value += digit
  if (model.value.length === 4) {
    emit('submit')
  }
}

function removeDigit() {
  if (model.value.length === 0) return
  model.value = model.value.slice(0, -1)
}

function clearPin() {
  model.value = ''
}
</script>

<template>
  <div class="flex flex-col gap-3">
    <div class="flex items-center justify-between px-4 h-11 rounded-[6px] bg-cabin-inset border border-cabin-card/75">
      <span class="text-[10.5px] font-semibold uppercase tracking-[0.06em] text-cabin-muted">
        4-Digit PIN
      </span>
      <div class="flex items-center gap-2.5">
        <span
          v-for="idx in 4"
          :key="idx"
          class="w-3 h-3 rounded-full border transition-colors"
          :class="
            model.length >= idx
              ? 'bg-cabin-ok border-cabin-ok'
              : 'bg-transparent border-cabin-card/80'
          "
        />
      </div>
    </div>

    <div class="grid grid-cols-3 gap-2">
      <button
        v-for="digit in keypadDigits"
        :key="digit"
        type="button"
        :disabled="disabled"
        class="h-11 rounded-[6px] bg-cabin-inset hover:bg-cabin-card/40 border border-cabin-card/75 font-mono text-[15px] font-bold text-cabin-text transition-colors cursor-pointer disabled:opacity-45"
        @click="appendDigit(digit)"
      >
        {{ digit }}
      </button>

      <button
        type="button"
        :disabled="disabled"
        class="h-11 rounded-[6px] bg-cabin-card/28 hover:bg-cabin-card/45 border border-cabin-card/75 text-[10.5px] font-bold uppercase tracking-[0.04em] text-cabin-muted hover:text-cabin-text transition-colors cursor-pointer disabled:opacity-45"
        @click="clearPin"
      >
        Clear
      </button>

      <button
        type="button"
        :disabled="disabled"
        class="h-11 rounded-[6px] bg-cabin-inset hover:bg-cabin-card/40 border border-cabin-card/75 font-mono text-[15px] font-bold text-cabin-text transition-colors cursor-pointer disabled:opacity-45"
        @click="appendDigit('0')"
      >
        0
      </button>

      <button
        type="button"
        :disabled="disabled"
        class="h-11 rounded-[6px] bg-cabin-card/28 hover:bg-cabin-card/45 border border-cabin-card/75 text-[10.5px] font-bold uppercase tracking-[0.04em] text-cabin-muted hover:text-cabin-text transition-colors cursor-pointer disabled:opacity-45"
        @click="removeDigit"
      >
        Del
      </button>
    </div>
  </div>
</template>
