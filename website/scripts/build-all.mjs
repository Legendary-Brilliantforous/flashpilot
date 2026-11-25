import { execSync } from 'node:child_process'
import { mkdirSync, writeFileSync, cpSync, rmSync, existsSync } from 'node:fs'
import { join } from 'node:path'

const locales = ['en', 'ar', 'de', 'es', 'fr', 'hi', 'ja', 'pt', 'ru', 'tr', 'zh']
const dist = 'dist'

console.log('=== typecheck ===')
execSync('npx tsc -b', { stdio: 'inherit' })

// Clean previous output.
if (existsSync(dist)) rmSync(dist, { recursive: true, force: true })
mkdirSync(dist, { recursive: true })

for (const code of locales) {
  console.log(`\n=== building locale: ${code} ===`)
  execSync(`LOCALE=${code} npx vite build --outDir dist/${code}`, {
    stdio: 'inherit',
    env: { ...process.env, LOCALE: code },
  })
}

// Root redirect to default locale.
writeFileSync(
  join(dist, 'index.html'),
  `<!doctype html><html lang="en"><head><meta charset="UTF-8" /><meta http-equiv="refresh" content="0; url=./en/" /><title>FlashPilot</title></head><body><a href="./en/">FlashPilot</a></body></html>`,
)

// Generate sitemap with all locales.
const urls = locales.map((c) => `  <url><loc>https://legendary-brilliantforous.github.io/flashpilot/${c}/</loc><xhtml:link rel="alternate" hreflang="${c}" href="https://legendary-brilliantforous.github.io/flashpilot/${c}/" /></url>`).join('\n')
writeFileSync(
  join(dist, 'sitemap.xml'),
  `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">\n${urls}\n</urlset>\n`,
)

// Copy robots.txt + favicon + img to root (from en build).
for (const f of ['robots.txt', 'favicon.svg']) {
  if (existsSync(join(dist, 'en', f))) cpSync(join(dist, 'en', f), join(dist, f))
}
if (existsSync(join(dist, 'en', 'img'))) cpSync(join(dist, 'en', 'img'), join(dist, 'img'), { recursive: true })

console.log('\n=== build:all complete ===')