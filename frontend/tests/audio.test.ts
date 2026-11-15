import { createHash } from 'node:crypto'
import { describe, expect, it } from 'vitest'
import { downsample, encodeWav, levelDb, sha256Fallback } from '../app/utils/audio'

describe('recording helpers', () => {
  it('matches the standard SHA-256 for any length', () => {
    for (const size of [0, 1, 55, 56, 64, 1000, 65537]) {
      const data = new Uint8Array(size).map((_, i) => (i * 31 + 7) & 0xFF)
      expect(sha256Fallback(data)).toBe(createHash('sha256').update(data).digest('hex'))
    }
  })

  it('writes a 16-bit mono WAV of the right size', () => {
    const wav = encodeWav(new Float32Array(4000).fill(0.5), 4000)
    expect(wav.length).toBe(44 + 8000)
    expect(String.fromCharCode(...wav.slice(0, 4))).toBe('RIFF')
    expect(new DataView(wav.buffer).getUint32(24, true)).toBe(4000)
  })

  it('down-samples 48 kHz to 4 kHz and measures level', () => {
    expect(downsample(new Float32Array(48000), 48000).length).toBe(4000)
    expect(levelDb(new Float32Array(100).fill(1))).toBeCloseTo(0)
    expect(levelDb(new Float32Array(100))).toBe(-100)
  })
})
