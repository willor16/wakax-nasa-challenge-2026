<script setup lang="ts">
import type { EmergencyItem, GuideArticle, GuideSearchResponse, KitDrawer } from '~/utils/guide'
import {
  activeDrawer,
  displayText,
  isPoweredStatus,
  physicianSuffix,
  stepNumber,
} from '~/utils/guide'

const route = useRoute()

const query = ref('')
const category = ref<string | null>(null)
const categories = ref<string[]>([])
const results = ref<GuideArticle[]>([])
const article = ref<GuideArticle | null>(null)
const drawers = ref<KitDrawer[]>([])
const emergency = ref<EmergencyItem[] | null>(null)
const physicianName = ref<string | null>(null)
const searched = ref(false)
const loadFailed = ref(false)
const lightOn = ref(false)
let lightTimer: ReturnType<typeof setTimeout> | null = null

const drawerCode = computed(() => activeDrawer(article.value, drawers.value))
const openDrawer = computed(() => drawers.value.find(d => d.code === drawerCode.value) ?? null)
const otherMatches = computed(() =>
  query.value.trim() || category.value ? results.value.filter(r => r.id !== article.value?.id) : [],
)
const escalateTitle = computed(() => physicianSuffix(physicianName.value))

async function search() {
  emergency.value = null
  loadFailed.value = false
  try {
    const res = await $fetch<GuideSearchResponse>('/api/v1/wiki/search', {
      query: { q: query.value, ...(category.value ? { category: category.value } : {}) },
    })
    categories.value = res.categories
    results.value = res.results
    article.value = res.results[0] ?? null
    searched.value = true
  }
  catch {
    loadFailed.value = true
  }
}

function pickCategory(topic: string) {
  category.value = category.value === topic ? null : topic
  void search()
}

async function openEmergencyIndex() {
  loadFailed.value = false
  try {
    emergency.value = (await $fetch<{ items: EmergencyItem[] }>('/api/v1/wiki/emergency-index')).items
  }
  catch {
    loadFailed.value = true
  }
}

async function openArticle(id: string) {
  emergency.value = null
  try {
    article.value = await $fetch<GuideArticle>(`/api/v1/wiki/articles/${encodeURIComponent(id)}`)
    searched.value = true
  }
  catch {
    loadFailed.value = true
  }
}

function illuminate() {
  lightOn.value = true
  if (lightTimer) clearTimeout(lightTimer)
  lightTimer = setTimeout(() => {
    lightOn.value = false
  }, 10000)
}

onMounted(async () => {
  const [kit, crew] = await Promise.all([
    $fetch<{ drawers: KitDrawer[] }>('/api/v1/kit/drawers').catch(() => null),
    $fetch<{ full_name: string, role: string }[]>('/api/v1/crew/profiles').catch(() => []),
  ])
  drawers.value = kit?.drawers ?? []
  physicianName.value = crew.find(c => c.role === 'PHYSICIAN')?.full_name ?? null
  const requested = typeof route.query.article === 'string' ? route.query.article : null
  await search()
  if (requested) await openArticle(requested)
})

onUnmounted(() => {
  if (lightTimer) clearTimeout(lightTimer)
})
</script>

<template>
  <div class="flex flex-col gap-[18px] flex-1">
    <section
      class="relative rounded-[6px] bg-cabin-card/28 border p-4 flex flex-col gap-3"
      :style="{ borderColor: 'var(--window-frame-stroke)' }"
    >
      <form
        class="flex gap-3"
        role="search"
        @submit.prevent="search"
      >
        <label class="flex-1 h-11 rounded-[4px] border border-cabin-card bg-cabin-inset px-3 flex items-center gap-2.5">
          <Icon
            name="spacescan:reticle"
            class="w-4 h-4 text-cabin-muted"
          />
          <input
            v-model="query"
            type="search"
            maxlength="200"
            :placeholder="$t('guide.searchPlaceholder')"
            :aria-label="$t('guide.search')"
            class="flex-1 bg-transparent text-[13px] text-cabin-text placeholder:text-cabin-muted outline-none"
          >
        </label>
        <button
          type="submit"
          class="h-11 px-10 rounded-[4px] border border-cabin-text/50 bg-cabin-card/70 text-[12.5px] font-semibold text-cabin-text inline-flex items-center gap-2 hover:bg-cabin-card"
        >
          <Icon
            name="spacescan:reticle"
            class="w-4 h-4"
          />
          {{ $t('guide.search') }}
        </button>
        <button
          type="button"
          class="h-11 px-10 rounded-[4px] border border-cabin-crit bg-cabin-crit/25 text-[12.5px] font-semibold text-cabin-text inline-flex items-center gap-2 hover:bg-cabin-crit/40"
          @click="openEmergencyIndex"
        >
          <Icon
            name="spacescan:shield"
            class="w-4 h-4"
          />
          {{ $t('guide.emergency') }}
        </button>
      </form>
      <div class="flex flex-wrap gap-2">
        <button
          v-for="topic in categories"
          :key="topic"
          type="button"
          class="h-7 px-5 rounded-full border text-[10.5px] font-semibold"
          :class="category === topic ? 'bg-cabin-navy/55 border-cabin-text/70 text-cabin-text' : 'bg-cabin-navy/42 border-cabin-navy-edge/70 text-cabin-text hover:border-cabin-text/50'"
          :aria-pressed="category === topic"
          @click="pickCategory(topic)"
        >
          {{ displayText(topic) }}
        </button>
      </div>
      <div
        v-if="otherMatches.length && !emergency"
        class="flex flex-wrap items-center gap-2"
      >
        <span class="text-[9.8px] font-bold tracking-[0.06em] text-cabin-muted">{{ $t('guide.otherMatches') }}</span>
        <button
          v-for="match in otherMatches"
          :key="match.id"
          type="button"
          class="h-7 px-3 rounded-[4px] border border-cabin-card/60 bg-cabin-inset text-[10.5px] text-cabin-text hover:bg-cabin-card/30"
          @click="article = match"
        >
          {{ displayText(match.title_en) }}
        </button>
      </div>
    </section>

    <p
      v-if="loadFailed"
      class="rounded-[4px] border border-cabin-crit bg-cabin-inset px-4 py-3 text-[12px]"
    >
      {{ $t('guide.loadError') }}
    </p>

    <div class="grid grid-cols-1 lg:grid-cols-[1.75fr_1fr] gap-[18px] flex-1">
      <ShellHudWindow
        v-if="emergency"
        :title="$t('guide.emergencyTitle')"
        icon="shield"
        :tag-text="$t('guide.emergencyTag')"
        tag-tone="critical"
      >
        <ul class="flex flex-col gap-3">
          <li
            v-for="item in emergency"
            :key="item.id"
          >
            <button
              type="button"
              class="w-full text-left rounded-[4px] border border-cabin-crit/70 bg-cabin-crit/12 px-4 py-3 flex flex-col gap-1 hover:bg-cabin-crit/20"
              @click="openArticle(item.id)"
            >
              <span class="text-[10px] font-bold tracking-[0.05em] text-cabin-muted">
                {{ displayText(item.category_en).toUpperCase() }} · {{ item.drawer_code }}
              </span>
              <span class="text-[12.5px] font-bold text-cabin-text">{{ displayText(item.title_en) }}</span>
              <span class="text-[11.5px] text-cabin-text">{{ displayText(item.escalation_en) }}</span>
            </button>
          </li>
        </ul>
      </ShellHudWindow>

      <ShellHudWindow
        v-else
        :title="article ? $t('guide.protocol', { title: displayText(article.title_en) }) : $t('guide.protocol', { title: '' })"
        icon="wiki"
        :tag-text="$t('guide.quickGuide')"
      >
        <p
          v-if="!article"
          class="text-[12.5px] text-cabin-muted"
        >
          {{ searched ? $t('guide.noResults') : $t('guide.pick') }}
        </p>
        <div
          v-else
          class="flex flex-col gap-3"
        >
          <ol class="flex flex-col gap-3">
            <li
              v-for="(step, index) in article.steps"
              :key="index"
              class="rounded-[4px] border border-cabin-card/55 bg-cabin-inset px-4 py-3 flex items-start gap-4"
            >
              <span
                class="w-9 h-9 shrink-0 rounded-[4px] border font-mono text-[13px] font-bold inline-flex items-center justify-center"
                :class="index < article.steps.length - 1 ? 'border-cabin-ok bg-cabin-ok/12 text-cabin-text' : 'border-cabin-navy-edge bg-cabin-navy/55 text-cabin-text'"
              >
                {{ stepNumber(index) }}
              </span>
              <span class="flex flex-col gap-1">
                <span class="text-[12.5px] font-bold uppercase tracking-[0.02em] text-cabin-text">{{ displayText(step.title_en) }}</span>
                <span
                  v-if="step.detail_en"
                  class="text-[11.5px] text-cabin-muted"
                >{{ displayText(step.detail_en) }}</span>
              </span>
            </li>
          </ol>

          <div class="rounded-[4px] border border-cabin-crit bg-cabin-crit/15 px-4 py-3 flex flex-col gap-1">
            <span class="text-[11.5px] font-bold tracking-[0.03em] text-cabin-text inline-flex items-center gap-2">
              <Icon
                name="spacescan:shield"
                class="w-4 h-4 text-cabin-crit"
              />
              {{ $t('guide.escalate', { name: escalateTitle }) }}
            </span>
            <span class="text-[11.5px] text-cabin-text">{{ displayText(article.escalation_en) }}</span>
          </div>
          <p
            v-if="article.source_en"
            class="text-[10px] text-cabin-muted"
          >
            {{ $t('guide.source', { source: article.source_en }) }}
          </p>
        </div>
      </ShellHudWindow>

      <ShellHudWindow
        :title="$t('guide.kit')"
        icon="kit"
        :tag-text="drawerCode ?? ''"
      >
        <div class="flex flex-col gap-3 h-full">
          <div class="grid grid-cols-2 gap-3">
            <div
              v-for="drawer in drawers"
              :key="drawer.code"
              class="rounded-[4px] border px-4 py-3 flex flex-col gap-1 transition-shadow"
              :class="[
                drawer.code === drawerCode ? 'border-cabin-ok bg-cabin-ok/10' : 'border-cabin-card/60 bg-cabin-inset',
                drawer.code === drawerCode && lightOn ? 'ring-2 ring-cabin-ok animate-pulse' : '',
              ]"
            >
              <span
                class="font-mono text-[10px] font-bold tracking-[0.05em]"
                :class="drawer.code === drawerCode ? 'text-cabin-ok' : 'text-cabin-muted'"
              >
                {{ drawer.code === drawerCode ? $t('guide.active', { code: drawer.code }) : drawer.code }}
              </span>
              <span class="text-[12px] font-bold text-cabin-text">{{ drawer.name_en }}</span>
            </div>
          </div>

          <template v-if="openDrawer">
            <span class="text-[9.8px] font-bold tracking-[0.06em] text-cabin-muted">
              {{ $t('guide.contents', { code: openDrawer.code }) }}
            </span>
            <ul class="flex flex-col gap-2">
              <li
                v-for="item in openDrawer.items"
                :key="item.slot_code"
                class="rounded-[4px] border border-cabin-card/55 bg-cabin-inset px-4 py-2.5 flex flex-col"
              >
                <span class="text-[12px] font-bold text-cabin-text">{{ item.name_en }}</span>
                <span
                  class="font-mono text-[10px]"
                  :class="isPoweredStatus(item.status_en) ? 'text-cabin-ok' : 'text-cabin-muted'"
                >{{ item.slot_code }} · {{ item.status_en }}</span>
              </li>
            </ul>
          </template>

          <p
            v-if="lightOn && drawerCode"
            class="text-[11px] text-cabin-ok"
          >
            {{ $t('guide.lightOn', { code: drawerCode }) }}
          </p>
          <button
            v-if="drawerCode"
            type="button"
            class="mt-auto h-11 rounded-[4px] border border-cabin-text/60 bg-cabin-card/40 text-[12px] font-semibold text-cabin-text inline-flex items-center justify-center gap-2 hover:bg-cabin-card/70"
            @click="illuminate"
          >
            <Icon
              name="spacescan:flame"
              class="w-4 h-4"
            />
            {{ $t('guide.illuminate', { code: drawerCode.replace('DRAWER', 'Drawer') }) }}
          </button>
        </div>
      </ShellHudWindow>
    </div>
  </div>
</template>
