<script setup lang="ts">
import VChart from 'vue-echarts'
import ProfileSubnavBar from '~/components/profile/ProfileSubnavBar.vue'
import { buildLeadIiEcgOption, shiftEcgSweepWindow } from '~/utils/profileCharts'
import type { StatusTone } from '~/utils/profileCharts'

const {
  profile,
  selectedStage,
  isLoading,
  errorMessage,
  loadProfile,
  openTelemetryStream,
} = useCrewProfile()

const ecgWindow = ref<number[]>([])
const ecgCursor = ref(0)
let sweepTimer: ReturnType<typeof setInterval> | null = null
let closeStream: (() => void) | null = null

const headerBadgeTone = computed<'reference' | 'warn' | 'critical'>(() => {
  const v = profile.value?.daily_vitals
  if (!v) return 'reference'
  const anyCritical = v.items.some(item => item.status_tone === 'critical')
  if (anyCritical) return 'critical'
  return v.on_target_count === v.total_count ? 'reference' : 'warn'
})

const ecgOption = computed(() => {
  const live = profile.value?.live_ecg
  const samples = ecgWindow.value.length > 0 ? ecgWindow.value : (live?.samples_mv ?? [])
  return buildLeadIiEcgOption(
    samples,
    live?.sample_rate_hz ?? 100,
    live?.rhythm_tone ?? 'reference',
  )
})

function syncEcgSweep() {
  const fullSamples = profile.value?.live_ecg.samples_mv ?? []
  if (fullSamples.length === 0) return
  const next = shiftEcgSweepWindow(fullSamples, ecgCursor.value, 180, 4)
  ecgWindow.value = next.window
  ecgCursor.value = next.nextCursor
}

function statusPillClass(tone: StatusTone): string {
  if (tone === 'critical') {
    return 'bg-cabin-crit/25 border-cabin-crit/85 text-cabin-text'
  }
  if (tone === 'warn') {
    return 'bg-cabin-navy/60 border-cabin-navy-edge/95 text-cabin-text'
  }
  return 'bg-cabin-navy/42 border-cabin-navy-edge/70 text-cabin-text'
}

function markerDotClass(tone: StatusTone): string {
  if (tone === 'critical') return 'bg-cabin-crit'
  if (tone === 'warn') return 'bg-cabin-navy-edge'
  return 'bg-cabin-ok'
}

function labAccentClass(tone: StatusTone): string {
  if (tone === 'critical') return 'bg-cabin-crit'
  if (tone === 'warn') return 'bg-cabin-navy-edge'
  return 'bg-cabin-ok'
}

watch(
  () => profile.value?.live_ecg.samples_mv,
  (nextSamples) => {
    if (nextSamples && nextSamples.length > 0) {
      ecgCursor.value = 0
      syncEcgSweep()
    }
  },
  { immediate: true },
)

onMounted(() => {
  void loadProfile()
  closeStream = openTelemetryStream()
  sweepTimer = setInterval(syncEcgSweep, 180)
})

onUnmounted(() => {
  if (sweepTimer) clearInterval(sweepTimer)
  closeStream?.()
})
</script>

<template>
  <div class="flex flex-col gap-[18px] flex-1">
    <ProfileSubnavBar
      v-model:selected-stage="selectedStage"
      :badge-text="profile?.daily_vitals.header_target_badge ?? 'READ ONLY'"
      :badge-tone="headerBadgeTone"
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
        No dedicated measurements logged in {{ profile.mission.selected_stage }} yet — displaying latest active vitals and clinical labs.
      </span>
      <span class="font-mono text-[10px] font-bold uppercase text-cabin-text">
        {{ profile.mission.mission_day_code }}
      </span>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-[1fr_1.39fr] gap-[18px] flex-1">
      <ShellHudWindow
        title="DAILY VITALS, EXERCISE & NUTRITION"
        icon="vitruvian"
        :tag-text="profile?.daily_vitals.tag_text ?? 'CONTINUOUS'"
      >
        <div v-if="profile" class="h-full flex flex-col justify-between gap-5 py-1">
          <div
            v-for="item in profile.daily_vitals.items"
            :key="item.key"
            class="flex flex-col gap-2.5"
          >
            <div class="flex items-end justify-between gap-3">
              <div class="flex flex-col gap-0.5">
                <span class="text-[13px] font-bold text-cabin-text leading-tight">
                  {{ item.label }}
                </span>
                <span class="text-[10.5px] text-cabin-muted leading-tight">
                  {{ item.subtitle }}
                </span>
              </div>

              <div class="flex items-center gap-3 shrink-0">
                <div class="flex items-baseline gap-1.5">
                  <span class="font-mono text-[21px] font-bold text-cabin-text leading-none">
                    {{ item.display_value }}
                  </span>
                  <span class="font-mono text-[11px] text-cabin-muted">
                    {{ item.unit }}
                  </span>
                </div>

                <span
                  class="h-[21px] px-2.5 rounded-full border text-[9.8px] font-semibold inline-flex items-center gap-1.5"
                  :class="statusPillClass(item.status_tone)"
                >
                  <span
                    v-if="item.status_tone !== 'nominal'"
                    class="w-1.5 h-1.5 rounded-full"
                    :class="markerDotClass(item.status_tone)"
                  />
                  {{ item.status_label }}
                </span>
              </div>
            </div>

            <div class="relative h-[8px] rounded-full bg-cabin-inset border border-cabin-card/45">
              <span
                class="pointer-events-none absolute inset-y-0 rounded-full bg-cabin-card/55 border border-cabin-ok/35"
                :style="{
                  left: `${item.band_start_pct}%`,
                  width: `${item.band_width_pct}%`,
                }"
              />
              <span
                class="pointer-events-none absolute top-1/2 -translate-y-1/2 -translate-x-1/2 w-[10px] h-[10px] rounded-full border border-cabin-bg"
                :class="markerDotClass(item.status_tone)"
                :style="{ left: `${item.progress_pct}%` }"
              />
            </div>
          </div>
        </div>

        <p v-else-if="isLoading" class="text-[12px] text-cabin-muted">
          Loading continuous crew vitals...
        </p>
      </ShellHudWindow>

      <div class="flex flex-col gap-[18px]">
        <ShellHudWindow
          title="LIVE ECG & BODY TEMPERATURE"
          icon="stethoscope"
          :tag-text="profile?.live_ecg.rhythm_label ?? 'NORMAL SINUS'"
          :tag-tone="profile?.live_ecg.rhythm_tone ?? 'reference'"
        >
          <div class="rounded-[4px] bg-cabin-inset border border-cabin-card/65 px-4 py-3 flex flex-col gap-2">
            <div class="flex flex-wrap items-center justify-between gap-2">
              <span class="font-mono text-[10px] font-bold tracking-[0.06em] uppercase text-cabin-ok">
                {{ profile?.live_ecg.lead_label ?? 'LEAD II · 25 mm/s' }}
              </span>
              <span class="font-mono text-[10px] font-bold tracking-[0.05em] uppercase text-cabin-text">
                {{ profile?.live_ecg.header_summary ?? '-- BPM · HRV -- MS · -- °C' }}
              </span>
            </div>

            <div class="h-[172px] w-full">
              <ClientOnly>
                <VChart
                  v-if="profile?.live_ecg.samples_mv.length"
                  :option="ecgOption"
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
          title="PERIODIC CLINICAL LAB RESULTS"
          icon="kit"
          tag-text="LATEST RESULTS"
        >
          <div v-if="profile" class="grid grid-cols-1 sm:grid-cols-2 gap-4 h-full">
            <div
              v-for="lab in profile.clinical_labs"
              :key="lab.key"
              class="relative rounded-[4px] bg-cabin-inset border border-cabin-card/60 pl-5 pr-4 py-4 flex flex-col justify-between min-h-[142px]"
            >
              <span
                class="pointer-events-none absolute left-0 top-3.5 bottom-3.5 w-[4px] rounded-r-[2px]"
                :class="labAccentClass(lab.status_tone)"
              />

              <div class="flex items-center justify-between gap-2">
                <span
                  class="text-[10px] font-bold tracking-[0.06em] uppercase"
                  :class="lab.status_tone === 'nominal' ? 'text-cabin-ok' : 'text-cabin-ice'"
                >
                  {{ lab.label }}
                </span>

                <span
                  class="h-[22px] px-3 rounded-full border text-[9.8px] font-semibold inline-flex items-center gap-1.5 shrink-0"
                  :class="statusPillClass(lab.status_tone)"
                >
                  <span
                    v-if="lab.status_tone !== 'nominal'"
                    class="w-1.5 h-1.5 rounded-full"
                    :class="markerDotClass(lab.status_tone)"
                  />
                  {{ lab.status_label }}
                </span>
              </div>

              <span class="font-mono text-[24px] font-bold text-cabin-text leading-none my-2">
                {{ lab.display_value }}
              </span>

              <span class="text-[11px] text-cabin-ice leading-snug">
                {{ lab.detail }}
              </span>
            </div>
          </div>

          <p v-else-if="isLoading" class="text-[12px] text-cabin-muted">
            Loading clinical strip and ocular results...
          </p>
        </ShellHudWindow>
      </div>
    </div>
  </div>
</template>
