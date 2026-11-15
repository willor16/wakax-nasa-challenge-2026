// Test translator backed by the real locale file, so tests assert the exact
// words the crew sees on screen.
import { vi } from 'vitest'
import type { Translate } from '../../app/utils/notifications'

vi.stubGlobal('defineI18nLocale', (factory: () => unknown) => factory)

type Messages = { [key: string]: string | Messages }

export async function loadTranslate(): Promise<Translate> {
  const factory = (await import('../../i18n/locales/en')).default as unknown as () => Messages
  const messages = factory()
  return (key, params = {}) => {
    let node: string | Messages | undefined = messages
    for (const part of key.split('.')) {
      node = typeof node === 'object' ? node[part] : undefined
    }
    if (typeof node !== 'string') throw new Error(`Missing locale text: ${key}`)
    return node.replace(/\{(\w+)\}/g, (_, name: string) => String(params[name]))
  }
}
