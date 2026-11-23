import { useState } from 'react'

import { INSTALL } from '../data/site'

function CopyButton({ value }: { value: string }) {
  const [copied, setCopied] = useState(false)

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(value)
    } catch {
      // Clipboard access can be blocked; the command is still selectable.
    }
    setCopied(true)
    window.setTimeout(() => setCopied(false), 1600)
  }

  return (
    <button type="button" className="copy" onClick={copy} data-state={copied ? 'copied' : 'idle'}>
      {copied ? 'Copied' : 'Copy'}
    </button>
  )
}

export default function QuickStart() {
  return (
    <section className="section" id="install">
      <div className="wrap">
        <div className="section__head">
          <h2>Build it in four commands</h2>
          <p>
            A Rust toolchain, Python 3.10 and a Linux desktop. That is the whole dependency list —
            libusb is vendored, so nothing has to be installed system-wide.
          </p>
        </div>

        <div className="steps-install">
          {INSTALL.map((step, index) => (
            <div className="install" key={step.command}>
              <span className="install__num">{String(index + 1).padStart(2, '0')}</span>
              <div className="install__body">
                <p className="install__text">{step.text}</p>
                <div className="codeblock">
                  <code>{step.command}</code>
                  <CopyButton value={step.command} />
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
