# Motorola / Lenovo — FRP reset (FlashPilot implementation)

Status: implemented
Chip: Qualcomm Snapdragon (most Moto G/E/Edge series) or MediaTek (some G/Edge)
VID: 22b8 (Motorola)
Transports: ADB, FASTBOOT

## Flows

| Flow key | Transport | What it does |
|---|---|---|
| `moto_frp_adb` | ADB | Zeroes the `frp` secure setting, marks setup complete / device provisioned, removes the persisted FRP store, disables Google + Motorola setup wizards. |
| `moto_frp_fastboot` | FASTBOOT | CVE-2016-10277 (initroot) chain: version + `fsg-id` UTAG gates, kernel-cmdline injection of a user-supplied initramfs (`--file` + `--partition` scratch address, never shipped), `continue` into root ADB, then the ADB wipe. |
| `frp_fake_login` / `frp_fake_login_testdpc` / `frp_fake_login_adp` | Wizard → ADB | QR provisioning with our DPC / TestDPC / Android Device Policy: enrolls as device owner in the setup wizard (6-tap QR scanner), completes setup, enables ADB, then clears FRP once authorized. |

The unlock-token flow (`moto_oem_unlock_token`) is retired: the 20-char
code is per-device and server-issued, so a tool-level token strategy is a
dead end. Bootloader unlock still runs through `fastboot_unlock --code`
once the Android-side OEM-unlocking toggle is on.

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

- **Fastboot path** is the CVE-2016-10277 (initroot) chain, staged with
  honest gates: bootloader-version check, `fsg-id` UTAG liveness read
  (`protected="false"` or stop), user-supplied per-device initramfs, then
  `oem config fsg-id a initrd=<addr>,<size>` + download-to-buffer +
  `continue` into a root ADB session that wipes FRP. Public research:
  alephsecurity/initroot. Newer bootloaders content-filter the injection —
  the flow reports that instead of pretending.
- **QR path** skips the Google/FRP check by provisioning a device owner
  before it: scan the generated QR on the wizard's Welcome screen, accept
  enrollment, tap OK on the ADB prompt, and the flow clears FRP.

## Honest limits

- A **bootloader unlock code is server-issued per device** (Motorola
  portal; Verizon/AT&T/Tracfone models are not eligible). No local tool —
  FlashPilot included — can generate it offline. `fastboot_unlock --code`
  automates the two-step confirm but needs the Android-side OEM-unlocking
  toggle ON first.
- The **initrd injection is patched on newer bootloaders** (2020+ builds
  content-filter `initrd=` even with an unprotected UTAG). The flow reads
  the UTAG and says so; the QR path is the realistic alternative there.
- Some **carrier variants disable `oem unlock` entirely**; on those, the ADB
  path is the only route, and it requires an already-authorized ADB shell.
- FRP removal on a device you don't own or aren't authorized to service may be
  illegal in your jurisdiction.

## Related device notes

- `moto_g6.md` — Moto G6 (SDM450), legacy Android 8/9 browser/emergency FRP.
- `../mdm/devices/motorola/` — Motorola MDM flows.