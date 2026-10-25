# Frida Setup

Frida is the standard dynamic-instrumentation framework for Android RE. This document covers only the **generic environment setup and verification** — getting Frida running on a rooted device and confirming the host can talk to it. Writing hook scripts and bypassing specific app protections belong to other skills (`frida-hooking`, `objection-runtime`, `frida-mitm-capture`).

> Prerequisite: a **rooted** device (frida-server runs as root) with USB debugging on, and adb working (`adb devices` shows it).

---

## Two halves that must match

Frida has two components, and **their versions must be identical** or the connection fails:

| Component | Runs on | Role |
|-----------|---------|------|
| `frida-tools` (Python package) | Host (PC) | provides `frida`, `frida-ps`, `frida-trace`, etc. |
| `frida-server` (binary) | Device | performs the actual hooking on the target |

Frida scripts are written in **JavaScript** (not Java). The script runs inside the injected process and drives it through Frida's JS API (`Interceptor.attach`, `Java.use`, etc.).

---

## Host: install frida-tools

```bash
pip install frida-tools
frida --version      # note this version, e.g. 17.7.3
```

> Unrelated dependency warnings (e.g. about `w3lib`, `websockets`) during install do not affect Frida — ignore them.

---

## Device: install frida-server

1. Download the **matching** server build from the Frida releases for your exact host version, e.g. `frida-server-<version>-android-arm64.xz`. Pick the architecture that matches the device:
   - 64-bit ARM phone → `android-arm64`
   - 32-bit ARM → `android-arm`
   - emulator → `android-x86` / `android-x86_64`

   Do **not** download `frida-core-devkit` (that is the development SDK, not the server).

2. Decompress the `.xz` — it yields a **single binary file** (not a folder). Rename it to `frida-server` (Android/Linux executables need no extension; dropping the version number just makes commands shorter).

3. Push it to the device and make it executable:
   ```bash
   adb push "<path>/frida-server" /data/local/tmp/frida-server
   adb shell chmod +x /data/local/tmp/frida-server
   ```

`/data/local/tmp/` is the conventional location for on-device tools (it is executable and writable by shell, runnable as root).

---

## Start frida-server

```bash
adb shell su -c "/data/local/tmp/frida-server &"
```

This starts it in the background as root. (It listens on TCP `27042` by default; you can change it with `-l 0.0.0.0:<port>` when an app scans for the default port.)

---

## Verify the connection

```bash
frida-ps -U
```

`-U` means "USB device." A process list printed back confirms host↔device Frida is working, e.g.:

```
14194  com.example.app
15402  Example App
```

Then you can spawn or attach:

```bash
frida -U -f com.example.app           # spawn (inject before any app code runs)
frida -U com.example.app              # attach to a running process
frida -U -f com.example.app -l hook.js
```

`-f` (spawn) injects before the app's own code executes — prefer it when you need to beat early anti-debug/anti-Frida initialization, since the script is in place before the protective `.so` runs.

---

## What Frida injection leaves behind (so you understand detection)

Hardened apps look for these footprints; knowing them helps you reason about why an injection gets killed:

| Footprint | Where | Note |
|-----------|-------|------|
| memory map | `/proc/self/maps` contains `frida-agent` | the agent `.so` is mapped in |
| file descriptors | `/proc/self/fd` has frida pipes | Frida's Unix sockets |
| port | `127.0.0.1:27042` listening | frida-server default port |
| thread names | `gmain`, `gdbus`, `gum-js-loop`, `pool-frida` | GLib/Frida threads |
| symbols | `frida_agent_main` resolvable in memory | agent export |

If an app process dies immediately on inject (`Process terminated`), it almost certainly detected one of these. Bypassing it is the job of `frida-hooking` / `objection-runtime`; for well-known apps, search "<app> frida bypass" first — the mechanism is often already published.

---

## Common Frida gotchas (generic, version-agnostic)

| Symptom | Cause | Fix |
|---------|-------|-----|
| `frida-ps -U` errors / hangs | server not running or version mismatch | restart frida-server; ensure host `frida --version` == server version |
| `not a function` on a found export | `Module.findExportByName(...)` returned a PLT stub, not the real address | resolve via `module.enumerateExports()` and use that address |
| truthiness check on a pointer fails | `NativePointer(0x0)` is a truthy object, so `if (!fn)` never fires | use `fn.isNull()` |
| `Memory.writeByteArray(ptr, bytes)` errors | API moved onto the pointer | use `ptr.writeByteArray(bytes)` |
| `android_dlopen_ext` won't hook | on recent Android it's a short PLT stub | don't hook dlopen; use `-f` spawn and hook earlier instead |

When a hook misbehaves, write a small diagnostic script first: confirm `Interceptor.attach` works on a known libc symbol, then locate your target export's real address via `enumerateExports()` before attaching.
