<script setup lang="ts">
// Astronaut Profile · Streak (read-only): the crew member's own consistency streak, today's
// four habits against their personal targets and the last 14 days. It reloads as soon as
// water, food, exercise or sleep is logged in Capture. The public board stays in /crew-streaks.
import type { StatusCode } from '~/utils/format'
import { formatDuration, formatNumber } from '~/utils/format'

interface DayEntry { date_utc: string, day_label: string, logged: boolean, compliant: boolean, habits_done: number, shield: boolean }
interface Habit { key: string, label: string, value: number | null, target: number, unit: string, pct: number }
interface PersonalStreak {
  crew: { id: string, code: string, full_name: string, title_en: string }
  today_label: string
  active_streak_days: number
  best_streak_days: number
  shield_active: boolean
  after_eva_today: boolean
  today_compliant: boolean
  habits_done_today: number
  habits: Habit[]
  last_14_days: DayEntry[]
  consistency_14d_pct: number
  rules: { compliant_habits: number, shield_habits: number }
}

const { crew } = useSession()
const { api } = useApi()
const { data, loading, error, refresh } = useResource(
  () => api<PersonalStreak>(`/streaks/${crew.value!.id}`), 30_000, ['streaks', 'vitals', 'psych', 'sleep'])

usePageHeader(() => ({
  title: 'Astronaut Profile · Streak',
  status: data.value
    ? { text: `${data.value.active_streak_days} day streak`, tone: data.value.today_compliant ? 'ok' : 'neutral' }
    : null,
}))

const HELP: Record<string, string> = {
  hydration: 'hydration_ml', nutrition: 'calories_kcal', exercise: 'exercise_min', sleep: 'sleep_duration',
}
const LABEL: Record<string, string> = { sleep: 'Sleep Window' }

function habitValue(habit: Habit): string {
  if (habit.value == null) return '—'
  if (habit.key === 'hydration') return (habit.value / 1000).toFixed(1)
  if (habit.unit === 'min') return formatDuration(habit.value)
  return formatNumber(habit.value)
}
function habitTarget(habit: Habit): string {
  if (habit.key === 'hydration') return `Personal target: ${(habit.target / 1000).toFixed(1)} L`
  if (habit.unit === 'min') return `Personal target: ${formatDuration(habit.target)}`
  return `Personal target: ${formatNumber(habit.target)} ${habit.unit}`
}
const habitStatus = (habit: Habit): StatusCode => (habit.pct >= 100 ? 'NOMINAL' : habit.value == null ? 'NO_DATA' : habit.pct >= 60 ? 'WATCH' : 'WARNING')
const habitText = (habit: Habit) => (habit.pct >= 100 ? 'Met' : habit.value == null ? 'Not logged' : `${habit.pct}%`)

function dayClass(day: DayEntry, last: boolean): string {
  if (!day.logged) return 'bg-cabin-tile border-cabin-line text-cabin-dim'
  if (day.shield) return 'bg-cabin-navy/60 border-cabin-navy-edge'
  if (day.compliant && day.habits_done === 4) return 'bg-cabin-ok/15 border-cabin-ok/70'
  if (day.compliant) return last ? 'bg-cabin-navy/60 border-cabin-navy-edge' : 'bg-cabin-ok/15 border-cabin-ok/70'
  return 'bg-cabin-crit/25 border-cabin-crit/80'
}
</script>

<template>
  <div class="page">
    <ShellProfileTabs />
    <UiStateNote v-if="!data" :loading="loading" :error="error" @retry="refresh()" />
    <div v-else class="flex-1 min-h-0 flex gap-[18px]">
      <ShellHudWindow
class="w-[31.1%] shrink-0" title="Personal Consistency Streak" icon="flame" help-key="habit_streak"
                      :tag-text="data.shield_active ? 'POST-EVA SHIELD' : data.today_compliant ? 'TODAY COUNTS' : 'IN PROGRESS'" flush>
        <div class="flex-1 min-h-0 flex flex-col px-[19px] pt-[clamp(10px,1.9dvh,18px)] pb-[16px] gap-[clamp(10px,1.7dvh,16px)]">
          <div class="tile flex-1 min-h-[150px] flex items-center justify-center">
            <UiArcGauge
              :fraction="data.active_streak_days / Math.max(data.best_streak_days, data.active_streak_days, 1)"
              :tone="data.today_compliant || data.shield_active ? 'ok' : 'watch'"
              label="Active Streak" :value="`${data.active_streak_days} Days`"
              :caption="`Best: ${data.best_streak_days} days`"
              size="clamp(120px, 19dvh, 220px)" :value-size="24"
            />
          </div>
          <div class="grid grid-cols-2 gap-[12px] shrink-0">
            <div class="tile h-[clamp(64px,8.5dvh,92px)] px-[16px] flex flex-col justify-center">
              <p class="label-caps">Today · {{ data.today_label }}</p>
              <p class="text-[20px] font-bold mt-[6px]">{{ data.habits_done_today }} / 4 <span class="text-[11px] font-normal text-cabin-ice">habits</span></p>
            </div>
            <div class="tile h-[clamp(64px,8.5dvh,92px)] px-[16px] flex flex-col justify-center">
              <p class="label-caps">14-day consistency</p>
              <p class="text-[20px] font-bold mt-[6px]">{{ data.consistency_14d_pct }}%</p>
            </div>
          </div>
          <div class="tile-hi shrink-0 px-[16px] py-[12px] text-[11.5px] leading-[1.55]">
            A day counts when {{ data.rules.compliant_habits }} of 4 habits are met. After exterior work,
            {{ data.rules.shield_habits }} habits keep the streak alive (post-EVA shield).
          </div>
        </div>
      </ShellHudWindow>

      <ShellHudWindow
class="flex-1 min-w-0" title="Today's Habits vs Personal Target" icon="heart"
                      :tag-text="`${data.habits_done_today} / 4 MET`" flush>
        <div class="flex-1 min-h-0 flex flex-col justify-around gap-[6px] px-[23px] py-[10px]">
          <UiBandRow
            v-for="habit in data.habits"
            :key="habit.key"
            :label="LABEL[habit.key] ?? habit.label"
            :help-key="HELP[habit.key]"
            :reference="habitTarget(habit)"
            :value-text="habitValue(habit)"
            :unit="habit.key === 'hydration' ? 'L' : habit.unit === 'min' ? '' : habit.unit"
            :status="habitStatus(habit)"
            :status-text="habitText(habit)"
            :value="Math.min(habit.pct, 120)"
            :scale-min="0"
            :scale-max="120"
            :band-low="100"
            :band-high="120"
          />
        </div>
      </ShellHudWindow>

      <ShellHudWindow class="w-[27%] shrink-0" title="Last 14 Days" icon="reticle" :tag-text="`${data.last_14_days.filter(d => d.compliant).length} / 14 COUNTED`" flush>
        <div class="flex-1 min-h-0 flex flex-col px-[19px] pt-[clamp(10px,1.9dvh,18px)] pb-[16px]">
          <div class="grid grid-cols-2 gap-[8px] flex-1 min-h-0 auto-rows-fr">
            <div
              v-for="(day, index) in data.last_14_days"
              :key="day.date_utc"
              class="rounded-[4px] border-[1.2px] flex items-center justify-between px-[12px] min-h-0"
              :class="dayClass(day, index === data.last_14_days.length - 1)"
              :title="`${day.day_label}: ${day.habits_done} of 4 habits`"
            >
              <span class="mono text-[10px] font-bold">{{ day.day_label }}</span>
              <span v-if="day.shield" class="mono text-[10px] font-bold">SHIELD</span>
              <span v-else-if="!day.logged" class="mono text-[10px]">—</span>
              <span v-else class="flex items-center gap-[6px] mono text-[10px] font-bold">
                {{ day.habits_done }}/4
                <Icon v-if="day.compliant" name="spacescan:check" class="w-[11px] h-[11px]" />
              </span>
            </div>
          </div>
          <div class="flex flex-wrap gap-x-[14px] gap-y-[4px] mt-[12px] text-[10px] text-cabin-ice shrink-0">
            <span class="flex items-center gap-[6px]"><i class="w-[8px] h-[8px] rounded-[2px] bg-cabin-ok/60" />Counted</span>
            <span class="flex items-center gap-[6px]"><i class="w-[8px] h-[8px] rounded-[2px] bg-cabin-navy-edge" />Shield / today</span>
            <span class="flex items-center gap-[6px]"><i class="w-[8px] h-[8px] rounded-[2px] bg-cabin-crit/70" />Missed</span>
          </div>
        </div>
      </ShellHudWindow>
    </div>
  </div>
</template>
