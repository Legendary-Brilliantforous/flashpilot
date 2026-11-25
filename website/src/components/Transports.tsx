import { FIGURES, TRANSPORTS } from '../data/site'
import { t } from '../i18n'

export default function Transports() {
  return (
    <section className="section" id="transports">
      <div className="wrap">
        <div className="section__head">
          <h2>{t('One bridge, {modes} ways in', { modes: FIGURES.modes })}</h2>
          <p>
            {t(
              'The flow registry covers {modes} transport modes across {jobs} job categories. A phone is detected through whichever interface it exposes, and the same console drives every operation from there.',
              { modes: FIGURES.modes, jobs: FIGURES.jobs },
            )}
          </p>
        </div>

        <div className="transports">
          {TRANSPORTS.map((transport) => (
            <div className="transport" key={transport.name}>
              <span className="transport__name">{transport.name}</span>
              <span className="transport__desc">{t(transport.desc)}</span>
              <span className="transport__id">{transport.usb}</span>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
