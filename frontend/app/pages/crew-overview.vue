<script setup lang="ts">
// 02 · Crew Overview: public, read-only. Four crew columns and the cabin readiness strip.
import type { CabinSnapshot } from '~/composables/useMission'
import type { StatusCode, Tone } from '~/utils/format'
import { crewTone, formatDuration, formatNumber, litres, scalePct, toneOf } from '~/utils/format'

interface OverviewCrew {
  id: string
  code: string
  full_name: string
  title_en: string
  status: string
  work_shift: { mode: string, minutes: number, location_en: string | null } | null
  vitals: {
    resting_hr_bpm: number | null
    hrv_rmssd_ms: number | null
    spo2_pct: number | null
    sleep_min_24h: number | null
    sleep_target_min: number
    resting_hr_status: StatusCode
    hrv_status: StatusCode
    spo2_status: StatusCode
  }
}
interface Overview {
  crew_score: number | null
  optimal_count: number
  crew_count: number
  readiness: {
    hydration_pct: number | null
    hydration_avg_ml: number | null
    hydration_target_ml: number | null
    sleep_target_pct: number | null
    sleep_below_count: number
    sleep_target_min: number
    exercise_pct: number | null
  }
  crew: OverviewCrew[]
  cabin: CabinSnapshot | null
}

const { api } = useApi()
const { data, loading, error, refresh } = useResource(() => api<Overview>('/crew-overview'), 15_000)
const { cabin: liveCabin } = useMission()
const cabin = computed(() => liveCabin.value ?? data.value?.cabin ?? null)

usePageHeader(() => ({
  title: 'Crew Overview',
  status: data.value
    ? { text: `${data.value.optimal_count} / ${data.value.crew_count} crew optimal`,
        tone: data.value.optimal_count === data.value.crew_count ? 'ok' : 'ok' }
    : null,
}))

function sleepTone(member: OverviewCrew): Tone {
  const minutes = member.vitals.sleep_min_24h
  if (minutes === null) return 'neutral'
  if (minutes >= member.vitals.sleep_target_min) return 'ok'
  return minutes < member.vitals.sleep_target_min - 60 ? 'critical' : 'watch'
}
function sleepNote(member: OverviewCrew): string {
  const minutes = member.vitals.sleep_min_24h
  const target = member.vitals.sleep_target_min
  if (minutes === null) return 'No sleep logged'
  if (minutes >= target) return `Target ≥${target / 60}h`
  const gap = target - minutes
  return gap >= 60 ? `-${formatDuration(gap)}` : `Below ≥${target / 60}h`
}
function hrvTone(member: OverviewCrew): Tone {
  // Under 50 ms is flagged on this board even though it is still inside the usual range.
  const value = member.vitals.hrv_rmssd_ms
  if (value === null) return 'neutral'
  const tone = toneOf(member.vitals.hrv_status)
  return tone === 'ok' && value < 50 ? 'critical' : tone
}
const toneText: Record<Tone, string> = {
  ok: 'text-cabin-ok', watch: 'text-cabin-text', critical: 'text-cabin-text', neutral: 'text-cabin-dim',
}
function tiles(member: OverviewCrew) {
  const v = member.vitals
  return [
    { label: 'Heart Rate', value: formatNumber(v.resting_hr_bpm), note: 'bpm', tone: toneOf(v.resting_hr_status),
      pct: scalePct(v.resting_hr_bpm, 30, 110) },
    { label: 'HRV', value: formatNumber(v.hrv_rmssd_ms), note: 'ms', tone: hrvTone(member),
      pct: scalePct(v.hrv_rmssd_ms, 10, 100) },
    { label: 'Sleep (24h)', value: formatDuration(v.sleep_min_24h), note: sleepNote(member), tone: sleepTone(member),
      pct: scalePct(v.sleep_min_24h, 0, 520), wide: true },
    { label: 'Oxygen (SpO₂)', value: v.spo2_pct === null ? '—' : `${formatNumber(v.spo2_pct)}%`,
      note: v.spo2_status === 'NOMINAL' ? 'Optimal' : v.spo2_status === 'NO_DATA' ? 'No reading' : 'Low',
      tone: toneOf(v.spo2_status), pct: scalePct(v.spo2_pct, 85, 100), wide: true },
  ]
}
const cabinLine = computed(() => {
  const c = cabin.value
  if (!c) return null
  return `${c.temp_c.toFixed(1)} °C · ${Math.round(c.humidity_pct)}% RH · ${Math.round(c.noise_dba)} dBA · CO₂ ${c.co2_mmhg.toFixed(1)} mmHg`
})
const cabinState = computed(() => {
  const s = cabin.value?.status
  return s === 'NOMINAL' ? 'NOMINAL' : s === 'CRITICAL' ? 'CRITICAL' : s ? 'ATTENTION' : ''
})
</script>

<template>
  <UiStateNote v-if="!data" :loading="loading" :error="error" empty="No crew data yet." @retry="refresh()" />
  <div v-else class="flex-1 min-h-0 flex flex-col gap-[14px]">
    <div class="flex gap-[19px] h-[592px] shrink-0">
      <ShellHudWindow
        v-for="member in data.crew"
        :key="member.id"
        class="flex-1"
        flush
        :critical="member.status === 'Attention'"
      >
        <template #header>
          <div class="leading-tight min-w-0">
            <h2 class="text-[13px] font-bold truncate">{{ member.code.slice(-2) }} · {{ member.full_name }}</h2>
            <p class="text-[10.5px] text-cabin-ice">{{ member.title_en }}</p>
          </div>
          <UiStatusPill :tone="crewTone(member.status) === 'critical' ? 'critical' : 'reference'">
            {{ member.status.toUpperCase() }}
          </UiStatusPill>
        </template>
        <div class="flex-1 flex flex-col px-[16px] pb-[16px]">
          <div class="flex-1 flex items-center justify-center">
            <UiHoloFigure
figure="body" :tone="crewTone(member.status)" :size="128"
                          :label="`${member.full_name}: ${member.status}`" />
          </div>
          <div class="tile h-[56px] px-[12px] flex flex-col justify-center">
            <p class="label-caps">Work shift &amp; location</p>
            <p class="text-[12px] mt-[5px] truncate">
              <template v-if="member.work_shift">
                {{ member.work_shift.mode }}: {{ formatDuration(member.work_shift.minutes) }}
                <template v-if="member.work_shift.location_en"> · {{ member.work_shift.location_en }}</template>
              </template>
              <span v-else class="text-cabin-dim">No shift logged today</span>
            </p>
          </div>
          <div class="grid grid-cols-2 gap-[11px] mt-[21px]">
            <div v-for="tile in tiles(member)" :key="tile.label" class="tile h-[123px] px-[12px] pt-[16px] pb-[14px] flex flex-col">
              <p class="label-caps">{{ tile.label }}</p>
              <p class="text-[22px] font-bold mt-[13px] leading-none">{{ tile.value }}</p>
              <p class="text-[10.5px] font-semibold mt-[13px]" :class="toneText[tile.tone]">{{ tile.note }}</p>
              <UiProgressBar :pct="tile.pct" :tone="tile.tone" class="mt-auto" />
            </div>
          </div>
        </div>
      </ShellHudWindow>
    </div>

    <ShellHudWindow
      class="flex-1"
      title="Crew Readiness & Cabin Environment"
      icon="rocket"
      :tag-text="data.crew_score === null ? undefined : `READINESS ${data.crew_score} / 100`"
      flush
    >
      <div class="flex-1 flex items-center px-[50px] gap-[58px]">
        <UiArcGauge
:fraction="(data.crew_score ?? 0) / 100" label="Crew Score"
                    :value="formatNumber(data.crew_score)" caption="of 100" :size="100" />
        <div
v-for="item in [
          { label: 'Hydration', pct: data.readiness.hydration_pct,
            note: `Avg ${litres(data.readiness.hydration_avg_ml)} L / ${litres(data.readiness.hydration_target_ml)} L goal` },
          { label: 'Sleep Target', pct: data.readiness.sleep_target_pct,
            note: `${data.readiness.sleep_below_count} of ${data.crew_count} below ≥${data.readiness.sleep_target_min / 60}h target` },
          { label: 'Daily Exercise', pct: data.readiness.exercise_pct, note: 'Share of today\'s exercise goals met' },
        ]" :key="item.label" class="w-[248px]">
          <div class="flex items-baseline justify-between">
            <span class="text-[12.5px] font-bold">{{ item.label }}</span>
            <span class="text-[15px] font-bold">{{ item.pct === null ? '—' : `${item.pct}%` }}</span>
          </div>
          <UiProgressBar :pct="item.pct ?? 0" :tone="(item.pct ?? 0) >= 80 ? 'ok' : 'watch'" thick class="mt-[10px]" />
          <p class="text-[10.5px] text-cabin-ice mt-[12px]">{{ item.note }}</p>
        </div>
        <div class="tile-hi flex-1 h-[82px] px-[20px] flex flex-col justify-center">
          <p
class="text-[9.5px] font-bold tracking-[0.04em] uppercase"
             :class="cabinState === 'NOMINAL' ? 'text-cabin-ok' : 'text-cabin-text'">
            {{ cabin?.location_en ?? 'Habitat' }} environment<template v-if="cabinState"> · {{ cabinState }}</template>
          </p>
          <p class="text-[12.5px] font-semibold mt-[10px]">{{ cabinLine ?? 'No cabin reading yet' }}</p>
        </div>
      </div>
    </ShellHudWindow>
  </div>
</template>
