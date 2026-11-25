import { useEffect, useMemo, useState } from 'react'

import { PROTOCOLS } from '../data/protocols'
import { useReducedMotion } from '../hooks/useReducedMotion'
import { t } from '../i18n'

export default function ProtocolConsole() {
  const reduced = useReducedMotion()
  const [activeId, setActiveId] = useState(PROTOCOLS[0].id)
  const [revealed, setRevealed] = useState(0)

  const active = useMemo(
    () => PROTOCOLS.find((protocol) => protocol.id === activeId) ?? PROTOCOLS[0],
    [activeId],
  )

  useEffect(() => {
    const steps = PROTOCOLS.find((protocol) => protocol.id === activeId)?.steps ?? []
    if (reduced) {
      setRevealed(steps.length)
      return
    }
    setRevealed(0)
    const timers = steps.map((_, index) =>
      window.setTimeout(() => setRevealed(index + 1), 200 + index * 360),
    )
    return () => timers.forEach((timer) => window.clearTimeout(timer))
  }, [activeId, reduced])

  const finished = revealed >= active.steps.length

  const stepState = (index: number) => {
    if (finished) return 'done'
    if (index < revealed - 1) return 'done'
    if (index === revealed - 1) return 'active'
    return 'pending'
  }

  return (
    <div className="panel console" id="protocols">
      <div className="console__bar">
        <span className="console__title">{t('handshake')}</span>
        <span className="console__status">
          <span className="console__dot" />
          {finished ? t('session ready') : t('negotiating')}
        </span>
      </div>

      <div className="console__tabs" role="tablist" aria-label={t('Bootloader protocol')}>
        {PROTOCOLS.map((protocol) => (
          <button
            key={protocol.id}
            type="button"
            role="tab"
            id={`tab-${protocol.id}`}
            aria-selected={protocol.id === activeId}
            aria-controls={`panel-${protocol.id}`}
            className="console__tab"
            onClick={() => setActiveId(protocol.id)}
          >
            {protocol.vendor}
          </button>
        ))}
      </div>

      <div
        className="console__body"
        role="tabpanel"
        id={`panel-${active.id}`}
        aria-labelledby={`tab-${active.id}`}
      >
        <div className="console__meta">
          <span className="tag tag--gold">{active.protocol}</span>
          <span className="tag">usb {active.usbId}</span>
          <span className="tag">{active.source}</span>
        </div>

        <div className="wire" aria-hidden="true">
          <span className="wire__node">{t('this linux host')}</span>
          <span className="wire__track">
            <i className="wire__pulse" />
          </span>
          <span className="wire__node">{t('phone in {vendor} mode', { vendor: active.vendor })}</span>
        </div>

        <p className="console__entry">{t(active.entry)}</p>

        <ol className="steps">
          {active.steps.map((step, index) => (
            <li className="step" key={step.title} data-state={stepState(index)}>
              <span className="step__idx">{String(index + 1).padStart(2, '0')}</span>
              <div>
                <div className="step__title">{t(step.title)}</div>
                <code className="step__wire">{step.wire}</code>
                <div className="step__note">{t(step.note)}</div>
              </div>
            </li>
          ))}
        </ol>
      </div>

      <div className="console__foot">
        <span>{active.cli}</span>
      </div>
    </div>
  )
}
