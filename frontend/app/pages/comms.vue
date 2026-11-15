<script setup lang="ts">
interface CommsPacket {
  id: string;
  packet_type: string;
  direction: string;
  crew_id: string | null;
  status: string;
  created_at_utc: string;
  deliver_after_utc: string;
  delivered_at_utc: string | null;
  summary: string;
  title_en: string | null;
  guidance_en: string | null;
}

interface SolarWeatherReading {
  radiation_msv: number;
  solar_event_flag: number;
  co2_ppm: number;
  recorded_at_utc: string;
}

interface CommsSnapshot {
  mission_code: string;
  earth_latency_min: number;
  outbound_packets: CommsPacket[];
  inbound_directives: CommsPacket[];
  solar_weather: SolarWeatherReading[];
}

const { activeCrew, authHeaders } = useSession();

const loading = ref(true);
const submitting = ref(false);
const flushing = ref(false);
const errorMessage = ref('');
const statusBanner = ref('');
const snapshot = ref<CommsSnapshot | null>(null);

const packetType = ref<'DAILY_SUMMARY' | 'CLINICAL_REPORT'>('DAILY_SUMMARY');
const noteEn = ref('');

const directiveTitle = ref('');
const directiveGuidance = ref('');
const loggingDirective = ref(false);

async function loadComms() {
  loading.value = true;
  errorMessage.value = '';
  try {
    snapshot.value = await $fetch<CommsSnapshot>('/api/v1/comms');
  } catch {
    errorMessage.value = 'Unable to reach Mission Control communications queue.';
  } finally {
    loading.value = false;
  }
}

async function queueHealthPacket() {
  submitting.value = true;
  errorMessage.value = '';
  statusBanner.value = '';
  try {
    await $fetch('/api/v1/comms/packets', {
      method: 'POST',
      headers: authHeaders(),
      body: {
        crew_id: activeCrew.value?.id ?? null,
        packet_type: packetType.value,
        note_en: noteEn.value.trim() || null,
      },
    });
    noteEn.value = '';
    statusBanner.value = 'Health summary queued for delayed Earth downlink.';
    await loadComms();
  } catch {
    errorMessage.value = 'Failed to queue outbound transmission packet.';
  } finally {
    submitting.value = false;
  }
}

async function flushDuePackets() {
  flushing.value = true;
  errorMessage.value = '';
  statusBanner.value = '';
  try {
    const res = await $fetch<{ delivered: number; in_transit: number }>('/api/v1/comms/flush', {
      method: 'POST',
      headers: authHeaders(),
    });
    statusBanner.value = `Link sweep complete: ${res.delivered} delivered, ${res.in_transit} in transit.`;
    await loadComms();
  } catch {
    errorMessage.value = 'Unable to run transmission queue sweep.';
  } finally {
    flushing.value = false;
  }
}

async function submitInboundDirective() {
  if (!directiveTitle.value.trim() || !directiveGuidance.value.trim()) {
    return;
  }
  loggingDirective.value = true;
  errorMessage.value = '';
  statusBanner.value = '';
  try {
    await $fetch('/api/v1/comms/directives', {
      method: 'POST',
      headers: authHeaders(),
      body: {
        crew_id: activeCrew.value?.id ?? null,
        title_en: directiveTitle.value.trim(),
        guidance_en: directiveGuidance.value.trim(),
      },
    });
    directiveTitle.value = '';
    directiveGuidance.value = '';
    statusBanner.value = 'Flight Surgeon directive recorded on crew board.';
    await loadComms();
  } catch {
    errorMessage.value = 'Unable to record Flight Surgeon directive.';
  } finally {
    loggingDirective.value = false;
  }
}

function packetStatusClass(status: string): string {
  if (status === 'DELIVERED' || status === 'ACKNOWLEDGED') {
    return 'border-cabin-ok text-cabin-ok';
  }
  if (status === 'IN_TRANSIT') {
    return 'border-cabin-ice text-cabin-ice';
  }
  return 'border-cabin-line text-cabin-muted';
}

onMounted(() => {
  void loadComms();
});
</script>

<template>
  <div class="grid grid-cols-1 lg:grid-cols-2 gap-[18px] flex-1">
    <ShellHudWindow
      title="Earth Transmission Queue"
      subtitle="Delayed store-and-forward clinical packets"
      icon="earth"
      :tag-text="`+${snapshot?.earth_latency_min ?? 12} MIN ONE-WAY`"
    >
      <div class="flex flex-col gap-4">
        <div
          v-if="errorMessage"
          class="rounded-hud-sm border border-cabin-crit bg-cabin-inset px-3 py-2 text-[12px] text-cabin-crit"
        >
          {{ errorMessage }}
        </div>
        <div
          v-else-if="statusBanner"
          class="rounded-hud-sm border border-cabin-ok bg-cabin-inset px-3 py-2 text-[12px] text-cabin-ok"
        >
          {{ statusBanner }}
        </div>

        <form
          class="rounded-hud-sm border border-cabin-line bg-cabin-inset p-3.5 flex flex-col gap-3"
          @submit.prevent="queueHealthPacket"
        >
          <div class="flex flex-wrap items-center justify-between gap-2">
            <span class="text-[11px] font-mono tracking-[0.12em] text-cabin-ice">
              COMPOSE OUTBOUND SUMMARY
            </span>
            <select
              v-model="packetType"
              aria-label="Packet Type"
              class="rounded-hud-sm border border-cabin-line bg-cabin-card px-2.5 py-1 text-[11px] font-mono text-cabin-text"
            >
              <option value="DAILY_SUMMARY">DAILY_SUMMARY</option>
              <option value="CLINICAL_REPORT">CLINICAL_REPORT</option>
            </select>
          </div>

          <input
            v-model="noteEn"
            type="text"
            maxlength="240"
            placeholder="Optional crew clinical note for Flight Surgeon..."
            class="w-full rounded-hud-sm border border-cabin-line bg-cabin-card px-3 py-2 text-[12px] text-cabin-text placeholder:text-cabin-muted"
          >

          <div class="flex flex-wrap items-center gap-2">
            <button
              type="submit"
              :disabled="submitting"
              class="rounded-hud-sm border border-cabin-ice bg-cabin-navy px-3.5 py-1.5 text-[11px] font-mono tracking-[0.08em] text-cabin-text hover:border-cabin-text disabled:opacity-50"
            >
              {{ submitting ? 'QUEUING...' : 'SEND HEALTH SUMMARY' }}
            </button>
            <button
              type="button"
              :disabled="flushing"
              class="rounded-hud-sm border border-cabin-line bg-cabin-card px-3 py-1.5 text-[11px] font-mono tracking-[0.08em] text-cabin-muted hover:text-cabin-text disabled:opacity-50"
              @click="flushDuePackets"
            >
              {{ flushing ? 'CHECKING...' : 'PROCESS DUE PACKETS' }}
            </button>
          </div>
        </form>

        <div v-if="loading" class="text-[12px] text-cabin-muted">
          Loading transmission ledger...
        </div>

        <div v-else class="flex flex-col gap-2 max-h-[320px] overflow-y-auto pr-1">
          <div
            v-for="pkt in snapshot?.outbound_packets ?? []"
            :key="pkt.id"
            class="rounded-hud-sm border border-cabin-line bg-cabin-inset p-3 flex flex-col gap-1.5"
          >
            <div class="flex items-center justify-between gap-2">
              <span class="text-[11px] font-mono text-cabin-text">
                {{ pkt.packet_type }} · {{ pkt.crew_id ?? 'CREW-ALL' }}
              </span>
              <span
                class="px-2 py-0.5 rounded border text-[10px] font-mono"
                :class="packetStatusClass(pkt.status)"
              >
                {{ pkt.status }}
              </span>
            </div>
            <p class="text-[12px] text-cabin-ice">
              {{ pkt.summary }}
            </p>
            <div class="text-[10px] font-mono text-cabin-muted flex items-center justify-between">
              <span>QUEUED {{ pkt.created_at_utc.slice(11, 19) }} UTC</span>
              <span>DUE {{ pkt.deliver_after_utc.slice(11, 19) }} UTC</span>
            </div>
          </div>

          <div
            v-if="!snapshot?.outbound_packets.length"
            class="text-[12px] text-cabin-muted py-3"
          >
            No outbound clinical summaries queued.
          </div>
        </div>
      </div>
    </ShellHudWindow>

    <ShellHudWindow
      title="Flight Surgeon & Solar Weather"
      subtitle="Inbound ground directives and cabin radiation log"
      icon="radio"
      tag-text="DEEP SPACE LINK"
    >
      <div class="flex flex-col gap-4">
        <div class="rounded-hud-sm border border-cabin-line bg-cabin-inset p-3.5 flex flex-col gap-2">
          <div class="text-[11px] font-mono tracking-[0.12em] text-cabin-ice">
            RECENT RADIATION & CO2 TELEMETRY
          </div>
          <div class="grid grid-cols-2 sm:grid-cols-3 gap-2">
            <div
              v-for="row in snapshot?.solar_weather.slice(0, 3) ?? []"
              :key="row.recorded_at_utc"
              class="rounded-hud-sm border border-cabin-line bg-cabin-card p-2.5"
            >
              <div class="text-[10px] font-mono text-cabin-muted">
                {{ row.recorded_at_utc.slice(11, 16) }} UTC
              </div>
              <div class="text-[14px] font-mono font-semibold text-cabin-text mt-0.5">
                {{ row.radiation_msv.toFixed(2) }} mSv
              </div>
              <div class="text-[10px] font-mono text-cabin-ice">
                CO2 {{ Math.round(row.co2_ppm) }} ppm ·
                <span :class="row.solar_event_flag ? 'text-cabin-crit' : 'text-cabin-ok'">
                  {{ row.solar_event_flag ? 'SPE ALERT' : 'NOMINAL' }}
                </span>
              </div>
            </div>
          </div>
        </div>

        <form
          class="rounded-hud-sm border border-cabin-line bg-cabin-inset p-3.5 flex flex-col gap-2.5"
          @submit.prevent="submitInboundDirective"
        >
          <div class="text-[11px] font-mono tracking-[0.12em] text-cabin-ice">
            LOG FLIGHT SURGEON DIRECTIVE
          </div>
          <input
            v-model="directiveTitle"
            type="text"
            maxlength="120"
            placeholder="Directive title (e.g., Hydration protocol update)"
            class="w-full rounded-hud-sm border border-cabin-line bg-cabin-card px-3 py-1.5 text-[12px] text-cabin-text placeholder:text-cabin-muted"
          >
          <input
            v-model="directiveGuidance"
            type="text"
            maxlength="240"
            placeholder="Clinical guidance for the crew..."
            class="w-full rounded-hud-sm border border-cabin-line bg-cabin-card px-3 py-1.5 text-[12px] text-cabin-text placeholder:text-cabin-muted"
          >
          <div>
            <button
              type="submit"
              :disabled="loggingDirective"
              class="rounded-hud-sm border border-cabin-navy-edge bg-cabin-navy px-3 py-1.5 text-[11px] font-mono tracking-[0.08em] text-cabin-text hover:border-cabin-ice disabled:opacity-50"
            >
              {{ loggingDirective ? 'SAVING...' : 'RECORD DIRECTIVE' }}
            </button>
          </div>
        </form>

        <div class="flex flex-col gap-2 max-h-[210px] overflow-y-auto pr-1">
          <div
            v-for="dir in snapshot?.inbound_directives ?? []"
            :key="dir.id"
            class="rounded-hud-sm border border-cabin-line bg-cabin-inset p-3 flex flex-col gap-1"
          >
            <div class="flex items-center justify-between gap-2">
              <span class="text-[12px] font-medium text-cabin-text">
                {{ dir.title_en ?? dir.summary }}
              </span>
              <span class="text-[10px] font-mono text-cabin-ok">
                {{ dir.status }}
              </span>
            </div>
            <p class="text-[11px] text-cabin-ice">
              {{ dir.guidance_en ?? dir.summary }}
            </p>
          </div>

          <div
            v-if="!snapshot?.inbound_directives.length"
            class="text-[12px] text-cabin-muted py-2"
          >
            No ground directives logged yet.
          </div>
        </div>
      </div>
    </ShellHudWindow>
  </div>
</template>
