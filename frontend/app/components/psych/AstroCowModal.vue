<script setup lang="ts">
import bg1Url from '~/assets/games/astrocow/bg-1.png'
import bg2Url from '~/assets/games/astrocow/bg-2.png'
import bg3Url from '~/assets/games/astrocow/bg-3.png'
import bg4Url from '~/assets/games/astrocow/bg-4.png'
import cowSpriteUrl from '~/assets/games/astrocow/cow-sprite.png'
import { computeAstroCowSummary, gameCanvasPalette, type AstroCowSummary } from '~/utils/astroCowTelemetry'
import { psychAudio } from '~/utils/psychAudio'

const props = defineProps<{
  expanded: boolean
  saving?: boolean
  savedNote?: { tone: 'ok' | 'critical', title: string, text: string } | null
}>()

const emit = defineEmits<{
  minimize: []
  exit: []
  'save-session': [summary: AstroCowSummary]
}>()

const { state } = usePsychGames()

const W = 900
const H = 560
const cvs = ref<HTMLCanvasElement | null>(null)
let ctx: CanvasRenderingContext2D | null = null
let rafId: number | null = null

type FlightState = 'IDLE' | 'FLYING' | 'PAUSED' | 'DEAD'
const gameState = ref<FlightState>('IDLE')
const score = ref(0)
const highScore = computed(() => state.value.astrocowHighScore)
const currentDifficultyLevel = ref(1)
const elapsedFlightSec = ref(0)
const reticleHits = ref(0)
const reticleTotal = ref(0)
const showTargetPreview = ref(true)
const isMuted = ref(psychAudio.muted)
const latestSummary = ref<AstroCowSummary | null>(state.value.astrocowLast)

interface Obstacle {
  x: number
  width: number
  topH: number
  botY: number
  scored: boolean
  hasSolarTop: boolean
  hasSolarBot: boolean
  hasEscapePod: boolean
  hazardType: 'NONE' | 'METEOR' | 'LASER'
  hazardY: number
  hazardCycle: number
  rustSpots: { yRel: number, h: number }[]
}

interface TargetReticle {
  x: number
  y: number
  radius: number
  createdTime: number
  maxLife: number
  isExpired: boolean
}

let isThrusting = false
let spaceKeyHeld = false
let isPointerDown = false
const heldFlightKeys = new Set<string>()
let pointerX = -100
let pointerY = -100

const bgImages: HTMLImageElement[] = []
let bgLoaded = false
let currentBgIndex = 0
let cowSprite: HTMLImageElement | null = null
let cowLoaded = false

const cowW = 48
const cowH = 50
const cowX = 130
let cowY = 260
let cowVy = 0
const thrustAcceleration = -0.22
const gravity = 0.11
const maxAscentSpeed = -2.4
const maxFallSpeed = 1.9
const inertialDamping = 0.962

let obstacles: Obstacle[] = []
const stars: { x: number, y: number, size: number, speed: number }[] = []
let speed = 1.35
let gapSize = 310
let obstacleSpacing = 620
let scrollOffset = 0
let shieldHp = 5
let invulnerabilityTimer = 0
let flightStartTime = 0
let pausedAtTime = 0
let totalPausedMs = 0
let lastTopHeight = 125
let patternStep = 0

let thrustParticles: { x: number, y: number, vx: number, vy: number, life: number, size: number, alt: boolean }[] = []
let feedbackFloatingTexts: { text: string, x: number, y: number, alpha: number, ok: boolean }[] = []
let targetReticle: TargetReticle | null = null
let nextTargetCoords: { x: number, y: number } | null = null
let nextTargetSpawnTime = 0

let reactionPairs: { stimulus: number, response: number }[] = []
let omittedResponsesCount = 0
let errorsAfterChangeCount = 0
let collisionCount = 0
let lastChangeTimestamp = 0
let awaitingRecoveryFromChange = false
let recoveryTimesSec: number[] = []
let targetTimelineEvents: { time: number, hit: boolean }[] = []

function preloadAssets() {
  if (typeof window === 'undefined' || bgImages.length > 0) return
  const sources = [bg1Url, bg2Url, bg3Url, bg4Url]
  let count = 0
  sources.forEach((src) => {
    const img = new Image()
    img.onload = () => {
      count++
      if (count >= 1) bgLoaded = true
    }
    img.src = src
    bgImages.push(img)
  })
  cowSprite = new Image()
  cowSprite.onload = () => {
    cowLoaded = true
  }
  cowSprite.src = cowSpriteUrl

  if (stars.length === 0) {
    for (let i = 0; i < 55; i++) {
      stars.push({
        x: Math.random() * W,
        y: Math.random() * H,
        size: Math.random() * 1.5 + 0.8,
        speed: Math.random() * 0.4 + 0.1,
      })
    }
  }
}

function effectiveNow() {
  return Date.now() - totalPausedMs
}

function updateDifficultyByTime(now: number) {
  const elapsedSec = Math.max(0, (now - flightStartTime) / 1000)
  elapsedFlightSec.value = Math.floor(elapsedSec)
  const computedLevel = Math.min(5, 1 + Math.floor(elapsedSec / 15))
  const progressRatio = Math.min(1, elapsedSec / 65)
  speed = Number((1.35 + progressRatio * 1.40).toFixed(2))
  obstacleSpacing = Math.round(620 - progressRatio * 290)
  gapSize = Math.round(310 - progressRatio * 110)

  if (computedLevel > currentDifficultyLevel.value) {
    currentDifficultyLevel.value = computedLevel
    lastChangeTimestamp = now
    awaitingRecoveryFromChange = true
    psychAudio.playLevelUp()
    feedbackFloatingTexts.push({
      text: `LEVEL ${computedLevel} · SPEED UP`,
      x: W / 2,
      y: 92,
      alpha: 1.35,
      ok: true,
    })
  }
}

function calculateNextObstacleGeometry() {
  patternStep++
  const lvl = currentDifficultyLevel.value
  let targetTop = lastTopHeight
  if (lvl === 1) {
    targetTop = Math.max(70, Math.min(H - gapSize - 70, lastTopHeight + (Math.random() - 0.5) * 45))
  }
  else if (lvl === 2) {
    targetTop = Math.max(65, Math.min(H - gapSize - 65, lastTopHeight + (Math.random() - 0.5) * 85))
  }
  else if (lvl === 3) {
    const phase = Math.sin(patternStep * 0.75)
    targetTop = 65 + ((phase + 1) / 2) * (H - gapSize - 130)
  }
  else {
    const phase = Math.max(-1, Math.min(1, Math.sin(patternStep * 1.05) + (Math.random() - 0.5) * 0.5))
    targetTop = 60 + ((phase + 1) / 2) * (H - gapSize - 120)
  }
  lastTopHeight = targetTop
  return { topH: targetTop, botY: targetTop + gapSize }
}

function spawnObstacle() {
  const { topH, botY } = calculateNextObstacleGeometry()
  const pipeWidth = 52
  let hazardType: Obstacle['hazardType'] = 'NONE'
  if (currentDifficultyLevel.value === 3 && Math.random() < 0.25) hazardType = 'METEOR'
  else if (currentDifficultyLevel.value >= 4 && Math.random() < 0.45) hazardType = Math.random() > 0.45 ? 'METEOR' : 'LASER'
  obstacles.push({
    x: W + 15,
    width: pipeWidth,
    topH,
    botY,
    scored: false,
    hasSolarTop: Math.random() > 0.45,
    hasSolarBot: Math.random() > 0.45,
    hasEscapePod: Math.random() > 0.6,
    hazardType,
    hazardY: topH + gapSize * 0.5,
    hazardCycle: 0,
    rustSpots: [
      { yRel: 0.2 + Math.random() * 0.4, h: 6 + Math.random() * 6 },
      { yRel: 0.4 + Math.random() * 0.3, h: 5 + Math.random() * 5 },
    ],
  })
}

function prepareNextTargetCoords() {
  const minX = 240
  const maxX = W - 120
  const padY = 105
  nextTargetCoords = {
    x: minX + Math.random() * (maxX - minX),
    y: padY + Math.random() * (H - padY * 2),
  }
}

function spawnTimedTarget(now: number) {
  if (!nextTargetCoords) prepareNextTargetCoords()
  const lvl = currentDifficultyLevel.value
  const timeLimit = Math.max(3600, 8200 - (lvl - 1) * 1100)
  const targetRad = Math.max(38, 52 - (lvl - 1) * 3.5)
  targetReticle = {
    x: nextTargetCoords!.x,
    y: nextTargetCoords!.y,
    radius: targetRad,
    createdTime: now,
    maxLife: timeLimit,
    isExpired: false,
  }
  nextTargetCoords = null
  reticleTotal.value++
  lastChangeTimestamp = now
  awaitingRecoveryFromChange = true
}

function claimTarget() {
  if (!targetReticle || targetReticle.isExpired) return
  const now = effectiveNow()
  const reactionLatency = Math.max(80, now - targetReticle.createdTime)
  reactionPairs.push({ stimulus: targetReticle.createdTime, response: now })
  reticleHits.value++
  score.value++

  if (awaitingRecoveryFromChange && lastChangeTimestamp > 0) {
    recoveryTimesSec.push(Number(((now - lastChangeTimestamp) / 1000).toFixed(2)))
    awaitingRecoveryFromChange = false
  }
  targetTimelineEvents.push({ time: Number(((now - flightStartTime) / 1000).toFixed(1)), hit: true })
  psychAudio.playTargetHit()

  feedbackFloatingTexts.push({
    text: `TARGET HIT ${reactionLatency}ms`,
    x: targetReticle.x,
    y: targetReticle.y - 20,
    alpha: 1.0,
    ok: true,
  })
  for (let i = 0; i < 14; i++) {
    thrustParticles.push({
      x: targetReticle.x,
      y: targetReticle.y,
      vx: (Math.random() - 0.5) * 5,
      vy: (Math.random() - 0.5) * 5,
      life: 24 + Math.random() * 10,
      size: 3 + Math.random() * 2,
      alt: i % 2 === 0,
    })
  }
  targetReticle = null
  nextTargetSpawnTime = now + 1600 + Math.random() * 600
  prepareNextTargetCoords()
}

function finishFlight() {
  if (!ctx || gameState.value === 'DEAD') return
  isThrusting = false
  psychAudio.stopThruster()
  gameState.value = 'DEAD'
  const now = effectiveNow()
  const dur = Math.max(1, Math.round((now - flightStartTime) / 1000))
  const summary = computeAstroCowSummary({
    score: score.value,
    highScore: state.value.astrocowHighScore,
    difficultyLevel: currentDifficultyLevel.value,
    durationSec: dur,
    reticleHits: reticleHits.value,
    reticleTotal: reticleTotal.value,
    collisions: collisionCount,
    errorsAfterChange: errorsAfterChangeCount,
    omittedResponses: omittedResponsesCount,
    reactionTimesMs: reactionPairs.map(r => Math.max(80, r.response - r.stimulus)),
    recoveryTimesSec,
    targetTimelineEvents,
  })
  latestSummary.value = summary
  state.value.astrocowLast = summary
  if (score.value > state.value.astrocowHighScore) {
    state.value.astrocowHighScore = score.value
  }
}

function startFlight() {
  currentBgIndex = Math.floor(Math.random() * Math.max(1, bgImages.length))
  gameState.value = 'FLYING'
  score.value = 0
  currentDifficultyLevel.value = 1
  elapsedFlightSec.value = 0
  cowY = H / 2 - 20
  cowVy = 0
  isThrusting = false
  obstacles = []
  thrustParticles = []
  feedbackFloatingTexts = []
  shieldHp = 5
  invulnerabilityTimer = 0
  speed = 1.35
  gapSize = 310
  obstacleSpacing = 620
  scrollOffset = 0
  totalPausedMs = 0
  pausedAtTime = 0
  flightStartTime = Date.now()

  targetReticle = null
  reticleHits.value = 0
  reticleTotal.value = 0
  nextTargetSpawnTime = flightStartTime + 2000
  prepareNextTargetCoords()

  reactionPairs = []
  omittedResponsesCount = 0
  errorsAfterChangeCount = 0
  collisionCount = 0
  lastChangeTimestamp = flightStartTime
  awaitingRecoveryFromChange = false
  recoveryTimesSec = []
  targetTimelineEvents = []
  lastTopHeight = 125
  patternStep = 0
}

function resumeFromPause() {
  if (gameState.value !== 'PAUSED') return
  if (pausedAtTime > 0) totalPausedMs += Date.now() - pausedAtTime
  pausedAtTime = 0
  gameState.value = 'FLYING'
}

function renderBackground(pal: ReturnType<typeof gameCanvasPalette>) {
  if (!ctx) return
  if (bgLoaded && bgImages[currentBgIndex] && bgImages[currentBgIndex]!.complete) {
    const img = bgImages[currentBgIndex]!
    const scale = H / Math.max(1, img.naturalHeight)
    const imgW = Math.max(1, img.naturalWidth * scale)
    const offsetX = -(scrollOffset * 0.35) % imgW
    for (let x = offsetX; x < W; x += imgW) {
      ctx.drawImage(img, x, 0, imgW, H)
    }
  }
  else {
    ctx.fillStyle = pal.bgTop
    ctx.fillRect(0, 0, W, H)
  }
  ctx.fillStyle = pal.text
  stars.forEach((st) => {
    st.x -= st.speed * speed
    if (st.x < 0) st.x = W + Math.random() * 20
    ctx.globalAlpha = 0.6
    ctx.fillRect(st.x, st.y, st.size, st.size)
  })
  ctx.globalAlpha = 1.0
}

function renderObstacle(obs: Obstacle, pal: ReturnType<typeof gameCanvasPalette>) {
  if (!ctx) return
  const { x, width: pw, topH, botY } = obs
  const botH = H - botY
  const rimW = pw + 12
  const rimH = 9
  const rimX = x - 6

  ctx.fillStyle = pal.surfaceCard
  ctx.fillRect(x, 0, pw, topH)
  ctx.fillRect(x, botY, pw, botH)
  ctx.fillStyle = pal.borderHi
  ctx.fillRect(x, 0, 4, topH)
  ctx.fillRect(x, botY, 4, botH)
  ctx.fillRect(rimX, topH - rimH, rimW, rimH)
  ctx.fillRect(rimX, botY, rimW, rimH)
  ctx.fillStyle = pal.bgInset
  ctx.fillRect(x + pw - 4, 0, 4, topH)
  ctx.fillRect(x + pw - 4, botY, 4, botH)

  ctx.fillStyle = pal.navy
  if (obs.hasSolarTop && topH > 60) {
    const spY = Math.floor(topH * 0.35)
    ctx.fillRect(x - 34, spY, 24, 34)
    ctx.strokeStyle = pal.rem
    ctx.lineWidth = 1.5
    ctx.strokeRect(x - 34, spY, 24, 34)
  }
  if (obs.hasSolarBot && botH > 65) {
    const spY = botY + Math.floor(botH * 0.25)
    ctx.fillRect(x + pw + 10, spY, 24, 34)
    ctx.strokeStyle = pal.rem
    ctx.lineWidth = 1.5
    ctx.strokeRect(x + pw + 10, spY, 24, 34)
  }

  if (obs.hazardType === 'METEOR') {
    obs.hazardCycle += 0.05
    const mX = x + pw / 2
    const mY = obs.hazardY + Math.sin(obs.hazardCycle) * 14
    ctx.fillStyle = pal.crit
    ctx.beginPath()
    ctx.moveTo(mX + 10, mY)
    ctx.lineTo(mX + 30, mY - 12)
    ctx.lineTo(mX + 14, mY + 11)
    ctx.fill()
    ctx.fillStyle = pal.text
    ctx.beginPath()
    ctx.arc(mX, mY, 12, 0, Math.PI * 2)
    ctx.fill()
    ctx.strokeStyle = pal.navyEdge
    ctx.lineWidth = 2
    ctx.stroke()
  }
  else if (obs.hazardType === 'LASER') {
    obs.hazardCycle += 0.08
    ctx.save()
    ctx.globalAlpha = 0.45 + Math.sin(obs.hazardCycle) * 0.35
    ctx.strokeStyle = pal.crit
    ctx.lineWidth = 3
    ctx.beginPath()
    ctx.moveTo(x + pw / 2, topH + rimH)
    ctx.lineTo(x + pw / 2, botY)
    ctx.stroke()
    ctx.restore()
  }
}

function renderCow(pal: ReturnType<typeof gameCanvasPalette>) {
  if (!ctx) return
  if (invulnerabilityTimer > 0 && Math.floor(invulnerabilityTimer / 4) % 2 === 0) return

  ctx.save()
  const pitch = isThrusting ? -0.18 : Math.min(0.35, cowVy * 0.06)
  ctx.translate(cowX + cowW / 2, cowY + cowH / 2)
  ctx.rotate(pitch)
  if (cowLoaded && cowSprite && cowSprite.complete) {
    ctx.drawImage(cowSprite, -cowW / 2, -cowH / 2, cowW, cowH)
  }
  else {
    ctx.fillStyle = pal.text
    ctx.fillRect(-cowW / 2, -cowH / 2, cowW, cowH)
  }

  if (isThrusting) {
    const flameLen = 12 + Math.random() * 8
    ctx.fillStyle = pal.crit
    ctx.beginPath()
    ctx.moveTo(-cowW / 2 + 2, -5)
    ctx.lineTo(-cowW / 2 - flameLen, 4)
    ctx.lineTo(-cowW / 2 + 2, 13)
    ctx.fill()
    ctx.fillStyle = pal.text
    ctx.beginPath()
    ctx.moveTo(-cowW / 2 + 3, -1)
    ctx.lineTo(-cowW / 2 - flameLen * 0.6, 4)
    ctx.lineTo(-cowW / 2 + 3, 9)
    ctx.fill()
    thrustParticles.push({
      x: cowX - 6,
      y: cowY + cowH * 0.55 + (Math.random() - 0.5) * 4,
      vx: -speed - Math.random() * 2,
      vy: (Math.random() - 0.5) * 1.5,
      life: 16 + Math.random() * 8,
      size: 2 + Math.random() * 2,
      alt: Math.random() > 0.5,
    })
  }
  ctx.restore()

  thrustParticles.forEach((p) => {
    if (!ctx) return
    ctx.fillStyle = p.alt ? pal.ok : pal.text
    ctx.globalAlpha = Math.max(0, p.life / 24)
    ctx.fillRect(p.x, p.y, p.size, p.size)
  })
  ctx.globalAlpha = 1.0
}

function renderTimedTarget(now: number, pal: ReturnType<typeof gameCanvasPalette>) {
  if (!ctx) return
  if (!targetReticle && showTargetPreview.value && nextTargetCoords && nextTargetSpawnTime > now) {
    const secToSpawn = ((nextTargetSpawnTime - now) / 1000).toFixed(1)
    const { x, y } = nextTargetCoords
    ctx.save()
    ctx.globalAlpha = 0.45 + Math.abs(Math.sin(now * 0.008)) * 0.5
    ctx.strokeStyle = pal.text
    ctx.lineWidth = 2
    ctx.setLineDash([5, 5])
    ctx.beginPath()
    ctx.arc(x, y, 40, 0, Math.PI * 2)
    ctx.stroke()
    ctx.setLineDash([4, 6])
    ctx.beginPath()
    ctx.moveTo(cowX + cowW / 2, cowY + cowH / 2)
    ctx.lineTo(x, y)
    ctx.stroke()
    ctx.setLineDash([])
    ctx.fillStyle = pal.text
    ctx.beginPath()
    ctx.arc(x, y, 5, 0, Math.PI * 2)
    ctx.fill()
    ctx.font = '700 11px "Inter", sans-serif'
    ctx.textAlign = 'center'
    ctx.fillText(`NEXT TARGET ${secToSpawn}s`, x, y - 46)
    ctx.restore()
    return
  }
  if (!targetReticle) return
  const elapsed = now - targetReticle.createdTime
  const remainingMs = Math.max(0, targetReticle.maxLife - elapsed)
  const ratio = remainingMs / targetReticle.maxLife
  if (ratio <= 0) return
  const { x, y, radius } = targetReticle
  const urgent = remainingMs < 1600

  ctx.save()
  ctx.strokeStyle = urgent ? pal.crit : pal.ok
  ctx.lineWidth = 2
  ctx.beginPath()
  ctx.arc(x, y, radius, 0, Math.PI * 2)
  ctx.stroke()

  ctx.lineWidth = 4.5
  ctx.beginPath()
  ctx.arc(x, y, radius + 4, -Math.PI / 2, -Math.PI / 2 + Math.PI * 2 * ratio)
  ctx.stroke()

  ctx.lineWidth = 1.5
  ctx.beginPath()
  ctx.moveTo(x - radius * 0.7, y)
  ctx.lineTo(x + radius * 0.7, y)
  ctx.moveTo(x, y - radius * 0.7)
  ctx.lineTo(x, y + radius * 0.7)
  ctx.stroke()

  ctx.fillStyle = urgent ? pal.crit : pal.ok
  ctx.beginPath()
  ctx.arc(x, y, 5, 0, Math.PI * 2)
  ctx.fill()

  ctx.fillStyle = pal.bgBase
  ctx.fillRect(x - 28, y + radius + 7, 56, 18)
  ctx.strokeRect(x - 28, y + radius + 7, 56, 18)
  ctx.fillStyle = urgent ? pal.crit : pal.text
  ctx.font = '700 11px "JetBrains Mono", monospace'
  ctx.textAlign = 'center'
  ctx.fillText(`${(remainingMs / 1000).toFixed(1)}s`, x, y + radius + 20)
  ctx.restore()
}

function renderHUD(pal: ReturnType<typeof gameCanvasPalette>) {
  if (!ctx) return
  ctx.save()
  ctx.fillStyle = pal.text
  ctx.font = '700 16px "JetBrains Mono", monospace'
  ctx.textAlign = 'center'
  ctx.fillText(`SCORE ${String(score.value).padStart(3, '0')}`, W / 2, 32)

  const heartX = W - 110
  const heartY = 20
  for (let s = 0; s < 5; s++) {
    ctx.fillStyle = s < shieldHp ? pal.ok : pal.bgInset
    ctx.fillRect(heartX + s * 16, heartY, 12, 10)
    ctx.strokeStyle = pal.borderHi
    ctx.strokeRect(heartX + s * 16, heartY, 12, 10)
  }

  ctx.fillStyle = pal.bgBase
  ctx.fillRect(14, 16, 136, 22)
  ctx.strokeStyle = targetReticle ? pal.ok : pal.borderHi
  ctx.strokeRect(14, 16, 136, 22)
  ctx.fillStyle = targetReticle ? pal.ok : pal.text
  ctx.font = '700 11px "JetBrains Mono", monospace'
  ctx.textAlign = 'center'
  ctx.fillText(targetReticle ? 'TARGET ACTIVE' : 'RADAR SCANNING', 82, 31)

  ctx.fillStyle = pal.bgBase
  ctx.fillRect(158, 16, 118, 22)
  ctx.strokeStyle = pal.ok
  ctx.strokeRect(158, 16, 118, 22)
  ctx.fillStyle = pal.ok
  ctx.fillText(`HITS ${reticleHits.value}/${reticleTotal.value}`, 217, 31)

  ctx.fillStyle = pal.bgBase
  ctx.fillRect(284, 16, 122, 22)
  ctx.strokeStyle = pal.text
  ctx.strokeRect(284, 16, 122, 22)
  ctx.fillStyle = pal.text
  ctx.fillText(`LVL ${currentDifficultyLevel.value} · ${elapsedFlightSec.value}s`, 345, 31)
  ctx.restore()
}

function gameLoop() {
  rafId = requestAnimationFrame(gameLoop)
  if (!ctx || !props.expanded) return
  const pal = gameCanvasPalette()

  if (gameState.value === 'IDLE') {
    renderBackground(pal)
    ctx.save()
    ctx.globalAlpha = 0.72
    ctx.fillStyle = pal.bgBase
    ctx.fillRect(0, 0, W, H)
    ctx.restore()

    ctx.fillStyle = pal.text
    ctx.font = '700 24px "JetBrains Mono", monospace'
    ctx.textAlign = 'center'
    ctx.fillText('ASTROCOW · AST-01', W / 2, H / 2 - 120)
    ctx.fillStyle = pal.ok
    ctx.font = '700 15px "Inter", sans-serif'
    ctx.fillText('DUAL-TASK SENSORIMOTOR & REFLEX SIMULATOR', W / 2, H / 2 - 90)
    if (cowLoaded && cowSprite) ctx.drawImage(cowSprite, W / 2 - cowW / 2, H / 2 - 70, cowW, cowH)

    ctx.fillStyle = pal.bgInset
    ctx.fillRect(W / 2 - 280, H / 2 - 6, 560, 126)
    ctx.strokeStyle = pal.borderHi
    ctx.strokeRect(W / 2 - 280, H / 2 - 6, 560, 126)
    ctx.fillStyle = pal.text
    ctx.font = '600 14px "Inter", sans-serif'
    ctx.fillText('THRUSTER (FLY UP): Hold [W] / [SHIFT] / [SPACE] / Click', W / 2, H / 2 + 28)
    ctx.fillStyle = pal.ok
    ctx.fillText('TIMED TARGETS: Hover / Click Target — or Press [E] / [ENTER]', W / 2, H / 2 + 58)
    ctx.fillStyle = pal.ice
    ctx.fillText('RADAR PREVIEW: Toggle 2.0s warning ring with [R] · Difficulty steps up every 15s', W / 2, H / 2 + 88)
    ctx.fillStyle = pal.text
    ctx.font = '700 14px "JetBrains Mono", monospace'
    ctx.fillText('CLICK CANVAS OR PRESS [SPACE] TO LAUNCH', W / 2, H / 2 + 152)
    return
  }

  if (gameState.value === 'PAUSED' || gameState.value === 'DEAD') {
    renderBackground(pal)
    obstacles.forEach(o => renderObstacle(o, pal))
    renderCow(pal)
    renderHUD(pal)
    return
  }

  if (isThrusting) {
    cowVy = Math.max(maxAscentSpeed, cowVy + thrustAcceleration)
  }
  else {
    cowVy = Math.min(maxFallSpeed, cowVy + gravity)
  }
  cowVy *= inertialDamping
  cowY += cowVy
  if (cowY < 0) {
    cowY = 0
    cowVy = 0
  }
  if (cowY + cowH > H - 6) {
    cowY = H - cowH - 6
    cowVy = -1.6
  }

  scrollOffset += speed
  if (invulnerabilityTimer > 0) invulnerabilityTimer--

  thrustParticles.forEach((p) => {
    p.x += p.vx
    p.y += p.vy
    p.life--
  })
  thrustParticles = thrustParticles.filter(p => p.life > 0)

  const now = effectiveNow()
  updateDifficultyByTime(now)

  if (!targetReticle && now >= nextTargetSpawnTime && now - flightStartTime > 1800) {
    spawnTimedTarget(now)
  }

  if (targetReticle && !targetReticle.isExpired && pointerX >= 0 && pointerY >= 0) {
    if (Math.hypot(pointerX - targetReticle.x, pointerY - targetReticle.y) <= targetReticle.radius + 22) {
      claimTarget()
    }
  }
  if (targetReticle) {
    const dist = Math.hypot(cowX + cowW / 2 - targetReticle.x, cowY + cowH / 2 - targetReticle.y)
    if (dist <= targetReticle.radius + 14) {
      claimTarget()
    }
    else if (now - targetReticle.createdTime > targetReticle.maxLife) {
      targetReticle.isExpired = true
      omittedResponsesCount++
      errorsAfterChangeCount++
      targetTimelineEvents.push({ time: Number(((now - flightStartTime) / 1000).toFixed(1)), hit: false })
      psychAudio.playTargetExpired()
      feedbackFloatingTexts.push({ text: 'MISSED TARGET', x: targetReticle.x, y: targetReticle.y - 15, alpha: 1.0, ok: false })
      targetReticle = null
      nextTargetSpawnTime = now + 1600 + Math.random() * 600
      prepareNextTargetCoords()
    }
  }

  obstacles.forEach((o) => { o.x -= speed })
  obstacles = obstacles.filter(o => o.x + o.width > -40)
  const runway = now - flightStartTime < 3200
  const lastObs = obstacles.at(-1)
  if (!runway && (!lastObs || lastObs.x < W - obstacleSpacing)) {
    spawnObstacle()
  }

  for (const obs of obstacles) {
    const cx = cowX + 12
    const cy = cowY + 12
    const cw = cowW - 24
    const ch = cowH - 24
    const hitTop = cx + cw > obs.x && cx < obs.x + obs.width && cy < obs.topH
    const hitBot = cx + cw > obs.x && cx < obs.x + obs.width && cy + ch > obs.botY
    if (hitTop || hitBot) {
      if (invulnerabilityTimer <= 0) {
        shieldHp--
        collisionCount++
        if (awaitingRecoveryFromChange || now - lastChangeTimestamp < 4000) errorsAfterChangeCount++
        lastChangeTimestamp = now
        awaitingRecoveryFromChange = true
        invulnerabilityTimer = 85
        psychAudio.playHit()
        if (shieldHp <= 0) {
          finishFlight()
          return
        }
      }
      break
    }
    if (!obs.scored && obs.x + obs.width < cowX) {
      obs.scored = true
      score.value++
      if (awaitingRecoveryFromChange && lastChangeTimestamp > 0) {
        recoveryTimesSec.push(Number(((now - lastChangeTimestamp) / 1000).toFixed(2)))
        awaitingRecoveryFromChange = false
      }
      psychAudio.playScore()
    }
  }

  renderBackground(pal)
  obstacles.forEach(o => renderObstacle(o, pal))
  renderTimedTarget(now, pal)

  ctx.save()
  feedbackFloatingTexts.forEach((ft) => {
    if (!ctx) return
    ctx.globalAlpha = Math.max(0, ft.alpha)
    ctx.fillStyle = ft.ok ? pal.ok : pal.crit
    ctx.font = '700 11px "JetBrains Mono", monospace'
    ctx.textAlign = 'center'
    ctx.fillText(ft.text, ft.x, ft.y)
    ft.y -= 0.8
    ft.alpha -= 0.022
  })
  feedbackFloatingTexts = feedbackFloatingTexts.filter(ft => ft.alpha > 0)
  ctx.restore()

  renderCow(pal)
  renderHUD(pal)
}

function updatePointerCoords(e: MouseEvent | PointerEvent | TouchEvent) {
  if (!cvs.value) return false
  const rect = cvs.value.getBoundingClientRect()
  let clientX: number | null = null
  let clientY: number | null = null
  if ('touches' in e && e.touches[0]) {
    clientX = e.touches[0].clientX
    clientY = e.touches[0].clientY
  }
  else if ('clientX' in e) {
    clientX = e.clientX
    clientY = e.clientY
  }
  if (clientX === null || clientY === null) return false
  pointerX = (clientX - rect.left) * (W / rect.width)
  pointerY = (clientY - rect.top) * (H / rect.height)
  return true
}

function checkTargetAtPoint(e: MouseEvent | PointerEvent | TouchEvent) {
  if (!updatePointerCoords(e)) return false
  if (targetReticle && !targetReticle.isExpired) {
    if (Math.hypot(pointerX - targetReticle.x, pointerY - targetReticle.y) <= targetReticle.radius + 24) {
      claimTarget()
      return true
    }
  }
  return false
}

function handlePointerMove(e: PointerEvent | MouseEvent) {
  if (!props.expanded || gameState.value !== 'FLYING') return
  updatePointerCoords(e)
  if (targetReticle && !targetReticle.isExpired) {
    if (Math.hypot(pointerX - targetReticle.x, pointerY - targetReticle.y) <= targetReticle.radius + 24) {
      claimTarget()
    }
  }
}

function handlePointerDown(e: PointerEvent | MouseEvent | TouchEvent) {
  if (!props.expanded) return
  if (gameState.value === 'IDLE') {
    startFlight()
    isPointerDown = true
    isThrusting = true
    psychAudio.startThruster()
    return
  }
  if (gameState.value === 'PAUSED') {
    resumeFromPause()
    return
  }
  if (gameState.value !== 'FLYING') return
  checkTargetAtPoint(e)
  if ('button' in e && e.button === 2) return
  isPointerDown = true
  if (!isThrusting) {
    isThrusting = true
    psychAudio.startThruster()
  }
}

function handlePointerUp(e?: PointerEvent | MouseEvent | TouchEvent) {
  if (e && 'button' in e && e.button === 2) return
  isPointerDown = false
  if (isThrusting && !spaceKeyHeld) {
    isThrusting = false
    psychAudio.stopThruster()
  }
}

function isFlightKey(code: string) {
  return ['Space', 'ArrowUp', 'KeyW', 'ShiftLeft', 'ShiftRight', 'ControlLeft', 'ControlRight'].includes(code)
}

function onKeyDown(e: KeyboardEvent) {
  if (!props.expanded) return
  if (e.code === 'Escape') {
    e.preventDefault()
    handleMinimize()
    return
  }
  if (e.code === 'KeyR' && !e.repeat) {
    showTargetPreview.value = !showTargetPreview.value
    return
  }
  if ((e.code === 'KeyE' || e.code === 'Enter') && !e.repeat) {
    if (gameState.value === 'FLYING' && targetReticle && !targetReticle.isExpired) claimTarget()
    return
  }
  if (!isFlightKey(e.code)) return
  e.preventDefault()
  heldFlightKeys.add(e.code)
  spaceKeyHeld = true
  if (e.repeat) return
  if (gameState.value === 'IDLE' || gameState.value === 'DEAD') {
    startFlight()
    isThrusting = true
    psychAudio.startThruster()
    return
  }
  if (gameState.value === 'PAUSED') {
    resumeFromPause()
  }
  if (!isThrusting) {
    isThrusting = true
    psychAudio.startThruster()
  }
}

function onKeyUp(e: KeyboardEvent) {
  if (!isFlightKey(e.code)) return
  heldFlightKeys.delete(e.code)
  spaceKeyHeld = heldFlightKeys.size > 0
  if (!spaceKeyHeld && isThrusting && !isPointerDown) {
    isThrusting = false
    psychAudio.stopThruster()
  }
}

function toggleAudio() {
  isMuted.value = psychAudio.toggleMute()
}

function handleMinimize() {
  if (gameState.value === 'FLYING') {
    gameState.value = 'PAUSED'
    pausedAtTime = Date.now()
    isThrusting = false
    isPointerDown = false
    spaceKeyHeld = false
    heldFlightKeys.clear()
    psychAudio.stopThruster()
  }
  emit('minimize')
}

function handleExit() {
  if (gameState.value === 'FLYING') finishFlight()
  psychAudio.stopThruster()
  emit('exit')
}

watch(() => props.expanded, async (open) => {
  if (open) {
    await nextTick()
    if (cvs.value) ctx = cvs.value.getContext('2d')
    preloadAssets()
    if (gameState.value === 'PAUSED') resumeFromPause()
  }
  else {
    isThrusting = false
    psychAudio.stopThruster()
  }
})

onMounted(() => {
  preloadAssets()
  if (cvs.value) ctx = cvs.value.getContext('2d')
  if (typeof window !== 'undefined') {
    window.addEventListener('keydown', onKeyDown, { passive: false })
    window.addEventListener('keyup', onKeyUp)
    window.addEventListener('mouseup', handlePointerUp)
  }
  rafId = requestAnimationFrame(gameLoop)
})

onBeforeUnmount(() => {
  if (rafId !== null) cancelAnimationFrame(rafId)
  psychAudio.stopThruster()
  if (typeof window !== 'undefined') {
    window.removeEventListener('keydown', onKeyDown)
    window.removeEventListener('keyup', onKeyUp)
    window.removeEventListener('mouseup', handlePointerUp)
  }
})
</script>

<template>
  <Teleport v-if="expanded" to="body">
    <div class="psych-battery-overlay" role="dialog" aria-modal="true" aria-label="AST-01 AstroCow Simulator">
      <header class="psych-overlay-header">
        <div class="max-w-[1280px] mx-auto flex flex-wrap items-center justify-between gap-[12px]">
          <div>
            <p class="label-caps text-cabin-ok">Sensorimotor Dual-Task · AST-01</p>
            <p class="text-[15px] font-bold mt-[2px]">AstroCow Flight &amp; Reflex Telemetry</p>
          </div>
          <div class="flex flex-wrap items-center gap-[8px]">
            <button type="button" class="px-[10px] py-[6px] rounded-[4px] border border-cabin-line mono text-[11px] text-cabin-ice hover:text-cabin-text" @click="toggleAudio">
              {{ isMuted ? 'MUTED' : 'AUDIO HUD' }}
            </button>
            <button type="button" class="px-[10px] py-[6px] rounded-[4px] border mono text-[11px]" :class="showTargetPreview ? 'menu-item-active text-cabin-ok' : 'border-cabin-line text-cabin-ice'" @click="showTargetPreview = !showTargetPreview">
              {{ showTargetPreview ? 'RADAR ON (R)' : 'RADAR OFF (R)' }}
            </button>
            <button v-if="gameState === 'FLYING' && elapsedFlightSec >= 5" type="button" class="px-[12px] py-[6px] rounded-[4px] border border-cabin-ok bg-cabin-ok/20 mono text-[11px] font-bold text-cabin-ok" @click="finishFlight">
              Finish &amp; Review
            </button>
            <button type="button" class="px-[12px] py-[6px] rounded-[4px] border border-cabin-line text-[12px] text-cabin-ice hover:text-cabin-text" @click="handleMinimize">
              Minimize
            </button>
            <button type="button" class="px-[12px] py-[6px] rounded-[4px] border border-cabin-crit/60 bg-cabin-crit/15 text-[12px] font-bold text-cabin-crit" @click="handleExit">
              Exit
            </button>
          </div>
        </div>
      </header>

      <div class="psych-overlay-scroll hud-scroll flex flex-col items-center justify-center gap-[12px]">
        <div class="astrocow-canvas-frame">
          <canvas
            ref="cvs"
            :width="W"
            :height="H"
            class="astrocow-canvas"
            @contextmenu.prevent="checkTargetAtPoint"
            @pointerdown="handlePointerDown"
            @pointermove="handlePointerMove"
            @pointerup="handlePointerUp"
            @pointercancel="handlePointerUp"
            @touchstart.prevent="handlePointerDown"
            @touchend.prevent="handlePointerUp"
          />

          <div v-if="gameState === 'DEAD' && latestSummary" class="astrocow-debrief">
            <p class="mono text-[13px] font-bold text-cabin-ok tracking-[0.06em]">FLIGHT DEBRIEF · AST-01 COMPLETE</p>
            <div class="grid grid-cols-2 sm:grid-cols-3 gap-[10px] w-full max-w-[540px] mt-[14px]">
              <div class="tile-hi p-[10px] text-center">
                <p class="label-caps">Score / High</p>
                <p class="mono text-[18px] font-bold mt-[4px]">{{ latestSummary.score }} / {{ latestSummary.high_score }}</p>
              </div>
              <div class="tile p-[10px] text-center">
                <p class="label-caps">Reaction Latency</p>
                <p class="mono text-[18px] font-bold mt-[4px]">{{ latestSummary.mean_reaction_ms }} ms</p>
              </div>
              <div class="tile p-[10px] text-center">
                <p class="label-caps">Target Precision</p>
                <p class="mono text-[18px] font-bold mt-[4px] text-cabin-ok">{{ latestSummary.precision_pct }}%</p>
              </div>
              <div class="tile p-[10px] text-center">
                <p class="label-caps">Recovery T_rec</p>
                <p class="mono text-[18px] font-bold mt-[4px]">{{ latestSummary.recovery_time_sec }} s</p>
              </div>
              <div class="tile p-[10px] text-center">
                <p class="label-caps">RT Variability</p>
                <p class="mono text-[18px] font-bold mt-[4px]">±{{ latestSummary.rt_variability_ms }} ms</p>
              </div>
              <div class="tile p-[10px] text-center">
                <p class="label-caps">Omissions / Errors</p>
                <p class="mono text-[18px] font-bold mt-[4px]">{{ latestSummary.omitted_responses }} / {{ latestSummary.errors_after_change }}</p>
              </div>
            </div>

            <UiSaveResult v-if="savedNote" :tone="savedNote.tone" :title="savedNote.title" :text="savedNote.text" class="mt-[12px] w-full max-w-[540px]" />

            <div class="flex flex-wrap gap-[10px] mt-[16px]">
              <button type="button" class="px-[16px] py-[10px] rounded-[6px] border border-cabin-line mono text-[12px] font-bold" @click="startFlight">
                Fly Again
              </button>
              <button type="button" class="px-[18px] py-[10px] rounded-[6px] border border-cabin-ok bg-cabin-ok/20 mono text-[12px] font-bold text-cabin-ok" :disabled="saving" @click="emit('save-session', latestSummary)">
                {{ saving ? 'Saving…' : 'Save Flight Telemetry' }}
              </button>
            </div>
          </div>
        </div>

        <div class="w-full max-w-[1020px] flex flex-wrap items-center justify-between gap-[10px] text-[11.5px] text-cabin-ice mono">
          <span>Thruster: [W] / [Shift] / [Space] / Click · Target: Mouse Hover / Click / [E]</span>
          <span>Level {{ currentDifficultyLevel }} · {{ elapsedFlightSec }}s · Best {{ highScore }} pts</span>
        </div>
      </div>
    </div>
  </Teleport>
</template>
