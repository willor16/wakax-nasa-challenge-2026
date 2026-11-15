// One place for every call to the onboard server: adds the session, turns
// failures into plain sentences and signs out when the session has ended.

interface ApiOptions {
  method?: 'GET' | 'POST' | 'PATCH'
  body?: Record<string, unknown> | FormData
  query?: Record<string, string | number | boolean | undefined>
}

interface FetchFailure {
  status?: number
  statusCode?: number
  data?: { detail?: unknown }
}

/** Plain-language message for a failed request. */
export function apiErrorMessage(error: unknown, fallback = 'Something went wrong. Please try again.'): string {
  const failure = error as FetchFailure
  const detail = failure?.data?.detail
  if (typeof detail === 'string' && detail.trim()) return detail
  if (Array.isArray(detail) && detail.length > 0) {
    const first = detail[0] as { msg?: string, loc?: (string | number)[] }
    const field = first.loc?.at(-1)
    const text = first.msg?.replace(/^Value error, /, '') ?? ''
    return field && typeof field === 'string' ? `${field.replaceAll('_', ' ')}: ${text}` : text || fallback
  }
  const status = failure?.status ?? failure?.statusCode
  if (status === undefined) return 'The onboard system is not answering. Check the cabin unit.'
  return fallback
}

export function useApi() {
  const base = useRuntimeConfig().public.apiBase
  const { authHeaders, logout } = useSession()

  async function api<T>(path: string, options: ApiOptions = {}): Promise<T> {
    try {
      return await $fetch<T>(`${base}/api/v1${path}`, {
        method: options.method ?? 'GET',
        body: options.body,
        query: options.query,
        headers: authHeaders(),
      })
    }
    catch (error) {
      const status = (error as FetchFailure)?.status ?? (error as FetchFailure)?.statusCode
      if (status === 401 && path !== '/auth/login') {
        logout()
        await navigateTo('/login')
      }
      throw error
    }
  }

  return { api }
}

/**
 * Loads one resource for a page with loading / error / data states and an optional refresh
 * interval. Nothing is shown from a previous crew member: data is cleared on failure.
 */
export function useResource<T>(loader: () => Promise<T>, refreshMs = 0) {
  const data = shallowRef<T | null>(null)
  const loading = ref(true)
  const error = ref<string | null>(null)
  let timer: ReturnType<typeof setInterval> | null = null
  let alive = true

  async function refresh(silent = false) {
    if (!silent) loading.value = data.value === null
    try {
      const result = await loader()
      if (!alive) return
      data.value = result
      error.value = null
    }
    catch (failure) {
      if (!alive) return
      if (!silent || data.value === null) {
        data.value = null
        error.value = apiErrorMessage(failure, 'This information could not be loaded.')
      }
    }
    finally {
      if (alive) loading.value = false
    }
  }

  onMounted(() => {
    void refresh()
    if (refreshMs > 0) timer = setInterval(() => void refresh(true), refreshMs)
  })
  onBeforeUnmount(() => {
    alive = false
    if (timer) clearInterval(timer)
  })

  return { data, loading, error, refresh }
}
