import { RELEASES, releaseUrl } from '../data/site'
import { t } from '../i18n'

export default function Releases() {
  const latest = RELEASES[0]
  return (
    <section className="section" id="releases">
      <div className="wrap">
        <div className="section__head">
          <h2>{t('Download and install')}</h2>
          <p>
            {t('Latest release')} {latest.version} — {t(latest.notes)}.
          </p>
        </div>

        <div className="release release--latest">
          <div className="release__meta">
            <span className="release__version">{latest.version}</span>
            <span className="release__date">
              {t('Released')} {latest.date}
            </span>
            <span className="release__size">{latest.size}</span>
          </div>
          <div className="release__actions">
            <a
              className="btn btn--primary"
              href={releaseUrl(latest.version, latest.asset)}
            >
              {t('Download the .deb')}
            </a>
            <code className="release__cmd">sudo dpkg -i {latest.asset}</code>
          </div>
        </div>

        <h3 style={{ marginTop: 'var(--s4)' }}>{t('All releases')}</h3>
        <ul className="release__list">
          {RELEASES.map((release) => (
            <li key={release.version}>
              <a href={releaseUrl(release.version, release.asset)}>
                {release.version}
              </a>
              <span>{release.date}</span>
              <span>{release.size}</span>
            </li>
          ))}
        </ul>
      </div>
    </section>
  )
}
