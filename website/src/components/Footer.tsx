import Logo from './Logo'
import { BRANCH, DOC_LANGUAGES, REPO, repoLink } from '../data/site'
import { t } from '../i18n'

export default function Footer() {
  return (
    <footer className="footer">
      <div className="wrap">
        <div className="footer__grid">
          <div>
            <a className="brand" href="#top">
              <Logo className="brand__mark" />
              FlashPilot
            </a>
            <p className="footer__blurb">
              {t('An open-source flashing and repair workbench for Linux. Rust at the wire, Python at the desk.')}
            </p>
          </div>

          <div>
            <h4>{t('Project')}</h4>
            <ul>
              <li>
                <a href={REPO} target="_blank" rel="noreferrer">
                  {t('Repository')}
                </a>
              </li>
              <li>
                <a href={`${REPO}/issues`} target="_blank" rel="noreferrer">
                  {t('Issues')}
                </a>
              </li>
              <li>
                <a href={`${REPO}/discussions`} target="_blank" rel="noreferrer">
                  {t('Discussions')}
                </a>
              </li>
              <li>
                <a href={`${REPO}/releases`} target="_blank" rel="noreferrer">
                  {t('Releases')}
                </a>
              </li>
            </ul>
          </div>

          <div>
            <h4>{t('Documentation')}</h4>
            <ul>
              <li>
                <a href={repoLink('/README.md')} target="_blank" rel="noreferrer">
                  {t('English README')}
                </a>
              </li>
              <li>
                <a href={repoLink('/CONTRIBUTING.md')} target="_blank" rel="noreferrer">
                  {t('Contributing')}
                </a>
              </li>
              <li>
                <a href={`${REPO}/tree/${BRANCH}/operations`} target="_blank" rel="noreferrer">
                  {t('Operation notes')}
                </a>
              </li>
              <li>
                <a href={repoLink('/docs/TRANSLATION.md')} target="_blank" rel="noreferrer">
                  {t('Translation guide')}
                </a>
              </li>
            </ul>
          </div>

          <div>
            <h4>{t('Docs in your language')}</h4>
            <div className="footer__langs">
              {DOC_LANGUAGES.map((language) => (
                <a
                  key={language.code}
                  href={repoLink(`/docs/${language.code}/README.md`)}
                  target="_blank"
                  rel="noreferrer"
                >
                  {language.label}
                </a>
              ))}
            </div>
          </div>
        </div>

        <div className="footer__base">
          <span>{t('MIT licensed. Odin constants derive from Heimdall; the SPD BSL reference is clean-room.')}</span>
          <span>
            <a href={repoLink('/LICENSE')} target="_blank" rel="noreferrer">
              {t('License')}
            </a>
            {' · '}
            <a href={repoLink('/SECURITY.md')} target="_blank" rel="noreferrer">
              {t('Security')}
            </a>
          </span>
        </div>
      </div>
    </footer>
  )
}
