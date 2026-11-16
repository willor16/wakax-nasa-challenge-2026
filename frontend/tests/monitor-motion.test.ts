// Bedside-monitor motion: the live ECG sweeps over the previous pass with an erase gap,
// recordings light up as they are heard, and trend charts draw in on load.
import { describe, expect, it } from 'vitest'
import { RingBuffer } from '../app/utils/ringBuffer'
import { SWEEP_GAP_S, captureTraceOption, envelopeOption, moodTrendOption, sweepSegments } from '../app/utils/charts'

describe('ECG sweep', () => {
  const rate = 10
  const windowS = 2 // 20 slots
  it('places every sample in its fixed slot and erases a gap ahead of the head', () => {
    const buffer = new RingBuffer(rate * windowS)
    buffer.push(Array.from({ length: 27 }, (_, i) => i)) // one full pass plus 7 samples
    expect(buffer.total).toBe(27)
    const { current, previous, head } = sweepSegments(buffer.toArray(), rate, windowS, buffer.total)
    expect(current.map(p => p[1])).toEqual([20, 21, 22, 23, 24, 25, 26]) // new pass from the left
    expect(head).toEqual([0.6, 26])
    const gap = Math.round(rate * SWEEP_GAP_S)
    expect(previous[0]![0]).toBeCloseTo((7 + gap) / rate) // old pass resumes after the gap
    expect(previous.at(-1)).toEqual([1.9, 19])
  })

  it('shows the whole first pass before the window is full', () => {
    const { current, previous } = sweepSegments([1, 2, 3], rate, windowS, 3)
    expect(current).toHaveLength(3)
    expect(previous).toHaveLength(0)
  })
})

describe('listening and recording traces', () => {
  const envelope = Array.from({ length: 200 }, (_, i) => Math.abs(Math.sin(i / 5)))
  it('lights up the part already heard and marks the position', () => {
    const option = envelopeOption(envelope, 'pulmonary', [], 20, 3.0)
    const series = option.series as { data: [number, number][], type: string, lineStyle?: { opacity?: number } }[]
    expect(series[0]!.lineStyle!.opacity).toBeLessThan(1) // pending part faint
    expect(series[1]!.data.at(-1)![0]).toBeLessThanOrEqual(3.0) // heard part ends at the cursor
    expect(['effectScatter', 'scatter']).toContain(series[2]!.type) // pulsing head
  })

  it('fills the capture window from the right with a head on the newest point', () => {
    const option = captureTraceOption(envelope.slice(0, 40), 'cardiac', 150)
    const series = option.series as { data: [number, number][] }[]
    expect(series[0]!.data.at(-1)![0]).toBe(149)
    expect(series[1]!.data).toEqual([series[0]!.data.at(-1)])
  })
})

describe('trend entrance animation', () => {
  it('draws trend lines in when motion is allowed', () => {
    const option = moodTrendOption([{ day_label: 'D01', mood: 4, calmness: 4 }], { band: [3.8, 5] })
    expect(option.animation).toBe(true)
    expect(option.animationDuration).toBeGreaterThan(500)
  })
})
