<script setup lang="ts">
// Wrapper for every interactive chart (M4): time-window buttons, Reset Zoom, the pinned
// points with their exact reading, and one line explaining the band and alert lines.
// Buttons only (no form fields), so results screens stay read-only.
import { getInstanceByDom } from 'echarts/core'
import type { ChartClick, ChartPin } from '~/composables/useChartPins'
import { pinLabel } from '~/composables/useChartPins'

const props = withDefaults(defineProps<{
  periods?: { id: string, label: string }[]
  pins?: ChartPin[]
  interpretation?: string
  zoom?: boolean
}>(), { periods: () => [], pins: () => [], interpretation: '', zoom: true })
const period = defineModel<string>('period')
const emit = defineEmits<{ unpin: [key: string], point: [click: ChartClick] }>()

const root = ref<HTMLElement | null>(null)

/** Back to the whole window on every chart inside this frame. */
function resetZoom() {
  for (const el of root.value?.querySelectorAll<HTMLElement>('[_echarts_instance_]') ?? []) {
    getInstanceByDom(el)?.dispatchAction({ type: 'dataZoom', start: 0, end: 100 })
  }
}

const PIN_RADIUS_PX = 28

/**
 * A click anywhere on a plot pins the nearest data point (by pixel distance, across all
 * series), so thin traces such as the ECG or the cabin CO2 line are as easy to pin as dots.
 */
function onRootClick(event: MouseEvent) {
  const host = (event.target as HTMLElement | null)?.closest<HTMLElement>('[_echarts_instance_]')
  const chart = host ? getInstanceByDom(host) : undefined
  if (!host || !chart) return
  const box = host.getBoundingClientRect()
  const pixel = [event.clientX - box.left, event.clientY - box.top]
  if (!chart.containPixel('grid', pixel)) return
  const series = (chart.getOption().series ?? []) as { name?: string, type?: string, data?: unknown[], silent?: boolean }[]
  let best: (ChartClick & { distance: number }) | null = null
  series.forEach((s, seriesIndex) => {
    if (!s.name || s.silent || !s.data?.length) return
    s.data.forEach((raw, dataIndex) => {
      const value = raw && typeof raw === 'object' && !Array.isArray(raw) ? (raw as { value: unknown }).value : raw
      if (value == null) return
      const point = Array.isArray(value)
        ? (s.type === 'custom' ? [(Number(value[0]) + Number(value[1])) / 2, value[2]] : [value[0], value[1]])
        : [dataIndex, value]
      const at = chart.convertToPixel({ seriesIndex }, point as number[]) as number[] | undefined
      if (!at) return
      const distance = Math.hypot(at[0]! - pixel[0]!, at[1]! - pixel[1]!)
      if (distance <= PIN_RADIUS_PX && (!best || distance < best.distance)) {
        best = { componentType: 'series', seriesName: s.name, seriesIndex, dataIndex, value, distance }
      }
    })
  })
  if (best) {
    const { distance: _distance, ...click } = best as ChartClick & { distance: number }
    emit('point', click)
  }
}

const STAGE: Record<string, string> = { LAUNCH: 'Pre-flight', MISSION: 'Mission', RETURN: 'Return' }
function when(pin: ChartPin): string {
  if (!pin.time_utc) return 'Pre-flight baseline'
  return `${pin.time_utc.slice(0, 10)} ${pin.time_utc.slice(11, 16)} UTC`
}
function delta(pin: ChartPin): string | null {
  if (pin.delta == null || !pin.reference_label) return null
  const sign = pin.delta > 0 ? '+' : pin.delta < 0 ? '−' : '±'
  return `Δ ${sign}${Math.abs(Number(pin.delta.toFixed(pin.digits)))} ${pin.unit} vs ${pin.reference_label}`.replace('  ', ' ')
}
const statusText: Record<ChartPin['status'], string> = { NOMINAL: 'Nominal', WATCH: 'Watch', CRITICAL: 'Alert', NO_DATA: 'No data' }
defineExpose({ resetZoom })
const hasBar = computed(() => props.periods.length > 0 || props.zoom || props.pins.length > 0)
</script>

<template>
  <div ref="root" class="flex-1 min-h-0 flex flex-col" @click="onRootClick">
    <div v-if="hasBar" class="shrink-0 flex items-center gap-[10px] min-h-[28px] flex-wrap">
      <div v-if="periods.length" class="flex gap-[4px]" role="group" aria-label="Time window">
        <button
          v-for="option in periods" :key="option.id" type="button"
          class="focus-ring h-[24px] px-[10px] rounded-[3px] mono text-[10px] font-bold border"
          :class="period === option.id ? 'menu-item-active text-cabin-text' : 'border-cabin-line text-cabin-ice hover:text-cabin-text'"
          :aria-pressed="period === option.id" @click="period = option.id"
        >
          {{ option.label }}
        </button>
      </div>
      <div class="flex-1 min-w-0 flex gap-[6px] flex-wrap" aria-live="polite">
        <span
          v-for="pin in pins" :key="pin.key"
          class="h-[24px] pl-[8px] pr-[4px] rounded-[3px] border border-cabin-edge/70 bg-cabin-tile flex items-center gap-[8px] text-[10px] max-w-full"
        >
          <i class="w-[6px] h-[6px] rotate-45 bg-cabin-text shrink-0" aria-hidden="true" />
          <span class="truncate">
            <b>{{ pin.series }} {{ pinLabel(pin) }} {{ pin.unit }}</b>
            · <span class="mono">{{ when(pin) }}</span>
            <template v-if="pin.stage"> · {{ STAGE[pin.stage] ?? pin.stage }}</template>
            <template v-if="delta(pin)"> · {{ delta(pin) }}</template>
          </span>
          <UiStatusPill size="sm" :tone="pin.status === 'CRITICAL' ? 'critical' : pin.status === 'WATCH' ? 'watch' : 'reference'">
            {{ statusText[pin.status] }}
          </UiStatusPill>
          <button
            type="button" class="focus-ring w-[16px] h-[16px] rounded-full text-[11px] leading-none text-cabin-ice hover:text-cabin-text"
            :aria-label="`Remove pin ${pin.series} ${pinLabel(pin)}`" @click="emit('unpin', pin.key)"
          >
            ×
          </button>
        </span>
        <span v-if="!pins.length" class="text-[10px] text-cabin-dim self-center">Click a point to pin it · scroll or drag to zoom</span>
      </div>
      <button
        v-if="zoom" type="button"
        class="focus-ring h-[24px] px-[10px] rounded-[3px] mono text-[10px] font-bold border border-cabin-line text-cabin-ice hover:text-cabin-text"
        @click="resetZoom"
      >
        Reset Zoom
      </button>
    </div>
    <div class="relative flex-1 min-h-0 mt-[6px]">
      <slot />
    </div>
    <p v-if="interpretation" class="shrink-0 mt-[6px] text-[10px] text-cabin-ice truncate" :title="interpretation">
      {{ interpretation }}
    </p>
  </div>
</template>
