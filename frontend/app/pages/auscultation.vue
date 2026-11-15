<script setup lang="ts">
import VChart from 'vue-echarts'
import type { AuscultationStageFilter } from '~/composables/useAuscultationRecorder'
import {
  auscultationMetricColorVar,
  auscultationToneColorVar,
  buildCabinCo2TrendOption,
  buildPhonocardiogramOption,
  buildPulmonaryEnvelopeOption,
} from '~/utils/auscultationCharts'
import type { AuscultationHudTone, AuscultationMetricTone } from '~/utils/auscultationCharts'

const {
  results,
  selectedStage,
  isLoading,
  errorMessage,
  loadAuscultationResults,
} = useAuscultation()

const stageFilters: Array<{ value: AuscultationStageFilter, label: string }> = [
  { value: 'ALL', label: 'ACTIVE' },
  { value: 'LAUNCH', label: 'LAUNCH' },
  { value: 'MISSION', label: 'MISSION' },
  { value: 'RETURN', label: 'RETURN' },
]

const phonocardiogramOption = computed(() =>
  buildPhonocardiogramOption(
    results.value?.phonocardiogram_samples ?? [],
    results.value?.cardiac_summary.tone ?? 'reference',
  ),
)

const pulmonaryEnvelopeOption = computed(() =>
  buildPulmonaryEnvelopeOption(
    results.value?.pulmonary_envelope_samples ?? [],
    results.value?.pulmonary_summary.tone ?? 'reference',
  ),
)

const co2TrendOption = computed(() =>
  buildCabinCo2TrendOption({
    points: results.value?.co2_trend ?? [],
    targetMaxMmhg: results.value?.co2_target_max_mmhg ?? 3.2,
    alertLimitMmhg: results.value?.co2_alert_limit_mmhg ?? 4.0,
    tone: results.value?.co2_tone ?? 'reference',
  }),
)

function pillBadgeClass(tone: AuscultationHudTone): string {
  if (tone === 'critical') {
    return 'bg-cabin-crit/25 border-cabin-crit/85 text-cabin-text'
  }
  if (tone === 'warn') {
    return 'bg-cabin-navy/60 border-cabin-navy-edge/95 text-cabin-text'
  }
  return 'bg-cabin-navy/42 border-cabin-navy-edge/70 text-cabin-text'
}

function metricFillStyle(fillPct: number, tone: AuscultationMetricTone) {
  return {
    width: `${Math.max(8, Math.min(100, fillPct))}%`,
    backgroundColor: auscultationMetricColorVar(tone),
  }
}

onMounted(() => {
  void loadAuscultationResults()
})
</script>

<template>
  <div class="flex flex-col gap-[18px] flex-1">
    <div class="flex flex-wrap items-center justify-between gap-3 min-h-[36px]">
      <div
        class="h-9 p-1 rounded-[4px] bg-cabin-inset border border-cabin-card/65 inline-flex items-center gap-1"
        role="group"
        aria-label="Read-only auscultation stage filter"
      >
        <span class="px-2.5 text-[9.5px] font-bold tracking-[0.06em] uppercase text-cabin-muted">
          Stage Filter
        </span>
        <button
          v-for="filter in stageFilters"
          :key="filter.value"
          type="button"
          class="h-7 px-3 rounded-[3px] font-mono text-[10.5px] tracking-[0.05em] uppercase transition-colors cursor-pointer"
          :class="
            selectedStage === filter.value
              ? 'menu-item-active font-bold text-cabin-text'
              : 'text-cabin-muted hover:text-cabin-text font-semibold border border-transparent'
          "
          @click="selectedStage = filter.value"
        >
          {{ filter.label }}
        </button>
      </div>

      <div class="flex flex-wrap items-center gap-2">
        <span
          v-if="results"
          class="px-3 h-7 rounded-full bg-cabin-inset border border-cabin-card/65 font-mono text-[10px] font-semibold tracking-[0.04em] text-cabin-ice inline-flex items-center gap-1.5"
        >
          <span
            class="w-1.5 h-1.5 rounded-full"
            :style="{ backgroundColor: auscultationToneColorVar(results.overall_tone) }"
          />
          {{ results.crew_code }} · {{ results.full_name.toUpperCase() }} · NOISE {{ results.cabin_noise_dba.toFixed(1) }} dBA
        </span>

        <span
          class="px-3.5 h-7 rounded-full bg-cabin-navy/42 border border-cabin-navy-edge/75 text-[10px] font-bold tracking-[0.05em] uppercase text-cabin-text inline-flex items-center"
        >
          READ-ONLY CLINICAL RESULTS · RECORD AUDIO IN CAPTURE
        </span>
      </div>
    </div>

    <div
      v-if="errorMessage"
      class="rounded-[5px] bg-cabin-crit/18 border border-cabin-crit/75 px-4 py-3 text-[11.5px] text-cabin-text"
    >
      {{ errorMessage }}
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-12 gap-[18px] flex-1">
      <ShellHudWindow
        class="lg:col-span-5"
        title="Cardiac & Pulmonary Audio Results"
        subtitle="Summary of 30-second recorded stethoscope samples"
        icon="stethoscope"
        :tag-text="results?.results_badge ?? 'NOMINAL'"
        :tag-tone="results?.overall_tone ?? 'reference'"
      >
        <div v-if="isLoading && !results" class="h-full flex items-center justify-center py-12">
          <span class="font-mono text-[11px] uppercase tracking-[0.06em] text-cabin-muted">
            Loading cardiopulmonary acoustic findings...
          </span>
        </div>

        <div v-else-if="results" class="flex flex-col justify-between gap-4 h-full">
          <div class="flex flex-col gap-3">
            <article
              class="rounded-[5px] bg-cabin-inset border border-cabin-card/65 p-3.5 flex items-center gap-3.5"
            >
              <div
                class="w-[84px] h-[88px] shrink-0 rounded-[4px] bg-cabin-bg/75 border border-cabin-card/60 flex items-center justify-center relative overflow-hidden hologram-scanline"
              >
                <svg
                  viewBox="0 0 80 84"
                  class="w-[62px] h-[66px] hologram-shell select-none"
                  role="img"
                  aria-label="Cardiac anatomical hologram"
                >
                  <circle cx="40" cy="44" r="30" fill="none" stroke="rgba(255, 236, 209, 0.16)" stroke-width="1" />
                  <path
                    d="M34 14 L34 26 M44 12 L44 25 M26 20 L33 28"
                    fill="none"
                    :stroke="auscultationToneColorVar(results.cardiac_summary.tone)"
                    stroke-width="2"
                    stroke-linecap="round"
                  />
                  <path
                    d="M40 31 C34 23, 21 26, 22 38 C23 50, 38 61, 40 65 C42 61, 57 50, 58 38 C59 26, 46 23, 40 31 Z"
                    fill="rgba(42, 239, 75, 0.18)"
                    :stroke="auscultationToneColorVar(results.cardiac_summary.tone)"
                    stroke-width="1.8"
                  />
                  <polyline
                    points="25,44 33,44 36,36 40,51 44,40 47,44 55,44"
                    fill="none"
                    stroke="var(--color-text-primary)"
                    stroke-width="1.35"
                    stroke-linejoin="round"
                  />
                </svg>
              </div>

              <div class="flex-1 min-w-0 flex flex-col gap-1">
                <span class="text-[10px] font-bold tracking-[0.06em] uppercase text-cabin-muted">
                  {{ results.cardiac_summary.title }}
                </span>
                <div class="flex flex-wrap items-center gap-2">
                  <span class="font-mono text-[22px] font-extrabold text-cabin-text leading-none">
                    {{ results.cardiac_summary.primary_metric }}
                  </span>
                  <span
                    class="px-2.5 h-5 rounded-full text-[9.5px] font-semibold border inline-flex items-center"
                    :class="pillBadgeClass(results.cardiac_summary.tone)"
                  >
                    {{ results.cardiac_summary.secondary_badge }}
                  </span>
                </div>
                <span class="text-[11px] font-medium text-cabin-ice truncate">
                  {{ results.cardiac_summary.sites_summary }}
                </span>
                <span class="font-mono text-[10px] text-cabin-muted">
                  {{ results.cardiac_summary.detail_line }}
                </span>
              </div>
            </article>

            <article
              class="rounded-[5px] bg-cabin-inset border border-cabin-card/65 p-3.5 flex items-center gap-3.5"
            >
              <div
                class="w-[84px] h-[88px] shrink-0 rounded-[4px] bg-cabin-bg/75 border border-cabin-card/60 flex items-center justify-center relative overflow-hidden hologram-scanline"
              >
                <svg
                  viewBox="0 0 84 84"
                  class="w-[66px] h-[66px] hologram-shell select-none"
                  role="img"
                  aria-label="Pulmonary bilateral lung hologram"
                >
                  <line
                    x1="42"
                    y1="12"
                    x2="42"
                    y2="34"
                    stroke="var(--color-text-primary)"
                    stroke-width="2.1"
                    stroke-linecap="round"
                  />
                  <path
                    d="M42 30 L31 39 M42 30 L53 39"
                    fill="none"
                    stroke="var(--color-text-primary)"
                    stroke-width="1.6"
                  />
                  <path
                    d="M37 24 C23 24, 15 38, 16 58 C17 67, 31 67, 37 59 Z"
                    fill="rgba(41, 148, 166, 0.22)"
                    :stroke="auscultationToneColorVar(results.pulmonary_summary.tone)"
                    stroke-width="1.75"
                  />
                  <path
                    d="M47 24 C61 24, 69 38, 68 58 C67 67, 53 67, 47 59 Z"
                    fill="rgba(41, 148, 166, 0.22)"
                    :stroke="auscultationToneColorVar(results.pulmonary_summary.tone)"
                    stroke-width="1.75"
                  />
                </svg>
              </div>

              <div class="flex-1 min-w-0 flex flex-col gap-1">
                <span class="text-[10px] font-bold tracking-[0.06em] uppercase text-cabin-muted">
                  {{ results.pulmonary_summary.title }}
                </span>
                <div class="flex flex-wrap items-center gap-2">
                  <span class="font-mono text-[22px] font-extrabold text-cabin-text leading-none">
                    {{ results.pulmonary_summary.primary_metric }}
                  </span>
                  <span
                    class="px-2.5 h-5 rounded-full text-[9.5px] font-semibold border inline-flex items-center"
                    :class="pillBadgeClass(results.pulmonary_summary.tone)"
                  >
                    {{ results.pulmonary_summary.secondary_badge }}
                  </span>
                </div>
                <span class="text-[11px] font-medium text-cabin-ice truncate">
                  {{ results.pulmonary_summary.sites_summary }}
                </span>
                <span class="font-mono text-[10px] text-cabin-muted">
                  {{ results.pulmonary_summary.detail_line }}
                </span>
              </div>
            </article>
          </div>

          <div class="flex flex-col gap-2.5">
            <div
              v-for="bar in results.clinical_bars"
              :key="bar.key"
              class="rounded-[5px] bg-cabin-inset border border-cabin-card/60 px-3.5 py-2.5 flex flex-col gap-1.5"
            >
              <div class="flex items-baseline justify-between gap-2">
                <div>
                  <div class="text-[11.5px] font-semibold text-cabin-text">
                    {{ bar.label }}
                  </div>
                  <div class="text-[9.8px] text-cabin-muted">
                    {{ bar.target_label }}
                  </div>
                </div>
                <span class="font-mono text-[14px] font-extrabold text-cabin-text">
                  {{ bar.display_value }}
                </span>
              </div>

              <div class="h-1.5 rounded-full bg-cabin-navy/65 overflow-hidden">
                <div
                  class="h-full rounded-full transition-all"
                  :style="metricFillStyle(bar.fill_pct, bar.tone)"
                />
              </div>
            </div>
          </div>
        </div>
      </ShellHudWindow>

      <div class="lg:col-span-7 flex flex-col gap-[18px]">
        <ShellHudWindow
          title="Recorded Cardiac & Pulmonary Acoustic Waveforms"
          subtitle="Filtered signal trace from digital stethoscope pickup"
          icon="mic"
          :tag-text="results?.signal_badge ?? 'SIGNAL 99%'"
          tag-tone="reference"
        >
          <div class="flex flex-col gap-3">
            <div class="rounded-[5px] bg-cabin-inset border border-cabin-card/65 p-3 flex flex-col gap-1.5">
              <div class="flex flex-wrap items-center justify-between gap-2">
                <span class="text-[10px] font-bold tracking-[0.05em] uppercase text-cabin-text">
                  Channel 1 · Cardiac Phonocardiogram (Mitral S1 / S2)
                </span>
                <span class="font-mono text-[10px] font-bold uppercase text-cabin-ok">
                  {{ results?.cardiac_channel_subtitle ?? '64 BPM · CLEAN ACOUSTIC SPECTRUM' }}
                </span>
              </div>
              <div class="h-[108px] w-full">
                <ClientOnly>
                  <VChart
                    class="w-full h-full"
                    :option="phonocardiogramOption"
                    theme="spacescan-hud"
                    autoresize
                  />
                </ClientOnly>
              </div>
            </div>

            <div class="rounded-[5px] bg-cabin-inset border border-cabin-card/65 p-3 flex flex-col gap-1.5">
              <div class="flex flex-wrap items-center justify-between gap-2">
                <span class="text-[10px] font-bold tracking-[0.05em] uppercase text-cabin-text">
                  Channel 2 · Pulmonary Breath Envelope (Bilateral)
                </span>
                <span class="font-mono text-[10px] font-semibold uppercase text-cabin-ice">
                  {{ results?.pulmonary_channel_subtitle ?? '14.2 RPM · CABIN NOISE 48.0 dBA' }}
                </span>
              </div>
              <div class="h-[108px] w-full">
                <ClientOnly>
                  <VChart
                    class="w-full h-full"
                    :option="pulmonaryEnvelopeOption"
                    theme="spacescan-hud"
                    autoresize
                  />
                </ClientOnly>
              </div>
            </div>
          </div>
        </ShellHudWindow>

        <ShellHudWindow
          class="flex-1"
          title="24-Hour Cabin CO2 Trend (mmHg)"
          subtitle="Atmospheric scrubber performance vs respiratory load"
          icon="reticle"
          :tag-text="results?.co2_badge ?? '2.8 mmHg · NOMINAL'"
          :tag-tone="results?.co2_tone ?? 'reference'"
        >
          <div class="h-[188px] w-full">
            <ClientOnly>
              <VChart
                class="w-full h-full"
                :option="co2TrendOption"
                theme="spacescan-hud"
                autoresize
              />
            </ClientOnly>
          </div>
        </ShellHudWindow>
      </div>
    </div>
  </div>
</template>
