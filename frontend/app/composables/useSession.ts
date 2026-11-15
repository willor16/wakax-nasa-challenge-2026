export interface ActiveCrewMember {
  id: string
  code: string
  fullName: string
  shortName: string
  role: 'ASTRONAUT' | 'PILOT' | 'OPERATOR' | 'PHYSICIAN'
}

interface LoginResponse {
  access_token: string
  token_type: string
  crew: {
    id: string
    code: string
    full_name: string
    short_name: string
    role: 'ASTRONAUT' | 'PILOT' | 'OPERATOR' | 'PHYSICIAN'
  }
}

interface MissionStatusResponse {
  unread_alerts: number
  critical_alerts: number
  cabin_mode: 'nominal' | 'critical'
}

export function useSession() {
  const token = useState<string | null>('session_token', () => null)
  const isAuthenticated = useState<boolean>('session_authenticated', () => false)
  const activeCrew = useState<ActiveCrewMember | null>('session_crew', () => null)
  const cabinMode = useState<'nominal' | 'critical'>('cabin_mode', () => 'nominal')
  const unreadAlerts = useState<number>('unread_alerts', () => 0)

  function setCabinMode(mode: 'nominal' | 'critical') {
    cabinMode.value = mode
    if (import.meta.client) {
      document.documentElement.dataset.cabinMode = mode === 'critical' ? 'critical' : ''
    }
  }

  async function refreshMissionStatus() {
    try {
      const res = await $fetch<MissionStatusResponse>('/api/v1/mission')
      unreadAlerts.value = res.unread_alerts
      setCabinMode(res.cabin_mode)
    }
    catch {
      // Keep last known cabin state if API is momentarily unavailable
    }
  }

  async function signInWithPin(crewId: string, pin: string): Promise<ActiveCrewMember> {
    const res = await $fetch<LoginResponse>('/api/v1/auth/login', {
      method: 'POST',
      body: { crew_id: crewId, pin },
    })
    token.value = res.access_token
    activeCrew.value = {
      id: res.crew.id,
      code: res.crew.code,
      fullName: res.crew.full_name,
      shortName: res.crew.short_name,
      role: res.crew.role,
    }
    isAuthenticated.value = true
    await refreshMissionStatus()
    return activeCrew.value
  }

  function signOut() {
    token.value = null
    isAuthenticated.value = false
    activeCrew.value = null
  }

  function authHeaders(): Record<string, string> {
    return token.value ? { Authorization: `Bearer ${token.value}` } : {}
  }

  return {
    token,
    isAuthenticated,
    activeCrew,
    cabinMode,
    unreadAlerts,
    setCabinMode,
    refreshMissionStatus,
    signInWithPin,
    signOut,
    authHeaders,
  }
}
