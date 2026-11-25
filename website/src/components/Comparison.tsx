import { COMPARISONS } from '../data/site'
import { t } from '../i18n'

export default function Comparison() {
  return (
    <section className="section" id="compare">
      <div className="wrap">
        <div className="section__head">
          <h2>{t('The tools this replaces')}</h2>
          <p>
            {t(
              'The Android repair world runs on closed, Windows-only suites. Their protocols are reverse-engineered by a handful of people and locked inside paid software or scattered across forum threads. FlashPilot turns that knowledge into a codebase you can read, run and extend.',
            )}
          </p>
        </div>

        <div className="compare">
          <div className="compare__row compare__row--head">
            <span>{t('Commercial tool')}</span>
            <span>{t('Where it stops')}</span>
            <span>{t('What FlashPilot does')}</span>
          </div>
          {COMPARISONS.map((row) => (
            <div className="compare__row" key={row.tool}>
              <div className="compare__tool">{row.tool}</div>
              <div className="compare__old">{t(row.constraint)}</div>
              <div className="compare__new">{t(row.replacement)}</div>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
