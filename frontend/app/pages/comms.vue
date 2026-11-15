<script setup lang="ts">
// 15 · Mission Control & Solar Weather: delayed messages, transmission log, radiation.
import { apiErrorMessage } from '~/composables/useApi'
import { formatTime } from '~/utils/format'

interface Message { id: number, sender_en: string, title_en: string, guidance_en: string
  received_at_utc: string, state: 'NEW' | 'CONFIRMED' | 'ARCHIVED' }
interface LogEntry { id: number, direction: string, title_en: string, state: string, at_utc: string }
interface Solar { kp_index: number | null, kp_label: string, forecast_en: string, state: string
  radiation_msv_day: number, radiation_status: string, radiation_mission_msv: number, radiation_yearly_limit_msv: number }
interface Comms { earth_latency_min: number, pending_packets: number, synchronized: boolean
  messages: Message[], transmission_log: LogEntry[], solar_weather: Solar | null }

const { api } = useApi()
const { data, loading, error, refresh } = useResource(() => api<Comms>('/comms'), 15_000)
const sending = ref(false)
const sendNote = ref<{ tone: 'ok' | 'critical', text: string } | null>(null)

usePageHeader(() => ({
  title: 'Mission Control & Solar Weather',
  status: data.value
    ? { text: `Link nominal · +${data.value.earth_latency_min}m`, tone: 'ok' }
    : null,
}))

async function sendSummary() {
  sending.value = true
  sendNote.value = null
  try {
    const packet = await api<{ deliver_after_utc: string }>('/comms/packets', { method: 'POST', body: { packet_type: 'DAILY_SUMMARY' } })
    sendNote.value = { tone: 'ok', text: `Queued. Arrives at Mission Control about ${formatTime(packet.deliver_after_utc)} UTC.` }
    await refresh(true)
  }
  catch (reason) {
    sendNote.value = { tone: 'critical', text: apiErrorMessage(reason) }
  }
  finally {
    sending.value = false
  }
}
async function confirm(message: Message) {
  try {
    await api(`/comms/messages/${message.id}/confirm`, { method: 'POST' })
    await refresh(true)
  }
  catch (reason) {
    sendNote.value = { tone: 'critical', text: apiErrorMessage(reason) }
  }
}
function when(message: Message): string {
  const age = Date.now() - new Date(message.received_at_utc).getTime()
  return age > 86_400_000 ? 'YESTERDAY' : `${formatTime(message.received_at_utc)} UTC`
}
const accent = (message: Message) => (message.state === 'ARCHIVED' ? 'bg-cabin-navy-edge' : 'bg-cabin-ok')
const solar = computed(() => data.value?.solar_weather ?? null)
const kpTone = computed(() => (solar.value?.state === 'ALERT' ? 'critical' : solar.value?.state === 'WATCH' ? 'watch' : 'ok'))
</script>

<template>
  <div class="page">
    <UiStateNote v-if="!data" :loading="loading" :error="error" @retry="refresh()" />
    <div v-else class="flex-1 min-h-0 flex gap-[18px]">
      <ShellHudWindow
class="w-[756px]" title="Flight Surgeon Messages · Houston" icon="mail"
                      :tag-text="`+${data.earth_latency_min} MIN ONE-WAY`" flush>
        <div class="flex-1 min-h-0 flex flex-col px-[23px] pt-[24px] pb-[20px]">
          <div class="flex-1 min-h-0 hud-scroll flex flex-col gap-[20px] pr-[2px]">
            <UiStateNote v-if="!data.messages.length" empty="No messages from Mission Control yet." />
            <div
v-for="message in data.messages" :key="message.id"
                 class="relative min-h-[182px] shrink-0 rounded-[5px] pl-[24px] pr-[20px] pt-[18px] pb-[18px] border-[1.2px]"
                 :class="message.state === 'NEW' ? 'border-cabin-text/70 bg-[var(--color-card-head)]' : 'border-cabin-line bg-cabin-tile'">
              <span class="absolute left-0 top-[18px] bottom-[18px] w-[3px] rounded-full" :class="accent(message)" />
              <div class="flex items-start justify-between gap-4">
                <p class="mono text-[10px] tracking-[0.04em] uppercase" :class="message.state === 'ARCHIVED' ? 'text-cabin-ice' : 'text-cabin-ok'">
                  {{ message.sender_en }} · {{ when(message) }}
                </p>
                <button v-if="message.state === 'NEW'" type="button" class="focus-ring h-[23px] px-[16px] rounded-full text-[9.5px] font-bold border-[1.2px] border-cabin-text/80 bg-cabin-card" @click="confirm(message)">CONFIRM READ</button>
                <UiStatusPill v-else class="min-w-[110px]">{{ message.state }}</UiStatusPill>
              </div>
              <p class="text-[16px] font-bold mt-[14px]">{{ message.title_en.replace(' - ', ' — ') }}</p>
              <p class="text-[12.5px] mt-[14px] leading-[2] text-cabin-ice">{{ message.guidance_en.replace(/CO2/g, 'CO₂') }}</p>
            </div>
          </div>
          <p v-if="sendNote" class="text-[11.5px] mt-[12px]" :class="sendNote.tone === 'ok' ? 'text-cabin-ok' : ''" role="status">{{ sendNote.text }}</p>
          <button type="button" class="hud-button relative mt-[14px] !h-[56px] shrink-0" :disabled="sending" @click="sendSummary">
            <Icon name="spacescan:mail" class="w-[17px] h-[17px] absolute left-[22px]" />
            {{ sending ? 'Queuing…' : 'Send Daily Crew Summary to Houston' }}
          </button>
        </div>
      </ShellHudWindow>

      <div class="flex-1 min-w-0 flex flex-col gap-[18px]">
        <ShellHudWindow
class="h-[392px] shrink-0" title="Solar Weather & Cabin Radiation" icon="earth" flush
                        :tag-text="solar ? (solar.state === 'QUIET' ? 'QUIET · SAFE' : solar.state) : undefined"
                        :tag-tone="kpTone === 'critical' ? 'critical' : 'reference'">
          <UiStateNote v-if="!solar" empty="No solar or radiation reading yet." />
          <div v-else class="flex-1 flex flex-col px-[30px] pt-[30px] pb-[22px]">
            <div class="grid grid-cols-2 gap-[28px] h-[198px] shrink-0">
              <div class="tile flex items-center justify-center">
                <UiArcGauge
:fraction="(solar.kp_index ?? 0) / 9" :tone="kpTone" label="Solar Activity"
                            :value="solar.kp_index === null ? '—' : `Kp ${solar.kp_index.toFixed(0)}`" :caption="solar.kp_label" :size="140" :value-size="24" />
              </div>
              <div class="tile flex items-center justify-center">
                <UiArcGauge
:fraction="Math.min(1, solar.radiation_msv_day / 1)" :tone="solar.radiation_status === 'NOMINAL' ? 'ok' : solar.radiation_status === 'CRITICAL' ? 'critical' : 'watch'"
                            label="Cabin Radiation" :value="solar.radiation_msv_day.toFixed(2)" caption="mSv / day" :size="140" :value-size="24" />
              </div>
            </div>
            <div class="tile mt-auto h-[70px] px-[20px] flex flex-col justify-center">
              <p class="text-[10px] font-bold tracking-[0.04em] uppercase text-cabin-ok">48-hour solar forecast</p>
              <p class="text-[12.5px] mt-[9px]">
                {{ solar.forecast_en }} · Mission dose {{ solar.radiation_mission_msv.toFixed(1) }} mSv
              </p>
            </div>
          </div>
        </ShellHudWindow>

        <ShellHudWindow
class="flex-1" title="Transmission Log" icon="rocket" flush
                        :tag-text="data.synchronized ? 'SYNCHRONIZED' : `${data.pending_packets} IN TRANSIT`">
          <div class="flex-1 min-h-0 hud-scroll flex flex-col gap-[14px] px-[23px] py-[22px]">
            <div v-for="entry in data.transmission_log.slice(0, 8)" :key="entry.id" class="tile h-[56px] shrink-0 px-[22px] flex items-center gap-[54px]">
              <span class="mono text-[12px] w-[78px] shrink-0">{{ formatTime(entry.at_utc) }} UTC</span>
              <span class="text-[13px] flex-1 truncate">{{ entry.title_en }}</span>
              <UiStatusPill class="min-w-[116px]" :tone="entry.state === 'QUEUED' || entry.state === 'IN TRANSIT' || entry.state === 'INCOMING' ? 'watch' : 'reference'">
                {{ entry.state }}
              </UiStatusPill>
            </div>
          </div>
        </ShellHudWindow>
      </div>
    </div>
  </div>
</template>
