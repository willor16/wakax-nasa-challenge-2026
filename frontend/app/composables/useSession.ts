// Crew session: PIN sign-in, the signed-in crew member and the access token.
// The session lives in this browser tab only (sessionStorage) and ends on Sign Out.

export interface SessionCrew {
  id: string
  code: string
  full_name: string
  short_name: string
  role: 'ASTRONAUT' | 'PILOT' | 'OPERATOR' | 'PHYSICIAN'
  title_en: string
}

interface StoredSession {
  token: string
  crew: SessionCrew
}

const STORAGE_KEY = 'spacescan.session'

function readStored(): StoredSession | null {
  if (!import.meta.client) return null
  try {
    const raw = window.sessionStorage.getItem(STORAGE_KEY)
    return raw ? (JSON.parse(raw) as StoredSession) : null
  }
  catch {
    return null
  }
}

function writeStored(session: StoredSession | null) {
  if (!import.meta.client) return
  try {
    if (session) window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(session))
    else window.sessionStorage.removeItem(STORAGE_KEY)
  }
  catch {
    // Storage can be unavailable (private mode); the session then lasts until reload.
  }
}

export function useSession() {
  const session = useState<StoredSession | null>('session', () => readStored())
  const base = useRuntimeConfig().public.apiBase.replace(/\/+$/, '')

  const crew = computed(() => session.value?.crew ?? null)
  const isAuthenticated = computed(() => session.value !== null)
  const isPhysician = computed(() => crew.value?.role === 'PHYSICIAN')
  const isOperator = computed(() => crew.value?.role === 'OPERATOR')

  function authHeaders(): Record<string, string> {
    return session.value ? { Authorization: `Bearer ${session.value.token}` } : {}
  }

  async function login(crewId: string, pin: string) {
    const result = await $fetch<{ access_token: string, crew: SessionCrew }>(
      `${base}/api/v1/auth/login`,
      { method: 'POST', body: { crew_id: crewId, pin } },
    )
    session.value = { token: result.access_token, crew: result.crew }
    writeStored(session.value)
  }

  function logout() {
    session.value = null
    writeStored(null)
  }

  /** Checks a restored session with the server; a stale one is dropped. */
  async function verify(): Promise<boolean> {
    if (!session.value) return false
    try {
      await $fetch(`${base}/api/v1/auth/me`, { headers: authHeaders() })
      return true
    }
    catch {
      logout()
      return false
    }
  }

  return { crew, isAuthenticated, isPhysician, isOperator, authHeaders, login, logout, verify }
}
