# apple/ — Apple device operations (top-level, not just FRP)
Shared Apple flows: iCloud, Activation Lock, MDM — uses checkm8 DFU (A9–A11) + usbmuxd/lockdownd for A12+.

```
apple/
  icloud/                  — iCloud remove/add (EXPERIMENTAL, A9–A11 DFU 05ac:1227, ramdisk)
  activation_lock/         — Activation Lock (Find My) bypass paths
  mdm/                     — Apple MDM / DEP removal (profile, ABM)
  enterprise_remote_lock/  — Enterprise remote lock (MDM/DEP remote lock clear)
  lost_mode_remove/        — Lost Mode remove (Find My lost mode)
  passcode_lock_remove/    — Passcode / Screen Time remove
```

Sources: Rust flows (`src/flows.rs` registry, `flow-run` CLI): `apple_info`, `apple_passcode_guide`, `apple_icloud_remove/add`; USB 05ac handling in `src/usb/`.
(The old `python/core/apple.py` engine module was retired when the flows moved to Rust; `python/core/flows/apple` was planned but never shipped.)
All lock removes live here now (not under carrier_unlock).
