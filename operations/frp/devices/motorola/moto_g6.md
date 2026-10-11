# Moto G6 (ali) — SDM450 — FRP
Chip: Snapdragon 450 (SDM450)
Engine: qcom (fastboot)
VID: 22b8 (PID 2e82 MTP vendor)
Status: researched
Actions: frp, info, flash, screen_lock
Live: ZY322PSBZ2, 22b8:2e82@2:37, iface 255/255/0 MTP, no ADB, no fastboot in FRP lock
FRP: QR fake-login in the wizard (6-tap scanner → device-owner enrollment → ADB authorize → FRP clear), browser/emergency wizard escapes (Android 8/9 Verify account), or the CVE-2016-10277 fastboot chain where the bootloader predates the initrd filter. `erase frp` needs an unlocked bootloader (Vol Down+Power to bootloader; unlock code is per-device, server-issued).
Notes: EDL 9008 test-point only; no BROM/DA like MTK.
