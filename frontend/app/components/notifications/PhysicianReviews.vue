<script setup lang="ts">
import type { ReviewDecision, ReviewItem, ReviewListResponse } from '~/utils/reviews'
import { metricLine, sourceLabel, strengthLabel } from '~/utils/reviews'
import { timeAgo } from '~/utils/notifications'

const emit = defineEmits<{ count: [value: number] }>()

const { authHeaders } = useSession()
const { t } = useI18n()

const items = ref<ReviewItem[]>([])
const selectedId = ref<number | null>(null)
const notes = ref('')
const loading = ref(true)
const loadFailed = ref(false)
const working = ref(false)
const actionFailed = ref(false)
const scanning = ref(false)
const scanResult = ref<string | null>(null)
const now = ref(new Date())

const selected = computed(() => items.value.find(i => i.id === selectedId.value) ?? null)

async function load() {
  loading.value = true
  loadFailed.value = false
  try {
    const res = await $fetch<ReviewListResponse>('/api/v1/diagnosis', {
      query: { status: 'PENDING_REVIEW' },
      headers: authHeaders(),
    })
    items.value = res.items
    emit('count', res.pending)
    if (!selected.value) selectedId.value = res.items[0]?.id ?? null
    now.value = new Date()
  }
  catch {
    loadFailed.value = true
  }
  finally {
    loading.value = false
  }
}

async function decide(decision: ReviewDecision) {
  if (!selected.value) return
  working.value = true
  actionFailed.value = false
  try {
    await $fetch(`/api/v1/diagnosis/${selected.value.id}/review`, {
      method: 'POST',
      headers: authHeaders(),
      body: { decision, notes_en: notes.value.trim() || null },
    })
    notes.value = ''
    selectedId.value = null
    await load()
  }
  catch {
    actionFailed.value = true
  }
  finally {
    working.value = false
  }
}

async function scanCrew() {
  scanning.value = true
  scanResult.value = null
  try {
    const crew = await $fetch<{ id: string }[]>('/api/v1/crew/profiles')
    let found = 0
    for (const member of crew) {
      const res = await $fetch<{ diagnosis: ReviewItem | null, repeated: boolean }>(
        '/api/v1/diagnosis/anomalies',
        { method: 'POST', headers: authHeaders(), body: { crew_id: member.id } },
      )
      if (res.diagnosis && !res.repeated) found += 1
    }
    scanResult.value = found ? t('notifications.reviews.found', { count: found }) : t('notifications.reviews.none')
    await load()
  }
  catch {
    scanResult.value = t('notifications.reviews.scanError')
  }
  finally {
    scanning.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="grid grid-cols-1 lg:grid-cols-2 gap-[18px] flex-1">
    <ShellHudWindow
      :title="$t('notifications.reviews.title')"
      icon="stethoscope"
      :tag-text="$t('notifications.items', { count: items.length })"
    >
      <div class="flex flex-col gap-3">
        <div class="flex items-center justify-between gap-3">
          <span class="text-[11.5px] text-cabin-muted">{{ scanResult ?? $t('notifications.reviews.hint') }}</span>
          <button
            type="button"
            class="h-8 px-4 shrink-0 rounded-[4px] border border-cabin-card bg-cabin-card/60 text-[11px] font-semibold text-cabin-text hover:bg-cabin-card disabled:opacity-60"
            :disabled="scanning"
            @click="scanCrew"
          >
            {{ scanning ? $t('notifications.reviews.scanning') : $t('notifications.reviews.scan') }}
          </button>
        </div>
        <p
          v-if="loadFailed"
          class="text-[11.5px] text-cabin-crit"
        >
          {{ $t('notifications.loadError') }}
        </p>
        <p
          v-else-if="!loading && items.length === 0"
          class="text-[12.5px] text-cabin-muted"
        >
          {{ $t('notifications.reviews.empty') }}
        </p>
        <ul class="flex flex-col gap-3 lg:max-h-[calc(100vh-340px)] lg:overflow-y-auto lg:pr-1">
          <li
            v-for="item in items"
            :key="item.id"
          >
            <button
              type="button"
              class="w-full text-left rounded-[4px] border border-l-[3px] border-l-cabin-navy-edge px-4 py-3 flex flex-col gap-1.5"
              :class="selectedId === item.id ? 'menu-item-active' : 'border-cabin-card/55 bg-cabin-inset hover:bg-cabin-card/25'"
              @click="selectedId = item.id"
            >
              <span class="text-[9.8px] font-bold tracking-[0.06em] text-cabin-muted">
                {{ $t('notifications.reviews.label', { name: item.crew_name.toUpperCase(), strength: strengthLabel(item.anomaly_score), ago: timeAgo(item.created_at_utc, now) }) }}
              </span>
              <span class="text-[13px] font-bold text-cabin-text">{{ item.pattern_label_en }}</span>
              <span class="text-[11.5px] text-cabin-muted">{{ item.llm_summary_en }}</span>
            </button>
          </li>
        </ul>
      </div>
    </ShellHudWindow>

    <ShellHudWindow
      :title="$t('notifications.care')"
      icon="shield"
      :tag-text="$t('notifications.reviews.pending')"
      tag-tone="warn"
    >
      <p
        v-if="!selected"
        class="text-[12.5px] text-cabin-muted"
      >
        {{ $t('notifications.reviews.pick') }}
      </p>
      <div
        v-else
        class="flex flex-col gap-3 h-full"
      >
        <div class="rounded-[4px] border border-cabin-card bg-cabin-card/20 px-4 py-3 flex flex-col gap-1">
          <span class="text-[10px] font-bold tracking-[0.06em] text-cabin-ok">
            {{ sourceLabel(selected.guidance_source) }} · {{ selected.crew_name.toUpperCase() }}
          </span>
          <span class="text-[12.5px] text-cabin-text">{{ selected.llm_summary_en }}</span>
          <ul class="mt-1 flex flex-col gap-0.5">
            <li
              v-for="metric in selected.top_metrics"
              :key="metric.metric_key"
              class="font-mono text-[10.5px] text-cabin-muted"
            >
              {{ metricLine(metric) }}
            </li>
          </ul>
        </div>

        <ol class="flex flex-col gap-3">
          <li
            v-for="(step, index) in selected.preventive_steps"
            :key="index"
            class="rounded-[4px] border border-cabin-card/55 border-l-[3px] border-l-cabin-navy-edge bg-cabin-inset px-4 py-3 flex items-start gap-3"
          >
            <span class="w-7 h-7 shrink-0 rounded-[4px] border border-cabin-navy-edge bg-cabin-navy/55 text-[12px] font-bold inline-flex items-center justify-center">
              {{ index + 1 }}
            </span>
            <span class="flex flex-col gap-1">
              <span class="text-[13px] font-bold text-cabin-text">{{ step.title_en }}</span>
              <span class="text-[11.5px] text-cabin-muted">{{ step.detail_en }}</span>
            </span>
          </li>
        </ol>

        <label class="flex flex-col gap-1">
          <span class="text-[9.8px] font-bold tracking-[0.06em] text-cabin-muted">{{ $t('notifications.reviews.notes') }}</span>
          <textarea
            v-model="notes"
            rows="2"
            maxlength="500"
            :placeholder="$t('notifications.reviews.notesHint')"
            class="rounded-[4px] border border-cabin-card/60 bg-cabin-inset px-3 py-2 text-[12px] text-cabin-text placeholder:text-cabin-muted"
          />
        </label>
        <p
          v-if="actionFailed"
          class="text-[11.5px] text-cabin-crit"
        >
          {{ $t('notifications.reviews.error') }}
        </p>

        <div class="mt-auto rounded-[4px] border border-cabin-card/55 bg-cabin-inset p-3 grid grid-cols-3 gap-3">
          <button
            type="button"
            class="h-10 rounded-[4px] border border-cabin-card bg-cabin-card/70 text-[12px] font-semibold text-cabin-text hover:bg-cabin-card disabled:opacity-60"
            :disabled="working"
            @click="decide('APPROVED')"
          >
            {{ $t('notifications.reviews.approve') }}
          </button>
          <button
            type="button"
            class="h-10 rounded-[4px] border border-cabin-text/70 bg-cabin-card/40 text-[12px] font-semibold text-cabin-text hover:bg-cabin-card/70 disabled:opacity-60"
            :disabled="working"
            @click="decide('PROMOTED_TO_GUIDE')"
          >
            {{ $t('notifications.reviews.promote') }}
          </button>
          <button
            type="button"
            class="h-10 rounded-[4px] border border-cabin-crit bg-cabin-crit/20 text-[12px] font-semibold text-cabin-text hover:bg-cabin-crit/35 disabled:opacity-60"
            :disabled="working"
            @click="decide('REJECTED')"
          >
            {{ $t('notifications.reviews.reject') }}
          </button>
        </div>
      </div>
    </ShellHudWindow>
  </div>
</template>
