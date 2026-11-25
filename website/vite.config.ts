import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { readFileSync } from 'node:fs'

const locale = process.env.LOCALE || 'en'
const meta = JSON.parse(readFileSync('./i18n/meta.json', 'utf-8'))[locale] ?? JSON.parse(readFileSync('./i18n/meta.json', 'utf-8')).en
const LOCALES = ['en', 'ar', 'de', 'es', 'fr', 'hi', 'ja', 'pt', 'ru', 'tr', 'zh']

const dir = locale === 'ar' ? 'rtl' : 'ltr'

// The site is published as static output. `base: './'` keeps every asset
// reference relative, so the same build works under a GitHub Pages project
// path, a custom domain, or a plain file server without a rebuild.
export default defineConfig({
  base: './',
  plugins: [
    react(),
    {
      name: 'locale-html',
      transformIndexHtml(html) {
        return html
          .replace(/<html lang="[^"]*"(\s+dir="[^"]*")?/, `<html lang="${locale}" dir="${dir}"`)
          .replace(/<title>[^<]*<\/title>/, `<title>${meta.title}</title>`)
          .replace(
            /<meta\s+name="description"\s+content="[^"]*"\s*\/>/,
            `<meta name="description" content="${meta.description}" />`,
          )
          .replace(
            /<meta property="og:title" content="[^"]*" \/>/,
            `<meta property="og:title" content="${meta.title}" />`,
          )
          .replace(
            /<meta\s+property="og:description"\s+content="[^"]*"\s*\/>/,
            `<meta property="og:description" content="${meta.ogDescription}" />`,
          )
          .replace(
            '</head>',
            (_m) =>
              LOCALES.map((c) => `    <link rel="alternate" hreflang="${c}" href="https://legendary-brilliantforous.github.io/flashpilot/${c}/" />`).join('\n') +
              '\n  </head>',
          )
      },
    },
  ],
  define: {
    __LOCALE__: JSON.stringify(locale),
  },
  build: {
    outDir: 'dist',
    assetsDir: 'assets',
    sourcemap: false,
    chunkSizeWarningLimit: 900,
  },
})
