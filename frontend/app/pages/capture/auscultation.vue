<script setup lang="ts">
import VChart from 'vue-echarts'
import type { CardiacSiteKey, PulmonarySiteKey } from '~/composables/useAuscultationRecorder'
import {
  buildPhonocardiogramOption,
  buildPulmonaryEnvelopeOption,
} from '~/utils/auscultationCharts'

const {
  results,
  missionStage,
  selectedCardiacSite,
  selectedPulmonarySite,
  cabinDba,
  isNoiseSafe,
  isCardiacRecording,
  isPulmonaryRecording,
  cardiacSeconds,
  pulmonarySeconds,
  cardiacLiveWave,
  pulmonaryLiveWave,
  cardiacCaptured,
  pulmonaryCaptured,
  cardiacSaving,
  pulmonarySaving,
  statusBanner,
  errorBanner,
  loadAuscultationResults,
  startRecording,
  saveRecording,
} = useAuscultationRecorder()

const cardiacSites: Array<{
  key: CardiacSiteKey
  label: string
  placementTitle: string
}> = [
  {
    key: 'aortic',
    label: 'Aortic · 2nd R',
    placementTitle: 'DIGITAL STETHOSCOPE · AORTIC AREA (2ND R ICS)',
  },
  {
    key: 'pulmonic',
    label: 'Pulmonic · 2nd L',
    placementTitle: 'DIGITAL STETHOSCOPE · PULMONIC AREA (2ND L ICS)',
  },
  {
    key: 'tricuspid',
    label: 'Tricuspid · 4th L',
    placementTitle: 'DIGITAL STETHOSCOPE · TRICUSPID AREA (4TH L ICS)',
  },
  {
    key: 'mitral',
    label: 'Mitral Apex',
    placementTitle: 'DIGITAL STETHOSCOPE · MITRAL APEX (5TH ICS)',
  },
]

const pulmonarySites: Array<{
  key: PulmonarySiteKey
  label: string
  placementTitle: string
}> = [
  {
    key: 'upper_left',
    label: 'Upper Left',
    placementTitle: 'PULMONARY PICKUP · UPPER LEFT ANTERIOR ZONE',
  },
  {
    key: 'upper_right',
    label: 'Upper Right',
    placementTitle: 'PULMONARY PICKUP · UPPER RIGHT ANTERIOR ZONE',
  },
  {
    key: 'lower_left',
    label: 'Lower Left',
    placementTitle: 'PULMONARY PICKUP · LOWER LEFT BASAL ZONE',
  },
  {
    key: 'lower_right',
    label: 'Lower Right',
    placementTitle: 'PULMONARY PICKUP · LOWER RIGHT BASAL ZONE',
  },
]

const activeCardiacPlacementTitle = computed(
  () =>
    cardiacSites.find(item => item.key === selectedCardiacSite.value)?.placementTitle
    ?? 'DIGITAL STETHOSCOPE · MITRAL APEX (5TH ICS)',
)

const activePulmonaryPlacementTitle = computed(
  () =>
    pulmonarySites.find(item => item.key === selectedPulmonarySite.value)?.placementTitle
    ?? 'PULMONARY PICKUP · UPPER RIGHT ANTERIOR ZONE',
)

function formatClock(sec: number): string {
  const clamped = Math.max(0, Math.min(30, Math.round(sec)))
  return `00:${String(clamped).padStart(2, '0')} / 00:30 SEC`
}

const cardiacHeaderLabel = computed(() => {
  if (isCardiacRecording.value) {
    return `RECORDING CARDIAC AUDIO · ${formatClock(cardiacSeconds.value)}`
  }
  if (cardiacCaptured.value) {
    return `SAMPLE CAPTURED · ${formatClock(cardiacCaptured.value.durationSec)}`
  }
  return `READY FOR CAPTURE · ${formatClock(cardiacSeconds.value)}`
})

const pulmonaryHeaderLabel = computed(() => {
  if (isPulmonaryRecording.value) {
    return `RECORDING PULMONARY AUDIO · ${formatClock(pulmonarySeconds.value)}`
  }
  if (pulmonaryCaptured.value) {
    return `SAMPLE CAPTURED · ${formatClock(pulmonaryCaptured.value.durationSec)}`
  }
  return `SAMPLE CAPTURED · ${formatClock(pulmonarySeconds.value)}`
})

const cardiacProgressPct = computed(
  () => `${Math.max(4, Math.min(100, (cardiacSeconds.value / 30) * 100))}%`,
)

const pulmonaryProgressPct = computed(
  () => `${Math.max(4, Math.min(100, (pulmonarySeconds.value / 30) * 100))}%`,
)

const cardiacLiveOption = computed(() =>
  buildPhonocardiogramOption(
    cardiacLiveWave.value,
    isNoiseSafe.value ? 'reference' : 'critical',
  ),
)

const pulmonaryLiveOption = computed(() =>
  buildPulmonaryEnvelopeOption(
    pulmonaryLiveWave.value,
    isNoiseSafe.value ? 'reference' : 'critical',
  ),
)

onMounted(() => {
  void loadAuscultationResults()
})
</script>

<template>
  <div class="flex flex-col gap-[18px] flex-1">
    <CaptureSubnavBar
      v-model:mission-stage="missionStage"
      :show-stage-selector="true"
    />

    <div
      v-if="errorBanner"
      class="rounded-[5px] bg-cabin-crit/20 border border-cabin-crit/80 px-4 py-2.5 text-[11.5px] font-medium text-cabin-text"
    >
      {{ errorBanner }}
    </div>

    <div
      v-else-if="statusBanner"
      class="rounded-[5px] bg-cabin-inset border border-cabin-ok/65 px-4 py-2.5 text-[11.5px] font-medium text-cabin-text flex items-center justify-between gap-3"
    >
      <span>{{ statusBanner }}</span>
      <NuxtLink
        to="/auscultation"
        class="font-mono text-[10.5px] font-bold uppercase tracking-[0.05em] text-cabin-ok hover:underline"
      >
        Open Read-Only Results →
      </NuxtLink>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-2 gap-[18px] flex-1">
      <ShellHudWindow
        title="Cardiac Audio Recording"
        subtitle="Place digital stethoscope on valve site · Record 30-second sample"
        icon="stethoscope"
        tag-text="HEART · 30S"
        :tag-tone="isNoiseSafe ? 'reference' : 'critical'"
      >
        <div class="flex flex-col justify-between gap-3.5 h-full">
          <div class="flex flex-col gap-1.5">
            <span class="text-[10px] font-bold tracking-[0.06em] uppercase text-cabin-muted">
              Select Cardiac Valve Placement
            </span>
            <div class="grid grid-cols-2 sm:grid-cols-4 gap-2">
              <button
                v-for="site in cardiacSites"
                :key="site.key"
                type="button"
                class="h-8 px-2.5 rounded-[4px] text-[10.8px] border transition-colors cursor-pointer truncate"
                :class="
                  selectedCardiacSite === site.key
                    ? 'menu-item-active font-bold text-cabin-text'
                    : 'bg-cabin-inset border-cabin-card/60 text-cabin-muted hover:text-cabin-text font-semibold'
                "
                @click="selectedCardiacSite = site.key"
              >
                {{ site.label }}
              </button>
            </div>
          </div>

          <div class="rounded-[5px] bg-cabin-inset border border-cabin-card/65 p-3.5 flex items-center gap-3.5">
            <div
              class="w-[92px] h-[102px] shrink-0 rounded-[4px] bg-cabin-bg/80 border border-cabin-card/60 flex items-center justify-center relative overflow-hidden hologram-scanline"
            >
              <svg
                viewBox="0 0 84 90"
                class="w-[68px] h-[74px] hologram-shell select-none"
                role="img"
                aria-label="Cardiac valve stethoscope placement"
              >
                <circle cx="42" cy="48" r="31" fill="none" stroke="rgba(255, 236, 209, 0.15)" stroke-width="1" />
                <path
                  d="M36 15 L36 28 M46 13 L46 27 M27 22 L34 30"
                  fill="none"
                  stroke="var(--color-status-ok)"
                  stroke-width="2"
                  stroke-linecap="round"
                />
                <path
                  d="M42 33 C35 24, 21 28, 22 41 C23 54, 40 66, 42 70 C44 66, 61 54, 62 41 C63 28, 49 24, 42 33 Z"
                  fill="rgba(42, 239, 75, 0.18)"
                  stroke="var(--color-status-ok)"
                  stroke-width="1.8"
                />
                <circle cx="48" cy="54" r="4.5" fill="var(--color-status-ok)" />
              </svg>
            </div>

            <div class="flex-1 min-w-0 flex flex-col gap-1.5">
              <div class="text-[11px] font-bold tracking-[0.04em] uppercase text-cabin-text truncate">
                {{ activeCardiacPlacementTitle }}
              </div>
              <div class="text-[11px] font-semibold text-cabin-ok">
                Sensor Seal: {{ results?.signal_quality_pct ?? 99 }}% Optimal · Heart Rate: {{ Math.round(results?.heart_rate_bpm ?? 64) }} bpm
              </div>
              <div
                class="text-[10.5px]"
                :class="isNoiseSafe ? 'text-cabin-muted' : 'text-cabin-crit font-semibold'"
              >
                Cabin Noise: {{ cabinDba.toFixed(1) }} dBA ({{ isNoiseSafe ? 'Below 55 dBA acoustic limit' : 'Exceeds 55 dBA limit' }})
              </div>
              <div class="pt-0.5 flex items-center gap-2.5">
                <span class="font-mono text-[9.5px] font-bold uppercase tracking-[0.05em] text-cabin-muted">
                  Input Gain
                </span>
                <div class="flex-1 h-1.5 rounded-full bg-cabin-navy/65 overflow-hidden">
                  <div class="h-full w-[76%] rounded-full bg-cabin-ok" />
                </div>
                <span class="font-mono text-[10px] font-bold text-cabin-text">
                  -12 dB
                </span>
              </div>
            </div>
          </div>

          <div class="rounded-[5px] bg-cabin-inset border border-cabin-card/65 p-3 flex flex-col gap-2">
            <div class="flex flex-wrap items-center justify-between gap-2">
              <span class="font-mono text-[10px] font-bold uppercase tracking-[0.04em] text-cabin-text">
                {{ cardiacHeaderLabel }}
              </span>
              <span class="font-mono text-[10px] font-bold uppercase text-cabin-ok">
                S1 / S2 LOCKED
              </span>
            </div>

            <div class="h-[112px] w-full">
              <ClientOnly>
                <VChart
                  class="w-full h-full"
                  :option="cardiacLiveOption"
                  theme="spacescan-hud"
                  autoresize
                />
              </ClientOnly>
            </div>

            <div class="h-1.5 rounded-full bg-cabin-navy/65 overflow-hidden">
              <div
                class="h-full rounded-full bg-cabin-ok transition-all"
                :style="{ width: cardiacProgressPct }"
              />
            </div>
          </div>

          <div class="rounded-[5px] bg-cabin-inset border border-cabin-card/60 px-3.5 py-2.5 flex flex-col gap-1">
            <span class="text-[9.8px] font-bold tracking-[0.06em] uppercase text-cabin-muted">
              Cardiac Recording Progress
            </span>
            <span class="font-mono text-[10.8px] text-cabin-ice">
              {{ results?.cardiac_progress_summary ?? 'Aortic: Ready (30s) · Pulmonic: Ready (30s) · Tricuspid: Ready (30s) · Mitral: Ready (30s)' }}
            </span>
          </div>

          <div class="grid grid-cols-2 gap-3">
            <button
              type="button"
              class="h-10 px-4 rounded-[5px] border text-[11.5px] font-bold tracking-[0.02em] transition-colors cursor-pointer"
              :class="
                isCardiacRecording
                  ? 'bg-cabin-crit/28 border-cabin-crit text-cabin-text'
                  : 'bg-cabin-inset border-cabin-card/80 text-cabin-text hover:border-cabin-ice/70'
              "
              @click="startRecording('CARDIAC')"
            >
              {{ isCardiacRecording ? 'Stop Heart Audio' : 'Record Heart Audio' }}
            </button>

            <button
              type="button"
              :disabled="cardiacSaving || !isNoiseSafe"
              class="h-10 px-4 rounded-[5px] text-[11.5px] font-bold tracking-[0.02em] text-cabin-text transition-opacity cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed menu-item-active"
              @click="saveRecording('CARDIAC')"
            >
              {{ cardiacSaving ? 'Saving Sample...' : 'Save Cardiac Recording' }}
            </button>
          </div>
        </div>
      </ShellHudWindow>

      <ShellHudWindow
        title="Pulmonary Audio Recording"
        subtitle="Place pickup on lung zone · Follow guided breath cadence"
        icon="mic"
        tag-text="LUNGS · 30S"
        :tag-tone="isNoiseSafe ? 'reference' : 'critical'"
      >
        <div class="flex flex-col justify-between gap-3.5 h-full">
          <div class="flex flex-col gap-1.5">
            <span class="text-[10px] font-bold tracking-[0.06em] uppercase text-cabin-muted">
              Select Bilateral Lung Zone
            </span>
            <div class="grid grid-cols-2 sm:grid-cols-4 gap-2">
              <button
                v-for="zone in pulmonarySites"
                :key="zone.key"
                type="button"
                class="h-8 px-2.5 rounded-[4px] text-[10.8px] border transition-colors cursor-pointer truncate"
                :class="
                  selectedPulmonarySite === zone.key
                    ? 'menu-item-active font-bold text-cabin-text'
                    : 'bg-cabin-inset border-cabin-card/60 text-cabin-muted hover:text-cabin-text font-semibold'
                "
                @click="selectedPulmonarySite = zone.key"
              >
                {{ zone.label }}
              </button>
            </div>
          </div>

          <div class="rounded-[5px] bg-cabin-inset border border-cabin-card/65 p-3.5 flex items-center gap-3.5">
            <div
              class="w-[92px] h-[102px] shrink-0 rounded-[4px] bg-cabin-bg/80 border border-cabin-card/60 flex items-center justify-center relative overflow-hidden hologram-scanline"
            >
              <svg
                viewBox="0 0 88 90"
                class="w-[70px] h-[74px] hologram-shell select-none"
                role="img"
                aria-label="Pulmonary bilateral pickup placement"
              >
                <line
                  x1="44"
                  y1="14"
                  x2="44"
                  y2="37"
                  stroke="var(--color-text-primary)"
                  stroke-width="2.2"
                  stroke-linecap="round"
                />
                <path
                  d="M44 33 L32 42 M44 33 L56 42"
                  fill="none"
                  stroke="var(--color-text-primary)"
                  stroke-width="1.7"
                />
                <path
                  d="M39 26 C24 26, 16 41, 17 62 C18 72, 33 72, 39 63 Z"
                  fill="rgba(41, 148, 166, 0.22)"
                  stroke="var(--color-status-ok)"
                  stroke-width="1.8"
                />
                <path
                  d="M49 26 C64 26, 72 41, 71 62 C70 72, 55 72, 49 63 Z"
                  fill="rgba(41, 148, 166, 0.22)"
                  stroke="var(--color-status-ok)"
                  stroke-width="1.8"
                />
                <circle cx="59" cy="43" r="4.5" fill="var(--color-status-ok)" />
              </svg>
            </div>

            <div class="flex-1 min-w-0 flex flex-col gap-1.5">
              <div class="text-[11px] font-bold tracking-[0.04em] uppercase text-cabin-text truncate">
                {{ activePulmonaryPlacementTitle }}
              </div>
              <div class="text-[11px] font-semibold text-cabin-ok">
                Guided Breath: Inhale 2.0s · Exhale 2.2s ({{ (results?.respiratory_rate_rpm ?? 14.2).toFixed(1) }} rpm)
              </div>
              <div class="text-[10.5px] text-cabin-muted">
                Airflow Clarity: 98% · Zero friction artifacts
              </div>
              <div class="pt-0.5 flex items-center gap-2.5">
                <span class="font-mono text-[9.5px] font-bold uppercase tracking-[0.05em] text-cabin-muted">
                  Airflow Gain
                </span>
                <div class="flex-1 h-1.5 rounded-full bg-cabin-navy/65 overflow-hidden">
                  <div class="h-full w-[82%] rounded-full bg-cabin-ok" />
                </div>
                <span class="font-mono text-[10px] font-bold text-cabin-text">
                  -9 dB
                </span>
              </div>
            </div>
          </div>

          <div class="rounded-[5px] bg-cabin-inset border border-cabin-card/65 p-3 flex flex-col gap-2">
            <div class="flex flex-wrap items-center justify-between gap-2">
              <span class="font-mono text-[10px] font-bold uppercase tracking-[0.04em] text-cabin-text">
                {{ pulmonaryHeaderLabel }}
              </span>
              <span class="font-mono text-[10px] font-bold uppercase text-cabin-ok">
                VESICULAR CLEAR
              </span>
            </div>

            <div class="h-[112px] w-full">
              <ClientOnly>
                <VChart
                  class="w-full h-full"
                  :option="pulmonaryLiveOption"
                  theme="spacescan-hud"
                  autoresize
                />
              </ClientOnly>
            </div>

            <div class="h-1.5 rounded-full bg-cabin-navy/65 overflow-hidden">
              <div
                class="h-full rounded-full bg-cabin-ok transition-all"
                :style="{ width: pulmonaryProgressPct }"
              />
            </div>
          </div>

          <div class="rounded-[5px] bg-cabin-inset border border-cabin-card/60 px-3.5 py-2.5 flex flex-col gap-1">
            <span class="text-[9.8px] font-bold tracking-[0.06em] uppercase text-cabin-muted">
              Pulmonary Recording Progress
            </span>
            <span class="font-mono text-[10.8px] text-cabin-ice">
              {{ results?.pulmonary_progress_summary ?? 'Upper Left: Ready (30s) · Upper Right: Ready (30s) · Lower Left: Ready (30s) · Lower Right: Ready (30s)' }}
            </span>
          </div>

          <div class="grid grid-cols-2 gap-3">
            <button
              type="button"
              class="h-10 px-4 rounded-[5px] border text-[11.5px] font-bold tracking-[0.02em] transition-colors cursor-pointer"
              :class="
                isPulmonaryRecording
                  ? 'bg-cabin-crit/28 border-cabin-crit text-cabin-text'
                  : 'bg-cabin-inset border-cabin-card/80 text-cabin-text hover:border-cabin-ice/70'
              "
              @click="startRecording('PULMONARY')"
            >
              {{ isPulmonaryRecording ? 'Stop Pulmonary Audio' : 'Record Pulmonary Audio' }}
            </button>

            <button
              type="button"
              :disabled="pulmonarySaving || !isNoiseSafe"
              class="h-10 px-4 rounded-[5px] text-[11.5px] font-bold tracking-[0.02em] text-cabin-text transition-opacity cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed menu-item-active"
              @click="saveRecording('PULMONARY')"
            >
              {{ pulmonarySaving ? 'Saving Sample...' : 'Save Lung Recording' }}
            </button>
          </div>
        </div>
      </ShellHudWindow>
    </div>
  </div>
</template>
