import { fileURLToPath } from 'node:url'
import tailwindcss from '@tailwindcss/vite'

// Build output must not carry paths from the build machine (folder names, home directory).
// The root is matched across OS path separators and encoded URIs alike.
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

const baseUrl = process.env.NUXT_APP_BASE_URL || '/'
const faviconHref = `${baseUrl.endsWith('/') ? baseUrl : `${baseUrl}/`}favicon.svg`

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
  app: {
    head: {
      title: 'SpaceScan',
      // The interface is English only: declare it, and stop browsers from auto-translating it.
      htmlAttrs: { lang: 'en', translate: 'no' },
      meta: [{ name: 'google', content: 'notranslate' }],
      link: [{ rel: 'icon', type: 'image/svg+xml', href: faviconHref }],
    },
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
      // The browser always calls relative /api/... URLs, so any device on the cabin network
      // (http://<LAN-IP>:3000) reaches the onboard server through this proxy. Live streams
      // are passed through uncompressed and unbuffered.
      proxy: {
        '/api': {
          target: process.env.SPACESCAN_API_TARGET ?? 'http://127.0.0.1:8080',
          changeOrigin: true,
          configure(proxy) {
            proxy.on('proxyRes', (response, request) => {
              if (!request.url?.startsWith('/api/v1/stream/')) return
              response.headers['x-accel-buffering'] = 'no'
              response.headers['cache-control'] = 'no-cache, no-transform'
              delete response.headers['content-encoding']
            })
          },
        },
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
    cssLayer: 'base',
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
