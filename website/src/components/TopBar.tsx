import Logo from './Logo'
import { REPO } from '../data/site'

const LINKS = [
  { href: '#protocols', label: 'Protocols' },
  { href: '#capabilities', label: 'Capabilities' },
  { href: '#devices', label: 'Devices' },
  { href: '#studio', label: 'Studio' },
  { href: '#install', label: 'Install' },
]

export default function TopBar() {
  return (
    <header className="topbar">
      <div className="wrap topbar__inner">
        <a className="brand" href="#top">
          <Logo className="brand__mark" />
          FlashPilot
        </a>

        <nav className="nav" aria-label="Sections">
          <div className="nav__links">
            {LINKS.map((link) => (
              <a key={link.href} href={link.href}>
                {link.label}
              </a>
            ))}
          </div>
          <a className="nav__cta" href={REPO} target="_blank" rel="noreferrer">
            GitHub
          </a>
        </nav>
      </div>
    </header>
  )
}
