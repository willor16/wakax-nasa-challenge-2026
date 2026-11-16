// M5: recordings travel gzip-compressed (lossless) and the results screen lets the crew
// listen to them, with the assisted interpretation marked "AI Used".
import { readFileSync } from 'node:fs'
import { join, resolve } from 'node:path'
import { gunzipSync } from 'node:zlib'
import { describe, expect, it } from 'vitest'
import { encodeWav, gzipWav } from '../app/utils/audio'

const APP = join(resolve(import.meta.dirname, '..'), 'app')

describe('compressed upload', () => {
  it('packs the WAV losslessly and smaller than the raw file', async () => {
    const samples = new Float32Array(4000 * 30).map((_, i) => Math.sin(i / 20) * 0.5 * Math.sin(i / 4000))
    const wav = encodeWav(samples)
    const packed = await gzipWav(wav)
    expect(packed.encoding).toBe('gzip')
    const bytes = new Uint8Array(await packed.body.arrayBuffer())
    expect(bytes.byteLength).toBeLessThan(wav.byteLength)
    expect(bytes.byteLength).toBeLessThanOrEqual(250 * 1024)
    expect(new Uint8Array(gunzipSync(bytes))).toEqual(wav)
  })
})

describe('results screen', () => {
  const page = readFileSync(join(APP, 'pages/auscultation.vue'), 'utf-8')
  it('plays the recording with buttons only and marks the assisted interpretation', () => {
    expect(page).toContain('player.toggle(')
    expect(page).toContain('<UiAiWatermark')
    expect(page).toContain('Pending physician validation')
    expect(page).not.toMatch(/<input|<select|<textarea|method: 'POST'/)
  })

  it('never names the internal techniques on screen', () => {
    const template = page.split('<template>').slice(1).join('')
    expect(template).not.toMatch(/\b(cnn|onnx|llm|neural)\b/i)
  })
})
