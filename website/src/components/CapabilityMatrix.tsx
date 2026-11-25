import { CAPABILITIES } from '../data/site'
import { t } from '../i18n'

function Cell({ text, tone }: { text: string; tone: 'yes' | 'no' }) {
  if (tone === 'no') {
    return <span className="cell-no">{t('not supported')}</span>
  }
  return (
    <>
      <span className="cell-yes">{t('supported')}</span>
      <br />
      <b>{t(text)}</b>
    </>
  )
}

export default function CapabilityMatrix() {
  return (
    <section className="section" id="capabilities">
      <div className="wrap">
        <div className="section__head">
          <h2>{t('What each chipset gets')}</h2>
          <p>
            {t(
              'The same work, four different wire protocols. Rows that touch Knox, QCN, IMEI or raw eMMC and UFS access sit behind the experimental gate and are audit logged.',
            )}
          </p>
        </div>

        <div className="matrix-scroll">
          <table className="matrix">
            <thead>
              <tr>
                <th scope="col">{t('Capability')}</th>
                <th scope="col">{t('Samsung')}</th>
                <th scope="col">{t('MediaTek')}</th>
                <th scope="col">{t('Qualcomm')}</th>
                <th scope="col">{t('UNISOC')}</th>
                <th scope="col">{t('Any ADB device')}</th>
              </tr>
            </thead>
            <tbody>
              {CAPABILITIES.map((row) => (
                <tr key={row.name}>
                  <th scope="row">{t(row.name)}</th>
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
          <span>{t('supported — the flow is wired and tested')}</span>
          <span>{t('not supported — no implementation exists for that chipset')}</span>
        </div>
      </div>
    </section>
  )
}
