import ProtocolConsole from './ProtocolConsole'
import { FIGURES, repoLink } from '../data/site'
import { t } from '../i18n'

export default function Hero() {
  return (
    <section className="hero" id="top">
      <div className="wrap hero__grid">
        <div>
          <h1>{t('Talk to the bootloader directly.')}</h1>
          <p className="hero__lead">
            {t(
              'FlashPilot is an open-source flashing and repair workbench for Linux. A Rust core speaks Samsung Odin, MediaTek BROM, Qualcomm Sahara and UNISOC BSL straight over USB; a PyQt6 studio puts every one of them behind a single console.',
            )}
          </p>

          <div className="hero__actions">
            <a className="btn btn--primary" href="#install">
              {t('Build from source')}
            </a>
            <a className="btn btn--ghost" href={repoLink('/README.md')} target="_blank" rel="noreferrer">
              {t('Read the documentation')}
            </a>
          </div>

          <ul className="hero__list">
            <li>{t('Flash firmware on Samsung, MediaTek, Qualcomm and UNISOC phones')}</li>
            <li>{t('Remove FRP, screen locks and MDM on any device with USB debugging')}</li>
            <li>{t('Read and back up partitions before you touch anything')}</li>
          </ul>

          <div className="hero__facts">
            <span>{t('MIT licensed')}</span>
            <span>{t('Linux native')}</span>
            <span>
              <b>{FIGURES.flows}</b> {t('registered flows')}
            </span>
            <span>
              <b>{FIGURES.models}</b> {t('device models catalogued')}
            </span>
          </div>
        </div>

        <ProtocolConsole />
      </div>
    </section>
  )
}
