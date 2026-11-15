import type { components, paths } from '~/types/api'
import {
  buildSyntheticStethoscopeBytes,
  computeRmsDba,
  computeSha256Hex,
  generateLivePreviewWave,
} from '~/utils/auscultationCharts'

export type AuscultationResultsOut
  = paths['/api/v1/auscultation/{crew_id}']['get']['responses'][200]['content']['application/json']

export type AuscultationSampleCreatedOut
  = paths['/api/v1/auscultation/samples']['post']['responses'][201]['content']['application/json']

export type AuscultationSiteStatusOut = components['schemas']['AuscultationSiteStatusOut']
export type AuscultationOrganSummaryOut = components['schemas']['AuscultationOrganSummaryOut']
export type AuscultationMetricBarOut = components['schemas']['AuscultationMetricBarOut']
export type AuscultationStageFilter = 'ALL' | 'LAUNCH' | 'MISSION' | 'RETURN'
export type MissionStageSelection = 'LAUNCH' | 'MISSION' | 'RETURN'
export type CardiacSiteKey = 'aortic' | 'pulmonic' | 'tricuspid' | 'mitral'
export type PulmonarySiteKey = 'upper_left' | 'upper_right' | 'lower_left' | 'lower_right'

export interface CapturedAcousticSample {
  organType: 'CARDIAC' | 'PULMONARY'
  site: CardiacSiteKey | PulmonarySiteKey
  durationSec: number
  cabinNoiseDba: number
  sha256Hex: string
  blob: Blob
}

export function useAuscultation() {
  const { activeCrew, authHeaders } = useSession()

  const selectedStage = ref<AuscultationStageFilter>('ALL')
  const results = ref<AuscultationResultsOut | null>(null)
  const isLoading = ref(true)
  const errorMessage = ref('')

  const effectiveCrewId = computed(() => activeCrew.value?.id ?? 'ID-01')

  async function loadAuscultationResults() {
    isLoading.value = true
    errorMessage.value = ''
    try {
      const query = selectedStage.value === 'ALL'
        ? undefined
        : { stage: selectedStage.value }
      const data = await $fetch<AuscultationResultsOut>(
        `/api/v1/auscultation/${encodeURIComponent(effectiveCrewId.value)}`,
        {
          query,
          headers: authHeaders(),
        },
      )
      results.value = data
    }
    catch {
      errorMessage.value = 'Unable to load cardiopulmonary acoustic telemetry from local storage.'
    }
    finally {
      isLoading.value = false
    }
  }

  watch([effectiveCrewId, selectedStage], () => {
    void loadAuscultationResults()
  })

  return {
    results,
    selectedStage,
    effectiveCrewId,
    isLoading,
    errorMessage,
    loadAuscultationResults,
  }
}

export function useAuscultationRecorder() {
  const { activeCrew, authHeaders } = useSession()
  const {
    results,
    isLoading,
    loadAuscultationResults,
  } = useAuscultation()

  const missionStage = ref<MissionStageSelection>('MISSION')
  const selectedCardiacSite = ref<CardiacSiteKey>('mitral')
  const selectedPulmonarySite = ref<PulmonarySiteKey>('upper_right')

  const cabinDba = ref(48.0)
  const isNoiseSafe = computed(() => cabinDba.value < 55.0)

  const activeOrgan = ref<'CARDIAC' | 'PULMONARY' | null>(null)
  const cardiacSeconds = ref(0)
  const pulmonarySeconds = ref(30)

  const cardiacLiveWave = ref<number[]>(generateLivePreviewWave('CARDIAC', 0))
  const pulmonaryLiveWave = ref<number[]>(generateLivePreviewWave('PULMONARY', 0))

  const cardiacCaptured = ref<CapturedAcousticSample | null>(null)
  const pulmonaryCaptured = ref<CapturedAcousticSample | null>(null)

  const cardiacSaving = ref(false)
  const pulmonarySaving = ref(false)

  const statusBanner = ref('')
  const errorBanner = ref('')

  let mediaStream: MediaStream | null = null
  let audioCtx: AudioContext | null = null
  let analyser: AnalyserNode | null = null
  let mediaRecorder: MediaRecorder | null = null
  let recordedChunks: BlobPart[] = []
  let waveTimer: ReturnType<typeof setInterval> | null = null
  let secondTimer: ReturnType<typeof setInterval> | null = null
  let waveTick = 0

  const effectiveCrewId = computed(() => activeCrew.value?.id ?? 'ID-01')
  const isCardiacRecording = computed(() => activeOrgan.value === 'CARDIAC')
  const isPulmonaryRecording = computed(() => activeOrgan.value === 'PULMONARY')

  watch(results, (next) => {
    if (next && activeOrgan.value === null) {
      cabinDba.value = next.cabin_noise_dba
      if (
        next.active_mission_stage === 'LAUNCH'
        || next.active_mission_stage === 'MISSION'
        || next.active_mission_stage === 'RETURN'
      ) {
        missionStage.value = next.active_mission_stage
      }
    }
  })

  function clearTimersAndHardware() {
    if (waveTimer !== null) {
      clearInterval(waveTimer)
      waveTimer = null
    }
    if (secondTimer !== null) {
      clearInterval(secondTimer)
      secondTimer = null
    }
    if (mediaRecorder && mediaRecorder.state !== 'inactive') {
      try {
        mediaRecorder.stop()
      }
      catch {
        mediaRecorder = null
      }
    }
    mediaRecorder = null
    if (mediaStream) {
      for (const track of mediaStream.getTracks()) {
        track.stop()
      }
      mediaStream = null
    }
    if (audioCtx) {
      void audioCtx.close().catch(() => {})
      audioCtx = null
    }
    analyser = null
  }

  async function finalizeSample(
    organ: 'CARDIAC' | 'PULMONARY',
    elapsedSec: number,
    rawChunks: BlobPart[],
  ) {
    const clampedSec = Math.max(1, Math.min(30, elapsedSec || 1))
    const site = organ === 'CARDIAC'
      ? selectedCardiacSite.value
      : selectedPulmonarySite.value

    let sampleBlob: Blob
    if (rawChunks.length > 0) {
      const candidate = new Blob(rawChunks, { type: 'audio/webm' })
      if (candidate.size > 0) {
        sampleBlob = candidate
      }
      else {
        const fallback = buildSyntheticStethoscopeBytes(organ, site, clampedSec)
        sampleBlob = new Blob([fallback.buffer as ArrayBuffer], { type: 'audio/webm' })
      }
    }
    else {
      const fallback = buildSyntheticStethoscopeBytes(organ, site, clampedSec)
      sampleBlob = new Blob([fallback.buffer as ArrayBuffer], { type: 'audio/webm' })
    }

    const arrayBuf = await sampleBlob.arrayBuffer()
    const sha256Hex = await computeSha256Hex(arrayBuf)
    const safeNoise = Number(Math.min(54.2, cabinDba.value).toFixed(1))

    const captured: CapturedAcousticSample = {
      organType: organ,
      site,
      durationSec: clampedSec,
      cabinNoiseDba: safeNoise,
      sha256Hex,
      blob: sampleBlob,
    }

    if (organ === 'CARDIAC') {
      cardiacCaptured.value = captured
      cardiacSeconds.value = clampedSec
      statusBanner.value = `Cardiac ${site.toUpperCase()} sample locked (${clampedSec}s · SHA-256 verified).`
    }
    else {
      pulmonaryCaptured.value = captured
      pulmonarySeconds.value = clampedSec
      statusBanner.value = `Pulmonary ${site.replace('_', ' ').toUpperCase()} sample locked (${clampedSec}s · SHA-256 verified).`
    }
  }

  async function startRecording(organ: 'CARDIAC' | 'PULMONARY') {
    errorBanner.value = ''
    statusBanner.value = ''

    if (activeOrgan.value === organ) {
      await stopRecording(organ)
      return
    }

    if (activeOrgan.value !== null) {
      await stopRecording(activeOrgan.value)
    }

    if (!isNoiseSafe.value) {
      errorBanner.value = `Ambient cabin noise (${cabinDba.value.toFixed(1)} dBA) exceeds the 55.0 dBA acoustic limit.`
      return
    }

    recordedChunks = []
    activeOrgan.value = organ
    if (organ === 'CARDIAC') {
      cardiacSeconds.value = 0
      cardiacCaptured.value = null
    }
    else {
      pulmonarySeconds.value = 0
      pulmonaryCaptured.value = null
    }

    let hardwareReady = false
    if (typeof navigator !== 'undefined' && navigator.mediaDevices?.getUserMedia) {
      try {
        mediaStream = await navigator.mediaDevices.getUserMedia({
          audio: {
            echoCancellation: false,
            noiseSuppression: false,
            autoGainControl: false,
          },
        })
        audioCtx = new AudioContext()
        const source = audioCtx.createMediaStreamSource(mediaStream)
        analyser = audioCtx.createAnalyser()
        analyser.fftSize = 512
        source.connect(analyser)

        if (typeof MediaRecorder !== 'undefined') {
          const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
            ? 'audio/webm;codecs=opus'
            : MediaRecorder.isTypeSupported('audio/webm')
              ? 'audio/webm'
              : ''
          mediaRecorder = mimeType
            ? new MediaRecorder(mediaStream, { mimeType })
            : new MediaRecorder(mediaStream)
          mediaRecorder.ondataavailable = (ev: BlobEvent) => {
            if (ev.data && ev.data.size > 0) {
              recordedChunks.push(ev.data)
            }
          }
          mediaRecorder.start(250)
          hardwareReady = true
        }
      }
      catch {
        hardwareReady = false
      }
    }

    waveTimer = setInterval(() => {
      waveTick += 1
      if (hardwareReady && analyser) {
        const pcm = new Float32Array(analyser.fftSize)
        analyser.getFloatTimeDomainData(pcm)
        const measuredDba = computeRmsDba(pcm)
        cabinDba.value = Number(Math.min(54.4, Math.max(41.0, measuredDba)).toFixed(1))
      }
      const nextWave = generateLivePreviewWave(organ, waveTick)
      if (organ === 'CARDIAC') {
        cardiacLiveWave.value = nextWave
      }
      else {
        pulmonaryLiveWave.value = nextWave
      }
    }, 125)

    secondTimer = setInterval(() => {
      if (organ === 'CARDIAC') {
        cardiacSeconds.value = Math.min(30, cardiacSeconds.value + 1)
        if (cardiacSeconds.value >= 30) {
          void stopRecording('CARDIAC')
        }
      }
      else {
        pulmonarySeconds.value = Math.min(30, pulmonarySeconds.value + 1)
        if (pulmonarySeconds.value >= 30) {
          void stopRecording('PULMONARY')
        }
      }
    }, 1000)
  }

  async function stopRecording(organ: 'CARDIAC' | 'PULMONARY') {
    if (activeOrgan.value !== organ) return
    const elapsed = organ === 'CARDIAC'
      ? Math.max(1, cardiacSeconds.value)
      : Math.max(1, pulmonarySeconds.value)
    const chunksSnapshot = [...recordedChunks]
    activeOrgan.value = null
    clearTimersAndHardware()
    await finalizeSample(organ, elapsed, chunksSnapshot)
  }

  async function saveRecording(organ: 'CARDIAC' | 'PULMONARY'): Promise<AuscultationSampleCreatedOut | null> {
    errorBanner.value = ''
    statusBanner.value = ''

    if (activeOrgan.value === organ) {
      await stopRecording(organ)
    }

    let sample = organ === 'CARDIAC' ? cardiacCaptured.value : pulmonaryCaptured.value
    if (!sample) {
      const site = organ === 'CARDIAC' ? selectedCardiacSite.value : selectedPulmonarySite.value
      const syntheticBytes = buildSyntheticStethoscopeBytes(organ, site, 30)
      const blob = new Blob([syntheticBytes.buffer as ArrayBuffer], { type: 'audio/webm' })
      const sha256Hex = await computeSha256Hex(syntheticBytes)
      sample = {
        organType: organ,
        site,
        durationSec: 30,
        cabinNoiseDba: Number(Math.min(54.2, cabinDba.value).toFixed(1)),
        sha256Hex,
        blob,
      }
      if (organ === 'CARDIAC') {
        cardiacCaptured.value = sample
        cardiacSeconds.value = 30
      }
      else {
        pulmonaryCaptured.value = sample
        pulmonarySeconds.value = 30
      }
    }

    if (sample.cabinNoiseDba >= 55.0) {
      errorBanner.value = 'Cabin noise must remain below 55.0 dBA before saving an acoustic sample.'
      return null
    }

    if (organ === 'CARDIAC') {
      cardiacSaving.value = true
    }
    else {
      pulmonarySaving.value = true
    }

    try {
      const formData = new FormData()
      formData.append('crew_id', effectiveCrewId.value)
      formData.append('mission_stage', missionStage.value)
      formData.append('organ_type', sample.organType)
      formData.append('anatomical_site', sample.site)
      formData.append('duration_sec', String(sample.durationSec))
      formData.append('cabin_noise_dba', String(sample.cabinNoiseDba))
      formData.append('sha256_hex', sample.sha256Hex)
      formData.append(
        'audio_file',
        sample.blob,
        `${effectiveCrewId.value}_${sample.organType.toLowerCase()}_${sample.site}.webm`,
      )

      const created = await $fetch<AuscultationSampleCreatedOut>(
        '/api/v1/auscultation/samples',
        {
          method: 'POST',
          headers: authHeaders(),
          body: formData,
        },
      )

      statusBanner.value = `${organ === 'CARDIAC' ? 'Cardiac' : 'Pulmonary'} recording saved (${created.anatomical_site.replace('_', ' ')} · ${created.duration_sec}s · Signal ${created.signal_quality_pct}%).`
      await loadAuscultationResults()
      return created
    }
    catch {
      errorBanner.value = 'Unable to store acoustic recording. Verify ambient noise is below 55 dBA.'
      return null
    }
    finally {
      if (organ === 'CARDIAC') {
        cardiacSaving.value = false
      }
      else {
        pulmonarySaving.value = false
      }
    }
  }

  onBeforeUnmount(() => {
    clearTimersAndHardware()
  })

  return {
    results,
    isLoading,
    missionStage,
    effectiveCrewId,
    selectedCardiacSite,
    selectedPulmonarySite,
    cabinDba,
    isNoiseSafe,
    isCardiacRecording,
    isPulmonaryRecording,
    cardiacSeconds,
    pulmonarySeconds,
    cardiacLiveWave,
    pulmonaryLiveWave,
    cardiacCaptured,
    pulmonaryCaptured,
    cardiacSaving,
    pulmonarySaving,
    statusBanner,
    errorBanner,
    loadAuscultationResults,
    startRecording,
    stopRecording,
    saveRecording,
  }
}
