import tailwindcss from '@tailwindcss/vite'

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
    plugins: [tailwindcss()],
    server: {
      proxy: {
        '/api': 'http://127.0.0.1:8000',
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
  runtimeConfig: {
    public: {
      apiBase: '',
    },
  },
})
