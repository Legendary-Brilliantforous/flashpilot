# Bundled MediaTek DA containers — attribution

`MTK_DA_V5.bin` / `MTK_DA_V6.bin` are mtkclient's generic Download Agent
containers, from B. Kerler's mtkclient (https://github.com/bkerler/mtkclient),
**GPLv3** — the same source the BROM SLA keys in `src/mtk_sla_keys.rs` are
derived from.

They are parsed natively by `src/mtk_daloader.rs` (container format,
per-chip DA entries, stage-1 region slicing) and drive
`mtk-frp-brom` — FRP removal for ANY MediaTek device via BROM with no
user-supplied DA.

- V5 (LEGACY DA protocol — this engine's native protocol): covers the
  65xx/67xx/68xx budget SoCs (dacodes 0x6570..0x6893).
- V6 (XML DA protocol): fallback for newer SoCs only; the native engine
  cannot drive XML-mode DAs, so V5 entries always win.

Per the GPLv3, modifying or redistributing these files keeps them under the
same license with this attribution intact.
