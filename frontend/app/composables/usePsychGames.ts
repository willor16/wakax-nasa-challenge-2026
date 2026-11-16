import type { AstroCowSummary } from '~/utils/astroCowTelemetry'
import type { NeuroFitReport, SquadId } from '~/utils/neuroFitEngine'

export interface PsychGamesState {
  astrocowLast: AstroCowSummary | null
  astrocowHighScore: number
  neurofitLast: NeuroFitReport | null
  neurofitCopilot: SquadId
  neurofitCabMetrics: Record<string, { code: string, label: string, score: number }>
  neurofitLevels: { sequence: number, bee: number, explorer: number, scan: number }
  matrixAnswers: (number | null)[]
  matrixCurrentIdx: number
  matrixCompleted: boolean
}

function defaultState(): PsychGamesState {
  return {
    astrocowLast: null,
    astrocowHighScore: 0,
    neurofitLast: null,
    neurofitCopilot: 'tamalito',
    neurofitCabMetrics: {
      memory: { code: 'CAB-ME', label: 'Working Memory', score: 425 },
      attention: { code: 'CAB-AT', label: 'Attention & Inhibition', score: 440 },
      spatial: { code: 'CAB-RS', label: 'Spatial Reasoning', score: 415 },
      reaction: { code: 'CAB-PC', label: 'Visual Perception', score: 435 },
    },
    neurofitLevels: { sequence: 1, bee: 1, explorer: 1, scan: 1 },
    matrixAnswers: Array.from({ length: 20 }, () => null),
    matrixCurrentIdx: 0,
    matrixCompleted: false,
  }
}

export function usePsychGames() {
  const state = useState<PsychGamesState>('psych-games-session', defaultState)

  function resetMatrix() {
    state.value.matrixAnswers = Array.from({ length: 20 }, () => null)
    state.value.matrixCurrentIdx = 0
    state.value.matrixCompleted = false
  }

  function resetNeurofit() {
    const fresh = defaultState()
    state.value.neurofitLast = null
    state.value.neurofitCabMetrics = fresh.neurofitCabMetrics
    state.value.neurofitLevels = fresh.neurofitLevels
  }

  return {
    state,
    resetMatrix,
    resetNeurofit,
  }
}
