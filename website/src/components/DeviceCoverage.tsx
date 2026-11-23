import { BRANDS, FIGURES, repoLink } from '../data/site'

export default function DeviceCoverage() {
  return (
    <section className="section" id="devices">
      <div className="wrap">
        <div className="section__head">
          <h2>The catalogue says "researched" only when it is</h2>
          <p>
            Every model in the device database carries its chipset, USB vendor id and the engine
            that drives it. Actions light up for the {FIGURES.researched} models whose flow set has
            actually been wired and tested — the rest are marked planned rather than claimed.
          </p>
        </div>

        <div className="coverage__stats">
          <div>
            <div className="stat__value">{FIGURES.brands}</div>
            <div className="stat__label">brands catalogued</div>
          </div>
          <div>
            <div className="stat__value">{FIGURES.models}</div>
            <div className="stat__label">device models listed</div>
          </div>
          <div>
            <div className="stat__value">{FIGURES.researched}</div>
            <div className="stat__label">models with a verified action set</div>
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
          The catalogue is a JSON file in the repository:{' '}
          <a href={repoLink('/python/gui/supported_devices.json')} target="_blank" rel="noreferrer">
            supported_devices.json
          </a>
          . Adding a model is a pull request away.
        </p>
      </div>
    </section>
  )
}
