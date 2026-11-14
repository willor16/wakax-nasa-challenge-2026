import tailwindcss from '@tailwindcss/vite'

export default defineNuxtConfig({
  compatibilityDate: '2026-11-01',
  ssr: false,
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
    langDir: 'locales',
    locales: [
      {
        code: 'en',
        name: 'English',
        file: 'en.json',
      },
    ],
  },
  runtimeConfig: {
    public: {
      apiBase: '',
    },
  },
})
