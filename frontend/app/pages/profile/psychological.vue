<script setup lang="ts">
import VChart from 'vue-echarts'
import type { PsychProfile } from '~/utils/mind'
import { buildMoodTrendOption, scalePercent, stateText } from '~/utils/mind'

const { authHeaders, isAuthenticated } = useSession()

const profile = ref<PsychProfile | null>(null)
const launchUtc = ref('2026-10-01T00:00:00Z')
const loading = ref(true)
const loadFailed = ref(false)

const state = computed(() => stateText(profile.value?.latest_state?.mood_state))
const logTime = computed(() => profile.value?.latest_state?.recorded_at_utc.slice(11, 16) ?? '--:--')
const chartOption = computed(() => (profile.value ? buildMoodTrendOption(profile.value, launchUtc.value) : null))
const lastTrend = computed(() => profile.value?.trend.at(-1) ?? null)
const reactionOk = computed(() => {
  const r = profile.value?.reaction
  return !!r && r.reaction_ms !== null && r.reaction_ms < r.reaction_target_ms
    && r.accuracy_pct >= r.accuracy_target_pct
})
const moodOk = computed(() => {
  const s = profile.value?.scales
  return !!s && s.stress_index.label === 'Low' && s.isolation.label === 'Low' && s.mood.label !== 'Low'
})
const ringStyle = computed(() => {
  const r = profile.value?.reaction
  const share = r?.reaction_ms ? Math.min(1, r.reaction_ms / 500) : 0
  return { background: `conic-gradient(var(--color-status-ok) ${share * 270}deg, transparent 0)` }
})

async function load() {
  loading.value = true
  loadFailed.value = false
  try {
    const [p, mission] = await Promise.all([
      $fetch<PsychProfile>('/api/v1/psych/profile', { headers: authHeaders() }),
      $fetch<{ mission: { launch_utc: string } | null }>('/api/v1/mission').catch(() => null),
    ])
    profile.value = p
    if (mission?.mission?.launch_utc) launchUtc.value = mission.mission.launch_utc
  }
  catch {
    loadFailed.value = true
  }
  finally {
    loading.value = false
  }
}

onMounted(() => {
  if (!isAuthenticated.value) {
    void navigateTo('/login')
    return
  }
  void load()
})
</script>

<template>
  <div class="flex flex-col gap-[18px] flex-1">
    <div class="flex gap-2">
      <NuxtLink
        to="/profile/personal"
        class="px-6 h-9 rounded-[4px] bg-cabin-inset border border-cabin-card/60 text-[11.5px] font-semibold flex items-center text-cabin-muted hover:text-cabin-text"
      >
        {{ $t('nav.profileTabs.personal') }}
      </NuxtLink>
      <NuxtLink
        to="/profile/psychological"
        class="px-6 h-9 rounded-[4px] menu-item-active text-[11.5px] font-bold flex items-center text-cabin-text"
      >
        {{ $t('nav.profileTabs.psychological') }}
      </NuxtLink>
      <NuxtLink
        to="/profile/physical"
        class="px-6 h-9 rounded-[4px] bg-cabin-inset border border-cabin-card/60 text-[11.5px] font-semibold flex items-center text-cabin-muted hover:text-cabin-text"
      >
        {{ $t('nav.profileTabs.physical') }}
      </NuxtLink>
    </div>

    <p
      v-if="loadFailed"
      class="rounded-[4px] border border-cabin-crit bg-cabin-inset px-4 py-3 text-[12px]"
    >
      {{ $t('mind.profile.loadError') }}
    </p>

    <div class="grid grid-cols-1 lg:grid-cols-[1fr_1.45fr] gap-[18px] flex-1">
      <ShellHudWindow
        :title="$t('mind.profile.results')"
        icon="profile"
        :tag-text="moodOk ? $t('mind.profile.optimal') : $t('mind.profile.attention')"
        :tag-tone="moodOk ? 'reference' : 'warn'"
      >
        <p
          v-if="!loading && !profile?.scales"
          class="text-[12.5px] text-cabin-muted"
        >
          {{ $t('mind.profile.noData') }}
        </p>
        <div
          v-else-if="profile?.scales"
          class="flex flex-col gap-6"
        >
          <div class="rounded-[4px] border border-cabin-card bg-cabin-card/20 border-l-[3px] border-l-cabin-ok px-4 py-3 flex items-start justify-between gap-3">
            <span class="flex flex-col gap-1">
              <span class="text-[10px] font-bold tracking-[0.06em] text-cabin-ok">
                {{ $t('mind.profile.latest', { state: state.title }) }}
              </span>
              <span class="text-[12px] text-cabin-text">{{ state.detail }}</span>
            </span>
            <span class="shrink-0 h-[22px] px-3 rounded-full border bg-cabin-navy/42 border-cabin-navy-edge/70 font-mono text-[9.8px] font-semibold inline-flex items-center">
              {{ $t('mind.profile.logTime', { time: logTime }) }}
            </span>
          </div>

          <div
            v-for="row in [
              { key: 'mood', value: profile.scales.mood.value, max: 5, label: profile.scales.mood.label, hint: $t('mind.profile.baseline', { low: profile.scales.mood.range[0], high: profile.scales.mood.range[1] }), pct: scalePercent(profile.scales.mood.value) },
              { key: 'stress', value: profile.scales.stress_index.value, max: 100, label: profile.scales.stress_index.label, hint: $t('mind.profile.target', { value: profile.scales.stress_index.target_below }), pct: profile.scales.stress_index.value },
              { key: 'isolation', value: profile.scales.isolation.value, max: 5, label: profile.scales.isolation.label, hint: $t('mind.profile.target', { value: profile.scales.isolation.target_below }), pct: scalePercent(profile.scales.isolation.value) },
              { key: 'motivation', value: profile.scales.motivation.value, max: 5, label: profile.scales.motivation.label, hint: $t('mind.profile.baseline', { low: profile.scales.motivation.range[0], high: profile.scales.motivation.range[1] }), pct: scalePercent(profile.scales.motivation.value) },
            ]"
            :key="row.key"
            class="flex flex-col gap-2"
          >
            <div class="flex items-end justify-between gap-3">
              <span class="flex flex-col">
                <span class="text-[12.5px] font-bold text-cabin-text">{{ $t(`mind.profile.${row.key}`) }}</span>
                <span class="text-[10px] text-cabin-muted">{{ row.hint }}</span>
              </span>
              <span class="flex items-center gap-3">
                <span class="text-[20px] font-bold text-cabin-text">{{ row.value }} <span class="text-[11px] text-cabin-muted">/ {{ row.max }}</span></span>
                <span class="h-[22px] px-3 rounded-full border bg-cabin-navy/42 border-cabin-navy-edge/70 text-[9.8px] font-semibold inline-flex items-center">
                  {{ row.label }}
                </span>
              </span>
            </div>
            <div class="relative h-[4px] rounded-full bg-cabin-navy/55">
              <span
                class="absolute -top-[3px] w-[10px] h-[10px] rounded-full bg-cabin-ok -translate-x-1/2"
                :style="{ left: `${row.pct}%` }"
              />
            </div>
          </div>
        </div>
      </ShellHudWindow>

      <div class="flex flex-col gap-[18px]">
        <ShellHudWindow
          :title="$t('mind.profile.trend')"
          icon="reticle"
          :tag-text="$t('mind.profile.stability', { value: profile?.stability_pct ?? 0 })"
        >
          <div class="relative h-[230px]">
            <span
              v-if="profile"
              class="absolute top-1 left-10 z-10 text-[9.8px] font-bold tracking-[0.05em] text-cabin-text"
            >
              {{ $t('mind.profile.zone', { low: profile.optimal_zone[0], high: profile.optimal_zone[1] }) }}
            </span>
            <span
              v-if="lastTrend"
              class="absolute top-1 right-4 z-10 flex gap-4 text-[9.8px] font-semibold"
            >
              <span class="inline-flex items-center gap-1.5"><i class="w-2 h-2 rounded-full bg-cabin-ok" />{{ $t('mind.profile.moodScore') }} ({{ lastTrend.mood }} / 5)</span>
              <span class="inline-flex items-center gap-1.5"><i class="w-2 h-2 rounded-full bg-cabin-card" />{{ $t('mind.profile.calmness') }} ({{ lastTrend.calmness }} / 5)</span>
            </span>
            <ClientOnly>
              <VChart
                v-if="chartOption && profile?.trend.length"
                :option="chartOption"
                theme="spacescan-hud"
                autoresize
                class="w-full h-full"
              />
            </ClientOnly>
          </div>
        </ShellHudWindow>

        <ShellHudWindow
          :title="$t('mind.profile.reaction')"
          icon="flame"
          :tag-text="reactionOk ? $t('mind.profile.optimal') : $t('mind.profile.attention')"
          :tag-tone="reactionOk ? 'reference' : 'warn'"
        >
          <p
            v-if="!loading && !profile?.reaction"
            class="text-[12.5px] text-cabin-muted"
          >
            {{ $t('mind.profile.noData') }}
          </p>
          <div
            v-else-if="profile?.reaction"
            class="grid grid-cols-4 gap-3"
          >
            <div class="rounded-[4px] border border-cabin-card/55 bg-cabin-inset flex items-center justify-center py-4">
              <div
                class="w-[104px] h-[104px] rounded-full p-[5px]"
                :style="ringStyle"
              >
                <div class="w-full h-full rounded-full bg-cabin-bg flex flex-col items-center justify-center">
                  <span class="text-[8.5px] font-bold text-cabin-muted">{{ $t('mind.profile.reactionTime') }}</span>
                  <span class="text-[22px] font-bold text-cabin-text">{{ profile.reaction.reaction_ms === null ? '--' : Math.round(profile.reaction.reaction_ms) }}</span>
                  <span class="text-[9px] text-cabin-muted">ms (&lt;{{ profile.reaction.reaction_target_ms }} ms)</span>
                </div>
              </div>
            </div>
            <div
              v-for="card in [
                { key: 'lapses', value: String(profile.reaction.lapses), hint: $t('mind.profile.lapsesHint') },
                { key: 'precision', value: `${profile.reaction.accuracy_pct}%`, hint: $t('mind.profile.precisionHint', { value: profile.reaction.accuracy_target_pct }) },
                { key: 'vigilance', value: `${Math.round(profile.reaction.attention_score)} / 100`, hint: profile.reaction.attention_score >= 90 ? $t('mind.profile.vigilanceHint') : $t('mind.profile.vigilanceLow') },
              ]"
              :key="card.key"
              class="rounded-[4px] border border-cabin-card/55 border-t-[3px] border-t-cabin-ok bg-cabin-inset px-4 py-3 flex flex-col justify-between"
            >
              <span class="text-[9.8px] font-bold tracking-[0.06em] text-cabin-muted">{{ $t(`mind.profile.${card.key}`) }}</span>
              <span class="text-[22px] font-bold text-cabin-text">{{ card.value }}</span>
              <span class="text-[10.5px] text-cabin-muted">{{ card.hint }}</span>
            </div>
          </div>
        </ShellHudWindow>
      </div>
    </div>
  </div>
</template>
