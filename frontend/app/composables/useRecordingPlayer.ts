// Plays a saved heart or lung recording and reports the playback position, so the waveform
// cursor can follow the sound. The audio route needs the session, so the file is fetched
// with it and played from memory; nothing is stored in the browser.
export function useRecordingPlayer() {
  const base = useRuntimeConfig().public.apiBase
  const { authHeaders } = useSession()

  const playing = ref<string | null>(null) // key of the recording being played
  const position = ref(0) // seconds
  const loading = ref<string | null>(null)
  const failed = ref<string | null>(null)
  let audio: HTMLAudioElement | null = null
  let objectUrl: string | null = null
  let loadedPath: string | null = null
  let ticker: ReturnType<typeof setInterval> | null = null

  function stop() {
    audio?.pause()
    if (ticker) clearInterval(ticker)
    ticker = null
    playing.value = null
    position.value = 0
  }

  async function toggle(key: string, path: string) {
    if (playing.value === key) {
      stop()
      return
    }
    stop()
    failed.value = null
    try {
      if (loadedPath !== path) {
        loading.value = key
        const blob = await $fetch<Blob>(`${base}/api/v1${path}`, { headers: authHeaders(), responseType: 'blob' })
        if (objectUrl) URL.revokeObjectURL(objectUrl)
        objectUrl = URL.createObjectURL(blob)
        loadedPath = path
        audio = new Audio(objectUrl)
        audio.addEventListener('ended', stop)
      }
      audio!.currentTime = 0
      await audio!.play()
      playing.value = key
      ticker = setInterval(() => {
        position.value = audio?.currentTime ?? 0
      }, 100)
    }
    catch {
      failed.value = key
      stop()
    }
    finally {
      loading.value = null
    }
  }

  onBeforeUnmount(() => {
    stop()
    if (objectUrl) URL.revokeObjectURL(objectUrl)
  })

  return { playing, position, loading, failed, toggle, stop }
}
