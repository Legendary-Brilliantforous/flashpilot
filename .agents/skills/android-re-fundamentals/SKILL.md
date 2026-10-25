---
name: android-re-fundamentals
description: Android reverse-engineering onboarding and fundamentals. Covers device preparation and rooting (unlock bootloader, flash a clean ROM, Magisk root, real-device vs emulator trade-offs), full environment setup (JDK, adb/fastboot, Frida server/tools, Charles/mitmproxy CA certificates), APK internal structure and the forward packaging pipeline, the Android filesystem and partition layout, decompile-and-hook basics, and phone UI automation. Use this when bootstrapping an Android RE workstation, when the user is new to Android reverse engineering, or when they ask how to root a phone, set up Frida/adb/Charles, understand APK/DEX structure, learn the Android filesystem, or automate a device. Trigger keywords — android reverse engineering basics, set up Frida, install adb, root phone, unlock bootloader, flash ROM, Magisk, APK structure, DEX, AndroidManifest, Android filesystem, phone automation, uiautomator2, Charles certificate, JDK install, Android reverse engineering getting started, flashing ROM, root, environment setup, Frida environment, APK structure, Android filesystem, phone automation.
trigger: android reverse engineering basics|android RE setup|set up Frida|frida-server|install adb|fastboot|root phone|unlock bootloader|flash ROM|Magisk|APK structure|DEX|AndroidManifest|Android filesystem|phone automation|uiautomator2|Charles certificate|JDK install|Android reverse engineering getting started|flashing ROM|root|environment setup|Frida environment|APK structure|Android filesystem|phone automation
---

# Android RE Fundamentals

The onboarding and fundamentals layer for Android reverse engineering. This skill is **generic and tool-agnostic** — it brings a fresh workstation and operator from zero to "ready to reverse any app." It does not target any specific application; once the environment is set up and the fundamentals are understood, hand off to a specialized skill (decompilation, runtime hooking, traffic capture, native analysis, unpacking, etc.).

## when_to_use

Use this skill when any of the following is true:

- The user is **new to Android reverse engineering** and needs the lay of the land.
- A **workstation is being bootstrapped** — JDK, adb/fastboot, Frida, Charles/mitmproxy, scrcpy are not yet installed or verified.
- The user needs to **prepare a device**: unlock the bootloader, flash a clean (near-stock) ROM, root with Magisk, or decide between a real device and an emulator.
- The user asks a **conceptual** question about how APKs are packaged, what is inside an APK/DEX, how the Android filesystem and partitions are laid out, or where an app stores its data.
- The user wants **phone UI automation** (adb input, uiautomator2, Appium, Airtest) to drive a target app.

If the user already has a working environment and a concrete target, prefer the specialized skill for the task at hand (decompile, hook, capture, native RE) — point them there from the workflow below.

## Workflow

Work top-down. Each phase points to a reference document with the full detail.

### Phase 0: Decide on a target device

Real device vs emulator is the first decision. Emulators are convenient (snapshots, multi-instance, disposable) and fine for learning and most ordinary apps, but they are **easily fingerprinted** by hardened apps (banking, mainstream games, packed/anti-debug apps) because the x86-vs-ARM gap and emulator-specific files are hard to hide. A rooted real device is the reliable workhorse. See `references/device-prep-and-root.md` (sections "Real device vs emulator" and the brand-by-brand unlock notes).

### Phase 1: Prepare and root the device

1. Install vendor/Google USB drivers so the host recognizes the device in both normal and fastboot modes.
2. Enable Developer Options and USB debugging.
3. Unlock the bootloader (brand-specific; Xiaomi has a binding + wait period, Pixel/OnePlus is a single fastboot command).
4. (Recommended) Flash a clean, near-stock ROM (e.g. a Pixel-experience-style or LineageOS build) — stock OEM skins add background behavior and restrictions that interfere with analysis.
5. Root with Magisk by patching `boot.img` and flashing it back.
6. Verify root: `adb shell su -c "whoami"` returns `root`.

Full step-by-step (including the `fastboot boot` vs `fastboot flash recovery` gotcha and Magisk modules like LSPosed / Shamiko / MagiskTrustUserCerts) is in `references/device-prep-and-root.md`.

### Phase 2: Set up the host environment

Install and verify, in roughly this order — see `references/environment-setup.md`:

1. **JDK** (8 for legacy tooling, 17+ for modern jadx) — verify with `java -version`.
2. **Android SDK Platform Tools** — `adb` and `fastboot` on PATH; verify with `adb devices`.
3. **Frida** — `frida-tools` on the host (`pip install frida-tools`) plus a version-matched `frida-server` binary on the device. The two versions **must match exactly**. See `references/frida-setup.md`.
4. **Traffic capture** — Charles (or mitmproxy) with its CA certificate installed; on Android 7+ user certificates are ignored by apps, so promote the CA to a system certificate via the `MagiskTrustUserCerts` module. See `references/environment-setup.md` (Charles section).
5. **scrcpy** (optional) for screen mirroring/control.

### Phase 3: Learn the fundamentals (reference reading)

Before touching a real target, understand the artifacts you will be manipulating:

- **APK internals** — what every entry in the ZIP is for, DEX format, Smali basics, signing schemes (V1/V2/V3). See `references/apk-structure.md`.
- **Forward packaging pipeline** — how source becomes an installable APK (aapt2 → javac/kotlinc → D8/R8 → zipalign → apksigner), because *reversing is this pipeline run backwards*. See `references/apk-packaging.md`.
- **Android filesystem** — partitions, `/system`, `/data/data/<pkg>`, `/proc/<pid>/maps`, where apps keep prefs/databases. See `references/android-filesystem.md`.
- **adb cheat sheet** — push/pull, install/uninstall, pulling an installed APK off the device, writing files without an editor. See `references/adb-cheatsheet.md`.

### Phase 4: Decompile and hook basics

Static decompilation (jadx/apktool) plus dynamic hooking (Frida) is the core RE loop. `references/decompile-and-hook.md` covers the tool chain, identifying third-party SDKs and packers from the `lib/` directory, what Frida injection leaves behind, and a minimal Java/native hook example. For deeper work hand off to the specialized skills (`android-re-decompile`, `apktool-decompile`, `frida-hooking`, `objection-runtime`, `android-unpacking`, `ghidra-reverse-engineering` / `ida-reverse-engineering`).

### Phase 5: Automate the device (optional)

When you need to repeatedly drive the target's UI, choose an automation approach by app type — accessibility-tree tools (uiautomator2, Appium, AutoX.js) for normal apps, vision-based tools (Airtest/OpenCV) for games and custom-rendered UIs. See `references/phone-automation.md`.

## References

- `references/device-prep-and-root.md` — Bootloader unlock, flashing a clean ROM, Magisk root, emulator vs real device, what root unlocks for RE.
- `references/environment-setup.md` — JDK install (Temurin), Platform Tools/PATH, drivers, Charles install + CA certificate + Android 7+ system-cert trick.
- `references/frida-setup.md` — frida-tools (host) + frida-server (device) install, version matching, starting the server, verification, injection footprint.
- `references/adb-cheatsheet.md` — push/pull/install/uninstall, pulling installed APKs, command-source taxonomy, writing files on-device.
- `references/apk-structure.md` — APK as a ZIP, every file/dir explained, DEX format, Smali basics, signing schemes, packer fingerprints.
- `references/apk-packaging.md` — Full forward build pipeline (AIDL → aapt2 → D8/R8 → zipalign → apksigner), AAB vs APK, forward↔reverse mapping, repackage flow.
- `references/android-filesystem.md` — Partitions, `/system`, `/vendor`, `/data`, `/proc`, `/dev`, boot flow, security model, RE-relevant paths.
- `references/decompile-and-hook.md` — Decompiler/hook tool chain, identifying third-party SDKs and packers, Frida footprint, minimal hook examples.
- `references/phone-automation.md` — Automation approaches (adb input, uiautomator2, Appium, AutoX.js, Airtest), accessibility vs vision-based, examples.
