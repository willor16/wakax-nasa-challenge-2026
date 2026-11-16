export interface MatrixItem {
  id: number
  en: string
  block: string
  construct: string
  code: 'T' | 'D' | 'C' | 'F' | 'S'
}

export const MATRIX_ITEMS: MatrixItem[] = [
  { id: 1, en: 'Tense', block: 'Block 1: Individual Mood', construct: 'Tension / Anxiety', code: 'T' },
  { id: 2, en: 'Disengaged', block: 'Block 1: Individual Mood', construct: 'Dejection (Motivation)', code: 'D' },
  { id: 3, en: 'Angry', block: 'Block 1: Individual Mood', construct: 'Anger / Hostility', code: 'C' },
  { id: 4, en: 'Tired', block: 'Block 1: Individual Mood', construct: 'Fatigue / Inertia', code: 'F' },
  { id: 5, en: 'Anxious', block: 'Block 1: Individual Mood', construct: 'Tension / Anxiety', code: 'T' },
  { id: 6, en: 'Unenthusiastic', block: 'Block 1: Individual Mood', construct: 'Dejection (Motivation)', code: 'D' },
  { id: 7, en: 'Annoyed', block: 'Block 1: Individual Mood', construct: 'Anger / Hostility', code: 'C' },
  { id: 8, en: 'Exhausted', block: 'Block 1: Individual Mood', construct: 'Fatigue / Inertia', code: 'F' },
  { id: 9, en: 'Nervous', block: 'Block 1: Individual Mood', construct: 'Tension / Anxiety', code: 'T' },
  { id: 10, en: 'Sad', block: 'Block 1: Individual Mood', construct: 'Dejection', code: 'D' },
  { id: 11, en: 'Resentful', block: 'Block 1: Individual Mood', construct: 'Anger / Hostility', code: 'C' },
  { id: 12, en: 'Fatigued', block: 'Block 1: Individual Mood', construct: 'Fatigue / Inertia', code: 'F' },
  { id: 13, en: 'Restless', block: 'Block 1: Individual Mood', construct: 'Tension / Anxiety', code: 'T' },
  { id: 14, en: 'Discouraged', block: 'Block 1: Individual Mood', construct: 'Dejection', code: 'D' },
  { id: 15, en: 'Furious', block: 'Block 1: Individual Mood', construct: 'Anger / Hostility', code: 'C' },
  { id: 16, en: 'Worn out', block: 'Block 1: Individual Mood', construct: 'Fatigue / Inertia', code: 'F' },
  { id: 17, en: 'Isolated', block: 'Block 2: Social Dynamics', construct: 'Social Cohesion', code: 'S' },
  { id: 18, en: 'Lonely', block: 'Block 2: Social Dynamics', construct: 'Social Cohesion', code: 'S' },
  { id: 19, en: 'Left out', block: 'Block 2: Social Dynamics', construct: 'Team Cohesion', code: 'S' },
  { id: 20, en: 'Unsupported', block: 'Block 2: Social Dynamics', construct: 'Perceived Support', code: 'S' },
]

export const MATRIX_SCALE_OPTIONS = [
  { val: 0, label: 'Not at all', desc: 'Absence' },
  { val: 1, label: 'A little', desc: 'Slight' },
  { val: 2, label: 'Moderately', desc: 'Moderate' },
  { val: 3, label: 'Quite a bit', desc: 'Substantial' },
  { val: 4, label: 'Extremely', desc: 'Severe' },
] as const

export interface MatrixSubscaleSummary {
  code: 'T' | 'D' | 'C' | 'F' | 'S'
  label: string
  score: number
  apaMean: number
  apaLabel: string
  tone: 'ok' | 'watch' | 'critical'
}

export interface MatrixEvaluationReport {
  totalLoad: number
  meanLoad: number
  readinessStatus: 'FIT FOR FLIGHT' | 'MONITORING REQUIRED' | 'RESTRICTED DUTY'
  readinessBadge: string
  rangeDescriptor: string
  tone: 'ok' | 'watch' | 'critical'
  subscales: MatrixSubscaleSummary[]
  gadMean: number
  gadScaled40: number
  gadLabel: string
  phq9Eq: number
  phq9Category: string
  stage2Triggered: boolean
  directiveText: string
  heading: string
  body: string
}

function apaSeverity(meanVal: number): { label: string, tone: 'ok' | 'watch' | 'critical' } {
  if (meanVal < 0.5) return { label: 'None (APA 0)', tone: 'ok' }
  if (meanVal < 1.5) return { label: 'Mild (APA 1)', tone: 'ok' }
  if (meanVal < 2.5) return { label: 'Moderate (APA 2)', tone: 'watch' }
  if (meanVal < 3.5) return { label: 'Severe (APA 3)', tone: 'critical' }
  return { label: 'Extreme (APA 4)', tone: 'critical' }
}

function phq9Label(score: number): string {
  if (score >= 20) return 'Severe (20-27)'
  if (score >= 15) return 'Moderately Severe (15-19)'
  if (score >= 10) return 'Moderate (10-14)'
  if (score >= 5) return 'Mild (5-9)'
  return 'Minimal or Absent (0-4)'
}

export function evaluateBehavioralMatrix(answers: number[]): MatrixEvaluationReport {
  const safe = answers.map(v => Math.max(0, Math.min(4, Number(v) || 0)))
  const T = safe[0]! + safe[4]! + safe[8]! + safe[12]!
  const D = safe[1]! + safe[5]! + safe[9]! + safe[13]!
  const C = safe[2]! + safe[6]! + safe[10]! + safe[14]!
  const F = safe[3]! + safe[7]! + safe[11]! + safe[15]!
  const S = safe[16]! + safe[17]! + safe[18]! + safe[19]!
  const totalLoad = T + D + C + F + S
  const meanLoad = Number((totalLoad / 20).toFixed(2))

  let readinessStatus: MatrixEvaluationReport['readinessStatus'] = 'FIT FOR FLIGHT'
  let readinessBadge = 'Cleared for Operations'
  let rangeDescriptor = 'Optimal State (0-20 pts)'
  let tone: MatrixEvaluationReport['tone'] = 'ok'
  let heading = 'Optimal Resilience & Social Cohesion'
  let body = 'Emotional balance and crew integration indicators remain inside your optimal personal baseline.'
  let directiveText = 'Maintain nominal schedule. Psychosocial and neurobehavioral baseline optimal.'

  if (totalLoad > 40) {
    readinessStatus = 'RESTRICTED DUTY'
    readinessBadge = 'Workload Reduction Mandated'
    rangeDescriptor = 'Critical Alert (41-80 pts)'
    tone = 'critical'
    heading = 'Critical Strain / Social Isolation Alert'
    body = 'Indicators reflect acute psychological strain, heavy fatigue, or marked social distance. Ground support notified.'
    directiveText = 'Restrict critical operations (EVA, manual docking). Mandate rest window and crew physician debriefing.'
  }
  else if (totalLoad > 20) {
    readinessStatus = 'MONITORING REQUIRED'
    readinessBadge = 'Moderate Load / Observation'
    rangeDescriptor = 'Moderate Load (21-40 pts)'
    tone = 'watch'
    heading = 'Moderate Psychosocial Load Detected'
    body = 'Moderate elevation in stress, fatigue, or isolation. Schedule crew connection and rest before demanding shifts.'
    directiveText = 'Cleared for routine duties. Monitor daily trend and review subscales at or above 8 points.'
  }

  const alerts: string[] = []
  if (S >= 8) alerts.push(`Social Isolation Spike (S=${S}/16)`)
  if (F >= 8 && T < 8) alerts.push(`Physical Fatigue Spike (F=${F}/16)`)
  if (D >= 8) alerts.push(`Motivation Dejection Spike (D=${D}/16)`)
  if (C >= 8 && T >= 8) alerts.push(`Concurrent Tension & Hostility (C=${C}, T=${T})`)
  if (alerts.length) directiveText += ` [${alerts.join(' · ')}]`

  const buildSub = (code: 'T' | 'D' | 'C' | 'F' | 'S', label: string, sum: number): MatrixSubscaleSummary => {
    const m = Number((sum / 4).toFixed(2))
    const apa = apaSeverity(m)
    return { code, label, score: sum, apaMean: m, apaLabel: apa.label, tone: apa.tone }
  }

  const gadMean = Number((T / 4).toFixed(2))
  const gadScaled40 = Math.round(gadMean * 10)
  const gadApa = apaSeverity(gadMean)
  const depCompositeMean = (D * 0.65 + F * 0.35) / 4
  const phq9Eq = Math.min(27, Math.round((depCompositeMean / 4) * 27))
  const stage2Triggered = gadMean >= 1.5 || phq9Eq >= 10 || S >= 8

  return {
    totalLoad,
    meanLoad,
    readinessStatus,
    readinessBadge,
    rangeDescriptor,
    tone,
    subscales: [
      buildSub('T', 'Tension & Stress', T),
      buildSub('D', 'Dejection / Inertia', D),
      buildSub('C', 'Anger / Irritability', C),
      buildSub('F', 'Fatigue / Exhaustion', F),
      buildSub('S', 'Social Isolation', S),
    ],
    gadMean,
    gadScaled40,
    gadLabel: gadApa.label,
    phq9Eq,
    phq9Category: phq9Label(phq9Eq),
    stage2Triggered,
    directiveText,
    heading,
    body,
  }
}
