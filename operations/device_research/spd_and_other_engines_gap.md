# SPD/Unisoc and other engines — capability register

**Scope:** FlashPilot's Spreadtrum/Unisoc transport plus the engines it
deliberately does not implement (LG, Apple restore, vendor-specific flashers).
Static analysis plus corpus review; no device was touched.

---

## 1. Executive summary

- FlashPilot implements the SPD/Unisoc download path natively: FDL upload,
  partition list/format/backup/readback, FRP wipe, factory reset, SPL patch,
  magic pack, boot-to-download.
- The corpus carries **94 SPD rows**; **45 are in the database**, 49 are not
  (mostly iTel).
- Everything else in this space — LGUP/KDZ, Huawei update tooling, Apple
  restore — is out of scope on Linux, and that is a design decision, not a
  backlog item.

---

## 2. What the engine does

### 2.1 Entry points (`src/spd.rs`)

| Function | Purpose |
|----------|---------|
| `detect_spd()` | detect SPD/Unisoc devices (VID 0x1782) |
| `spd_detect_cli()` | CLI detection |
| `spd_info_cli()` | chip, version, security state |
| `spd_partitions_cli()` | list partitions |
| `spd_flash_cli()` / `spd_flash_cli_v()` | flash firmware |
| `spd_format_cli()` | format partitions |
| `spd_backup_cli()` | back up partitions |
| `spd_readback_cli()` | readback partitions |
| `spd_frp_cli()` | FRP wipe (frp, nvdata, persistent) |
| `spd_reset_cli()` | factory reset |
| `spd_spl_patch_cli()` | SPL patch (bypass security checks) |
| `spd_magic_pack_cli()` | build a custom pack |
| `spd_boot_cli()` | boot to download mode |

### 2.2 Commands

| Command | Operation |
|---------|-----------|
| `spd-detect` | detect SPD/Unisoc devices |
| `spd-info` | device info |
| `spd-partitions` | list partitions |
| `spd-flash` | flash firmware |
| `spd-format` | format partitions |
| `spd-backup` | back up partitions |
| `spd-readback` | readback partitions |
| `spd-frp` | FRP bypass |
| `spd-reset` | factory reset |
| `spd-spl-patch` | SPL patch |
| `spd-magic-pack` | magic pack creation |
| `spd-boot` | boot to download mode |

### 2.3 Protocol coverage

- **Detection** — VID `0x1782`, download-mode PIDs (0x0001, 0x0002).
- **FDL upload** — FDL1/FDL2 staging, BSL handshake, baud switch.
- **Partition work** — list, format, backup, readback, exec.
- **Security** — SPL patch (erase/rewrite of the signature check region),
  magic-pack construction for signed-pack devices.
- **IMEI** — reuses the shared MTK/SPD flow helpers; there is no SPD-specific
  NV writer.
- **NVRAM** — backup via `SP_META_*`-equivalent operations.

### 2.4 Device coverage

Any Unisoc device that exposes download mode is reachable once FDL1/FDL2 and
firmware are supplied. The database carries 59 SPD models, notably:

- Samsung A03/A03s/A03 Core (T606/SC9863A)
- Tecno/Infinix T6xx models
- Oppo/Realme budget models (SC9863A)
- iTel (24 models, all SPD)
- Nokia and Lava Unisoc models

---

## 3. Samsung / Odin

Odin is implemented natively (`odin-*`), including PIT read/write, tar and
multi-file flash (BL/AP/CP/CSC), and an MTK variant path. Samsung FRP, factory
reset, ADB enable and Knox/KG operations ride `src/flows.rs` and are
audit-logged.

Gaps:

- **Write-PIT is destructive and lightly tested.** It needs a mandatory PIT
  backup and a second confirmation before it is considered safe.
- **No Heimdall interop.** Not needed — the native path covers the same devices
  without the `libusb` quirks Heimdall carries.
- **No LGUP/KDZ.** LG firmware arrives as KDZ archives and needs LG's own
  protocol; LG has also exited the phone business, so the database bucket was
  removed.

## 4. Apple

`apple-detect` and `apple-info` cover normal/recovery/DFU enumeration. There is
no restore/update flow: that requires a signed IPSW chain and is out of scope.

## 5. Vendor-specific flashers

| Area | Status | Rationale |
|---|---|---|
| LGUP/KDZ | absent | Windows-only, dead vendor |
| Huawei `update.app` / Kirin flashing | absent | Needs vendor signing; Kirin FRP is an open research gap instead |
| Xiaomi fastboot ROM | covered by `fastboot-*` + `unified-flash` | No vendor tooling needed |
| Motorola blank-flash | `moto_flash.rs` path | Native |
| Apple restore | absent | Signed IPSW chain |

The pattern is consistent: implement the transport, require the user to supply
firmware, never bundle a vendor EXE.

---

## 6. Gaps and risks

| Gap | Impact | Effort |
|---|---|---|
| SPL patch hardware-unverified | Advertised operation may fail on secured devices | M |
| 49 SPD catalogue rows unimported | iTel-heavy list understates coverage | S |
| No SPD-specific NV/IMEI writer | IMEI work depends on shared helpers | M |
| Write-PIT safety | One bad PIT can hard-brick | S/M |
| No SPD 5G (T7xx) validation | Newer Unisoc parts may need a different FDL stage | M |

## 7. Recommendations

1. Import the remaining 49 SPD rows (mostly iTel A12–A60 / Vision / S-series).
2. Validate SPL patch on a secured SC9863A device before promoting it from
   `partial`.
3. Add PIT backup + double confirmation around `odin-send-pit`.
4. Add a SPD NV/IMEI writer behind the existing token gate and audit log.
5. Add SPD 5G (T7xx) to the FDL matrix once a device is available.

## 8. Conclusion

SPD/Unisoc coverage is protocol-complete for the 4G parts FlashPilot targets.
The remaining work is validation and device-list breadth; the non-goals (LG,
Huawei vendor flashing, Apple restore) stay non-goals.
