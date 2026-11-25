import { SHOTS } from '../data/site'
import { t } from '../i18n'

export default function Gallery() {
  return (
    <section className="section" id="studio">
      <div className="wrap">
        <div className="section__head">
          <h2>{t('The studio')}</h2>
          <p>
            {t(
              'A frameless window with a live connection banner, a device list on the left, the operation pages in the middle and the protocol console on the right. One phone or several, running side by side.',
            )}
          </p>
        </div>

        <div className="gallery">
          {SHOTS.map((shot) => (
            <figure className="shot" key={shot.file}>
              <img src={shot.file} alt={t('{title} view in the FlashPilot studio', { title: shot.title })} loading="lazy" />
              <figcaption>
                <b>{shot.title}</b> — {t(shot.caption)}
              </figcaption>
            </figure>
          ))}
        </div>
      </div>
    </section>
  )
}
