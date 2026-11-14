export interface ActiveCrewMember {
  id: string
  code: string
  fullName: string
  shortName: string
  role: 'ASTRONAUT' | 'PILOT' | 'OPERATOR' | 'PHYSICIAN'
}

export function useSession() {
  const isAuthenticated = useState<boolean>('session_authenticated', () => false)
  const activeCrew = useState<ActiveCrewMember | null>('session_crew', () => null)
  const cabinMode = useState<'nominal' | 'critical'>('cabin_mode', () => 'nominal')
  const unreadAlerts = useState<number>('unread_alerts', () => 1)

  function setCabinMode(mode: 'nominal' | 'critical') {
    cabinMode.value = mode
    if (import.meta.client) {
      document.documentElement.dataset.cabinMode = mode === 'critical' ? 'critical' : ''
    }
  }

  function signInMock(member?: Partial<ActiveCrewMember>) {
    activeCrew.value = {
      id: member?.id ?? 'ID-01',
      code: member?.code ?? 'ID·01',
      fullName: member?.fullName ?? 'Elena Vargas',
      shortName: member?.shortName ?? 'E. VARGAS',
      role: member?.role ?? 'PILOT',
    }
    isAuthenticated.value = true
  }

  function signOut() {
    isAuthenticated.value = false
    activeCrew.value = null
  }

  return {
    isAuthenticated,
    activeCrew,
    cabinMode,
    unreadAlerts,
    setCabinMode,
    signInMock,
    signOut,
  }
}
