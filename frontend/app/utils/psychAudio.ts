class PsychAudioEngine {
  private ctx: AudioContext | null = null
  private thrusterOsc: OscillatorNode | null = null
  private thrusterGain: GainNode | null = null
  public muted = false

  private ensureCtx(): AudioContext | null {
    if (this.muted || typeof window === 'undefined') return null
    if (!this.ctx) {
      const Ctor = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext
      if (Ctor) this.ctx = new Ctor()
    }
    if (this.ctx && this.ctx.state === 'suspended') {
      void this.ctx.resume()
    }
    return this.ctx
  }

  toggleMute(): boolean {
    this.muted = !this.muted
    if (this.muted) this.stopThruster()
    return this.muted
  }

  playTone(freq = 440, duration = 0.16, type: OscillatorType = 'sine', volume = 0.08): void {
    const ctx = this.ensureCtx()
    if (!ctx) return
    try {
      const osc = ctx.createOscillator()
      const gain = ctx.createGain()
      osc.type = type
      osc.frequency.setValueAtTime(freq, ctx.currentTime)
      gain.gain.setValueAtTime(volume, ctx.currentTime)
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + duration)
      osc.connect(gain)
      gain.connect(ctx.destination)
      osc.start()
      osc.stop(ctx.currentTime + duration)
    }
    catch {
      return
    }
  }

  startThruster(): void {
    const ctx = this.ensureCtx()
    if (!ctx) return
    try {
      if (!this.thrusterOsc || !this.thrusterGain) {
        this.thrusterOsc = ctx.createOscillator()
        this.thrusterGain = ctx.createGain()
        this.thrusterOsc.type = 'triangle'
        this.thrusterOsc.frequency.setValueAtTime(130, ctx.currentTime)
        this.thrusterGain.gain.setValueAtTime(0.03, ctx.currentTime)
        this.thrusterOsc.connect(this.thrusterGain)
        this.thrusterGain.connect(ctx.destination)
        this.thrusterOsc.start()
      }
      else {
        this.thrusterGain.gain.setValueAtTime(0.03, ctx.currentTime)
      }
    }
    catch {
      return
    }
  }

  stopThruster(): void {
    if (this.thrusterGain && this.ctx) {
      try {
        this.thrusterGain.gain.setValueAtTime(0.0001, this.ctx.currentTime)
      }
      catch {
        return
      }
    }
  }

  playClick(): void {
    this.playTone(620, 0.06, 'sine', 0.07)
  }

  playSuccess(): void {
    this.playTone(523.25, 0.12, 'sine', 0.1)
    setTimeout(() => this.playTone(659.25, 0.18, 'sine', 0.1), 80)
  }

  playError(): void {
    this.playTone(175, 0.22, 'triangle', 0.12)
  }

  playScore(): void {
    this.playTone(880, 0.1, 'sine', 0.05)
  }

  playHit(): void {
    this.playTone(110, 0.2, 'sawtooth', 0.08)
  }

  playTargetHit(): void {
    this.playTone(1050, 0.08, 'sine', 0.07)
    setTimeout(() => this.playTone(1350, 0.09, 'sine', 0.07), 75)
  }

  playTargetExpired(): void {
    this.playTone(220, 0.14, 'triangle', 0.04)
  }

  playLevelUp(): void {
    [523.25, 659.25, 783.99, 1046.5].forEach((f, idx) => {
      setTimeout(() => this.playTone(f, 0.16, 'sine', 0.09), idx * 70)
    })
  }
}

export const psychAudio = new PsychAudioEngine()
