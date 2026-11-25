import { INSTALL, REPO, repoLink } from '../data/site'
import { t } from '../i18n'

export default function Contribute() {
  return (
    <section className="section" id="contribute">
      <div className="wrap">
        <div className="section__head">
          <h2>{t('Get involved')}</h2>
          <p>{t('Pull requests welcome')}</p>
        </div>

        <div className="contribute__grid">
          <div>
            <h3>{t('Build from source')}</h3>
            <div className="steps-install">
              {INSTALL.map((step, index) => (
                <div className="install" key={step.command}>
                  <span className="install__num">{String(index + 1).padStart(2, '0')}</span>
                  <div className="install__body">
                    <p className="install__text">{t(step.text)}</p>
                    <div className="codeblock">
                      <code>{step.command}</code>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div>
            <h3>{t('How to contribute')}</h3>
            <ul className="contribute__list">
              <li>
                <a href={`${REPO}/issues`} target="_blank" rel="noreferrer">
                  {t('Good first issues')}
                </a>
              </li>
              <li>
                <a href={repoLink('/CONTRIBUTING.md')} target="_blank" rel="noreferrer">
                  {t('Contributing')}
                </a>
              </li>
              <li>
                <a href={`${REPO}/pulls`} target="_blank" rel="noreferrer">
                  {t('Pull requests welcome')}
                </a>
              </li>
              <li>
                <a href={repoLink('/python/gui/supported_devices.json')} target="_blank" rel="noreferrer">
                  {t('Adding a model is a pull request away.')}
                </a>
              </li>
            </ul>
          </div>
        </div>
      </div>
    </section>
  )
}
