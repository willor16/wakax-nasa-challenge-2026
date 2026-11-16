import { createDefaultSandraSession, type SandraSessionState } from '~/utils/sandraVisualBattery'

export function useSandraBattery() {
  const session = useState<SandraSessionState>('sandra-visual-session', createDefaultSandraSession)

  function resetBattery() {
    session.value = createDefaultSandraSession()
  }

  return { session, resetBattery }
}
