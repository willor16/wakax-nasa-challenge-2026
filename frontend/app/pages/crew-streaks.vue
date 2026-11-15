<script setup lang="ts">
interface DayCompliance {
  date_utc: string;
  compliant: boolean;
  logs_completed: number;
  habits_met: boolean;
}

interface CrewStreakMember {
  id: string;
  code: string;
  full_name: string;
  role: string;
  active_streak_days: number;
  best_streak_days: number;
  last_7_days: DayCompliance[];
}

interface CrewStreaksResponse {
  window_dates: string[];
  team_streak_days: number;
  team_compliance_pct: number;
  eva_shield_ready: boolean;
  crew: CrewStreakMember[];
}

const loading = ref(true);
const errorMessage = ref('');
const streakData = ref<CrewStreaksResponse | null>(null);

async function loadCrewStreaks() {
  loading.value = true;
  errorMessage.value = '';
  try {
    streakData.value = await $fetch<CrewStreaksResponse>('/api/v1/crew-streaks');
  } catch {
    errorMessage.value = 'Unable to retrieve crew streak telemetry.';
  } finally {
    loading.value = false;
  }
}

function shortDayLabel(isoDate: string): string {
  return isoDate.slice(5);
}

onMounted(() => {
  void loadCrewStreaks();
});
</script>

<template>
  <div class="grid grid-cols-1 lg:grid-cols-3 gap-[18px] flex-1">
    <ShellHudWindow
      class="lg:col-span-2"
      title="Crew Consistency Streaks"
      subtitle="Read-only 7-day individual compliance overview"
      icon="flame"
      tag-text="7-DAY WINDOW"
    >
      <div v-if="loading" class="text-[12px] text-cabin-muted py-4">
        Synchronizing crew compliance records...
      </div>

      <div
        v-else-if="errorMessage"
        class="rounded-hud-sm border border-cabin-crit bg-cabin-inset p-3 text-[12px] text-cabin-crit"
      >
        {{ errorMessage }}
      </div>

      <div v-else-if="streakData" class="grid grid-cols-1 md:grid-cols-2 gap-[14px]">
        <div
          v-for="member in streakData.crew"
          :key="member.id"
          class="rounded-hud-sm border border-cabin-line bg-cabin-inset p-[14px] flex flex-col gap-3"
        >
          <div class="flex items-start justify-between gap-2">
            <div>
              <div class="text-[11px] font-mono tracking-[0.12em] text-cabin-ice">
                {{ member.code }} · {{ member.role }}
              </div>
              <div class="text-[15px] font-medium text-cabin-text mt-0.5">
                {{ member.full_name }}
              </div>
            </div>

            <div class="text-right">
              <div class="text-[18px] font-mono font-semibold text-cabin-ok leading-none">
                {{ member.active_streak_days }}d
              </div>
              <div class="text-[10px] font-mono text-cabin-muted mt-1">
                BEST {{ member.best_streak_days }}d
              </div>
            </div>
          </div>

          <div class="grid grid-cols-7 gap-1.5 pt-1">
            <div
              v-for="day in member.last_7_days"
              :key="day.date_utc"
              class="flex flex-col items-center gap-1"
            >
              <div
                class="w-full h-6 rounded-[4px] border flex items-center justify-center text-[10px] font-mono"
                :class="
                  day.compliant
                    ? 'border-cabin-ok bg-cabin-ok/15 text-cabin-ok'
                    : 'border-cabin-line bg-cabin-card text-cabin-muted'
                "
                :title="`${day.date_utc}: ${day.logs_completed} logs`"
              >
                {{ day.compliant ? 'OK' : '--' }}
              </div>
              <span class="text-[9px] font-mono text-cabin-muted">
                {{ shortDayLabel(day.date_utc) }}
              </span>
            </div>
          </div>
        </div>
      </div>
    </ShellHudWindow>

    <ShellHudWindow
      title="Team Streak & EVA Shield"
      subtitle="Collective daily readiness and EVA eligibility"
      icon="shield"
      :tag-text="streakData?.eva_shield_ready ? 'SHIELD READY' : 'BUILDING'"
    >
      <div v-if="streakData" class="flex flex-col gap-4">
        <div class="rounded-hud-sm border border-cabin-line bg-cabin-inset p-4">
          <div class="text-[10px] font-mono uppercase tracking-[0.14em] text-cabin-muted">
            TEAM CONSECUTIVE STREAK
          </div>
          <div class="mt-2 flex items-baseline gap-2">
            <span class="text-[32px] font-mono font-semibold text-cabin-ok leading-none">
              {{ streakData.team_streak_days }}
            </span>
            <span class="text-[12px] font-mono text-cabin-ice">DAYS</span>
          </div>
          <p class="text-[11px] text-cabin-muted mt-2">
            Consecutive mission days with 100% crew compliance across assigned health checks.
          </p>
        </div>

        <div class="rounded-hud-sm border border-cabin-line bg-cabin-inset p-4">
          <div class="flex items-center justify-between text-[11px] font-mono">
            <span class="text-cabin-muted">7-DAY TEAM COMPLIANCE</span>
            <span class="text-cabin-ice font-semibold">
              {{ streakData.team_compliance_pct }}%
            </span>
          </div>
          <div class="mt-2 h-2 w-full rounded-full bg-cabin-card overflow-hidden border border-cabin-line">
            <div
              class="h-full bg-cabin-ok transition-all"
              :style="{ width: `${streakData.team_compliance_pct}%` }"
            />
          </div>
        </div>

        <div
          class="rounded-hud-sm border p-4"
          :class="
            streakData.eva_shield_ready
              ? 'border-cabin-ok bg-cabin-ok/10'
              : 'border-cabin-navy-edge bg-cabin-navy/30'
          "
        >
          <div class="flex items-center justify-between">
            <span class="text-[11px] font-mono tracking-[0.12em] text-cabin-text">
              EVA SHIELD STATUS
            </span>
            <span
              class="px-2 py-0.5 rounded text-[10px] font-mono border"
              :class="
                streakData.eva_shield_ready
                  ? 'border-cabin-ok text-cabin-ok'
                  : 'border-cabin-ice text-cabin-ice'
              "
            >
              {{ streakData.eva_shield_ready ? 'CLEARED' : 'PENDING 3D' }}
            </span>
          </div>
          <p class="text-[11px] text-cabin-muted mt-2">
            Requires at least 3 consecutive team compliant days prior to extravehicular readiness sign-off.
          </p>
        </div>
      </div>

      <div v-else class="text-[12px] text-cabin-muted">
        Awaiting compliance metrics.
      </div>
    </ShellHudWindow>
  </div>
</template>
