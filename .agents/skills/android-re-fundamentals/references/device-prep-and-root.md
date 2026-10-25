# Device Preparation and Rooting

Getting a phone ready for reverse engineering means: drivers installed, bootloader unlocked, (ideally) a clean ROM flashed, and root obtained via Magisk. This document is brand-agnostic in principle but uses a Qualcomm Xiaomi device as the worked example because it represents the *hardest* common case (binding + wait period). Pixel/OnePlus are strictly easier.

> Replace every `<placeholder>` with your own value. Do not hardcode device serials or personal paths.

---

## Real device vs emulator

PC Android emulators (Genymotion, official AVD, and the various consumer emulators) are convenient — snapshots, multi-instance, disposable — but they are **easily detected** by hardened apps.

### How apps detect an emulator

| Signal | Real device | Emulator |
|--------|-------------|----------|
| `Build.MODEL` / `BRAND` / `HARDWARE` | concrete vendor values | `generic`, `goldfish`, `ranchu`, `sdk_gphone_*` |
| `Build.FINGERPRINT` | real device fingerprint | contains `generic`, `test-keys` |
| CPU architecture | ARM (arm64-v8a) | usually x86 / x86_64 |
| Sensors / battery / radio | full, realistic | missing or fixed values; IMEI all-zero |
| GL renderer | real GPU string | `SwiftShader`, `Android Emulator` |
| Marker files | absent | `/dev/qemu_pipe`, `/dev/goldfish_pipe`, vendor-specific `.so`/props |

No emulator perfectly emulates a real device — the x86-vs-ARM gap alone is hard to hide.

### Practical guidance

| Scenario | Emulator usable? |
|----------|------------------|
| Ordinary app traffic capture / static analysis | Yes |
| Basic dynamic debugging practice | Yes |
| Banking / finance apps | Generally no |
| Mainstream games (anti-cheat) | No |
| Packed / anti-debug apps | Often no |

**Recommendation:** use an emulator while learning and for quick tests; use a rooted real device for real targets. Keep both available.

---

## Step 1: Drivers and Platform Tools

Windows does not ship Android adb/fastboot drivers, so a freshly connected phone shows up as "unknown device."

| Driver source | Notes |
|---------------|-------|
| Google USB Driver | ships with the SDK Platform Tools, broadly compatible |
| Vendor driver | bundled with OEM flashing tools |
| Universal ADB Driver | one-click installers exist |

**Android SDK Platform Tools** provide the two core CLIs:

- **adb** — talks to the device while it is booted normally.
- **fastboot** — talks to the device while it is in bootloader/fastboot mode.

Download, extract to a stable path (e.g. `C:\platform-tools`), and add that path to the system `PATH`. Verify:

```bash
adb devices
# "<serial>    device" means connected
```

---

## Step 2: Enable developer options and USB debugging

1. Settings → About phone → tap the build/version number **7 times** to unlock Developer Options.
2. Settings → System → Developer options → enable **USB debugging**.
3. Re-run `adb devices` and accept the RSA authorization prompt on the phone.

---

## Core concepts

### Bootloader (BL) and the BL lock

The bootloader is the first program to run at power-on (analogous to BIOS/UEFI). It initializes hardware and verifies+loads the boot/system images. OEMs ship it **locked** so only officially signed images can boot. With the BL locked you cannot flash any third-party image — and you need to modify the `boot` partition (flash Magisk) to get root, so the BL must be unlocked first.

### Line-flash vs card-flash

| | Line-flash (fastboot) | Card-flash (recovery) |
|---|---|---|
| Method | USB cable + fastboot/OEM tool | zip placed on device, flashed via recovery |
| Mode | Fastboot / Download (Samsung Odin) | Recovery |
| Use | official firmware, un-brick, partition images | third-party ROMs, Magisk zips |

### Brand-by-brand unlock

- **Xiaomi** — bind account in Developer Options, then use Mi Unlock; has a mandatory wait period (often 168h / sometimes 72h).
- **OnePlus / Pixel** — `fastboot oem unlock` or `fastboot flashing unlock`, no wait.
- **Huawei** — official unlock codes were discontinued.
- **Samsung** — enable OEM unlock, then unlock from Download mode.

---

## Step 3: Unlock the bootloader (Xiaomi worked example)

1. **Bind the account**: Developer options → Mi Unlock status → bind account and device. This tells the vendor server you intend to unlock this device.
2. **Wait** the mandatory period (anti-theft; cannot be skipped).
3. **Unlock with Mi Unlock**:
   - Log into the bound account in the official Mi Unlock tool.
   - Power off, then hold **Volume-Down + Power** to enter Fastboot (fastboot logo).
   - Connect USB and click Unlock.

> Unlocking **wipes all data** — back up first. After unlocking, an "unlocked" banner appears on each boot; this is normal.

**Driver tip during first fastboot connect:** open the OEM tool, run its driver check while the phone is connected and set to *file transfer* mode; when it asks for fastboot, do **not** pull the cable — power off and hold Volume-Down + Power to force fastboot, then let the host install the driver. Repeat the file-transfer → power-off → fastboot sequence so the unlock tool detects the device. If unlock fails, disable any VPN/proxy on the host and retry.

---

## Step 4 (recommended): Flash a clean ROM

Stock OEM skins add background behavior and restrictions that interfere with analysis. A near-stock ROM (Pixel-experience-style, LineageOS, etc.) is cleaner.

### Generic flashing sequence

Prerequisite: BL unlocked, device in Fastboot mode, the ROM `.zip` and recovery `.img` for your **exact device codename** downloaded.

1. **Boot the custom recovery** (do not permanently flash it — stock can overwrite it on reboot):
   ```bash
   fastboot boot "<path-to-recovery>.img"
   ```
   Using `fastboot boot` (temporary) instead of `fastboot flash recovery` avoids the stock system re-overwriting the recovery on the next boot.
2. **Factory reset / format data** inside the custom recovery.
3. **Sideload the ROM**: in recovery choose Apply update → Apply from ADB, then on the host:
   ```bash
   adb sideload "<path-to-rom>.zip"
   ```
   Wait for the transfer to complete.
4. **Reboot** → Reboot system now.
5. Re-enable Developer Options + USB debugging on the new ROM (same 7-tap procedure).

> Always follow your device's official install wiki alongside this generic outline — partition layouts (A/B, dynamic partitions, `vbmeta`) differ per device.

---

## Step 5: Root with Magisk

Installing the Magisk APK is only step one; root comes from patching and flashing the `boot.img`.

1. **Get the matching `boot.img`** — extract it from the **exact** firmware/ROM build you are running (a mismatched boot image can bootloop). Push it to the device:
   ```bash
   adb push "<path>/boot.img" /sdcard/Download/
   ```
2. **Patch on-device**: Magisk app → Install → "Select and Patch a File" → pick `boot.img` → wait for "All done". This produces `magisk_patched-xxxxx.img` in `Download/`.
3. **Pull it back**:
   ```bash
   adb shell ls /sdcard/Download/magisk_patched*
   adb pull /sdcard/Download/magisk_patched-xxxxx.img .
   ```
4. **Flash the patched boot**:
   ```bash
   adb reboot bootloader
   fastboot flash boot "<path>/magisk_patched-xxxxx.img"
   fastboot reboot
   ```
5. **Verify**: open the Magisk app (should show a version and "installed"), then:
   ```bash
   adb shell su -c "whoami"     # -> root
   ```
   Approve the Magisk superuser prompt on the device when it appears.

---

## What root unlocks for RE

| Need | Why root is required |
|------|----------------------|
| Frida injection | `frida-server` must run as root |
| SSL pinning bypass | modify the system cert store / inject with Frida |
| Read app private data | `/data/data/<pkg>/` is owned by the app's UID |
| Hook system APIs | Xposed/LSPosed need Magisk + root |
| Capture encrypted traffic | installing a system CA cert needs root |

**The essence of root** is obtaining UID 0, which bypasses Linux permission checks and (with the right setup) SELinux, allowing access to any file and arbitrary operations.

---

## Magisk modules and features useful for RE

Magisk's value beyond bare root is its **systemless module system** (it never touches the `/system` partition) and its hiding mechanisms.

| Module / feature | Role |
|------------------|------|
| **LSPosed** | Xposed successor; hook arbitrary app Java methods. Core RE tooling. |
| **Shamiko** | Hide root state, bypass root detection. |
| **MagiskTrustUserCerts** | Promote user CA certs to system certs (needed for app traffic capture on Android 7+). |
| **Busybox** | Fill out the Linux command-line toolset. |
| **Zygisk** | Built-in injection in the Zygote process. |
| **DenyList** | Make selected apps unable to see root (banking/payment apps, anti-cheat, Play Integrity). |

**Magisk + LSPosed** is the backbone of the Android RE toolchain. Common combinations: LSPosed + a crypto-helper module to read plaintext at crypto calls; LSPosed + JustTrustMe to bypass SSL pinning for capture; root + Frida for dynamic instrumentation; root + filesystem access to read `/data/data/`.
