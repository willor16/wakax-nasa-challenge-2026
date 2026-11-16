export type EyeSide = 'OD' | 'OS' | 'OU'
export type BinaryEye = 'OD' | 'OS'
export type AmslerTool = 'metamorphopsia' | 'scotoma'
export type BatteryStatusClass = 'ok' | 'warn' | 'critica'

export const EXAM_MILESTONES = [
  'Pre-Flight Baseline',
  'Mission Day 30',
  'Mission Day 90',
  '30 Days Before Return',
  'Post-Flight Recovery',
] as const

export type ExamMilestone = (typeof EXAM_MILESTONES)[number]

export interface AcuityEyeResult {
  snellen: string
  decimal: string
  logMar: string
  avgResponseTime: string
  statusClass: BatteryStatusClass
  statusLabel: string
}

export type AcuityResultsMap = Record<EyeSide, AcuityEyeResult | null>

export interface AmslerCell {
  row: number
  col: number
  type: AmslerTool
}

export interface AmslerPerceptualAnswers {
  seeCenter: boolean | null
  seeCorners: boolean | null
  hasWavyLines: boolean | null
  hasBlankSpots: boolean | null
}

export interface AmslerEyeSummary {
  totalCells: number
  affectedPercent: number
  status: BatteryStatusClass
  hasMetamorphopsia: boolean
  hasScotoma: boolean
  hasPerceptualAlert: boolean
  centralInvolved: boolean
  metamorphopsiaCount: number
  scotomaCount: number
}

export interface AmslerCorrelation {
  hasMetamorphopsia: boolean
  affectedEye: string
  odSeverity: AmslerEyeSummary | null
  osSeverity: AmslerEyeSummary | null
}

export interface AmslerReportData {
  OD: AmslerEyeSummary | null
  OS: AmslerEyeSummary | null
  answers: Record<BinaryEye, AmslerPerceptualAnswers> | null
  gridData?: Record<BinaryEye, Record<string, AmslerCell>>
}

export interface SymptomAnswers {
  q1_1_near: { experienced: boolean | null, eye: string, severity: number }
  q1_2_intermediate: { experienced: boolean | null, eye: string, severity: number }
  q1_3_distance: { experienced: boolean | null, eye: string, severity: number }
  q1_4_glasses: { used: boolean | null, power: string }
  q2_1_fluctuations: { experienced: boolean | null, frequency: string, severity: number }
  q2_2_dimLight: { experienced: boolean | null, severity: number }
  q2_3_metamorphopsia: { experienced: boolean | null, eye: string }
  q2_4_depth: { experienced: boolean | null, operationalImpact: boolean }
  q3_1_diplopia: { experienced: boolean | null, type: string }
  q3_2_transientLoss: { experienced: boolean | null, duration: string, trigger: string }
  q3_3_headache: { experienced: boolean | null, intensity: number, location: string }
  q3_4_phosphenes: { experienced: boolean | null, frequency: string }
  q4_1_dryEye: { experienced: boolean | null, eye: string, dropsUsage: string }
}

export interface QuestionnaireData {
  answers: SymptomAnswers
  score: number
  level: string
  statusClass: BatteryStatusClass
  answeredCount: number
  timestamp?: string
}

export interface SandraSessionState {
  milestone: ExamMilestone
  pxPerMm: number
  acuity: AcuityResultsMap
  amslerGrid: Record<BinaryEye, Record<string, AmslerCell>>
  amslerAnswers: Record<BinaryEye, AmslerPerceptualAnswers>
  amslerSummary: AmslerReportData
  symptoms: SymptomAnswers
  questionnaire: QuestionnaireData | null
}

export function createDefaultSymptomAnswers(): SymptomAnswers {
  return {
    q1_1_near: { experienced: null, eye: 'Both', severity: 2 },
    q1_2_intermediate: { experienced: null, eye: 'Both', severity: 2 },
    q1_3_distance: { experienced: null, eye: 'Both', severity: 2 },
    q1_4_glasses: { used: null, power: '+1.00 D' },
    q2_1_fluctuations: { experienced: null, frequency: 'Occasional', severity: 2 },
    q2_2_dimLight: { experienced: null, severity: 2 },
    q2_3_metamorphopsia: { experienced: null, eye: 'Both' },
    q2_4_depth: { experienced: null, operationalImpact: false },
    q3_1_diplopia: { experienced: null, type: 'Intermittent' },
    q3_2_transientLoss: {
      experienced: null,
      duration: '< 30 seconds',
      trigger: 'Postural change / Head tilt',
    },
    q3_3_headache: {
      experienced: null,
      intensity: 4,
      location: 'Retro-ocular (Behind the globes)',
    },
    q3_4_phosphenes: { experienced: null, frequency: 'Rare (1-2 per week)' },
    q4_1_dryEye: { experienced: null, eye: 'Both', dropsUsage: '1 to 2 drops/day' },
  }
}

export function createDefaultSandraSession(): SandraSessionState {
  return {
    milestone: 'Mission Day 30',
    pxPerMm: 3.78,
    acuity: { OD: null, OS: null, OU: null },
    amslerGrid: { OD: {}, OS: {} },
    amslerAnswers: {
      OD: { seeCenter: null, seeCorners: null, hasWavyLines: null, hasBlankSpots: null },
      OS: { seeCenter: null, seeCorners: null, hasWavyLines: null, hasBlankSpots: null },
    },
    amslerSummary: { OD: null, OS: null, answers: null },
    symptoms: createDefaultSymptomAnswers(),
    questionnaire: null,
  }
}

export function computeAmslerEyeSummary(
  cellsMap: Record<string, AmslerCell>,
  exam: AmslerPerceptualAnswers,
): AmslerEyeSummary {
  const cells = Object.values(cellsMap)
  const totalCells = cells.length
  const affectedPercent = Math.round((totalCells / 400) * 100 * 10) / 10
  const scotomaCount = cells.filter(c => c.type === 'scotoma').length
  const metamorphopsiaCount = cells.filter(c => c.type === 'metamorphopsia').length
  const centralInvolved = exam.seeCenter === false
  const hasPerceptualAlert = centralInvolved
    || exam.seeCorners === false
    || exam.hasWavyLines === true
    || exam.hasBlankSpots === true
  const isCritical = centralInvolved || exam.seeCorners === false || scotomaCount > 2 || affectedPercent >= 3.0
  const isWarn = exam.hasWavyLines === true || exam.hasBlankSpots === true || totalCells > 0
  return {
    totalCells,
    affectedPercent,
    status: isCritical ? 'critica' : (isWarn ? 'warn' : 'ok'),
    hasMetamorphopsia: exam.hasWavyLines === true || metamorphopsiaCount > 0,
    hasScotoma: exam.hasBlankSpots === true || scotomaCount > 0,
    hasPerceptualAlert,
    centralInvolved,
    metamorphopsiaCount,
    scotomaCount,
  }
}

export function countAnsweredSymptoms(f: SymptomAnswers): number {
  let count = 0
  if (f.q1_1_near.experienced !== null) count++
  if (f.q1_2_intermediate.experienced !== null) count++
  if (f.q1_3_distance.experienced !== null) count++
  if (f.q1_4_glasses.used !== null) count++
  if (f.q2_1_fluctuations.experienced !== null) count++
  if (f.q2_2_dimLight.experienced !== null) count++
  if (f.q2_3_metamorphopsia.experienced !== null) count++
  if (f.q2_4_depth.experienced !== null) count++
  if (f.q3_1_diplopia.experienced !== null) count++
  if (f.q3_2_transientLoss.experienced !== null) count++
  if (f.q3_3_headache.experienced !== null) count++
  if (f.q3_4_phosphenes.experienced !== null) count++
  if (f.q4_1_dryEye.experienced !== null) count++
  return count
}

export function calculateSymptomRisk(f: SymptomAnswers) {
  let riskScore = 0
  if (f.q1_1_near.experienced) riskScore += f.q1_1_near.severity * 2
  if (f.q1_2_intermediate.experienced) riskScore += f.q1_2_intermediate.severity * 2
  if (f.q1_3_distance.experienced) riskScore += f.q1_3_distance.severity * 2
  if (f.q1_4_glasses.used) riskScore += 10
  if (f.q2_1_fluctuations.experienced) riskScore += f.q2_1_fluctuations.severity * 2
  if (f.q2_2_dimLight.experienced) riskScore += f.q2_2_dimLight.severity * 1.5
  if (f.q2_3_metamorphopsia.experienced) riskScore += 15
  if (f.q2_4_depth.experienced) riskScore += f.q2_4_depth.operationalImpact ? 12 : 5
  if (f.q3_1_diplopia.experienced) riskScore += f.q3_1_diplopia.type === 'Constant' ? 30 : 20
  if (f.q3_2_transientLoss.experienced) riskScore += 25
  if (f.q3_3_headache.experienced) riskScore += f.q3_3_headache.intensity * 2.5
  if (f.q3_4_phosphenes.experienced) riskScore += 8
  if (f.q4_1_dryEye.experienced) riskScore += 4

  let riskLevel = 'NOMINAL'
  let statusClass: BatteryStatusClass = 'ok'
  if (riskScore >= 40 || f.q3_1_diplopia.experienced || f.q3_2_transientLoss.experienced) {
    riskLevel = 'CRITICAL'
    statusClass = 'critica'
  }
  else if (riskScore >= 18 || f.q2_3_metamorphopsia.experienced || f.q1_4_glasses.used) {
    riskLevel = 'OBSERVATION'
    statusClass = 'warn'
  }
  return { riskScore: Math.round(riskScore), riskLevel, statusClass }
}

export function computeConsolidatedSANS(session: SandraSessionState) {
  let riskScore = 0
  const criticalFlags: string[] = []
  const warnFlags: string[] = []

  const odDec = session.acuity.OD ? Number.parseFloat(session.acuity.OD.decimal) : 1.0
  const osDec = session.acuity.OS ? Number.parseFloat(session.acuity.OS.decimal) : 1.0
  if (odDec < 0.5 || osDec < 0.5) {
    riskScore += 30
    criticalFlags.push('Visual acuity below 20/40 in at least one eye')
  }
  else if (odDec < 1.0 || osDec < 1.0) {
    riskScore += 12
    warnFlags.push('Mild central visual acuity reduction')
  }

  const odAmsler = computeAmslerEyeSummary(session.amslerGrid.OD, session.amslerAnswers.OD)
  const osAmsler = computeAmslerEyeSummary(session.amslerGrid.OS, session.amslerAnswers.OS)
  if (odAmsler.hasScotoma || osAmsler.hasScotoma) {
    riskScore += 35
    criticalFlags.push('Scotoma detected on Amsler Grid')
  }
  else if (odAmsler.hasMetamorphopsia || osAmsler.hasMetamorphopsia) {
    riskScore += 18
    warnFlags.push('Metamorphopsia detected on Amsler Grid')
  }

  const symptomRisk = calculateSymptomRisk(session.symptoms)
  if (symptomRisk.riskScore) riskScore += symptomRisk.riskScore * 0.5
  const qAns = session.symptoms
  if (qAns.q3_1_diplopia.experienced) criticalFlags.push('Active diplopia reported')
  if (qAns.q3_2_transientLoss.experienced) criticalFlags.push('Transient vision loss episodes (TVL)')

  riskScore = Math.min(100, Math.round(riskScore))

  if (criticalFlags.length > 0 || riskScore >= 45) {
    return {
      score: riskScore,
      triageLevel: 'ALERT',
      level: 'CRITICAL SANS ALERT',
      statusClass: 'critica' as BatteryStatusClass,
      directive: 'Requires telemetry consultation with the Flight Surgeon. Prioritize retinal OCT, ocular ultrasound ONSD, and intraocular pressure evaluation.',
      recommendations: [
        'Perform ocular ultrasound (ONSD) and retinal OCT within the next 6 hours.',
        'Evaluate Lower-Body Negative Pressure (LBNP) countermeasure session per protocol.',
        'Avoid Valsalva maneuvers and maximal isometric strain inside the cabin.',
        'Monitor blood pressure and ocular perfusion pressure every 12 hours.',
      ],
    }
  }
  if (warnFlags.length > 0 || riskScore >= 18) {
    return {
      score: riskScore,
      triageLevel: 'OBSERVATION',
      level: 'OBSERVATION / ADVISORY',
      statusClass: 'warn' as BatteryStatusClass,
      directive: 'Early neuro-ocular shift indicators detected. Consistent with cephalad fluid shift without major functional loss.',
      recommendations: [
        'Use prescribed Space Anticipation Glasses if near or console viewing causes eyestrain.',
        'Repeat Amsler Grid and Landolt C assessment in 48 hours.',
        'Maintain balanced hydration and daily resistance exercise countermeasures.',
        'Apply lubricating eye drops if cabin airflow causes surface irritation.',
      ],
    }
  }
  return {
    score: riskScore,
    triageLevel: 'NOMINAL',
    level: 'NOMINAL / CLEARED',
    statusClass: 'ok' as BatteryStatusClass,
    directive: 'Visual parameters remain optimal and stable in microgravity. Macular and central field function show no signs of edema or distortion.',
    recommendations: [
      'Continue standard scheduled visual evaluations per mission milestone.',
      'Maintain sleep hygiene and regular visual rest breaks at cockpit consoles.',
    ],
  }
}

export function activeSymptomFlags(f: SymptomAnswers): string[] {
  const flags: string[] = []
  if (f.q1_1_near.experienced) flags.push('near_shift')
  if (f.q1_2_intermediate.experienced) flags.push('intermediate_shift')
  if (f.q1_3_distance.experienced) flags.push('distance_shift')
  if (f.q1_4_glasses.used) flags.push('anticipation_glasses')
  if (f.q2_1_fluctuations.experienced) flags.push('acuity_fluctuation')
  if (f.q2_2_dimLight.experienced) flags.push('low_contrast')
  if (f.q2_3_metamorphopsia.experienced) flags.push('metamorphopsia')
  if (f.q2_4_depth.experienced) flags.push('stereopsis_deficit')
  if (f.q3_1_diplopia.experienced) flags.push('diplopia')
  if (f.q3_2_transientLoss.experienced) flags.push('transient_vision_loss')
  if (f.q3_3_headache.experienced) flags.push('retroocular_headache')
  if (f.q3_4_phosphenes.experienced) flags.push('phosphenes')
  if (f.q4_1_dryEye.experienced) flags.push('dry_eye')
  return flags
}

export function worstSnellenDenominator(acuity: AcuityResultsMap): number {
  const denoms = (['OD', 'OS', 'OU'] as const)
    .map(side => acuity[side]?.snellen)
    .filter((v): v is string => Boolean(v && v.includes('/')))
    .map(v => Number(v.split('/')[1]))
    .filter(n => Number.isFinite(n) && n > 0)
  return denoms.length ? Math.max(...denoms) : 20
}

export function hasAnySandraData(session: SandraSessionState): boolean {
  const hasAcuity = Boolean(session.acuity.OD || session.acuity.OS || session.acuity.OU)
  const hasAmsler = Object.keys(session.amslerGrid.OD).length > 0
    || Object.keys(session.amslerGrid.OS).length > 0
    || Object.values(session.amslerAnswers.OD).some(v => v !== null)
    || Object.values(session.amslerAnswers.OS).some(v => v !== null)
  const hasSymptoms = countAnsweredSymptoms(session.symptoms) > 0
  return hasAcuity || hasAmsler || hasSymptoms
}

export function buildSandraPayload(session: SandraSessionState) {
  const odAmsler = computeAmslerEyeSummary(session.amslerGrid.OD, session.amslerAnswers.OD)
  const osAmsler = computeAmslerEyeSummary(session.amslerGrid.OS, session.amslerAnswers.OS)
  const symRisk = calculateSymptomRisk(session.symptoms)
  const overall = computeConsolidatedSANS(session)
  const flags = activeSymptomFlags(session.symptoms)

  const summaryRows = [
    {
      label: 'Refractive Shift / Space Glasses',
      value: session.symptoms.q1_4_glasses.used ? `Yes (${session.symptoms.q1_4_glasses.power})` : 'Not required',
      critical: false,
    },
    {
      label: 'Subjective Metamorphopsia',
      value: session.symptoms.q2_3_metamorphopsia.experienced ? `Detected (${session.symptoms.q2_3_metamorphopsia.eye})` : 'Negative',
      critical: Boolean(session.symptoms.q2_3_metamorphopsia.experienced),
    },
    {
      label: 'Diplopia (Double Vision)',
      value: session.symptoms.q3_1_diplopia.experienced ? `PRESENT (${session.symptoms.q3_1_diplopia.type})` : 'Not reported',
      critical: Boolean(session.symptoms.q3_1_diplopia.experienced),
    },
    {
      label: 'Transient Vision Loss',
      value: session.symptoms.q3_2_transientLoss.experienced ? `PRESENT (${session.symptoms.q3_2_transientLoss.duration})` : 'Not reported',
      critical: Boolean(session.symptoms.q3_2_transientLoss.experienced),
    },
    {
      label: 'Retro-ocular Pressure / Headache',
      value: session.symptoms.q3_3_headache.experienced ? `Severity ${session.symptoms.q3_3_headache.intensity}/10` : 'Negative',
      critical: false,
    },
    {
      label: 'Cabin Ocular Surface',
      value: session.symptoms.q4_1_dryEye.experienced ? `Dryness (${session.symptoms.q4_1_dryEye.dropsUsage})` : 'Nominal',
      critical: false,
    },
  ]

  const compactCells = (eye: BinaryEye) => Object.values(session.amslerGrid[eye]).map(cell => ({
    r: cell.row,
    c: cell.col,
    t: cell.type,
  }))

  return {
    sandra_test: {
      milestone: session.milestone,
      acuity_bilateral: {
        OD: session.acuity.OD,
        OS: session.acuity.OS,
        OU: session.acuity.OU,
      },
      amsler: {
        OD: {
          affectedCount: odAmsler.totalCells,
          metamorphopsiaCount: odAmsler.metamorphopsiaCount,
          scotomaCount: odAmsler.scotomaCount,
          affectedPercent: odAmsler.affectedPercent,
          hasMetamorphopsia: odAmsler.hasMetamorphopsia,
          hasScotoma: odAmsler.hasScotoma,
          hasPerceptualAlert: odAmsler.hasPerceptualAlert,
          centralInvolved: odAmsler.centralInvolved,
          status: odAmsler.status,
          cells: compactCells('OD'),
          perceptual: session.amslerAnswers.OD,
        },
        OS: {
          affectedCount: osAmsler.totalCells,
          metamorphopsiaCount: osAmsler.metamorphopsiaCount,
          scotomaCount: osAmsler.scotomaCount,
          affectedPercent: osAmsler.affectedPercent,
          hasMetamorphopsia: osAmsler.hasMetamorphopsia,
          hasScotoma: osAmsler.hasScotoma,
          hasPerceptualAlert: osAmsler.hasPerceptualAlert,
          centralInvolved: osAmsler.centralInvolved,
          status: osAmsler.status,
          cells: compactCells('OS'),
          perceptual: session.amslerAnswers.OS,
        },
      },
      symptoms: {
        risk_score: symRisk.riskScore,
        risk_level: symRisk.riskLevel,
        triage_score: overall.score,
        triage_level: overall.triageLevel,
        active_flags: flags,
        answered_count: countAnsweredSymptoms(session.symptoms),
        total_questions: 13,
        summary_rows: summaryRows,
      },
    },
  }
}
