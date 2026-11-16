// Crew session: PIN sign-in, the signed-in crew member and the access token.
// The session lives in this browser tab only (sessionStorage) and ends on Sign Out.

export interface SessionCrew {
  id: string
  code: string
  full_name: string
  short_name: string
  role: 'ASTRONAUT' | 'PILOT' | 'OPERATOR' | 'PHYSICIAN'
  title_en: string
  /** Physiological sex, used to show the female or male normal range. */
  sex?: 'F' | 'M' | null
}

interface StoredSession {
  token: string
  crew: SessionCrew
}

const STORAGE_KEY = 'spacescan.session'
const PATIENT_KEY = 'spacescan.patient'

function readPatient(): string | null {
  if (!import.meta.client) return null
  try {
    return window.sessionStorage.getItem(PATIENT_KEY)
  }
  catch {
    return null
  }
}

function writePatient(id: string | null) {
  if (!import.meta.client) return
  try {
    if (id) window.sessionStorage.setItem(PATIENT_KEY, id)
    else window.sessionStorage.removeItem(PATIENT_KEY)
  }
  catch {
    // Storage unavailable: the choice lasts until reload.
  }
}

/** A crew member the physician can look at (from the patient list). */
export interface PatientSummary {
  id: string
  code: string
  full_name: string
  short_name: string
  role: SessionCrew['role']
  title_en: string | null
  sex: 'F' | 'M' | 'X' | null
  open_alerts: number
  open_critical: number
}

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
  const base = useRuntimeConfig().public.apiBase

  const crew = computed(() => session.value?.crew ?? null)
  const isAuthenticated = computed(() => session.value !== null)
  const isPhysician = computed(() => crew.value?.role === 'PHYSICIAN')
  const isOperator = computed(() => crew.value?.role === 'OPERATOR')

  // Whose health screens are shown. Everyone sees their own; the physician can switch to any
  // patient. Capture screens always record for the signed-in crew member.
  const chosenPatient = useState<string | null>('activePatient', () => readPatient())
  const patients = useState<PatientSummary[]>('patients', () => [])
  const activePatientId = computed(() =>
    (isPhysician.value && chosenPatient.value ? chosenPatient.value : crew.value?.id) ?? null)
  const activePatient = computed<PatientSummary | null>(() => {
    const listed = patients.value.find(p => p.id === activePatientId.value)
    if (listed) return listed
    const me = crew.value
    return me && me.id === activePatientId.value
      ? { id: me.id, code: me.code, full_name: me.full_name, short_name: me.short_name, role: me.role,
          title_en: me.title_en, sex: me.sex ?? null, open_alerts: 0, open_critical: 0 }
      : null
  })
  const viewingOther = computed(() => activePatientId.value !== crew.value?.id)
  function setActivePatient(id: string) {
    if (!isPhysician.value) return
    chosenPatient.value = id === crew.value?.id ? null : id
    writePatient(chosenPatient.value)
  }

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
    chosenPatient.value = null
    patients.value = []
    writePatient(null)
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

  return { crew, isAuthenticated, isPhysician, isOperator, authHeaders, login, logout, verify,
    activePatientId, activePatient, viewingOther, patients, setActivePatient }
}
