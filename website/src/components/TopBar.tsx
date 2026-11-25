import Logo from './Logo'
import { REPO } from '../data/site'
import { LOCALES, LOCALE, t } from '../i18n'

const LINKS = [
  { href: '#protocols', label: t('Protocols') },
  { href: '#capabilities', label: t('Capabilities') },
  { href: '#devices', label: t('Devices') },
  { href: '#studio', label: t('Studio') },
  { href: '#install', label: t('Install') },
  { href: '#releases', label: t('Releases') },
  { href: '#contribute', label: t('Contribute') },
]

export default function TopBar() {
  return (
    <header className="topbar">
      <div className="wrap topbar__inner">
        <a className="brand" href="#top">
          <Logo className="brand__mark" />
          FlashPilot
        </a>

        <nav className="nav" aria-label={t('Sections')}>
          <div className="nav__links">
            {LINKS.map((link) => (
              <a key={link.href} href={link.href}>
                {link.label}
              </a>
            ))}
          </div>
          <label className="lang-switch">
            <span className="sr-only">{t('Language')}</span>
            <select
              value={LOCALE}
              onChange={(e) => {
                const next = e.target.value
                if (next && next !== LOCALE) {
                  window.location.href = `../${next}/`
                }
              }}
              aria-label={t('Language')}
            >
              {LOCALES.map((l) => (
                <option key={l.code} value={l.code}>
                  {l.name}
                </option>
              ))}
            </select>
          </label>
          <a className="nav__cta" href={REPO} target="_blank" rel="noreferrer">
            GitHub
          </a>
        </nav>
      </div>
    </header>
  )
}
