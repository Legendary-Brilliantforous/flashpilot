import { SHOTS } from '../data/site'

export default function Gallery() {
  return (
    <section className="section" id="studio">
      <div className="wrap">
        <div className="section__head">
          <h2>The studio</h2>
          <p>
            A frameless window with a live connection banner, a device list on the left, the
            operation pages in the middle and the protocol console on the right. One phone or
            several, running side by side.
          </p>
        </div>

        <div className="gallery">
          {SHOTS.map((shot) => (
            <figure className="shot" key={shot.file}>
              <img src={shot.file} alt={`${shot.title} view in the FlashPilot studio`} loading="lazy" />
              <figcaption>
                <b>{shot.title}</b> — {shot.caption}
              </figcaption>
            </figure>
          ))}
        </div>
      </div>
    </section>
  )
}
