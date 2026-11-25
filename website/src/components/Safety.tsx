import { SAFETY } from '../data/site'
import { t } from '../i18n'

function WarningIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true" fill="none">
      <path
        d="M8 1.6 15 14H1L8 1.6Z"
        stroke="#fbbf24"
        strokeWidth="1.4"
        strokeLinejoin="round"
      />
      <path d="M8 6v4" stroke="#fbbf24" strokeWidth="1.4" strokeLinecap="round" />
      <circle cx="8" cy="12" r="0.8" fill="#fbbf24" />
    </svg>
  )
}

export default function Safety() {
  return (
    <section className="section section--tight" id="safety">
      <div className="wrap">
        <div className="safety">
          <h3>{t('Before you plug anything in')}</h3>
          <p style={{ marginTop: 'var(--s3)' }}>
            {t(
              'FlashPilot writes to bootloaders. It can wipe a phone, and a wrong image can leave a device that will not start. These are not formalities.',
            )}
          </p>

          <div className="safety__list">
            {SAFETY.map((item) => (
              <div className="safety__item" key={item.title}>
                <WarningIcon />
                <div>
                  <b>{t(item.title)}</b>
                  <span>{t(item.text)}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  )
}
