<script setup lang="ts">
import VChart from 'vue-echarts'
import SleepTimeFilterBar from '~/components/sleep/SleepTimeFilterBar.vue'
import {
  buildSleepScoreGaugeOption,
  buildSleepStageRibbonOption,
  stageColorVar,
} from '~/utils/sleepCharts'
import type { SleepHudTone } from '~/utils/sleepCharts'

const {
  monitor,
  selectedPeriod,
  isLoading,
  errorMessage,
  loadSleepMonitor,
} = useSleep()

const scoreGaugeOption = computed(() =>
  buildSleepScoreGaugeOption(
    monitor.value?.sleep_score ?? 0,
    monitor.value?.score_subtitle ?? 'of 100 · Optimal',
    monitor.value?.quality_tone ?? 'reference',
  ),
)

const ribbonOption = computed(() =>
  buildSleepStageRibbonOption(
    monitor.value?.ribbon_bouts ?? [],
    monitor.value?.window_total_min ?? 480,
    monitor.value?.axis_ticks ?? [],
  ),
)

function stagePillClass(tone: SleepHudTone): string {
  if (tone === 'critical') {
    return 'bg-cabin-crit/25 border-cabin-crit/85 text-cabin-text'
  }
  if (tone === 'warn') {
    return 'bg-cabin-navy/60 border-cabin-navy-edge/95 text-cabin-text'
  }
  return 'bg-cabin-navy/42 border-cabin-navy-edge/70 text-cabin-text'
}

onMounted(() => {
  void loadSleepMonitor()
})
</script>

<template>
  <div class="flex flex-col gap-[18px] flex-1">
    <SleepTimeFilterBar
      v-model:selected-period="selectedPeriod"
      :last-night-label="monitor?.last_night_tab_label ?? 'Last Night (D45)'"
      :rest-window-badge="monitor?.rest_window_badge ?? 'REST WINDOW · 22:18 – 05:54 UTC'"
      :score-badge="monitor?.header_score_badge ?? 'SCORE 84 · OPTIMAL'"
      :quality-tone="monitor?.quality_tone ?? 'reference'"
    />

    <div
      v-if="errorMessage"
      class="rounded-[4px] border border-cabin-crit bg-cabin-inset px-4 py-3 text-[12px] text-cabin-text"
      role="alert"
    >
      {{ errorMessage }}
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-[1fr_2.16fr] gap-[18px] flex-1">
      <ShellHudWindow
        title="SLEEP QUALITY & STAGE TIME"
        subtitle="Read-only sleep score, duration target, and restorative stage balance"
        icon="moon"
        :tag-text="monitor?.quality_tag ?? 'OPTIMAL'"
        :tag-tone="monitor?.quality_tone ?? 'reference'"
      >
        <div
          v-if="isLoading && !monitor"
          class="py-8 text-center text-[12px] text-cabin-muted"
        >
          Loading sleep quality metrics...
        </div>

        <div
          v-else-if="monitor"
          class="flex flex-col justify-between gap-3.5 h-full"
        >
          <div class="grid grid-cols-2 gap-3">
            <div class="rounded-[4px] border border-cabin-card/70 bg-cabin-inset p-3 flex flex-col items-center justify-between">
              <span class="self-start text-[9.5px] font-bold tracking-[0.06em] uppercase text-cabin-muted">
                SLEEP SCORE
              </span>
              <div class="w-full h-[126px]">
                <ClientOnly>
                  <VChart
                    :option="scoreGaugeOption"
                    theme="spacescan-hud"
                    autoresize
                    class="w-full h-full"
                  />
                </ClientOnly>
              </div>
            </div>

            <div class="relative rounded-[4px] border border-cabin-card/70 bg-cabin-inset p-3.5 overflow-hidden flex flex-col justify-between">
              <span
                class="absolute top-0 inset-x-0 h-[3.5px]"
                :class="monitor.target_met ? 'bg-cabin-ok' : 'bg-cabin-navy-edge'"
              />

              <span class="text-[9.5px] font-bold tracking-[0.06em] uppercase text-cabin-muted pt-0.5">
                {{ monitor.sleep_time_heading }}
              </span>

              <div class="my-1.5">
                <div class="font-mono text-[23px] font-extrabold text-cabin-text leading-tight">
                  {{ monitor.total_sleep_display }}
                </div>
                <span
                  class="mt-1 inline-flex items-center gap-1.5 text-[10.5px] font-semibold"
                  :class="monitor.target_met ? 'text-cabin-ok' : 'text-cabin-ice'"
                >
                  <span
                    class="w-1.5 h-1.5 rounded-full"
                    :class="monitor.target_met ? 'bg-cabin-ok' : 'bg-cabin-navy-edge'"
                  />
                  {{ monitor.target_label }}
                </span>
              </div>

              <div class="pt-2 border-t border-cabin-card/45 flex flex-col gap-0.5 text-[10.5px] text-cabin-muted font-mono">
                <span>{{ monitor.in_bed_display }}</span>
                <span>{{ monitor.efficiency_label }}</span>
              </div>
            </div>
          </div>

          <div class="flex flex-col gap-2.5">
            <div class="flex items-center justify-between">
              <span class="text-[10px] font-bold tracking-[0.07em] uppercase text-cabin-muted">
                TIME IN EACH SLEEP STAGE
              </span>
              <span class="font-mono text-[10px] text-cabin-muted">
                {{ monitor.nights_analyzed }} {{ monitor.nights_analyzed === 1 ? 'night' : 'nights' }}
              </span>
            </div>

            <div
              v-for="card in monitor.stage_cards"
              :key="card.stage"
              class="relative rounded-[4px] border border-cabin-card/65 bg-cabin-inset pl-4 pr-3.5 py-2.5 overflow-hidden flex flex-col gap-1.5"
            >
              <span
                class="absolute left-0 inset-y-0 w-[4px]"
                :style="{ backgroundColor: stageColorVar(card.stage) }"
              />

              <div class="flex items-center justify-between gap-2">
                <span class="text-[12px] font-bold text-cabin-text">
                  {{ card.label }}
                </span>
                <div class="flex items-center gap-2">
                  <span class="font-mono text-[13.5px] font-extrabold text-cabin-text">
                    {{ card.duration_display }}
                  </span>
                  <span
                    class="px-2 py-0.5 rounded-full border text-[9.5px] font-semibold leading-tight"
                    :class="stagePillClass(card.badge_tone)"
                  >
                    {{ card.badge_label }}
                  </span>
                </div>
              </div>

              <div class="w-full h-[7px] rounded-full bg-cabin-bg/90 border border-cabin-card/45 overflow-hidden">
                <div
                  class="h-full rounded-full"
                  :style="{
                    width: `${card.bar_fill_pct}%`,
                    backgroundColor: stageColorVar(card.stage),
                  }"
                />
              </div>

              <span class="text-[10.5px] text-cabin-muted">
                {{ card.subtitle }}
              </span>
            </div>
          </div>
        </div>
      </ShellHudWindow>

      <div class="flex flex-col gap-[18px]">
        <ShellHudWindow
          :title="monitor?.ribbon_title ?? 'SLEEP STAGE RIBBON CHART'"
          subtitle="Ultradian sleep architecture bouts and consolidated stage ribbon"
          icon="reticle"
          :tag-text="monitor?.cycle_badge ?? '5 CYCLES'"
          tag-tone="reference"
        >
          <div class="rounded-[4px] border border-cabin-card/70 bg-cabin-inset p-3.5 flex flex-col gap-2.5">
            <div class="flex flex-wrap items-center justify-between gap-2 pb-1.5 border-b border-cabin-card/45">
              <div class="flex flex-wrap items-center gap-4">
                <span
                  v-for="item in monitor?.ribbon_legend ?? []"
                  :key="item.stage"
                  class="inline-flex items-center gap-1.5 text-[10.5px] font-semibold text-cabin-ice"
                >
                  <span
                    class="w-2.5 h-2.5 rounded-[2px]"
                    :style="{ backgroundColor: stageColorVar(item.stage) }"
                  />
                  {{ item.label }}
                </span>
              </div>

              <span class="font-mono text-[10px] font-semibold uppercase tracking-[0.04em] text-cabin-muted">
                {{ monitor?.rest_window_inline ?? 'REST WINDOW: 22:18 – 05:54 UTC' }}
              </span>
            </div>

            <div class="w-full h-[238px]">
              <ClientOnly>
                <VChart
                  :option="ribbonOption"
                  theme="spacescan-hud"
                  autoresize
                  class="w-full h-full"
                />
              </ClientOnly>
            </div>
          </div>
        </ShellHudWindow>

        <ShellHudWindow
          class="flex-1"
          title="STAGE LAPSES & CYCLE INTERVALS"
          subtitle="Recorded UTC bout windows, lapse frequency, and total stage duration"
          icon="moon"
          :tag-text="monitor?.bouts_badge ?? '0 BOUTS LOGGED'"
          tag-tone="reference"
        >
          <div class="flex flex-col gap-2">
            <div class="grid grid-cols-12 gap-3 px-3.5 py-1 text-[9.5px] font-bold tracking-[0.06em] uppercase text-cabin-muted">
              <span class="col-span-2">SLEEP STAGE</span>
              <span class="col-span-5">RECORDED UTC LAPSES (BOUT INTERVALS)</span>
              <span class="col-span-1 text-right">BOUTS</span>
              <span class="col-span-2 text-right">AVG / MAX LAPSE</span>
              <span class="col-span-2 text-right">TOTAL</span>
            </div>

            <div
              v-for="row in monitor?.lapse_rows ?? []"
              :key="row.stage"
              class="relative grid grid-cols-12 items-center gap-3 rounded-[4px] border border-cabin-card/65 bg-cabin-inset pl-4 pr-3.5 py-2.5 overflow-hidden"
            >
              <span
                class="absolute left-0 inset-y-0 w-[4px]"
                :style="{ backgroundColor: stageColorVar(row.stage) }"
              />

              <span class="col-span-2 text-[12px] font-bold text-cabin-text truncate">
                {{ row.label }}
              </span>

              <span class="col-span-5 font-mono text-[11px] text-cabin-ice truncate">
                {{ row.intervals_summary }}
              </span>

              <span class="col-span-1 font-mono text-[11px] font-semibold text-cabin-muted text-right">
                {{ row.bouts_label }}
              </span>

              <span class="col-span-2 font-mono text-[11px] text-cabin-muted text-right">
                {{ row.avg_max_label }}
              </span>

              <span class="col-span-2 font-mono text-[12.5px] font-extrabold text-cabin-text text-right">
                {{ row.total_display }}
              </span>
            </div>
          </div>
        </ShellHudWindow>
      </div>
    </div>
  </div>
</template>
