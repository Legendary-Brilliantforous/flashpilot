# Moto G6 (ali) — SDM450 — FRP
Chip: Snapdragon 450 (SDM450)
Engine: qcom (fastboot)
VID: 22b8 (observed live: 22b8:2e80 fastboot · 22b8:2e2c MTP · 22b8:2eb7 mass-storage)
Status: researched
Actions: frp, info, flash, screen_lock
Live: ZY322PSBZ2, fastboot 22b8:2e80@2:9, MTP 22b8:2e2c, no ADB in FRP lock
FRP: QR fake-login in the wizard (MDM ▸ Generate QR → device-owner enrollment → ADB authorize → FRP clear), the CVE-2016-10277 chain where the bootloader predates the initrd filter (ali's 2020 MBM content-filters it — flow reports honestly), the factory-bootmode cycle (fb_mode_set → reboot ×3 → tap authorize → wipe, flag restored), or browser/emergency wizard escapes (Android 8/9 Verify account). `erase frp` needs an unlocked bootloader (per-device server-issued code; the Android-side OEM-unlocking toggle must be ON).
Notes: EDL 9008 test-point only; no BROM/DA like MTK.
