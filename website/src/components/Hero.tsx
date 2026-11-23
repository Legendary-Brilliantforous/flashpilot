import ProtocolConsole from './ProtocolConsole'
import { FIGURES, repoLink } from '../data/site'

export default function Hero() {
  return (
    <section className="hero" id="top">
      <div className="wrap hero__grid">
        <div>
          <h1>Talk to the bootloader directly.</h1>
          <p className="hero__lead">
            FlashPilot is an open-source flashing and repair workbench for Linux. A Rust core
            speaks Samsung Odin, MediaTek BROM, Qualcomm Sahara and UNISOC BSL straight over USB;
            a PyQt6 studio puts every one of them behind a single console.
          </p>

          <div className="hero__actions">
            <a className="btn btn--primary" href="#install">
              Build from source
            </a>
            <a className="btn btn--ghost" href={repoLink('/README.md')} target="_blank" rel="noreferrer">
              Read the documentation
            </a>
          </div>

          <ul className="hero__list">
            <li>Flash firmware on Samsung, MediaTek, Qualcomm and UNISOC phones</li>
            <li>Remove FRP, screen locks and MDM on any device with USB debugging</li>
            <li>Read and back up partitions before you touch anything</li>
          </ul>

          <div className="hero__facts">
            <span>
              <b>MIT</b> licensed
            </span>
            <span>
              <b>Linux</b> native
            </span>
            <span>
              <b>{FIGURES.flows}</b> registered flows
            </span>
            <span>
              <b>{FIGURES.models}</b> device models catalogued
            </span>
          </div>
        </div>

        <ProtocolConsole />
      </div>
    </section>
  )
}
