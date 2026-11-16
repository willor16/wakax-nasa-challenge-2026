import tamalitoUrl from '../assets/games/squad/tamalito.svg'
import chipilinUrl from '../assets/games/squad/chipilin.svg'
import wakaxUrl from '../assets/games/squad/wakax.svg'
import kuokiUrl from '../assets/games/squad/kuoki.svg'
import misiUrl from '../assets/games/squad/misi.svg'
import tayuyoUrl from '../assets/games/squad/tayuyo.svg'
import cakeUrl from '../assets/games/squad/cake.svg'
import asteroidGrazeUrl from '../assets/games/squad/asteroid-graze.svg'
import asteroidImpactUrl from '../assets/games/squad/asteroid-impact.svg'

export type SquadId = 'tamalito' | 'chipilin' | 'wakax' | 'kuoki' | 'misi' | 'tayuyo'
export type StageKey = 'sequence' | 'bee' | 'explorer' | 'scan'

export interface SquadMember {
  id: SquadId
  name: string
  role: string
  quote: string
  spriteUrl: string
  endingOnly?: boolean
}

export const SQUAD_SPRITES: Record<SquadId, SquadMember> = {
  tamalito: {
    id: 'tamalito',
    name: 'Tamalito',
    role: 'Memory Specialist',
    quote: 'Memorize the rhythm and lights of our squad.',
    spriteUrl: tamalitoUrl,
  },
  chipilin: {
    id: 'chipilin',
    name: 'Chipilin',
    role: 'Attention & Reflex Lead',
    quote: 'Sharp eyes! Do not fall for radar decoy signals.',
    spriteUrl: chipilinUrl,
  },
  wakax: {
    id: 'wakax',
    name: 'Wakax',
    role: 'Spatial Reasoning Pilot',
    quote: 'Coordinates locked! Let us plot the cleanest route to the beacon.',
    spriteUrl: wakaxUrl,
  },
  kuoki: {
    id: 'kuoki',
    name: 'Kuoki',
    role: 'Rapid Recon Scout',
    quote: 'Star radar online! Let us spot every target at warp speed.',
    spriteUrl: kuokiUrl,
  },
  misi: {
    id: 'misi',
    name: 'Misi',
    role: 'Visual Perception Analyst',
    quote: 'Feline vision engaged! No hidden pattern will escape us.',
    spriteUrl: misiUrl,
  },
  tayuyo: {
    id: 'tayuyo',
    name: 'Tayuyo',
    role: 'Orbital Specialist',
    quote: 'Cosmic focus! Reach optimal accuracy to celebrate with the squad.',
    spriteUrl: tayuyoUrl,
    endingOnly: true,
  },
}

export const ACTIVE_SQUAD = Object.values(SQUAD_SPRITES).filter(m => !m.endingOnly)

export const ENDING_SPRITES = {
  cakeUrl,
  asteroidGrazeUrl,
  asteroidImpactUrl,
}

export interface CampaignStageMeta {
  key: StageKey
  title: string
  shortTitle: string
  lead: SquadId
  cabCode: string
  cabName: string
  catName: string
  weights: Partial<Record<'memory' | 'attention' | 'spatial' | 'reaction', number>>
  briefing: {
    objective: string
    controls: string
    rules: string
  }
}

export const CAMPAIGN_STAGES: CampaignStageMeta[] = [
  {
    key: 'sequence',
    title: '1. Sequence Factory',
    shortTitle: 'Sequence',
    lead: 'tamalito',
    cabCode: 'CAB-ME',
    cabName: 'Working Memory',
    catName: 'CAT · Visuospatial Sequence (Corsi-Type)',
    weights: { memory: 1.0, attention: 0.4 },
    briefing: {
      objective: 'Evaluate your short-term visuospatial and auditory sequential retention capacity under increasing load.',
      controls: 'Watch which squad members light up and emit a tone. When your turn starts, tap them in exact order.',
      rules: 'Duration: 30 seconds. Completed sequences grow in length; mistakes recalibrate complexity.',
    },
  },
  {
    key: 'bee',
    title: '2. Color Squad',
    shortTitle: 'Stroop',
    lead: 'chipilin',
    cabCode: 'CAB-AT',
    cabName: 'Focused Attention & Inhibition',
    catName: 'CAT · Color-Word Interference Test (Stroop)',
    weights: { attention: 1.0, reaction: 0.6 },
    briefing: {
      objective: 'Measure inhibitory control and selective attention against conflicting stimuli.',
      controls: 'Verify whether the badge color matches its word (GREEN = OPTIMAL, RED = CRITICAL, CREAM = NOMINAL) and choose MATCH or DECOY.',
      rules: 'Duration: 30 seconds. Ignore conflicting text labels when frame color differs.',
    },
  },
  {
    key: 'explorer',
    title: '3. Space Explorer',
    shortTitle: 'Explorer',
    lead: 'wakax',
    cabCode: 'CAB-RS',
    cabName: 'Spatial Reasoning & Planning',
    catName: 'CAT · Sequential Route Planning',
    weights: { spatial: 1.0, memory: 0.5 },
    briefing: {
      objective: 'Evaluate executive planning, spatial anticipation, and mental pathfinding.',
      controls: 'Program the full route with directional arrows to pick up crewmates, avoid red ALERT cells, land on GOAL, and press Launch.',
      rules: 'Clear 2 orbital sectors. Pre-launch planning speed and error-free navigation are recorded.',
    },
  },
  {
    key: 'scan',
    title: '4. Rapid Scan',
    shortTitle: 'Scan',
    lead: 'misi',
    cabCode: 'CAB-PC',
    cabName: 'Visual Perception & Processing Speed',
    catName: 'CAT · Selective Visual Search',
    weights: { reaction: 1.0, attention: 0.5 },
    briefing: {
      objective: 'Measure rapid visual scanning, perceptual discrimination, and processing speed.',
      controls: 'Identify the Target crew member shown at the top and tap them quickly inside the matrix.',
      rules: 'Duration: 30 seconds. Grid expands from 3x3 to 4x4 and 5x5 as hit streaks build.',
    },
  },
]

export interface NeuroFitStageResult {
  key: StageKey
  title: string
  cabCode: string
  cabName: string
  score: number
  accuracy: number
  correct_attempts: number
  error_attempts: number
  total_attempts: number
  avg_reaction_ms: number
  level_reached: number
  duration_sec: number
  leadCharId: SquadId
  gains: Record<string, number>
}

export interface NeuroFitReport {
  copilot_id: SquadId
  duration_sec: number
  total_score: number
  ecg_index: number
  overall_accuracy_pct: number
  mean_reaction_ms: number
  retention_pct: number
  sustained_attention_pct: number
  spatial_reasoning_pct: number
  visual_perception_pct: number
  focus_index_score: number
  total_hits: number
  total_errors: number
  total_attempts: number
  stages: NeuroFitStageResult[]
  cab_metrics: Record<string, { code: string, label: string, score: number }>
  diagnostic: {
    narrative: string
    strengthLabel: string
    weaknessLabel: string
  }
}

export function buildNeuroFitReport(
  results: NeuroFitStageResult[],
  copilotId: SquadId,
  cabMetrics: Record<string, { code: string, label: string, score: number }>,
): NeuroFitReport {
  const totalScore = results.reduce((sum, r) => sum + r.score, 0)
  const totalHits = results.reduce((sum, r) => sum + r.correct_attempts, 0)
  const totalErrors = results.reduce((sum, r) => sum + r.error_attempts, 0)
  const totalAttempts = results.reduce((sum, r) => sum + r.total_attempts, 0)
  const durationSec = Math.max(1, results.reduce((sum, r) => sum + r.duration_sec, 0))
  const overallAccuracy = totalAttempts > 0 ? Math.round((totalHits / totalAttempts) * 100) : 0

  const validRts = results.filter(r => r.avg_reaction_ms > 0).map(r => r.avg_reaction_ms)
  const meanRt = validRts.length > 0 ? Math.round(validRts.reduce((a, b) => a + b, 0) / validRts.length) : 0

  const byKey = Object.fromEntries(results.map(r => [r.key, r])) as Partial<Record<StageKey, NeuroFitStageResult>>
  const retentionPct = byKey.sequence?.accuracy ?? 0
  const stroopAcc = byKey.bee?.accuracy ?? 0
  const spatialPct = byKey.explorer?.accuracy ?? 0
  const scanAcc = byKey.scan?.accuracy ?? 0
  const sustainedAttentionPct = Math.round((stroopAcc + scanAcc) / 2)

  const rawFocus = retentionPct * 0.3 + sustainedAttentionPct * 0.35 + spatialPct * 0.2 + scanAcc * 0.15
  const rtPenalty = meanRt > 2500 ? (meanRt - 2500) / 250 : 0
  const focusIndex = Math.round(Math.max(0, Math.min(100, rawFocus - rtPenalty)))

  const metricVals = Object.values(cabMetrics)
  const ecgIndex = metricVals.length
    ? Math.round(metricVals.reduce((acc, m) => acc + m.score, 0) / metricVals.length)
    : 400

  const ranked = [...results].sort((a, b) => {
    const sa = a.accuracy * 0.7 + Math.min(100, a.score / 2) * 0.3
    const sb = b.accuracy * 0.7 + Math.min(100, b.score / 2) * 0.3
    return sb - sa
  })
  const strongest = ranked[0]
  const weakest = ranked[ranked.length - 1]
  const speedNote = meanRt > 0 && meanRt < 1100
    ? `Processing speed was crisp (${meanRt} ms average).`
    : meanRt > 2400
      ? `Deliberate pacing (${meanRt} ms average); timed drills can improve agility.`
      : `Balanced response pace (${meanRt} ms average).`

  const narrative = overallAccuracy >= 80
    ? `Composite Focus ${focusIndex}/100 and ${overallAccuracy}% accuracy show strong executive function across all 4 tasks. ${speedNote}`
    : overallAccuracy >= 50
      ? `Composite Focus ${focusIndex}/100 and ${overallAccuracy}% accuracy show steady function with room to tighten error control. ${speedNote}`
      : `Composite Focus ${focusIndex}/100 and ${overallAccuracy}% accuracy indicate elevated interference or missed trials. Repeat the battery after rest.`

  return {
    copilot_id: copilotId,
    duration_sec: durationSec,
    total_score: totalScore,
    ecg_index: ecgIndex,
    overall_accuracy_pct: overallAccuracy,
    mean_reaction_ms: meanRt,
    retention_pct: retentionPct,
    sustained_attention_pct: sustainedAttentionPct,
    spatial_reasoning_pct: spatialPct,
    visual_perception_pct: scanAcc,
    focus_index_score: focusIndex,
    total_hits: totalHits,
    total_errors: totalErrors,
    total_attempts: totalAttempts,
    stages: results,
    cab_metrics: cabMetrics,
    diagnostic: {
      narrative,
      strengthLabel: strongest ? `${strongest.cabCode}: ${strongest.cabName} (${strongest.accuracy}%)` : 'Nominal',
      weaknessLabel: weakest ? `${weakest.cabCode}: ${weakest.cabName} (${weakest.accuracy}% · ${weakest.error_attempts} err)` : 'Nominal',
    },
  }
}
