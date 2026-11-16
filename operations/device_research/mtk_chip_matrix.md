# MTK chip support matrix

Planning record for FlashPilot's MTK chip-coverage expansion, cross-checked
against upstream `bkerler/mtkclient` (`mtkclient/config/brom_config.py`, main)
and against the per-SoC parameter set published by the MIT-licensed
`chaanel/bypass_utility` project.

| | Chips |
|---|---|
| Before | 17 |
| Added — kamakiri2 (Group A) | 17 |
| Added — bypass_utility (Group B) | 18 |
| **After** | **52** |

Two exploit engines are now selected per chip:

- **kamakiri2** — CVE-2020-11152 line-coding overflow; needs `send_ptr` and
  `brom_reg_ptr`. Covers 2020-era and newer SoCs.
- **bypass_utility** — watchdog-adjacent pointer write + `0xE0` upload + USB
  control-transfer jump. Port of `chaanel/bypass_utility` (MIT). Covers older
  SoCs that predate CVE-2020-11152.

`MtkChipConfig::exploit` selects the engine; `payload` names the bundled BootROM
payload used by `BypassUtility`.

---

## Existing 17 (kamakiri2, unchanged)

| hw | Name | watchdog |
|---|---|---|
| `0x699` | MT6739/MT6731/MT8765 | `0x10007000` |
| `0x766` | MT6765/MT8768T | `0x10007000` |
| `0x707` | MT6768/MT6769 | `0x10007000` |
| `0x788` | MT6771/MT8385/MT8183/MT8666 | `0x10007000` |
| `0x725` | MT6779 | `0x10007000` |
| `0x1066` | MT6781 | `0x10007000` |
| `0x813` | MT6785 | `0x10007000` |
| `0x989` | MT6833 | `0x10007000` |
| `0x996` | MT6853 | `0x10007000` |
| `0x886` | MT6873 | `0x10007000` |
| `0x816` | MT6885/MT6883/MT6889/MT6890 | `0x10007000` |
| `0x950` | MT6891/MT6893 | `0x10007000` |
| `0x959` | MT6877/MT8791N | `0x10007000` |
| `0x1129` | MT6855 | `0x1c007000` |
| `0x1209` | MT6835V | `0x1C007000` |
| `0x6899` | MT6899 | `0x1C010000` ⚠ see note |
| `0x6781` | MT6781 | `0x10007000` |

> ⚠ **MT6899 watchdog** disagrees with upstream (`0x1C00B000`). Upstream also
> comments out its `send_ptr`/`brom_register_access`, so this entry is
> speculative either way. Needs hardware confirmation — see
> `mtk_gap_analysis.md` §7.2.

---

## Group A — 17 additions, kamakiri2

All `send_ptr`/`brom_reg_ptr` values verified against upstream mtkclient.
Four (`0x717`, `0x8127`, `0x8163`, `0x8590`) are also present in
bypass_utility's published config with identical values; the other 13 are
upstream-only.

| hw | Name | watchdog | send_ptr | brom_reg_ptr | var1 | Cross-check |
|---|---|---|---|---|---|---|
| `0x717` | MT6761/MT6762/MT3369/MT8766B/MT8761/AC8259/AC8257 | `0x10007000` | `0xbc8c` | `0xc158` | `0x25` | upstream + bypass_utility |
| `0x8127` | MT8127/MT3367/AC8227L | `0x10007000` | `0xb2b8` | `0xb740` | `0xA` | upstream + bypass_utility |
| `0x8163` | MT8163 | `0x10007000` | `0xc12c` | `0xc5c8` | `0xB1` | upstream + bypass_utility |
| `0x8590` | MT8590/MT7683/MT8521/MT7623 | `0x10007000` | `0xbbe4` | `0xc06c` | `0xA` | upstream + bypass_utility |
| `0x571` | MT0571 | `0x10007000` | `0xba68` | `0x40befc` | `0xA` | upstream |
| `0x1172` | MT6895 | `0x1c007000` | `0xE79C` | `0xec5c` | `0xA` | upstream |
| `0x1203` | MT6897 | `0x1c007000` | `0xE79C` | `0xec5c` | `0xA` | upstream |
| `0x1208` | MT6789/MT8781V | `0x10007000` | `0xE79C` | `0xfa0c` | `0xA` | upstream |
| `0x1229` | MT6886 | `0x1c007000` | `0xE79C` | `0xfa0c` | `0xA` | upstream |
| `0x1236` | MT6989W | `0x1C00B000` | `0xE79C` | `0xfa0c` | `0xA` | upstream |
| `0x1296` | MT6985 | `0x1C007000` | `0xE79C` | `0xfa0c` | `0xA` | upstream |
| `0x1357` | MT6991 | `0x1c010000` | `0xE79C` | `0xec5c` | `0xA` | upstream |
| `0x1375` | MT6878 | `0x1C00A000` | `0xE79C` | `0xfa0c` | `0xA` | upstream |
| `0x1471` | MT6993 | `0x1c010000` | `0xE79C` | `0xfa0c` | `0xA` | upstream |
| `0x2625` | MT2625 | `0x10007000` | `0xba68` | `0x40befc` | `0xA` | upstream |
| `0x6516` | MT6516 | `0x10003000` | `0x40ba68` | `0x40befc` | `0xA` | upstream |
| `0x8512` | MT8512 | `0x10007000` | `0xcc44` | `0xd194` | `0xA` | upstream |

---

## Group B — 18 additions, bypass_utility

These predate CVE-2020-11152, so kamakiri2 cannot reach them.

| hw | Name | watchdog | payload_addr | var1 | var0 | payload |
|---|---|---|---|---|---|---|
| `0x279` | MT6797/MT6767 | `0x10007000` | `0x100A00` | `0xA` | — | `mt6797_payload.bin` |
| `0x321` | MT6735/MT8735A | `0x10212000` | `0x100A00` | `0x28` | `0x10` | `mt6735_payload.bin` |
| `0x326` | MT6755/MT6750 | `0x10007000` | `0x100A00` | `0xA` | — | `mt6755_payload.bin` |
| `0x335` | MT6737M/MT6735G | `0x10212000` | `0x100A00` | `0x28` | `0x10` | `mt6737_payload.bin` |
| `0x337` | MT6753 | `0x10212000` | `0x100A00` | `0x28` | `0x10` | `mt6753_payload.bin` |
| `0x551` | MT6757/MT6757D | `0x10007000` | `0x100A00` | `0xA` | — | `mt6757_payload.bin` |
| `0x562` | MT6799 | `0x10211000` | `0x100A00` | `0xA` | — | `mt6799_payload.bin` |
| `0x690` | MT6763 | `0x10007000` | `0x100A00` | `0x7F` | — | `mt6763_payload.bin` |
| `0x6261` | MT6261/MT2503 | `0xA0030000` | `0x100A00` | `0x28` | — | `mt6261_payload.bin` |
| `0x6572` | MT6572 | `0x10007000` | `0x10036A0` | `0xA` | — | `mt6572_payload.bin` |
| `0x6580` | MT6580 | `0x10007000` | `0x100A00` | `0xAC` | — | `mt6580_payload.bin` |
| `0x6582` | MT6582/MT6574/MT8382 | `0x10007000` | `0x100A00` | `0xA` | — | `mt6582_payload.bin` |
| `0x6592` | MT6592/MT8392 | `0x10007000` | `0x100A00` | `0xA` | — | `mt6592_payload.bin` |
| `0x6595` | MT6595 | `0x10007000` | `0x100A00` | `0xA` | — | `mt6595_payload.bin` |
| `0x6795` | MT6795 | `0x10007000` | `0x100A00` | `0xA` | — | `mt6795_payload.bin` |
| `0x8167` | MT8167/MT8516/MT8362 | `0x10007000` | `0x100A00` | `0xCC` | — | `mt8167_payload.bin` |
| `0x8172` | **MT8173** | `0x10007000` | `0x120A00` | `0xA` | — | `mt8173_payload.bin` |
| `0x8695` | MT8695 | `0x10007000` | `0x100A00` | `0xA` | — | `mt8695_payload.bin` |

> **`0x8172` naming:** some Windows tuning tables name the payload
> `mt8172_payload.bin` and never ship it. Upstream maps hw `0x8172` to MT8173 and
> loads `mt8173_payload.bin`; that mapping is used here.

---

## The bypass_utility sequence

Ported from `chaanel/bypass_utility` `src/exploit.py`:

```text
addr = watchdog + 0x50
write32(addr, payload_address)

# prime the BROM read path
if var0 is Some(v):
    read32(addr - v, (v + 4) / 4)          # one read
else:
    for i in 0..15:
        n = 15 - i
        read32(addr - n*4, n + 1)          # 15 descending reads,
                                           # first (addr-60, 16), last (addr-4, 2)

echo(0xE0)
echo_dword(payload.len())
status = read_exact(2)                     # must be 00 00
write(payload)
read_exact(4)                              # discard clear
control_transfer(0xA1, 0, 0, var1, len 0)  # jump
read_exact(4)                              # success pattern
```

The priming sequence is implemented as a pure helper so the address/count
arithmetic is unit-testable without hardware.

---

## Payload provenance and licensing

- Payloads are `mt*_payload.bin` / `generic_*_payload.bin` from
  **`bkerler/mtkclient`** (GPLv3).
- They are aggregated under `payloads/mtk/` as separate works invoked at
  runtime — not linked into the MIT-licensed crate. See
  `payloads/mtk/README.md`.
- Resolution order: `MTK_PAYLOAD_DIR` →
  `$XDG_DATA_HOME/flashpilot/payloads/mtk` (or
  `~/.local/share/flashpilot/payloads/mtk`, no root needed) →
  `<exe_dir>/payloads/mtk`.
- The `.deb` installs the bundle to
  `/usr/lib/flashpilot/payloads/mtk`; `build.rs` copies it next to
  `target/<profile>/` for in-source runs, so release binaries never bake in a
  build-machine path.
- `flashpilot-bridge mtk-payload-check` lists every bypass chip and whether
  its payload resolves — no device required. On a protected chip a missing
  payload is a hard error (exit 1) naming the file and all three fix paths; an
  unprotected chip still works, because it needs no auth bypass.
- FlashPilot still ships no DA/loader images; those remain user-supplied.

## Caveats

1. **No hardware validation.** Every added entry is table data from upstream
   mtkclient and bypass_utility.
   The exploit engines themselves are unchanged on the kamakiri2 side; the
   bypass_utility path is new and unproven on a device.
2. **MT6899 watchdog** remains unresolved (§7.2).
3. **Older SoCs may need more than the pointers.** Some pre-2014 parts also
   require blacklist patching or a different crash method; the table carries
   only what bypass_utility's config uses.
4. The `ptr_usbdl`/`ptr_da` fields used by Windows tuning tables were
   deliberately **not** imported — they are a different abstraction from
   mtkclient's `send_ptr`/`brom_register_access`, and mixing the two silently
   breaks the exploit.
