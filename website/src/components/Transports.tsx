import { FIGURES, TRANSPORTS } from '../data/site'

export default function Transports() {
  return (
    <section className="section" id="transports">
      <div className="wrap">
        <div className="section__head">
          <h2>One bridge, {FIGURES.modes} ways in</h2>
          <p>
            The flow registry covers {FIGURES.modes} transport modes across {FIGURES.jobs} job
            categories. A phone is detected through whichever interface it exposes, and the same
            console drives every operation from there.
          </p>
        </div>

        <div className="transports">
          {TRANSPORTS.map((transport) => (
            <div className="transport" key={transport.name}>
              <span className="transport__name">{transport.name}</span>
              <span className="transport__desc">{transport.desc}</span>
              <span className="transport__id">{transport.usb}</span>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
