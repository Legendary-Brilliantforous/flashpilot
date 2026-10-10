# frp/ — Factory Reset Protection (Android only)

> Apple has no FRP (Apple uses Activation Lock / iCloud instead) — see `apple/`.

Per-engine documentation trees for FRP bypass. The **real code is in
`python/core/flows/`** (see [INDEX.md](./INDEX.md) for the full engine
map and flow-key table). This directory holds:

- One README per engine (`mtk_frp/`, `samsung_frp/`, `qualcomm_frp/`,
  `unisoc_frp/`, `generic_frp/`) explaining what that engine is for and
  where the actual code lives.
- `chips/` — placeholder for per-chip research notes. Most chips are
  handled by the engine-level dispatch in `python/core/flows/brom.py`,
  so per-chip files are only needed when a specific chipset needs
  manual offsets or an out-of-band workaround.
- `devices/<brand>/<model>.md` — per-device research notes (dump size,
  build fingerprint, partition map, the working FRP recipe). One model
  per file. Currently only Nokia G20 has a real note.

To add a new device FRP recipe, see [INDEX.md](./INDEX.md) § "How a
new per-model recipe lands here".
