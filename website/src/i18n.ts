/*
 * Lightweight i18n for the static site.
 *
 * The active locale is chosen at BUILD TIME via the LOCALE env var (see
 * `npm run build:all`), so each language ships as its own self-contained
 * bundle under `dist/<code>/`. At runtime we only need to resolve a single
 * catalog, which keeps the bundle small and the page fast.
 *
 * Strings are keyed by their English source text, so `t('Hello')` returns the
 * translation for the active locale (or the English source when missing). This
 * keeps components readable and makes untranslated strings fall back gracefully.
 */

// @ts-ignore - injected by Vite's `define`
declare const __LOCALE__: string

import en from './i18n/en.json'
import ar from './i18n/ar.json'
import de from './i18n/de.json'
import es from './i18n/es.json'
import fr from './i18n/fr.json'
import hi from './i18n/hi.json'
import ja from './i18n/ja.json'
import pt from './i18n/pt.json'
import ru from './i18n/ru.json'
import tr from './i18n/tr.json'
import zh from './i18n/zh.json'

const CATALOGS: Record<string, Record<string, string>> = {
  en, ar, de, es, fr, hi, ja, pt, ru, tr, zh,
}

export const LOCALE =
  typeof __LOCALE__ !== 'undefined' && __LOCALE__ ? __LOCALE__ : 'en'

export const catalog = CATALOGS[LOCALE] ?? CATALOGS.en

export function t(key: string, vars?: Record<string, string | number>): string {
  let out = catalog[key] ?? CATALOGS.en[key] ?? key
  if (vars) {
    for (const [k, v] of Object.entries(vars)) {
      out = out.replace(new RegExp(`\\{${k}\\}`, 'g'), String(v))
    }
  }
  return out
}

export const LOCALES = [
  { code: 'en', name: 'English', dir: 'ltr' },
  { code: 'ar', name: 'العربية', dir: 'rtl' },
  { code: 'de', name: 'Deutsch', dir: 'ltr' },
  { code: 'es', name: 'Español', dir: 'ltr' },
  { code: 'fr', name: 'Français', dir: 'ltr' },
  { code: 'hi', name: 'हिन्दी', dir: 'ltr' },
  { code: 'ja', name: '日本語', dir: 'ltr' },
  { code: 'pt', name: 'Português', dir: 'ltr' },
  { code: 'ru', name: 'Русский', dir: 'ltr' },
  { code: 'tr', name: 'Türkçe', dir: 'ltr' },
  { code: 'zh', name: '简体中文', dir: 'ltr' },
] as const

export type LocaleCode = (typeof LOCALES)[number]['code']
