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

Sources: `python/core/apple.py`, `python/core/flows/apple` (planned), `src/` usb 05ac handling.
All lock removes live here now (not under carrier_unlock).
