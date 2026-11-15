<script setup lang="ts">
import VChart from 'vue-echarts'
import {
  buildOcularSheathGaugeOption,
  buildOnsdBilateralTrendOption,
  eyeSeriesColorVar,
  visionMetricColorVar,
  visionToneColorVar,
} from '~/utils/visionCharts'
import type { VisionMetricTone } from '~/utils/visionCharts'
import type { VisionStageFilter } from '~/composables/useVision'

const {
  exam,
  selectedStage,
  isLoading,
  errorMessage,
  loadVisionExam,
} = useVision()

const stageFilters: Array<{ value: VisionStageFilter, label: string }> = [
  { value: 'ALL', label: 'ACTIVE' },
  { value: 'LAUNCH', label: 'LAUNCH' },
  { value: 'MISSION', label: 'MISSION' },
  { value: 'RETURN', label: 'RETURN' },
]

const leftEyeGaugeOption = computed(() =>
  buildOcularSheathGaugeOption(
    exam.value?.left_eye ?? {
      side: 'LEFT',
      label: 'LEFT EYE',
      sheath_mm: 4.5,
      display_value: '4.5',
      status_label: 'mm (Normal)',
      tone: 'reference',
    },
  ),
)

const rightEyeGaugeOption = computed(() =>
  buildOcularSheathGaugeOption(
    exam.value?.right_eye ?? {
      side: 'RIGHT',
      label: 'RIGHT EYE',
      sheath_mm: 5.2,
      display_value: '5.2',
      status_label: 'mm (Normal)',
      tone: 'reference',
    },
  ),
)

const onsdTrendOption = computed(() =>
  buildOnsdBilateralTrendOption({
    points: exam.value?.trend_points ?? [],
    baselineBandMinMm: exam.value?.baseline_band_min_mm ?? 4.2,
    baselineBandMaxMm: exam.value?.baseline_band_max_mm ?? 5.5,
    alertThresholdMm: exam.value?.alert_threshold_mm ?? 5.8,
    rightEyeTone: exam.value?.right_eye.tone ?? 'reference',
    leftEyeTone: exam.value?.left_eye.tone ?? 'reference',
  }),
)

function metricPillClass(tone: VisionMetricTone): string {
  if (tone === 'critical') {
    return 'bg-cabin-crit/25 border-cabin-crit/85 text-cabin-text'
  }
  if (tone === 'warn') {
    return 'bg-cabin-navy/60 border-cabin-navy-edge/95 text-cabin-text'
  }
  return 'bg-cabin-navy/42 border-cabin-navy-edge/70 text-cabin-text'
}

onMounted(() => {
  void loadVisionExam()
})
</script>

<template>
  <div class="flex flex-col gap-[18px] flex-1">
    <div class="flex flex-wrap items-center justify-between gap-3 min-h-[36px]">
      <div
        class="h-9 p-1 rounded-[4px] bg-cabin-inset border border-cabin-card/65 inline-flex items-center gap-1"
        role="group"
        aria-label="Read-only ocular mission stage comparison"
      >
        <span class="px-2.5 text-[9.5px] font-bold tracking-[0.06em] uppercase text-cabin-muted">
          Stage Comparison
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

      <div class="flex flex-wrap items-center gap-2.5">
        <span
          class="px-3.5 h-7 rounded-full border border-cabin-card/75 bg-cabin-inset font-mono text-[10px] font-semibold tracking-[0.05em] uppercase text-cabin-ice inline-flex items-center"
        >
          {{ exam?.reviewed_by_label ?? 'Baseline verified · Medical Officer' }}
        </span>

        <span
          class="px-3.5 h-7 rounded-full border text-[10px] font-bold tracking-[0.05em] uppercase text-cabin-text inline-flex items-center gap-1.5"
          :class="{
            'bg-cabin-navy/42 border-cabin-navy-edge/75': (exam?.overall_tone ?? 'reference') === 'reference',
            'bg-cabin-navy/60 border-cabin-navy-edge': exam?.overall_tone === 'warn',
            'bg-cabin-crit/25 border-cabin-crit/85': exam?.overall_tone === 'critical',
          }"
        >
          <span
            class="w-1.5 h-1.5 rounded-full"
            :class="{
              'bg-cabin-ok': (exam?.overall_tone ?? 'reference') === 'reference',
              'bg-cabin-navy-edge': exam?.overall_tone === 'warn',
              'bg-cabin-crit': exam?.overall_tone === 'critical',
            }"
          />
          {{ exam?.header_status_badge ?? 'NOMINAL' }}
        </span>
      </div>
    </div>

    <div
      v-if="errorMessage"
      class="rounded-[4px] border border-cabin-crit bg-cabin-inset px-4 py-3 text-[12px] text-cabin-text"
      role="alert"
    >
      {{ errorMessage }}
    </div>

    <div
      v-if="exam && !exam.stage_has_records"
      class="rounded-[4px] border border-cabin-navy-edge/80 bg-cabin-navy/35 px-4 py-2 text-[11px] text-cabin-ice flex items-center justify-between gap-3"
    >
      <span>
        No dedicated ocular ultrasound logged in {{ exam.selected_stage }} yet — displaying latest verified bilateral exam.
      </span>
      <span class="font-mono text-[10px] font-bold uppercase text-cabin-text">
        DAY {{ String(exam.mission_day).padStart(3, '0') }}
      </span>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-[1fr_2.16fr] gap-[18px] flex-1">
      <ShellHudWindow
        title="OCULAR MEASUREMENTS"
        subtitle="Read-only bilateral optic nerve sheath, tonometry, and retinal status"
        icon="sans"
        :tag-text="exam?.header_status_badge ?? 'NOMINAL'"
        :tag-tone="exam?.overall_tone ?? 'reference'"
      >
        <div
          v-if="isLoading && !exam"
          class="py-8 text-center text-[12px] text-cabin-muted"
        >
          Loading bilateral ocular measurements...
        </div>

        <div
          v-else-if="exam"
          class="flex flex-col justify-between gap-3.5 h-full"
        >
          <div
            class="rounded-[4px] border p-3.5 flex items-center gap-3.5"
            :class="
              exam.overall_tone === 'critical'
                ? 'bg-cabin-crit/16 border-cabin-crit/80'
                : 'bg-cabin-inset border-cabin-card/70'
            "
          >
            <div class="w-[74px] h-[74px] shrink-0 flex items-center justify-center">
              <svg viewBox="0 0 88 88" class="w-full h-full">
                <circle
                  cx="44"
                  cy="44"
                  r="38"
                  fill="none"
                  :stroke="visionToneColorVar(exam.overall_tone)"
                  stroke-opacity="0.55"
                  stroke-width="1.3"
                  stroke-dasharray="4 4"
                />
                <circle
                  cx="44"
                  cy="44"
                  r="24"
                  fill="none"
                  stroke="var(--color-text-primary)"
                  stroke-opacity="0.35"
                  stroke-width="1.2"
                />
                <line
                  x1="10"
                  y1="44"
                  x2="78"
                  y2="44"
                  stroke="var(--color-navy-edge)"
                  stroke-opacity="0.65"
                  stroke-width="1.1"
                />
                <line
                  x1="44"
                  y1="10"
                  x2="44"
                  y2="78"
                  stroke="var(--color-navy-edge)"
                  stroke-opacity="0.65"
                  stroke-width="1.1"
                />
                <circle
                  cx="44"
                  cy="44"
                  r="9"
                  fill="none"
                  :stroke="visionToneColorVar(exam.overall_tone)"
                  stroke-width="2"
                />
              </svg>
            </div>

            <div class="flex flex-col gap-1 min-w-0">
              <span class="text-[9.5px] font-bold tracking-[0.06em] uppercase text-cabin-muted">
                OCULAR ALERT SUMMARY
              </span>
              <span class="text-[13.5px] font-bold text-cabin-text leading-snug">
                {{ exam.alert_headline }}
              </span>
              <span class="text-[11px] font-medium text-cabin-ice">
                {{ exam.reviewed_by_label }}
              </span>
            </div>
          </div>

          <div class="grid grid-cols-2 gap-3">
            <div class="rounded-[4px] border border-cabin-card/70 bg-cabin-inset p-2.5 flex flex-col items-center">
              <span class="text-[9.5px] font-bold tracking-[0.06em] uppercase text-cabin-muted">
                {{ exam.left_eye.label }}
              </span>
              <div class="w-full h-[108px]">
                <ClientOnly>
                  <VChart
                    :option="leftEyeGaugeOption"
                    theme="spacescan-hud"
                    autoresize
                    class="w-full h-full"
                  />
                </ClientOnly>
              </div>
            </div>

            <div
              class="rounded-[4px] border bg-cabin-inset p-2.5 flex flex-col items-center"
              :class="
                exam.right_eye.tone === 'critical'
                  ? 'border-cabin-crit/75'
                  : 'border-cabin-card/70'
              "
            >
              <span class="text-[9.5px] font-bold tracking-[0.06em] uppercase text-cabin-muted">
                {{ exam.right_eye.label }}
              </span>
              <div class="w-full h-[108px]">
                <ClientOnly>
                  <VChart
                    :option="rightEyeGaugeOption"
                    theme="spacescan-hud"
                    autoresize
                    class="w-full h-full"
                  />
                </ClientOnly>
              </div>
            </div>
          </div>

          <div class="flex flex-col gap-3">
            <div
              v-for="metric in exam.ocular_metrics"
              :key="metric.key"
              class="flex flex-col gap-1.5"
            >
              <div class="flex items-start justify-between gap-2">
                <div class="flex flex-col">
                  <span class="text-[12px] font-bold text-cabin-text leading-tight">
                    {{ metric.label }}
                  </span>
                  <span class="text-[10.5px] text-cabin-muted">
                    {{ metric.subtitle }}
                  </span>
                </div>

                <div class="flex items-center gap-2 shrink-0">
                  <span class="font-mono text-[15px] font-extrabold text-cabin-text">
                    {{ metric.display_value }}
                    <span v-if="metric.unit" class="text-[10.5px] font-normal text-cabin-muted">
                      {{ metric.unit }}
                    </span>
                  </span>

                  <span
                    class="px-2 py-0.5 rounded-full border text-[9.5px] font-semibold leading-tight"
                    :class="metricPillClass(metric.tone)"
                  >
                    {{ metric.badge_label }}
                  </span>
                </div>
              </div>

              <div class="relative w-full h-[8px] rounded-full bg-cabin-bg/90 border border-cabin-card/55">
                <div
                  class="absolute inset-y-0 rounded-full bg-cabin-card/55 border-x border-cabin-ice/35"
                  :style="{
                    left: `${metric.nominal_band_start_pct}%`,
                    width: `${metric.nominal_band_width_pct}%`,
                  }"
                />
                <span
                  class="absolute top-1/2 -translate-y-1/2 -translate-x-1/2 w-[9px] h-[9px] rounded-full border border-cabin-bg"
                  :style="{
                    left: `${metric.marker_pct}%`,
                    backgroundColor: visionMetricColorVar(metric.tone),
                  }"
                />
              </div>
            </div>
          </div>

          <div class="rounded-[4px] border border-cabin-card/70 bg-cabin-inset px-3.5 py-2.5 flex flex-col gap-0.5">
            <span class="font-mono text-[10px] font-bold tracking-[0.05em] uppercase text-cabin-ok">
              {{ exam.latest_scan_heading }}
            </span>
            <span class="text-[11px] text-cabin-ice">
              {{ exam.latest_scan_subtitle }}
            </span>
          </div>
        </div>
      </ShellHudWindow>

      <div class="flex flex-col gap-[18px]">
        <ShellHudWindow
          title="OPTIC NERVE SHEATH TREND (MM)"
          subtitle="Longitudinal bilateral ultrasound width versus personal baseline and alert threshold"
          icon="reticle"
          tag-text="BILATERAL"
          :tag-tone="exam?.overall_tone ?? 'reference'"
        >
          <div class="rounded-[4px] border border-cabin-card/70 bg-cabin-inset p-3.5 flex flex-col gap-2">
            <div class="flex flex-wrap items-center justify-between gap-2 pb-1.5 border-b border-cabin-card/45">
              <div class="flex flex-wrap items-center gap-3 font-mono text-[10px] font-semibold text-cabin-muted">
                <span>{{ exam?.baseline_band_label ?? 'PERSONAL BASELINE (4.2 – 5.5 mm)' }}</span>
                <span class="text-cabin-text">
                  {{ exam?.alert_threshold_label ?? 'ALERT THRESHOLD (5.8 mm)' }}
                </span>
              </div>

              <div class="flex flex-wrap items-center gap-4 text-[10.5px] font-semibold">
                <span class="inline-flex items-center gap-1.5 text-cabin-text">
                  <span
                    class="w-2.5 h-2.5 rounded-full"
                    :style="{
                      backgroundColor: eyeSeriesColorVar('RIGHT', exam?.right_eye.tone ?? 'reference'),
                    }"
                  />
                  {{ exam?.right_legend_label ?? 'Right Eye (5.2 mm)' }}
                </span>

                <span class="inline-flex items-center gap-1.5 text-cabin-ice">
                  <span
                    class="w-2.5 h-2.5 rounded-full"
                    :style="{
                      backgroundColor: eyeSeriesColorVar('LEFT', exam?.left_eye.tone ?? 'reference'),
                    }"
                  />
                  {{ exam?.left_legend_label ?? 'Left Eye (4.5 mm)' }}
                </span>
              </div>
            </div>

            <div class="w-full h-[274px]">
              <ClientOnly>
                <VChart
                  :option="onsdTrendOption"
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
          title="PREVENTIVE CARE PLAN"
          subtitle="Countermeasure protocol reviewed against bilateral ocular trend"
          icon="sans"
          :tag-text="exam?.steps_badge ?? '3 STEPS'"
          tag-tone="reference"
        >
          <div class="grid grid-cols-1 md:grid-cols-3 gap-3.5 h-full">
            <div
              v-for="step in exam?.preventive_steps ?? []"
              :key="step.step_number"
              class="relative rounded-[4px] border border-cabin-card/70 bg-cabin-inset p-4 overflow-hidden flex flex-col justify-between gap-2.5"
            >
              <span
                class="absolute top-0 inset-x-0 h-[3.5px]"
                :class="step.accent_tone === 'ok' ? 'bg-cabin-ok' : 'bg-cabin-ice'"
              />

              <div class="flex flex-col gap-1.5 pt-0.5">
                <span
                  class="font-mono text-[10px] font-bold tracking-[0.05em] uppercase"
                  :class="step.accent_tone === 'ok' ? 'text-cabin-ok' : 'text-cabin-ice'"
                >
                  {{ step.code_label }}
                </span>

                <h3 class="text-[13.5px] font-bold text-cabin-text leading-snug">
                  {{ step.title }}
                </h3>
              </div>

              <p class="text-[11.5px] text-cabin-muted leading-relaxed">
                {{ step.description }}
              </p>
            </div>
          </div>
        </ShellHudWindow>
      </div>
    </div>
  </div>
</template>
