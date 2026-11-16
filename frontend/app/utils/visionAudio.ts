class VisionAudioEngine {
  private ctx: AudioContext | null = null
  public muted = false

  private ensureContext(): AudioContext | null {
    if (typeof window === 'undefined') return null
    const ctor = window.AudioContext
      || (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext
    if (!this.ctx && ctor) this.ctx = new ctor()
    if (this.ctx && this.ctx.state === 'suspended') void this.ctx.resume()
    return this.ctx
  }

  public toggleMute(): boolean {
    this.muted = !this.muted
    return this.muted
  }

  public playTone(freq = 440, type: OscillatorType = 'sine', duration = 0.1, gainVal = 0.1) {
    if (this.muted) return
    try {
      const ctx = this.ensureContext()
      if (!ctx) return
      const osc = ctx.createOscillator()
      const gain = ctx.createGain()
      osc.type = type
      osc.frequency.setValueAtTime(freq, ctx.currentTime)
      gain.gain.setValueAtTime(gainVal, ctx.currentTime)
      gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + duration)
      osc.connect(gain)
      gain.connect(ctx.destination)
      osc.start()
      osc.stop(ctx.currentTime + duration)
    }
    catch {
      return
    }
  }

  public playClick() {
    this.playTone(850, 'triangle', 0.04, 0.08)
  }

  public playSuccess() {
    if (this.muted) return
    try {
      const ctx = this.ensureContext()
      if (!ctx) return
      const now = ctx.currentTime
      ;[587.33, 880, 1174.66].forEach((freq, idx) => {
        const osc = ctx.createOscillator()
        const gain = ctx.createGain()
        osc.type = 'sine'
        osc.frequency.setValueAtTime(freq, now + idx * 0.06)
        gain.gain.setValueAtTime(0.12, now + idx * 0.06)
        gain.gain.exponentialRampToValueAtTime(0.0001, now + idx * 0.06 + 0.18)
        osc.connect(gain)
        gain.connect(ctx.destination)
        osc.start(now + idx * 0.06)
        osc.stop(now + idx * 0.06 + 0.18)
      })
    }
    catch {
      return
    }
  }

  public playError() {
    if (this.muted) return
    try {
      const ctx = this.ensureContext()
      if (!ctx) return
      const now = ctx.currentTime
      ;[220, 185].forEach((freq, idx) => {
        const osc = ctx.createOscillator()
        const gain = ctx.createGain()
        osc.type = 'sawtooth'
        osc.frequency.setValueAtTime(freq, now + idx * 0.08)
        gain.gain.setValueAtTime(0.09, now + idx * 0.08)
        gain.gain.exponentialRampToValueAtTime(0.0001, now + idx * 0.08 + 0.15)
        osc.connect(gain)
        gain.connect(ctx.destination)
        osc.start(now + idx * 0.08)
        osc.stop(now + idx * 0.08 + 0.15)
      })
    }
    catch {
      return
    }
  }

  public playWarning() {
    if (this.muted) return
    this.playTone(493.88, 'square', 0.15, 0.08)
    setTimeout(() => this.playTone(440, 'square', 0.2, 0.08), 120)
  }

  public playComplete() {
    if (this.muted) return
    try {
      const ctx = this.ensureContext()
      if (!ctx) return
      const chords = [523.25, 659.25, 783.99, 1046.50]
      const now = ctx.currentTime
      chords.forEach((freq, idx) => {
        const osc = ctx.createOscillator()
        const gain = ctx.createGain()
        osc.type = 'sine'
        osc.frequency.setValueAtTime(freq, now + idx * 0.09)
        gain.gain.setValueAtTime(0.14, now + idx * 0.09)
        gain.gain.exponentialRampToValueAtTime(0.0001, now + idx * 0.09 + 0.35)
        osc.connect(gain)
        gain.connect(ctx.destination)
        osc.start(now + idx * 0.09)
        osc.stop(now + idx * 0.09 + 0.35)
      })
    }
    catch {
      return
    }
  }
}

export const visionAudio = new VisionAudioEngine()
