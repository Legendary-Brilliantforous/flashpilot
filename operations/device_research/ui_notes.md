# Device hub — layout decisions

Notes on how FlashPilot's GUI presents devices and actions, and why it is laid
out this way. It supersedes the earlier UI study, which described another
product's managed layer and contained no reusable code — only a few layout
lessons, recorded here.

Source of truth: `python/gui/devices.py`, `python/gui/nav.py`,
`python/gui/qt_app.py`, `python/gui/widgets/action_row.py`,
`python/gui/theme.py`.

---

## 1. Shape of the app

```
┌──────────────┬──────────────────────────────────────────────────────┐
│ nav rail     │  section content                                     │
│  Samsung     │                                                      │
│  General     │   ┌ brand grid ─┬─ model grid ─┬─ model board ──┐   │
│  FUS         │   │  Xiaomi     │  Redmi 13C   │  ▸ Flash       │   │
│  MTK         │   │  Oppo       │  Note 12     │  ▸ Info        │   │
│  Qualcomm    │   │  SPD        │  …           │  ▸ FRP         │   │
│  SPD         │   └─────────────┴──────────────┴────────────────┘   │
│  Settings    │                                                      │
└──────────────┴──────────────────────────────────────────────────────┘
```

The rail is the primary axis: one entry per OEM (built from
`supported_devices.json`) plus one per engine section. It is not a menu tree —
there is no modal "select operation" dialog anywhere in the flow.

## 2. Three-level drill-down

1. **Brand** — rail entry, or a card in the brand grid. Cards are built from the
   database, not hardcoded, so adding a bucket adds a card with no UI change.
2. **Model** — a scrollable grid of model cards. Each card shows the model name
   and a sub-label carrying the mode/engine chip (`mtk`, `qcom`, `spd`, `odin`,
   `apple`) plus the chipset string.
3. **Model board** — a stack of full-width `ActionRow` cards, one per action the
   engine supports, plus a back affordance. This is the only place from which an
   operation can be launched.

The board is reached with a back stack, so the user never loses the model they
were on when an operation fails.

## 3. Capability gating, not role gating

Rules that the board enforces:

- **Lit, not hidden.** An action the engine supports is rendered even when the
  device is not currently connected; it is disabled until the required transport
  appears. Hiding unsupported actions made testers think the app had lost a
  feature.
- **Transport-aware.** `apply_applicability()` walks the visible rows and
  disables any whose `required_transports()` set is not satisfied by the live
  device (e.g. an FRP ADB path needs `ADB`, an Odin flash needs `ODIN`).
- **Status-aware.** `status: "planned"` models render every action disabled and
  the card is visibly marked; the model still appears so the research list is
  honest about its size.
- **Honest tooltips.** Every row carries the bridge command that will run, e.g.
  `qcom-detect`, `mtk-frp-brom`. A row that names no command is a bug.

## 4. Visual language

- **Risk edge.** Each `ActionRow` paints a 3 px left edge: `err` for
  wipe/destructive actions, `accent_hi` otherwise. Same language as
  `MethodCard.set_risk` in the flow browser, so "red edge = this deletes
  something" is learned once.
- **One-line descriptions.** Row descriptions are elided, never wrapped; a long
  flow label used to force the board wider than its pane.
- **Chips.** Engine/mode chips use the `chip_blue` / `chip_text` tokens; the
  same chip appears on the connected-device bar so the label is consistent
  between "this model is MTK" and "this attached device is in BROM".
- **Focus ring.** Rows are `StrongFocus` and activate on Enter/Return/Space, so
  the board is usable without a mouse.
- **Tokens only.** No literal colours in page code; everything comes from
  `theme.C`, which is also what the themes swap (`Slate Professional`, etc.).

## 5. Connected-device bar

`buckets_from_rows()` groups live USB rows into `samsung`, `mtk`, `spd`, `qcom`,
`adb`, `fastboot` buckets; the bar shows per-bucket counts and the current mode
label from `mode_hint`. Selecting a bucket filters the device list, which is how
a bench with five phones attached stays legible.

`connected_rows()` is cached and invalidated on USB events rather than polled
per repaint.

## 6. Hub pages

Beyond the brand drill-down there are three transport-first hubs:

| Hub | Purpose |
|---|---|
| `build_adb_hub_page` | actions available over plain ADB (FRP, info, reboot, shell) |
| `build_fastboot_hub_page` | fastboot actions (boot image, vbmeta, slot queries) |
| `build_easylogin_hub_page` | one-tap flows that chain several transports |

These exist because some operations are transport-first, not model-first: a user
with an unknown device in ADB should not have to find a brand card first.

## 7. Deliberate non-features

Decisions taken against the common layout in commercial suites:

| Not built | Why |
|---|---|
| Licence/activation dialog | No activation exists; a fake one would be dishonest UI |
| Server-side loader download | Every flash uses local, user-supplied firmware |
| Nested "choose operation" modals | The model board is the chooser; modals lose context |
| Status text built from subprocess substring matching | Structured bridge output drives state instead |
| Hidden disabled actions | Replaced with lit-but-disabled + tooltip |

## 8. Known gaps

1. **No device picker for an ambiguous bus.** The bridge refuses to guess
   (`find_mtk_dev("auto")`), but the UI has no way to disambiguate.
2. **Permission failures look like absence.** A missing udev rule should surface
   as "no access to 0e8d:0003", not "no device".
3. **Model search is linear.** The 719-model database deserves a filter box
   before it grows further.

These are tracked in `usb_detection_gap.md` §4 and `feature_logic_matrix.md` §9.
