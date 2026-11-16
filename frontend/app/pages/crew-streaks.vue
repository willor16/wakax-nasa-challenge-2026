<script setup lang="ts">
// 03 · Crew Streaks: public, read-only. Individual streaks, last 7 days and today's habits.
import type { Tone } from '~/utils/format'

interface DayEntry { day_label: string, logged: boolean, compliant: boolean, habits_done: number, shield: boolean }
interface StreakCrew {
  id: string
  code: string
  full_name: string
  title_en: string
  active_streak_days: number
  best_streak_days: number
  today_compliant: boolean
  today_shield: boolean
  habits_done_today: number
  last_7_days: DayEntry[]
  habits: { key: string, label: string, pct: number }[]
}
interface Streaks {
  today_label: string
  window: { day_label: string }[]
  team_streak_days: number
  team_completed_pct: number | null
  team: {
    hydration_pct: number | null
    hydration_on_pace: number
    nutrition_pct: number | null
    nutrition_met: number
    exercise_pct: number | null
    exercise_met: number
    post_eva_rest: number
    consistency_30d_pct: number | null
    active_streaks: number
    crew_count: number
  }
  crew: StreakCrew[]
}

const { api } = useApi()
const { data, loading, error, refresh } = useResource(() => api<Streaks>('/crew-streaks'), 15_000)

usePageHeader(() => ({
  title: 'Crew Streaks',
  status: data.value ? { text: `Team streak · ${data.value.team_streak_days} days`, tone: 'ok' } : null,
}))

const attention = (member: StreakCrew) => !member.today_compliant && member.habits_done_today < 3
function habitTone(pct: number): Tone {
  return pct >= 80 ? 'ok' : pct >= 60 ? 'watch' : 'critical'
}
function streakCaption(member: StreakCrew): string {
  if (member.today_shield) return 'EVA Rest Shield'
  if (attention(member)) {
    const weakest = [...member.habits].sort((a, b) => a.pct - b.pct)[0]
    return weakest ? `${weakest.label.replace(' Routine', '')} below target` : 'Below target'
  }
  return `Best: ${member.best_streak_days} days`
}
function tag(member: StreakCrew): string {
  if (attention(member)) return 'ATTENTION'
  return member.today_shield ? `${member.active_streak_days} DAYS · SHIELD` : `${member.active_streak_days} DAYS`
}
function dayClass(day: DayEntry, last: boolean): string {
  if (!day.logged) return 'bg-cabin-tile border-cabin-line text-cabin-dim'
  if (day.shield) return 'bg-cabin-navy/60 border-cabin-navy-edge'
  if (day.compliant && day.habits_done === 4) return 'bg-cabin-ok/15 border-cabin-ok/70'
  if (day.compliant) return last ? 'bg-cabin-navy/60 border-cabin-navy-edge' : 'bg-cabin-ok/15 border-cabin-ok/70'
  return 'bg-cabin-crit/25 border-cabin-crit/80'
}
const windowText = computed(() => {
  const days = data.value?.window ?? []
  return days.length ? `${days[0]!.day_label} – ${days.at(-1)!.day_label}` : ''
})
</script>

<template>
  <UiStateNote v-if="!data" :loading="loading" :error="error" empty="No streak data yet." @retry="refresh()" />
  <div v-else class="flex-1 min-h-0 flex flex-col gap-[14px]">
    <div class="flex gap-[19px] h-[592px] shrink-0">
      <ShellHudWindow v-for="member in data.crew" :key="member.id" class="flex-1" flush :critical="attention(member)">
        <template #header>
          <div class="leading-tight min-w-0">
            <h2 class="text-[13px] font-bold truncate">{{ member.code.slice(-2) }} · {{ member.full_name }}</h2>
            <p class="text-[10.5px] text-cabin-ice">{{ member.title_en }}</p>
          </div>
          <UiStatusPill :tone="attention(member) ? 'critical' : 'reference'">{{ tag(member) }}</UiStatusPill>
        </template>
        <div class="flex-1 flex flex-col px-[16px] pt-[16px] pb-[14px]">
          <div class="tile h-[168px] flex items-center justify-center">
            <UiArcGauge
              :fraction="member.active_streak_days / Math.max(member.best_streak_days, member.active_streak_days, 1)"
              :tone="attention(member) ? 'critical' : 'ok'"
              label="Active Streak"
              :value="`${member.active_streak_days} Days`"
              :caption="streakCaption(member)"
              :size="124"
              :value-size="19"
            />
          </div>
          <p class="label-caps mt-[22px]">Last 7 days ({{ windowText }})</p>
          <div class="flex gap-[5px] mt-[10px]">
            <div
              v-for="(day, index) in member.last_7_days"
              :key="day.day_label"
              class="flex-1 h-[46px] rounded-[4px] border-[1.2px] flex flex-col items-center justify-center gap-[3px]"
              :class="dayClass(day, index === member.last_7_days.length - 1)"
              :title="`${day.day_label}: ${day.habits_done} of 4 habits`"
            >
              <span class="mono text-[8.5px] font-bold">{{ day.day_label }}</span>
              <span v-if="day.shield" class="mono text-[9px] font-bold">SHD</span>
              <span v-else-if="!day.logged" class="mono text-[9px]">—</span>
              <Icon v-else-if="day.habits_done === 4" name="spacescan:check" class="w-[11px] h-[11px]" />
              <span v-else class="mono text-[9px] font-bold">{{ day.habits_done }}/4</span>
            </div>
          </div>
          <p class="label-caps mt-[20px]">{{ data.today_label }} habits</p>
          <div class="flex flex-col gap-[10px] mt-[10px]">
            <div v-for="habit in member.habits" :key="habit.key" class="tile h-[44px] px-[14px] flex flex-col justify-center">
              <div class="flex items-center justify-between">
                <span class="text-[11.5px] font-bold">{{ habit.label }}</span>
                <span class="mono text-[10.5px]" :class="habit.pct >= 80 ? 'text-cabin-ok' : 'text-cabin-text'">
                  {{ habit.pct }}%
                </span>
              </div>
              <UiProgressBar :pct="habit.pct" :tone="habitTone(habit.pct)" class="mt-[7px]" />
            </div>
          </div>
        </div>
      </ShellHudWindow>
    </div>

    <ShellHudWindow
      class="flex-1"
      title="Collective Streak & Daily Habits · Habitat A"
      icon="flame"
      :tag-text="data.team_completed_pct === null ? undefined : `${data.team_completed_pct}% COMPLETED`"
      flush
    >
      <div class="flex-1 flex items-center px-[50px] gap-[58px]">
        <UiArcGauge
:fraction="Math.min(1, data.team_streak_days / 30)" label="Team Streak"
                    :value="String(data.team_streak_days)" caption="Days active" :size="100" />
        <div
v-for="item in [
          { label: 'Crew Hydration', pct: data.team.hydration_pct,
            note: `${data.team.hydration_on_pace} of ${data.team.crew_count} crew on pace` },
          { label: 'Daily Nutrition', pct: data.team.nutrition_pct,
            note: data.team.nutrition_met === data.team.crew_count
              ? `All ${data.team.crew_count} meal plans completed`
              : `${data.team.nutrition_met} of ${data.team.crew_count} meal plans completed` },
          { label: 'Scheduled Exercise', pct: data.team.exercise_pct,
            note: `${data.team.exercise_met} complete`
              + (data.team.post_eva_rest ? ` · ${data.team.post_eva_rest} post-EVA rest` : '') },
        ]" :key="item.label" class="w-[248px]">
          <div class="flex items-baseline justify-between">
            <span class="text-[12.5px] font-bold">{{ item.label }}</span>
            <span class="text-[15px] font-bold">{{ item.pct === null ? '—' : `${item.pct}%` }}</span>
          </div>
          <UiProgressBar :pct="item.pct ?? 0" :tone="(item.pct ?? 0) >= 80 ? 'ok' : 'watch'" thick class="mt-[10px]" />
          <p class="text-[10.5px] text-cabin-ice mt-[12px]">{{ item.note }}</p>
        </div>
        <div class="tile-hi flex-1 h-[82px] px-[20px] flex flex-col justify-center">
          <p class="text-[9.5px] font-bold tracking-[0.04em] uppercase text-cabin-ok">30-day mission consistency</p>
          <p class="text-[12.5px] font-semibold mt-[10px]">
            <template v-if="data.team.consistency_30d_pct !== null">
              {{ data.team.consistency_30d_pct }}% of daily habits met ·
              {{ data.team.active_streaks }} / {{ data.team.crew_count }} crew streaks active
            </template>
            <template v-else>No habits logged yet</template>
          </p>
        </div>
      </div>
    </ShellHudWindow>
  </div>
</template>
