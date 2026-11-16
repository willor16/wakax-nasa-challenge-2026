import { fileURLToPath } from 'node:url'
import tailwindcss from '@tailwindcss/vite'

// Build output must not carry paths from the build machine (folder names, home directory).
const projectRoot = fileURLToPath(new URL('.', import.meta.url)).replace(/[/\\]+$/, '')
const localRoots = Array.from(new Set([
  projectRoot,
  projectRoot.replaceAll('\\', '\\\\'),
  projectRoot.replaceAll('\\', '/'),
  encodeURI(projectRoot.replaceAll('\\', '/')),
]))
function cleanMachinePaths(input: string): string {
  let next = input
  for (const root of localRoots) {
    if (root && next.includes(root)) next = next.split(root).join('.')
  }
  return next
}
const stripLocalPaths = {
  name: 'strip-local-paths',
  enforce: 'post' as const,
  renderChunk(code: string) {
    const cleaned = cleanMachinePaths(code)
    return cleaned !== code ? { code: cleaned, map: null } : null
  },
}

export default defineNuxtConfig({
  compatibilityDate: '2026-11-01',
  ssr: false,
  devServer: {
    host: '0.0.0.0',
    port: 3000,
  },
  future: {
    compatibilityVersion: 4,
  },
  css: ['~/assets/css/tokens.css'],
  modules: [
    '@nuxt/eslint',
    '@nuxt/fonts',
    '@nuxt/icon',
    '@nuxtjs/i18n',
    '@pinia/nuxt',
  ],
  vite: {
    plugins: [tailwindcss(), stripLocalPaths],
    server: {
      proxy: {
        '/api': 'http://127.0.0.1:8080',
      },
    },
  },
  fonts: {
    providers: {
      google: false,
      googleicons: false,
      bunny: false,
      fontshare: false,
      fontsource: false,
    },
  },
  icon: {
    provider: 'none',
    fallbackToApi: false,
    clientBundle: {
      scan: true,
    },
    customCollections: [
      {
        prefix: 'spacescan',
        dir: './app/assets/icons/spacescan',
      },
    ],
  },
  i18n: {
    defaultLocale: 'en',
    strategy: 'no_prefix',
    locales: [
      {
        code: 'en',
        name: 'English',
        file: 'en.ts',
      },
    ],
  },
  nitro: {
    hooks: {
      // Generated pages embed the app settings; keep build-machine paths out of them too.
      'prerender:generate'(route) {
        if (typeof route.contents === 'string') route.contents = cleanMachinePaths(route.contents)
      },
    },
  },
  runtimeConfig: {
    public: {
      apiBase: '',
    },
  },
})
