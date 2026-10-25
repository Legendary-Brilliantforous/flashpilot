# Android Filesystem and Partitions

Knowing where things live on an Android device tells you where to read app data, find loaded libraries, and inspect process state.

---

## Partitions

| Partition | Mount | Role |
|-----------|-------|------|
| boot | - | kernel + ramdisk; boots the system (Magisk patches this for root) |
| recovery | - | recovery mode (OTA, factory reset) |
| system | `/system` | Android OS core |
| vendor | `/vendor` | OEM drivers/libs |
| userdata | `/data` | app + user data |
| cache | `/cache` | OTA temp |
| persist | `/persist` | calibration, DRM |
| metadata | `/metadata` | encryption metadata |
| dtbo | - | device tree overlay |
| vbmeta | - | Verified Boot metadata |

> RE-relevant partitions: `system`, `vendor`, `data`.

---

## Root directory `/`

```
/
├── system/   vendor/   data/   cache/
├── dev/      # device nodes
├── proc/     # kernel/process info (virtual fs)
├── sys/      # kernel device/driver info (virtual fs)
├── mnt/      storage/    # mount points / user-visible storage
├── init      init.rc     default.prop
├── sepolicy  # SELinux policy
└── ...
```

---

## /system (OS core)

```
/system/
├── app/          # removable system apps
├── priv-app/     # privileged system apps (Settings, SystemUI, Launcher3, ...) — higher privilege
├── framework/    # core JARs: framework.jar, services.jar, core-libart.jar, boot-*.oat
├── lib/  lib64/  # 32/64-bit system .so (libc.so, libm.so, liblog.so, ...)
├── bin/          # executables: app_process (Zygote), surfaceflinger, servicemanager, logcat, sh
├── xbin/         # extra executables (su, ...)
├── etc/          # configs: permissions/, init/, security/ (CA certs), hosts
├── fonts/  media/ (bootanimation.zip)  usr/
└── build.prop    # ★ build properties (device model, version, fingerprint)
```

Key files:
- **`build.prop`** — device model, Android version, API level, fingerprint. Often modified to spoof device info.
- **`framework/framework.jar`** — core framework implementation; Xposed/LSPosed hook target.
- **`priv-app/`** — `signatureOrSystem`-level privileges; high-value RE targets.
- **`etc/security/`** — system CA certificate store (where a promoted Charles cert lands).

---

## /vendor (OEM)

```
/vendor/  app/  bin/  lib/  lib64/  etc/  firmware/  overlay/  build.prop
```

Since Android 8.0 (Project Treble), `/vendor` is strictly separated from `/system` to ease OS upgrades.

---

## /data (user data) — the most important RE directory

```
/data/
├── app/                          # installed APKs
│   └── com.example.app-1/  base.apk  lib/  oat/
├── data/                         # ★ per-app private data
│   └── com.example.app/
│       ├── shared_prefs/         # SharedPreferences XML (config, login state, tokens)
│       ├── databases/            # SQLite DBs
│       ├── files/                # app internal files
│       ├── cache/  code_cache/
│       ├── lib/                  # private .so (symlink)
│       └── no_backup/
├── user/  user_de/               # multi-user / device-encrypted data
├── system/                       # system-level data
│   ├── packages.xml              # ★ installed-app registry (permissions, signatures)
│   ├── packages.list             # package → UID map
│   └── appops.xml  users/
├── misc/  (wifi/  adb/  profiles/)
├── local/tmp/                    # local temp (push tools here)
├── dalvik-cache/                 # Dalvik/ART cache
└── media/0/                      # internal storage (= /sdcard): DCIM, Download, Android/data, Android/obb, ...
```

### Commonly used RE paths

| Path | Use |
|------|-----|
| `/data/data/<pkg>/shared_prefs/` | config, login state, tokens |
| `/data/data/<pkg>/databases/` | local DBs, possibly sensitive |
| `/data/data/<pkg>/files/` | app-written files |
| `/data/app/<pkg>/base.apk` | installed APK (pull for analysis) |
| `/data/system/packages.xml` | app permissions/signatures |
| `/data/local/tmp/` | drop tools like frida-server (runnable) |

`/data/data/<pkg>/` is owned by the app's UID — read it as root: `adb shell su -c "ls /data/data/<pkg>/"`.

---

## /proc (virtual filesystem)

```
/proc/
├── cpuinfo  meminfo  mounts  version
└── <pid>/
    ├── maps      # ★ memory map — key for dynamic debugging
    ├── status    # process status (TracerPid field used by anti-debug)
    ├── cmdline   fd/   mem
```

> **`/proc/<pid>/maps`** shows the process memory layout and `.so` load base addresses — the foundation of dynamic analysis. It is also what anti-Frida code scans for the string `frida`.

---

## /dev (device nodes)

```
/dev/  null  zero  random
       binder    # ★ Binder IPC device node
       ashmem    # anonymous shared memory
       input/event*   block/
```

---

## /mnt and /storage

```
/mnt/      sdcard/    media_rw/
/storage/  emulated/0/   (= /sdcard)    XXXX-XXXX/ (external SD by UUID)
```

---

## Boot flow (files involved)

```
Bootloader
   v
boot partition -> Linux kernel
   v
init (/init) parses init.rc -> mounts system/vendor/data
   v
core services (servicemanager, surfaceflinger, ...)
   v
Zygote (/system/bin/app_process) loads framework.jar
   v
System Server (AMS, PMS, WMS, ...)
   v
Launcher -> UI
```

---

## Security model

| Mechanism | Description |
|-----------|-------------|
| Linux UID/GID | each app gets a unique UID → sandbox isolation |
| SELinux | mandatory access control (`/sepolicy`) |
| dm-verity | verifies system/vendor partition integrity |
| Verified Boot | boot-chain verification against tampering |
| file permissions | `/data/data/<pkg>/` is private to the app by default |

**Root, in essence**, is obtaining UID 0, bypassing Linux permission checks and SELinux so any file is readable and any operation runnable.

---

## Quick ADB commands

```bash
adb shell mount                              # partition mounts
adb shell getprop                            # system properties
adb shell pm path com.example.app            # locate installed APK
adb pull /data/app/com.example.app-1/base.apk
adb shell su -c "ls /data/data/com.example.app/"   # app data (root)
adb shell su -c "cat /proc/<pid>/maps"             # memory map (root)
adb shell pm list packages                   # installed packages
adb shell dumpsys package com.example.app | grep permission
adb shell ls -la /system/
```
