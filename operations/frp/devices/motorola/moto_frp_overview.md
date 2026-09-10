# Motorola / Lenovo — FRP reset (FlashPilot implementation)

Status: implemented
Chip: Qualcomm Snapdragon (most Moto G/E/Edge series) or MediaTek (some G/Edge)
VID: 22b8 (Motorola)
Transports: ADB, FASTBOOT

## Flows

| Flow key | Transport | What it does |
|---|---|---|
| `moto_frp_adb` | ADB | Zeroes the `frp` secure setting, marks setup complete / device provisioned, removes the persisted FRP store, disables Google + Motorola setup wizards. |
| `moto_frp_fastboot` | FASTBOOT | Reads lock state, guides the official unlock-token flow, then `erase frp` + `erase cache` with session resets. |
| `moto_oem_unlock_token` | FASTBOOT | Read-only: dumps `oem get_unlock_data` and explains the unlock-code request. |

These flows are **brand-wide, not per-model**: they appear under Motorola →
All Motorola / Lenovo (universal) and every Moto model page, with the vendor
detected at runtime. The fastboot legs run over the **native Rust fastboot
transport** (`fastboot-cmd`, target-pinned `vid:pid@bus:addr`, kernel-driver
detach) and fall back to the system `fastboot` binary only when the bridge
has no matching device.

## Technique notes (clean-room, derived from public Motorola fastboot/ADB behavior)

- **ADB path** is the same class of provisioning reset used on other Android
  devices (`settings put secure frp 0`, `user_setup_complete`, `device_provisioned`,
  `setup_wizard_has_run`, removal of `/data/system/frp`, and setup-wizard disable).
  Motorola additionally exposes a `com.motorola.setupwizard` package to disable.
  This only works when an ADB shell is already authorized.

- **Fastboot path** is gated by Motorola's per-device bootloader key. The
  sequence is `oem get_unlock_data` → Motorola unlock portal
  (`https://en-us.support.motorola.com/app/standalone/bootloader/unlock-your-device-a`
  — the old `motorola.com/unlockbootloader` address is dead; sign-in required;
  Verizon/AT&T/Tracfone models are not eligible)
  → 20-char code → `oem unlock <code>` (wipes) → `erase frp` + `erase cache`.

## Honest limits

- The **unlock code is server-issued per device**. No local tool — FlashPilot
  included — can generate it offline. The fastboot flow automates the fastboot
  steps but the user must fetch the code from Motorola's portal.
- Some **carrier variants disable `oem unlock` entirely**; on those, the ADB
  path is the only route, and it requires an already-authorized ADB shell.
- FRP removal on a device you don't own or aren't authorized to service may be
  illegal in your jurisdiction.

## Related device notes

- `moto_g6.md` — Moto G6 (SDM450), legacy Android 8/9 browser/emergency FRP.
- `../mdm/devices/motorola/` — Motorola MDM flows.