<script setup lang="ts">
import type { AdvisoryItem, NotificationItem, NotificationsResponse, NotificationView } from '~/utils/notifications'
import {
  captureRoute,
  defaultSelection,
  dueLabel,
  guideRoute,
  itemDetail,
  itemKey,
  itemLabel,
  itemTone,
} from '~/utils/notifications'

const { activeCrew, authHeaders, isAuthenticated, unreadAlerts } = useSession()
const { t } = useI18n()

const view = ref<NotificationView>('all')
const data = ref<NotificationsResponse | null>(null)
const selectedKey = ref<string | null>(null)
const loading = ref(true)
const loadFailed = ref(false)
const acknowledging = ref(false)
const ackFailed = ref(false)
const now = ref(new Date())
let clock: ReturnType<typeof setInterval> | null = null

type PageTab = NotificationView | 'reviews'

const tab = ref<PageTab>('all')
const reviewCount = ref(0)
const isPhysician = computed(() => activeCrew.value?.role === 'PHYSICIAN')
const tabs = computed<PageTab[]>(() =>
  isPhysician.value ? ['all', 'advisories', 'checks', 'reviews'] : ['all', 'advisories', 'checks'],
)

function tabCount(name: PageTab): number {
  return name === 'reviews' ? reviewCount.value : (data.value?.counts[name] ?? 0)
}

const items = computed(() => data.value?.items ?? [])
const selected = computed<NotificationItem | null>(() =>
  items.value.find(i => itemKey(i) === selectedKey.value) ?? null,
)
const selectedAdvisory = computed<AdvisoryItem | null>(() =>
  selected.value?.kind === 'ADVISORY' ? selected.value : null,
)

async function load() {
  loading.value = true
  loadFailed.value = false
  try {
    data.value = await $fetch<NotificationsResponse>('/api/v1/alerts', {
      query: { view: view.value },
      headers: authHeaders(),
    })
    unreadAlerts.value = data.value.counts.advisories
    if (!selected.value) {
      const first = defaultSelection(data.value.items)
      selectedKey.value = first ? itemKey(first) : null
    }
  }
  catch {
    loadFailed.value = true
  }
  finally {
    loading.value = false
  }
}

async function acknowledge() {
  const advisory = selectedAdvisory.value
  if (!advisory || advisory.acknowledged_at_utc) return
  acknowledging.value = true
  ackFailed.value = false
  try {
    await $fetch(`/api/v1/alerts/${advisory.id}/acknowledge`, {
      method: 'POST',
      headers: authHeaders(),
    })
    selectedKey.value = null
    await load()
  }
  catch {
    ackFailed.value = true
  }
  finally {
    acknowledging.value = false
  }
}

function selectTab(next: PageTab) {
  if (tab.value === next) return
  tab.value = next
  if (next === 'reviews') return
  view.value = next
  selectedKey.value = null
  void load()
}

onMounted(() => {
  if (!isAuthenticated.value) {
    void navigateTo('/login')
    return
  }
  void load()
  if (isPhysician.value) {
    $fetch<{ pending: number }>('/api/v1/diagnosis', {
      query: { status: 'PENDING_REVIEW' },
      headers: authHeaders(),
    }).then((res) => {
      reviewCount.value = res.pending
    }).catch(() => {})
  }
  clock = setInterval(() => {
    now.value = new Date()
  }, 30000)
})

onUnmounted(() => {
  if (clock) clearInterval(clock)
})
</script>

<template>
  <div class="flex flex-col gap-[18px] flex-1">
    <div class="h-9 flex items-center justify-between gap-3">
      <div class="flex items-center gap-2">
        <button
          v-for="name in tabs"
          :key="name"
          type="button"
          class="h-9 px-5 rounded-[4px] border text-[11.5px] font-semibold transition-colors"
          :class="
            tab === name
              ? 'menu-item-active text-cabin-text'
              : 'bg-cabin-inset border-cabin-card/65 text-cabin-muted hover:text-cabin-text'
          "
          @click="selectTab(name)"
        >
          {{ $t(`notifications.tabs.${name}`) }} ({{ tabCount(name) }})
        </button>
      </div>
      <span
        v-if="data"
        class="h-8 px-4 rounded-full border bg-cabin-navy/42 border-cabin-navy-edge/80 font-mono text-[10.5px] font-bold tracking-[0.05em] text-cabin-text inline-flex items-center gap-2"
      >
        <i
          v-if="data.quiet_hours.active"
          class="w-2 h-2 rounded-full bg-cabin-ok"
        />
        {{ $t('notifications.quietHours', { start: data.quiet_hours.start_utc, end: data.quiet_hours.end_utc }) }}
        <template v-if="data.quiet_hours.active">· {{ $t('notifications.quietActive') }}</template>
      </span>
    </div>

    <div
      v-if="loadFailed"
      class="rounded-[4px] border border-cabin-crit bg-cabin-inset px-4 py-3 text-[12px] text-cabin-text flex items-center justify-between gap-3"
    >
      <span>{{ $t('notifications.loadError') }}</span>
      <button
        type="button"
        class="h-8 px-4 rounded-[4px] border border-cabin-card bg-cabin-card/60 text-[11px] font-semibold"
        @click="load"
      >
        {{ $t('notifications.retry') }}
      </button>
    </div>

    <NotificationsPhysicianReviews
      v-if="tab === 'reviews'"
      @count="reviewCount = $event"
    />

    <div
      v-else
      class="grid grid-cols-1 lg:grid-cols-2 gap-[18px] flex-1"
    >
      <ShellHudWindow
        :title="$t('notifications.recent')"
        icon="bell"
        :tag-text="$t('notifications.items', { count: items.length })"
      >
        <p
          v-if="!loading && items.length === 0 && !loadFailed"
          class="text-[12.5px] text-cabin-muted"
        >
          {{ $t('notifications.empty') }}
        </p>
        <ul class="flex flex-col gap-3 lg:max-h-[calc(100vh-300px)] lg:overflow-y-auto lg:pr-1">
          <li
            v-for="item in items"
            :key="itemKey(item)"
          >
            <button
              type="button"
              class="w-full text-left rounded-[4px] border border-l-[3px] px-4 py-3 flex flex-col gap-1.5 transition-colors"
              :class="[
                {
                  'border-l-cabin-crit': itemTone(item) === 'critical',
                  'border-l-cabin-navy-edge': itemTone(item) === 'warning',
                  'border-l-cabin-navy': itemTone(item) === 'scheduled',
                  'border-l-cabin-card': itemTone(item) === 'info',
                },
                selectedKey === itemKey(item)
                  ? (itemTone(item) === 'critical' ? 'border-cabin-crit bg-cabin-crit/12' : 'menu-item-active')
                  : 'border-cabin-card/55 bg-cabin-inset hover:bg-cabin-card/25',
                item.kind === 'ADVISORY' && item.acknowledged_at_utc ? 'opacity-60' : '',
              ]"
              @click="selectedKey = itemKey(item)"
            >
              <span class="text-[9.8px] font-bold tracking-[0.06em] text-cabin-muted">
                {{ itemLabel(item, now, t) }}
              </span>
              <span class="text-[13px] font-bold text-cabin-text">{{ item.title_en }}</span>
              <span class="text-[11.5px] text-cabin-muted">{{ itemDetail(item) }}</span>
              <span
                class="mt-1 self-start h-[22px] px-6 rounded-full border text-[10px] font-semibold inline-flex items-center"
                :class="
                  selectedKey === itemKey(item)
                    ? (itemTone(item) === 'critical' ? 'bg-cabin-crit/45 border-cabin-crit' : 'bg-cabin-navy/55 border-cabin-navy-edge')
                    : 'bg-cabin-navy/42 border-cabin-navy-edge/70'
                "
              >
                {{ selectedKey === itemKey(item) ? $t('notifications.selected') : $t('notifications.view') }}
              </span>
            </button>
          </li>
        </ul>
      </ShellHudWindow>

      <ShellHudWindow
        :title="$t('notifications.care')"
        icon="shield"
        :tag-text="$t('notifications.plan')"
      >
        <p
          v-if="!selected"
          class="text-[12.5px] text-cabin-muted"
        >
          {{ $t('notifications.pick') }}
        </p>

        <div
          v-else
          class="flex flex-col gap-3 h-full"
        >
          <div class="rounded-[4px] border border-cabin-card bg-cabin-card/20 px-4 py-3 flex flex-col gap-1">
            <span class="text-[10px] font-bold tracking-[0.06em] text-cabin-ok">
              {{ $t('notifications.summary', { name: (activeCrew?.fullName ?? '').toUpperCase() }) }}
            </span>
            <span class="text-[12.5px] text-cabin-text">{{ selected.title_en }}</span>
            <span class="text-[11.5px] text-cabin-muted">
              <template v-if="selected.kind === 'ADVISORY'">{{ selected.message_en }}</template>
              <template v-else>
                {{ selected.detail_en }}
                {{ $t('notifications.checkSummary', { due: dueLabel(selected.due_at_utc, now, t) }) }}
              </template>
            </span>
          </div>

          <ol
            v-if="selectedAdvisory"
            class="flex flex-col gap-3"
          >
            <li
              v-for="(step, index) in selectedAdvisory.care_steps"
              :key="index"
              class="rounded-[4px] border border-cabin-card/55 border-l-[3px] border-l-cabin-navy-edge bg-cabin-inset px-4 py-3 flex items-start gap-3"
            >
              <span class="w-7 h-7 shrink-0 rounded-[4px] border border-cabin-navy-edge bg-cabin-navy/55 text-[12px] font-bold inline-flex items-center justify-center">
                {{ index + 1 }}
              </span>
              <span class="flex flex-col gap-1">
                <span class="text-[9.8px] font-bold tracking-[0.06em] text-cabin-muted">
                  {{ $t('notifications.step', { n: index + 1 }) }}
                </span>
                <span class="text-[13px] font-bold text-cabin-text">{{ step.title_en }}</span>
                <span
                  v-if="step.detail_en"
                  class="text-[11.5px] text-cabin-muted"
                >{{ step.detail_en }}</span>
              </span>
            </li>
          </ol>

          <p
            v-if="ackFailed"
            class="text-[11.5px] text-cabin-crit"
          >
            {{ $t('notifications.ackError') }}
          </p>

          <div class="mt-auto rounded-[4px] border border-cabin-card/55 bg-cabin-inset p-3 grid grid-cols-2 gap-3">
            <button
              v-if="selectedAdvisory"
              type="button"
              class="h-10 rounded-[4px] border border-cabin-card bg-cabin-card/70 text-[12px] font-semibold text-cabin-text inline-flex items-center justify-center gap-2 hover:bg-cabin-card disabled:opacity-60"
              :disabled="acknowledging || !!selectedAdvisory.acknowledged_at_utc"
              @click="acknowledge"
            >
              <Icon
                name="spacescan:shield"
                class="w-4 h-4"
              />
              {{ selectedAdvisory.acknowledged_at_utc ? $t('notifications.acknowledged') : $t('notifications.acknowledge') }}
            </button>
            <NuxtLink
              v-else-if="selected.kind === 'SCHEDULED'"
              :to="captureRoute(selected.check_type)"
              class="h-10 rounded-[4px] border border-cabin-card bg-cabin-card/70 text-[12px] font-semibold text-cabin-text inline-flex items-center justify-center gap-2 hover:bg-cabin-card"
            >
              <Icon
                name="spacescan:capture"
                class="w-4 h-4"
              />
              {{ $t('notifications.openCapture') }}
            </NuxtLink>
            <NuxtLink
              :to="guideRoute(selectedAdvisory?.guide_article_id ?? null)"
              class="h-10 rounded-[4px] border border-cabin-text/70 bg-cabin-card/40 text-[12px] font-semibold text-cabin-text inline-flex items-center justify-center gap-2 hover:bg-cabin-card/70"
            >
              <Icon
                name="spacescan:wiki"
                class="w-4 h-4"
              />
              {{ $t('notifications.openGuide') }}
            </NuxtLink>
          </div>
        </div>
      </ShellHudWindow>
    </div>
  </div>
</template>
