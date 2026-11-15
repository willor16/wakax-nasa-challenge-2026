<script setup lang="ts">
import ProfileSubnavBar from '~/components/profile/ProfileSubnavBar.vue'
import SpaceScanHologram from '~/components/telemetry/SpaceScanHologram.vue'
import { computeGaugeArcStroke, formatZScoreLabel } from '~/utils/profileCharts'
import type { StatusTone } from '~/utils/profileCharts'

const {
  profile,
  selectedStage,
  isLoading,
  errorMessage,
  loadProfile,
  openTelemetryStream,
} = useCrewProfile()

let closeStream: (() => void) | null = null

const demographicsLine = computed(() => {
  const c = profile.value?.crew
  if (!c) return 'Age: -- yrs · Sex: -- · Blood Type: --'
  const agePart = c.age !== null ? `${c.age} yrs` : '--'
  const bloodPart = c.blood_type ?? '--'
  return `Age: ${agePart} · Sex: ${c.sex_display} · Blood Type: ${bloodPart}`
})

function topBarClass(tone: StatusTone): string {
  if (tone === 'critical') return 'bg-cabin-crit'
  if (tone === 'warn') return 'bg-cabin-navy-edge'
  return 'bg-cabin-ok'
}

function leftBarClass(tone: StatusTone): string {
  if (tone === 'critical') return 'bg-cabin-crit'
  if (tone === 'warn') return 'bg-cabin-navy-edge'
  return 'bg-cabin-ok'
}

function gaugeStrokeVar(tone: StatusTone): string {
  if (tone === 'critical') return 'var(--color-status-critical)'
  if (tone === 'warn') return 'var(--color-rem-accent)'
  return 'var(--color-status-ok)'
}

onMounted(() => {
  void loadProfile()
  closeStream = openTelemetryStream()
})

onUnmounted(() => {
  closeStream?.()
})
</script>

<template>
  <div class="flex flex-col gap-[18px] flex-1">
    <ProfileSubnavBar
      v-model:selected-stage="selectedStage"
      :badge-text="profile?.biometric_scan.scan_label ?? 'NOMINAL'"
      :badge-tone="profile?.biometric_scan.scan_tone ?? 'reference'"
    />

    <div
      v-if="errorMessage"
      class="rounded-[4px] border border-cabin-crit bg-cabin-inset px-4 py-3 text-[12px] text-cabin-text"
      role="alert"
    >
      {{ errorMessage }}
    </div>

    <div
      v-if="profile && !profile.mission.stage_has_records"
      class="rounded-[4px] border border-cabin-navy-edge/80 bg-cabin-navy/35 px-4 py-2 text-[11px] text-cabin-ice flex items-center justify-between gap-3"
    >
      <span>
        No dedicated measurements logged in {{ profile.mission.selected_stage }} yet — displaying latest active values compared against personal pre-flight baseline.
      </span>
      <span class="font-mono text-[10px] font-bold uppercase text-cabin-text">
        {{ profile.mission.mission_day_code }}
      </span>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-[1.08fr_1fr_1.08fr] gap-[18px] flex-1">
      <ShellHudWindow
        title="PERSONAL BIOMETRICS"
        icon="profile"
        :tag-text="profile?.crew.code ?? 'ID·01'"
      >
        <div v-if="profile" class="h-full flex flex-col justify-between gap-4">
          <div class="rounded-[4px] bg-cabin-card/35 border border-cabin-card/85 px-4 py-3.5 flex items-start justify-between gap-3">
            <div class="flex flex-col gap-1">
              <span class="text-[17px] font-bold text-cabin-text leading-tight">
                {{ profile.crew.full_name }}
              </span>
              <span class="text-[11.5px] text-cabin-ice">
                {{ demographicsLine }}
              </span>
            </div>
            <span class="shrink-0 h-[22px] px-3 rounded-full bg-cabin-navy/48 border border-cabin-navy-edge/80 text-[9.5px] font-bold tracking-[0.05em] uppercase text-cabin-text inline-flex items-center">
              {{ profile.crew.role_badge }}
            </span>
          </div>

          <div class="grid grid-cols-2 gap-3.5 flex-1">
            <div
              v-for="card in profile.biometrics"
              :key="card.key"
              class="relative rounded-[4px] bg-cabin-inset border border-cabin-card/60 px-4 py-3.5 flex flex-col justify-between overflow-hidden min-h-[126px]"
            >
              <span
                class="pointer-events-none absolute top-0 inset-x-0 h-[3px]"
                :class="topBarClass(card.status_tone)"
              />

              <div class="flex items-center justify-between gap-2 pt-0.5">
                <span class="text-[10px] font-bold tracking-[0.06em] uppercase text-cabin-muted">
                  {{ card.label }}
                </span>
                <span
                  v-if="card.z_score !== null"
                  class="font-mono text-[9.5px] text-cabin-muted"
                >
                  {{ formatZScoreLabel(card.z_score) }}
                </span>
              </div>

              <span class="font-mono text-[24px] font-bold text-cabin-text leading-none my-2">
                {{ card.display_value }}
              </span>

              <span class="text-[11px] text-cabin-ice">
                {{ card.subtitle }}
              </span>
            </div>
          </div>
        </div>

        <p v-else-if="isLoading" class="text-[12px] text-cabin-muted">
          Loading personal biometrics...
        </p>
      </ShellHudWindow>

      <ShellHudWindow
        title="BIOMETRIC SCAN"
        icon="vitruvian"
        :tag-text="profile?.biometric_scan.scan_label ?? 'NOMINAL'"
        :tag-tone="profile?.biometric_scan.scan_tone ?? 'reference'"
      >
        <div v-if="profile" class="h-full flex flex-col justify-between gap-3">
          <SpaceScanHologram
            class="flex-1"
            :core-temp-display="profile.biometric_scan.core_temp_display"
            :hydration-display="profile.biometric_scan.hydration_display"
            :cardiac-tone="profile.biometric_scan.cardiac_tone"
            :pulmonary-tone="profile.biometric_scan.pulmonary_tone"
            :ocular-tone="profile.biometric_scan.ocular_tone"
          />

          <div class="grid grid-cols-3 gap-2 pt-1">
            <div
              v-for="snap in profile.stage_comparison"
              :key="snap.stage"
              class="rounded-[4px] bg-cabin-inset/75 border border-cabin-card/50 px-2.5 py-2 flex flex-col gap-0.5"
            >
              <span class="font-mono text-[9px] font-bold tracking-[0.06em] text-cabin-muted uppercase">
                {{ snap.stage }}
              </span>
              <span class="font-mono text-[11.5px] font-bold text-cabin-text">
                {{ snap.body_weight_kg !== null ? `${snap.body_weight_kg.toFixed(1)} kg` : 'Pending' }}
              </span>
              <span class="font-mono text-[9.5px] text-cabin-ice">
                {{ snap.resting_hr_bpm !== null ? `${Math.round(snap.resting_hr_bpm)} bpm` : 'No log' }}
              </span>
            </div>
          </div>
        </div>

        <p v-else-if="isLoading" class="text-[12px] text-cabin-muted">
          Initializing anatomical scan...
        </p>
      </ShellHudWindow>

      <ShellHudWindow
        title="ENVIRONMENT & WORK HOURS"
        icon="shield"
        :tag-text="profile?.environment_work.habitat_tag ?? 'HABITAT A'"
      >
        <div v-if="profile" class="h-full flex flex-col justify-between gap-4">
          <div class="grid grid-cols-2 gap-3.5">
            <div
              v-for="gauge in profile.environment_work.gauges"
              :key="gauge.key"
              class="rounded-[4px] bg-cabin-inset border border-cabin-card/60 px-3 py-3 flex flex-col items-center justify-center relative min-h-[132px]"
            >
              <div class="relative w-[108px] h-[108px] flex items-center justify-center">
                <svg
                  viewBox="0 0 96 96"
                  class="w-full h-full -rotate-[218deg]"
                  aria-hidden="true"
                >
                  <circle
                    cx="48"
                    cy="48"
                    r="38"
                    fill="none"
                    stroke="rgba(21, 97, 109, 0.42)"
                    stroke-width="4.2"
                    :stroke-dasharray="`${computeGaugeArcStroke(100, 38).arcSpan} ${computeGaugeArcStroke(100, 38).circumference}`"
                    stroke-linecap="round"
                  />
                  <circle
                    cx="48"
                    cy="48"
                    r="38"
                    fill="none"
                    :stroke="gaugeStrokeVar(gauge.status_tone)"
                    stroke-width="4.2"
                    :stroke-dasharray="computeGaugeArcStroke(gauge.arc_pct, 38).dashArray"
                    stroke-linecap="round"
                  />
                </svg>

                <div class="absolute inset-0 flex flex-col items-center justify-center text-center px-2">
                  <span class="text-[8.8px] font-bold tracking-[0.05em] uppercase text-cabin-muted leading-tight">
                    {{ gauge.label }}
                  </span>
                  <span class="font-mono text-[21px] font-bold text-cabin-text leading-tight mt-0.5">
                    {{ gauge.display_value }}
                  </span>
                  <span class="text-[9.5px] text-cabin-muted leading-tight mt-0.5">
                    {{ gauge.subtitle }}
                  </span>
                </div>
              </div>
            </div>
          </div>

          <div class="flex flex-col gap-2.5">
            <span class="text-[10px] font-bold tracking-[0.07em] uppercase text-cabin-muted">
              {{ profile.environment_work.work_header }}
            </span>

            <div
              v-for="row in profile.environment_work.work_rows"
              :key="row.key"
              class="relative rounded-[4px] bg-cabin-inset border border-cabin-card/60 pl-5 pr-4 py-3 flex items-center justify-between gap-3"
            >
              <span
                class="pointer-events-none absolute left-0 top-3 bottom-3 w-[4px] rounded-r-[2px]"
                :class="leftBarClass(row.status_tone)"
              />

              <div class="flex flex-col gap-0.5">
                <span class="text-[10px] font-bold tracking-[0.06em] uppercase text-cabin-muted">
                  {{ row.label }}
                </span>
                <span class="text-[11.5px] text-cabin-ice">
                  {{ row.subtitle }}
                </span>
              </div>

              <span class="font-mono text-[21px] font-bold text-cabin-text shrink-0">
                {{ row.display_value }}
              </span>
            </div>
          </div>
        </div>

        <p v-else-if="isLoading" class="text-[12px] text-cabin-muted">
          Loading habitat telemetry...
        </p>
      </ShellHudWindow>
    </div>
  </div>
</template>
