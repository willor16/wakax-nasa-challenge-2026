import { fileURLToPath } from 'node:url'
import tailwindcss from '@tailwindcss/vite'

// Build output must not carry paths from the build machine (folder names, home directory).
// The root is matched with both separators so Windows and Linux builds are cleaned alike.
const projectRoot = fileURLToPath(new URL('.', import.meta.url)).replace(/[\\/]$/, '')
const rootForms = [...new Set([projectRoot, projectRoot.replaceAll('\\', '/'), projectRoot.replaceAll('/', '\\')])]
const stripLocalPaths = {
  name: 'strip-local-paths',
  enforce: 'post' as const,
  renderChunk(code: string) {
    const found = rootForms.filter(form => code.includes(form))
    if (found.length === 0) return null
    return { code: found.reduce((text, form) => text.split(form).join('.'), code), map: null }
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
        if (typeof route.contents === 'string') route.contents = route.contents.split(projectRoot).join('.')
      },
    },
  },
  runtimeConfig: {
    public: {
      apiBase: '',
    },
  },
})
