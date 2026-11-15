// Fixed-size sliding window of the most recent samples (the live ECG keeps 6 s at 125 Hz).
export class RingBuffer {
  private readonly data: Float32Array
  private start = 0
  private size = 0

  constructor(readonly capacity: number) {
    this.data = new Float32Array(capacity)
  }

  push(values: readonly number[]): void {
    for (const value of values) {
      const end = (this.start + this.size) % this.capacity
      this.data[end] = value
      if (this.size < this.capacity) this.size += 1
      else this.start = (this.start + 1) % this.capacity
    }
  }

  /** Oldest to newest. */
  toArray(): number[] {
    const out = new Array<number>(this.size)
    for (let i = 0; i < this.size; i += 1) out[i] = this.data[(this.start + i) % this.capacity]!
    return out
  }

  get length(): number {
    return this.size
  }

  clear(): void {
    this.start = 0
    this.size = 0
  }
}
