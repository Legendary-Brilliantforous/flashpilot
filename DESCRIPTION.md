# FlashPilot

Open-source Linux flashing & repair workbench for Android devices — the free
equivalent of commercial Windows flashing suites.

A native **Rust** core (`flashpilot-bridge`, ~9,300 LOC, vendored libusb) speaks the
bootloader protocols directly — Samsung Odin/HID, MediaTek BROM/DA, Qualcomm
Sahara/Firehose, and Spreadtrum/UNISOC BSL — while a polished **PyQt6** studio
presents 8 transport modes, 8 job categories and ~120 operations: firmware
flashing, FRP bypass, screen-lock removal, MDM unlock, partition backup/flash,
device info, reboot, and battery/network repair on any ADB device.

- **Platform:** Linux
- **Language:** Rust (core) + Python 3 / PyQt6 (UI)
- **License:** MIT
- **Status:** actively developed — contributors welcome

Use it on devices you own or are authorized to service.