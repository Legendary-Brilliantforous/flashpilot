# Decompile and Hook Basics

The core RE loop is **static** decompilation (read the code) plus **dynamic** hooking (change behavior at runtime). This document gives the fundamentals and points to specialized skills for depth.

---

## What "hooking" means

A hook intercepts a function call at runtime and substitutes/modifies its behaviour before (optionally) letting the original run:

```
normal:   app code -> system function -> result
hooked:   app code -> system function -> [intercepted] -> your code -> modified result
```

Hooking is the central technique of dynamic Android RE: read/modify arguments, replace return values, log call flow, or bypass a check.

### Hook frameworks

| Framework | Characteristics | Use |
|-----------|-----------------|-----|
| **Frida** | dynamic injection, Java + native, JS scripts; flexible | analysis, dynamic debugging, custom logic |
| **Xposed / LSPosed** | modular, needs root + Magisk; persistent | system-level persistent modifications |
| **objection** | Frida-based, ready-made commands | quick runtime exploration without writing scripts |

Beginners should start with **Frida**. See the `frida-hooking` and `objection-runtime` skills.

---

## Static decompilation tool chain

| Goal | Tool | Notes |
|------|------|-------|
| DEX → readable Java | **jadx** / jadx-gui | first choice; broad coverage, handles resources |
| APK decompile + recompile | **apktool** | Smali-level edits, resources, manifest |
| DEX → Smali | baksmali | faithful assembly |
| DEX → JAR → Java | dex2jar + JD-GUI/CFR | comparison/fallback |
| Native `.so` | IDA Pro / Ghidra / radare2 | disassembly/decompilation |
| Pro all-in-one | JEB | commercial |

Specialized skills cover these in depth: `android-re-decompile` (jadx/Fernflower, API extraction, call-flow tracing), `apktool-decompile` (patch + repackage), `jadx-reverse-engineering` (JADX MCP), `ghidra-reverse-engineering` / `ida-reverse-engineering` (native), `capa-triage` (native capability triage).

### Minimal static workflow

1. Open the APK in jadx-gui (or `jadx -d out/ app.apk`).
2. Read `AndroidManifest.xml`: launcher Activity, `Application` class, permissions, exported components, `<meta-data>`.
3. Read every `BuildConfig.java` — rarely obfuscated, often leaks base URLs, flavor, keys.
4. Survey packages; look for `api`/`network`/`data`/`http`/`retrofit`.
5. Search for high-signal strings: URLs, `http`, `secret`, `token`, `sign`, crypto class names.

---

## Identify the app type and embedded SDKs from `lib/`

An APK is a ZIP — the fastest triage is to look at `lib/<abi>/`:

```bash
unzip app.apk -d app_dir
ls app_dir/lib/arm64-v8a/
```

Or check `System.loadLibrary(...)` calls in decompiled Java to see which native libs load:

```java
System.loadLibrary("native-lib");
System.loadLibrary("msaoaidsec");
```

### Third-party security SDKs (common)

| `.so` | Source | Function |
|-------|--------|----------|
| `libmsaoaidsec.so` | MSA OAID alliance | device fingerprint + anti-debug |
| `libsgmain.so` | Alibaba security | anti-debug + integrity check |
| `libNSaferOnly.so` | NetEase Yidun | anti-cheat + anti-debug |
| `libshield.so` | TongDun | device risk control |
| `libtprt.so` | Tencent game protect | anti-cheat |

> Many of these SDKs ship anti-Frida as a side feature. A bypass for one app often generalizes to every app embedding the same SDK.

### Packer/hardening SDKs (common)

| `.so` / sign | Vendor | Note |
|--------------|--------|------|
| `libjiagu.so` | 360 Jiagu | common in utility apps |
| `libshell-super.*.so` | Tencent Legu | common in games |
| `libDexHelper.so` | Bangcle | |
| `libprotectClass.so` | Ijiami | |
| `Application = com.stub.StubApp` | generic shell | real Application replaced |

### Fingerprinting tools

```bash
pip install apkid
apkid app.apk          # detects compiler, packer, anti-vm signatures
```

If jadx shows only a shell stub, the app is packed — hand off to the `android-unpacking` skill (frida-dexdump dumps the real DEX from memory).

---

## Dynamic hooking with Frida (fundamentals)

Setup is in `frida-setup.md`. Once `frida-ps -U` works, attach or spawn (`frida -U -f <pkg> -l hook.js`).

### Hook a Java method

```javascript
Java.perform(function () {
    var Mgr = Java.use("com.example.UserManager");
    // log + override a boolean check
    Mgr.isVip.implementation = function () {
        var orig = this.isVip();
        console.log("[*] isVip() original =", orig);
        return true;                 // force VIP
    };
});
```

### Hook a native function

```javascript
Interceptor.attach(Module.findExportByName("libnative-lib.so",
        "Java_com_example_NativeLib_check"), {
    onEnter: function (args) { console.log("[*] check() called"); },
    onLeave: function (retval) { retval.replace(ptr(1)); }   // force success
});
```

### What injection leaves behind, and detection

Hardened apps detect Frida via `/proc/self/maps` (the `frida-agent` mapping), the default `27042` port, Frida thread names (`gum-js-loop`, `gmain`, `pool-frida`), and resolvable agent symbols. If a process dies immediately on inject, it detected one of these. See `frida-setup.md` for the footprint table and common pitfalls; bypassing is the job of `frida-hooking` / `objection-runtime`.

---

## Time-shift hooking (a worked example of why hooks are powerful)

A "speed hack" is just hooking the time source so the value advances N× faster — game logic that reads "time" then runs faster. Android time sources span both layers:

| Function | Layer |
|----------|-------|
| `System.currentTimeMillis()`, `SystemClock.uptimeMillis()` | Java |
| `clock_gettime()`, `gettimeofday()` | native (C/C++) |

```javascript
// Java-layer 2x time
var start = Date.now(), speed = 2.0;
Java.use("java.lang.System").currentTimeMillis.implementation = function () {
    return start + Math.floor((Date.now() - start) * speed);
};
```

To affect C/C++ engines you must hook the native time functions too. This illustrates the general pattern: identify the function an app relies on, hook it, and control its output.

---

## Static + dynamic, combined

A realistic flow ties the two together:

1. **Triage** — package/version/permissions (manifest), packer/SDK signs (`lib/`, apkid), signature (`apksigner verify`).
2. **Static** — jadx for logic; find entry points (`Application.onCreate` → Activity lifecycle); search URLs/keys/crypto; Ghidra/IDA for `.so`.
3. **Dynamic** — Charles/mitmproxy for traffic (mind pinning); Frida hooks to intercept and modify; flip `debuggable` for a debugger; `logcat` filtered to the app.
4. **Patch + repackage** (if modifying) — apktool decompile → edit Smali/resources/manifest → recompile → zipalign → re-sign → install (see `apk-packaging.md`).

Hand off each deep phase to its specialized skill rather than doing everything here.
