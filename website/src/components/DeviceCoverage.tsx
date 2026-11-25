import { BRANDS, FIGURES, repoLink } from '../data/site'
import { t } from '../i18n'

export default function DeviceCoverage() {
  return (
    <section className="section" id="devices">
      <div className="wrap">
        <div className="section__head">
          <h2>{t('The catalogue says "researched" only when it is')}</h2>
          <p>
            {t(
              'Every model in the device database carries its chipset, USB vendor id and the engine that drives it. Actions light up for the {researched} models whose flow set has actually been wired and tested — the rest are marked planned rather than claimed.',
              { researched: FIGURES.researched },
            )}
          </p>
        </div>

        <div className="coverage__stats">
          <div>
            <div className="stat__value">{FIGURES.brands}</div>
            <div className="stat__label">{t('brands catalogued')}</div>
          </div>
          <div>
            <div className="stat__value">{FIGURES.models}</div>
            <div className="stat__label">{t('device models listed')}</div>
          </div>
          <div>
            <div className="stat__value">{FIGURES.researched}</div>
            <div className="stat__label">{t('models with a verified action set')}</div>
          </div>
        </div>

        <div className="brands">
          {BRANDS.map((brand) => (
            <div className="brandcell" key={brand.name}>
              <span className="brandcell__name">{brand.name}</span>
              <span className="brandcell__count">{brand.models}</span>
            </div>
          ))}
        </div>

        <p style={{ marginTop: 'var(--s4)', fontSize: '0.875rem' }}>
          {t('The catalogue is a JSON file in the repository:')}{' '}
          <a href={repoLink('/python/gui/supported_devices.json')} target="_blank" rel="noreferrer">
            supported_devices.json
          </a>
          . {t('Adding a model is a pull request away.')}
        </p>
      </div>
    </section>
  )
}
