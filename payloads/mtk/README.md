# MediaTek BROM payloads

These files are MediaTek BootROM (BROM) exploit payloads taken from the
[`bkerler/mtkclient`](https://github.com/bkerler/mtkclient) project
(upstream source: <https://github.com/bkerler/mtkclient/tree/main/payloads>).
They are aggregated here so `flashpilot-bridge` can resolve and upload them at
runtime through `BypassUtility` on pre-2020 SoCs where kamakiri2 does not apply.

## Licensing

* mtkclient is distributed under the **GNU General Public License v3.0**
  (GPLv3). See <https://github.com/bkerler/mtkclient/blob/main/LICENSE> and
  <https://www.gnu.org/licenses/gpl-3.0.html>.
* The `flashpilot-bridge` crate itself is MIT-licensed. These payload binaries
  are **separate works**: they are neither compiled into nor linked with the
  crate. They are shipped as standalone data files, invoked as opaque blobs at
  runtime, and remain covered by GPLv3.
* Redistributing this directory therefore carries GPLv3 obligations for these
  files. If you modify or redistribute them, keep this notice and the upstream
  license with them.

## Contents

* `mt<chip>_payload.bin` — per-SoC bypass_utility payloads (e.g.
  `mt6580_payload.bin`, `mt8173_payload.bin`).
* `generic_*_payload.bin` — chip-independent helper payloads (dump, loader,
  patcher, reboot, stage1, UART dump).

Not included on purpose: `da_x.bin`, `pl.bin`, `stage2.bin` (DA/preloader
images, not bypass_utility payloads).

## Runtime lookup order

`flashpilot_bridge::mtk_exploit::resolve_payload(name)` searches:

1. `$MTK_PAYLOAD_DIR/<name>`
2. `<directory of the executable>/payloads/mtk/<name>`
3. `<crate source>/payloads/mtk/<name>` (development builds)

Set `MTK_PAYLOAD_DIR` to point at your own mtkclient checkout if you prefer not
to use the bundled copies.

## Current usage (chip table)

The 52-chip table in `src/mtk_exploit.rs` references 18 `*_payload.bin` files via the
`MtkChipConfig::bypass()` entries:

| Chip (hw code) | Payload filename | Platform |
|----------------|------------------|----------|
| `0x0279` (MT6797/MT6767) | `mt6797_payload.bin` | MT6797 |
| `0x321` (MT6735/T/MT8735A) | `mt6735_payload.bin` | MT6735 |
| `0x326` (MT6755/MT6750) | `mt6755_payload.bin` | MT6755 |
| `0x335` (MT6737M/MT6735G) | `mt6737_payload.bin` | MT6737 |
| `0x337` (MT6753) | `mt6753_payload.bin` | MT6753 |
| `0x551` (MT6757/MT6757D) | `mt6757_payload.bin` | MT6757 |
| `0x562` (MT6799) | `mt6799_payload.bin` | MT6799 |
| `0x690` (MT6763) | `mt6763_payload.bin` | MT6763 |
| `0x6261` (MT6261/MT2503) | `mt6261_payload.bin` | MT6261 |
| `0x6572` (MT6572) | `mt6572_payload.bin` | MT6572 |
| `0x6580` (MT6580) | `mt6580_payload.bin` | MT6580 |
| `0x6582` (MT6582/MT6574/MT8382) | `mt6582_payload.bin` | MT6582 |
| `0x6592` (MT6592/MT8392) | `mt6592_payload.bin` | MT6592 |
| `0x6595` (MT6595) | `mt6595_payload.bin` | MT6595 |
| `0x6795` (MT6795) | `mt6795_payload.bin` | MT6795 |
| `0x8167` (MT8167/MT8516/MT8362) | `mt8167_payload.bin` | MT8167 |
| `0x8172` (MT8173) | `mt8173_payload.bin` | MT8173 |
| `0x8695` (MT8695) | `mt8695_payload.bin` | MT8695 |

**Note:** The chip table also defines 34 kamakiri2 entries (no payload required) and 17 existing entries, for a total of 52 chips. The payloads above are only the 18 bypass_utility entries.

### Bundled but currently unused

The following 27 payload files are bundled but not yet referenced by any chip entry:

- `mt6739_payload.bin`
- `mt6758_payload.bin`
- `mt6761_payload.bin`
- `mt6765_payload.bin`
- `mt6768_payload.bin`
- `mt6771_payload.bin`
- `mt6779_payload.bin`
- `mt6781_payload.bin`
- `mt6785_payload.bin`
- `mt6833_payload.bin`
- `mt6853_payload.bin`
- `mt6873_payload.bin`
- `mt6877_payload.bin`
- `mt6885_payload.bin`
- `mt6893_payload.bin`
- `mt8127_payload.bin`
- `mt8163_payload.bin`
- `mt8512_payload.bin`
- `mt8590_payload.bin`
- `mt2601_payload.bin`
- `generic_dump_payload.bin`
- `generic_loader_payload.bin`
- `generic_patcher_payload.bin`
- `generic_preloader_dump_payload.bin`
- `generic_reboot_payload.bin`
- `generic_stage1_payload.bin`
- `generic_uart_dump_payload.bin`

These payloads are kept for future chip additions or alternative exploit methods. If you wish to reduce the bundle size, you can remove them, but ensure any future chip table entries that reference them are updated accordingly.
