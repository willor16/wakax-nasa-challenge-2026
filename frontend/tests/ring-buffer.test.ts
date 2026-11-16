// The live ECG keeps a sliding window of the most recent samples.
import { describe, expect, it } from 'vitest'
import { RingBuffer } from '../app/utils/ringBuffer'

describe('ring buffer', () => {
  it('keeps the newest samples in order once full', () => {
    const buffer = new RingBuffer(5)
    buffer.push([1, 2, 3])
    expect(buffer.toArray()).toEqual([1, 2, 3])
    buffer.push([4, 5, 6, 7])
    expect(buffer.toArray()).toEqual([3, 4, 5, 6, 7])
    expect(buffer.length).toBe(5)
  })

  it('holds six seconds of a 125 Hz trace fed four times a second', () => {
    const buffer = new RingBuffer(125 * 6)
    for (let frame = 0; frame < 40; frame += 1) buffer.push(Array.from({ length: 31 }, (_, i) => frame * 31 + i))
    const window = buffer.toArray()
    expect(window).toHaveLength(750)
    expect(window.at(-1)).toBe(40 * 31 - 1)
    expect(window[0]).toBe(40 * 31 - 750)
  })
})
