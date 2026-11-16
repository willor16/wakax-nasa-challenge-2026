// Audio helpers for the 30-second heart and lung recordings: down-sampling, a standard
// WAV file, a SHA-256 checksum (also where the browser's own one is unavailable) and the
// sound envelope drawn while recording.

export const TARGET_RATE = 4000
export const RECORD_SECONDS = 30

/** Average-and-pick down-sampling to ``TARGET_RATE`` (heart and lung sounds sit below 1 kHz). */
export function downsample(samples: Float32Array, fromRate: number, toRate = TARGET_RATE): Float32Array {
  if (fromRate <= toRate) return samples
  const ratio = fromRate / toRate
  const out = new Float32Array(Math.floor(samples.length / ratio))
  for (let i = 0; i < out.length; i++) {
    const start = Math.floor(i * ratio)
    const end = Math.min(samples.length, Math.floor((i + 1) * ratio))
    let sum = 0
    for (let j = start; j < end; j++) sum += samples[j]!
    out[i] = sum / Math.max(1, end - start)
  }
  return out
}

/** 16-bit mono PCM WAV. */
export function encodeWav(samples: Float32Array, rate = TARGET_RATE): Uint8Array<ArrayBuffer> {
  let peak = 0
  for (const value of samples) peak = Math.max(peak, Math.abs(value))
  const scale = peak > 0 ? 0.92 / peak : 1
  const buffer = new ArrayBuffer(44 + samples.length * 2)
  const view = new DataView(buffer)
  const text = (offset: number, value: string) => [...value].forEach((c, i) => view.setUint8(offset + i, c.charCodeAt(0)))
  text(0, 'RIFF')
  view.setUint32(4, 36 + samples.length * 2, true)
  text(8, 'WAVE')
  text(12, 'fmt ')
  view.setUint32(16, 16, true)
  view.setUint16(20, 1, true)
  view.setUint16(22, 1, true)
  view.setUint32(24, rate, true)
  view.setUint32(28, rate * 2, true)
  view.setUint16(32, 2, true)
  view.setUint16(34, 16, true)
  text(36, 'data')
  view.setUint32(40, samples.length * 2, true)
  samples.forEach((value, i) => view.setInt16(44 + i * 2, Math.max(-1, Math.min(1, value * scale)) * 0x7FFF, true))
  return new Uint8Array(buffer)
}

const K = new Uint32Array([
  0x428A2F98, 0x71374491, 0xB5C0FBCF, 0xE9B5DBA5, 0x3956C25B, 0x59F111F1, 0x923F82A4, 0xAB1C5ED5,
  0xD807AA98, 0x12835B01, 0x243185BE, 0x550C7DC3, 0x72BE5D74, 0x80DEB1FE, 0x9BDC06A7, 0xC19BF174,
  0xE49B69C1, 0xEFBE4786, 0x0FC19DC6, 0x240CA1CC, 0x2DE92C6F, 0x4A7484AA, 0x5CB0A9DC, 0x76F988DA,
  0x983E5152, 0xA831C66D, 0xB00327C8, 0xBF597FC7, 0xC6E00BF3, 0xD5A79147, 0x06CA6351, 0x14292967,
  0x27B70A85, 0x2E1B2138, 0x4D2C6DFC, 0x53380D13, 0x650A7354, 0x766A0ABB, 0x81C2C92E, 0x92722C85,
  0xA2BFE8A1, 0xA81A664B, 0xC24B8B70, 0xC76C51A3, 0xD192E819, 0xD6990624, 0xF40E3585, 0x106AA070,
  0x19A4C116, 0x1E376C08, 0x2748774C, 0x34B0BCB5, 0x391C0CB3, 0x4ED8AA4A, 0x5B9CCA4F, 0x682E6FF3,
  0x748F82EE, 0x78A5636F, 0x84C87814, 0x8CC70208, 0x90BEFFFA, 0xA4506CEB, 0xBEF9A3F7, 0xC67178F2,
])

/** Plain SHA-256 (FIPS 180-4), used when the page is not served over a secure origin. */
export function sha256Fallback(data: Uint8Array): string {
  const h = new Uint32Array([0x6A09E667, 0xBB67AE85, 0x3C6EF372, 0xA54FF53A, 0x510E527F, 0x9B05688C, 0x1F83D9AB, 0x5BE0CD19])
  const bitLength = data.length * 8
  const padded = new Uint8Array(((data.length + 9 + 63) >> 6) << 6)
  padded.set(data)
  padded[data.length] = 0x80
  const tail = new DataView(padded.buffer)
  tail.setUint32(padded.length - 8, Math.floor(bitLength / 2 ** 32))
  tail.setUint32(padded.length - 4, bitLength >>> 0)
  const w = new Uint32Array(64)
  const rotr = (x: number, n: number) => (x >>> n) | (x << (32 - n))
  for (let offset = 0; offset < padded.length; offset += 64) {
    for (let i = 0; i < 16; i++) w[i] = tail.getUint32(offset + i * 4)
    for (let i = 16; i < 64; i++) {
      const s0 = rotr(w[i - 15]!, 7) ^ rotr(w[i - 15]!, 18) ^ (w[i - 15]! >>> 3)
      const s1 = rotr(w[i - 2]!, 17) ^ rotr(w[i - 2]!, 19) ^ (w[i - 2]! >>> 10)
      w[i] = (w[i - 16]! + s0 + w[i - 7]! + s1) >>> 0
    }
    let [a, b, c, d, e, f, g, hh] = h as unknown as number[]
    for (let i = 0; i < 64; i++) {
      const t1 = (hh! + (rotr(e!, 6) ^ rotr(e!, 11) ^ rotr(e!, 25)) + ((e! & f!) ^ (~e! & g!)) + K[i]! + w[i]!) >>> 0
      const t2 = ((rotr(a!, 2) ^ rotr(a!, 13) ^ rotr(a!, 22)) + ((a! & b!) ^ (a! & c!) ^ (b! & c!))) >>> 0
      hh = g; g = f; f = e; e = (d! + t1) >>> 0; d = c; c = b; b = a; a = (t1 + t2) >>> 0
    }
    h[0] = (h[0]! + a!) >>> 0; h[1] = (h[1]! + b!) >>> 0; h[2] = (h[2]! + c!) >>> 0; h[3] = (h[3]! + d!) >>> 0
    h[4] = (h[4]! + e!) >>> 0; h[5] = (h[5]! + f!) >>> 0; h[6] = (h[6]! + g!) >>> 0; h[7] = (h[7]! + hh!) >>> 0
  }
  return [...h].map(x => x.toString(16).padStart(8, '0')).join('')
}

export async function sha256Hex(data: Uint8Array<ArrayBuffer>): Promise<string> {
  if (globalThis.crypto?.subtle) {
    const digest = await globalThis.crypto.subtle.digest('SHA-256', data)
    return [...new Uint8Array(digest)].map(b => b.toString(16).padStart(2, '0')).join('')
  }
  return sha256Fallback(data)
}

/**
 * Lossless gzip of the WAV for upload (the stethoscope band is kept intact). Browsers
 * without CompressionStream send the WAV as is. The checksum is always taken on the WAV,
 * so the onboard server verifies it after unpacking.
 */
export async function gzipWav(wav: Uint8Array<ArrayBuffer>): Promise<{ body: Blob, encoding: 'gzip' | 'identity' }> {
  if (typeof CompressionStream === 'undefined') return { body: new Blob([wav], { type: 'audio/wav' }), encoding: 'identity' }
  const stream = new Blob([wav]).stream().pipeThrough(new CompressionStream('gzip'))
  const packed = await new Response(stream).arrayBuffer()
  // Keep whichever is smaller (a very noisy recording may not shrink).
  return packed.byteLength < wav.byteLength
    ? { body: new Blob([packed], { type: 'application/gzip' }), encoding: 'gzip' }
    : { body: new Blob([wav], { type: 'audio/wav' }), encoding: 'identity' }
}

/** Root-mean-square level of a block in decibels relative to full scale. */
export function levelDb(block: Float32Array): number {
  let sum = 0
  for (const value of block) sum += value * value
  const rms = Math.sqrt(sum / Math.max(1, block.length))
  return rms > 0 ? 20 * Math.log10(rms) : -100
}
