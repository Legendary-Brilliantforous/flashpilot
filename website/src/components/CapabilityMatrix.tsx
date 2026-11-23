import { CAPABILITIES } from '../data/site'

function Cell({ text, tone }: { text: string; tone: 'yes' | 'no' }) {
  if (tone === 'no') {
    return <span className="cell-no">not supported</span>
  }
  return (
    <>
      <span className="cell-yes">supported</span>
      <br />
      <b>{text}</b>
    </>
  )
}

export default function CapabilityMatrix() {
  return (
    <section className="section" id="capabilities">
      <div className="wrap">
        <div className="section__head">
          <h2>What each chipset gets</h2>
          <p>
            The same work, four different wire protocols. Rows that touch Knox, QCN, IMEI or raw
            eMMC and UFS access sit behind the experimental gate and are audit logged.
          </p>
        </div>

        <div className="matrix-scroll">
          <table className="matrix">
            <thead>
              <tr>
                <th scope="col">Capability</th>
                <th scope="col">Samsung</th>
                <th scope="col">MediaTek</th>
                <th scope="col">Qualcomm</th>
                <th scope="col">UNISOC</th>
                <th scope="col">Any ADB device</th>
              </tr>
            </thead>
            <tbody>
              {CAPABILITIES.map((row) => (
                <tr key={row.name}>
                  <th scope="row">{row.name}</th>
                  <td>
                    <Cell {...row.samsung} />
                  </td>
                  <td>
                    <Cell {...row.mediatek} />
                  </td>
                  <td>
                    <Cell {...row.qualcomm} />
                  </td>
                  <td>
                    <Cell {...row.spd} />
                  </td>
                  <td>
                    <Cell {...row.adb} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="legend">
          <span>supported — the flow is wired and tested</span>
          <span>not supported — no implementation exists for that chipset</span>
        </div>
      </div>
    </section>
  )
}
