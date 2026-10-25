# APK File Structure

An APK (Android Package Kit) is fundamentally a **ZIP archive** — you can open it with any unzip tool (or rename to `.zip`):

```bash
unzip -l example.apk
```

It contains everything an app needs to run: code, resources, configuration, and signatures.

---

## Overall layout

```
example.apk
├── AndroidManifest.xml      # app manifest (binary XML)
├── classes.dex              # primary Dalvik bytecode
├── classes2.dex             # additional DEX (MultiDex)
├── classes3.dex             # ...
├── resources.arsc           # compiled resource index table
├── res/                     # compiled resources
│   ├── layout/  drawable-*/  values/  xml/  anim/  color/  menu/  mipmap-*/  raw/
├── lib/                     # native .so libraries
│   ├── armeabi-v7a/  arm64-v8a/  x86/  x86_64/
├── assets/                  # raw files (not compiled)
├── META-INF/                # signing & integrity
│   ├── MANIFEST.MF  CERT.SF  CERT.RSA
├── kotlin/                  # Kotlin metadata (optional)
└── ...                      # third-party lib config files
```

---

## AndroidManifest.xml — the manifest (importance: ★★★★★)

The single most important file. It declares the app's core information. Inside the APK it is **binary XML (AXML)** and must be decoded with a tool.

Declares: package name, versionCode/versionName, permissions, SDK requirements, the `Application` class, and the four component types (Activity / Service / BroadcastReceiver / ContentProvider).

### RE focus points

| Field | RE meaning |
|-------|------------|
| `package` | app package name → locates the data directory |
| `android:debuggable` | whether a debugger can attach; flipping to `true` enables debugging |
| `android:allowBackup` | if `true`, data can be exported via `adb backup` |
| component `exported` | exported components are externally invokable → attack surface |
| `<meta-data>` | may hold API keys, channel IDs, other sensitive values |
| `networkSecurityConfig` | trust config that affects traffic capture |

### Decoding tools

```bash
apktool d example.apk                                   # full decode (recommended)
aapt2 dump xmltree example.apk --file AndroidManifest.xml
jadx-gui example.apk                                    # browse the manifest in the tree
```

---

## classes.dex — Dalvik bytecode (importance: ★★★★★)

The app's core code: all Java/Kotlin compiled to Dalvik bytecode.

### DEX file format

```
header       magic (dex\n035), checksum, sizes
string_ids   index of all strings
type_ids     class/primitive type index
proto_ids    method prototype (params + return) index
field_ids    field reference index
method_ids   method reference index
class_defs   class definitions
data         actual code and string data
link_data    link data
```

### MultiDex

A single DEX caps at **65536 methods** (the 64K limit); beyond that it splits into `classes.dex`, `classes2.dex`, `classes3.dex`, … Large apps may have a dozen.

### Tool chain

```bash
apktool d example.apk          # DEX -> Smali (most faithful)
baksmali d classes.dex         # DEX -> Smali (single dex)
jadx -d out/ example.apk       # DEX -> Java (most readable)
jadx-gui example.apk           # GUI (recommended)
d2j-dex2jar classes.dex        # DEX -> JAR, then open in JD-GUI
```

Commercial/other: JEB (best output), GDA (free DEX analyzer).

### Smali basics

Smali is the assembly representation of DEX; you edit it when patching.

```smali
.method public static isVip()Z    # Z = boolean return
    .registers 1
    const/4 v0, 0x0               # v0 = false
    # change to const/4 v0, 0x1   -> always return true
    return v0
.end method
```

Type abbreviations: `V`=void, `Z`=boolean, `I`=int, `J`=long, `F`=float, `D`=double, `L...;`=object (`Lcom/example/MyClass;`), `[`=array (`[I` = int[]).

---

## resources.arsc — resource index (importance: ★★★☆☆)

Binary table mapping every resource ID (`R.` constants) to the actual resource file/value: strings, colors, dimens, styles, and ID→path mappings.

```
0x7f010001  ->  type + name  ->  file path / value
```

```bash
aapt2 dump resources example.apk
apktool d example.apk       # restores res/values/strings.xml etc.
```

---

## res/ — compiled resources (importance: ★★★☆☆)

XML files here are compiled to binary XML. Key subdirectories: `layout/`, `drawable-*/`, `mipmap-*/` (app icons), `values/` (strings, colors, dimens, styles, attrs), `xml/`, `anim/`, `color/`, `menu/`, `raw/`.

RE focus:
- **`xml/network_security_config.xml`** — decides whether the app trusts user certificates; directly affects HTTPS capture. Editing it can defeat basic certificate-pinning protection.
- **`values/strings.xml`** — may contain hardcoded URLs/keys.
- **`layout/`** — helps map UI to logic.

---

## lib/ — native .so libraries (importance: ★★★★☆)

C/C++ shared libraries, split by CPU architecture:

| Architecture | Use |
|--------------|-----|
| `arm64-v8a` | modern phones (most devices since ~2016) |
| `armeabi-v7a` | older / 32-bit ARM |
| `x86` / `x86_64` | emulators |

```bash
file lib/arm64-v8a/libapp.so
readelf -h lib/arm64-v8a/libapp.so
nm -D lib/arm64-v8a/libapp.so      # exported functions
# analyze in IDA Pro / Ghidra / radare2
```

Frida hook of a native function:

```javascript
Interceptor.attach(Module.findExportByName("libapp.so", "Java_com_example_NativeLib_check"), {
    onEnter: function(args) { console.log("called"); },
    onLeave: function(retval) { retval.replace(1); }
});
```

Common `.so` purposes:

| `.so` name | Typical purpose |
|------------|-----------------|
| `libapp.so` | Flutter app core |
| `libil2cpp.so` | Unity IL2CPP code |
| `libjiagu.so` / `libexec.so` | packer/hardening core |
| `libsec.so` / `libsgmain.so` | security / signature check |
| `libnative-lib.so` | NDK business logic |

The `lib/` directory is also the fastest way to see which **third-party security/packer SDKs** an app embeds — see `decompile-and-hook.md` for the lookup tables.

---

## assets/ — raw files (importance: ★★★☆☆)

Files that bypass the resource compiler and are copied verbatim: config JSON, WebView H5 pages, embedded certs, ML models, fonts, scripts, seed databases, channel markers.

RE focus: may hold an **encrypted DEX** (a common packer technique — decrypted and loaded at runtime), embedded certs for SSL pinning, config files with server addresses/keys, and the business code of H5/RN/Flutter cross-platform apps.

---

## META-INF/ — signatures (importance: ★★★★☆)

The digital signature, verifying integrity and origin.

```
META-INF/
├── MANIFEST.MF   # SHA digest of each file
├── CERT.SF       # signature over MANIFEST.MF entries
└── CERT.RSA      # developer cert + public key (may be .EC / .DSA)
```

### Signing schemes

| Scheme | Location | Property |
|--------|----------|----------|
| V1 (JAR) | inside `META-INF/` | legacy; only verifies ZIP entries |
| V2 (APK) | signing block before the central directory | verifies the whole APK file; more secure |
| V3 (APK) | same as V2 | adds key rotation |
| V4 | separate `.idsig` file | incremental install optimization |

### RE impact

A modified APK **must be re-signed** before it can install. Use `apksigner` (handles V2/V3, which cover the whole file):

```bash
apksigner verify --verbose --print-certs example.apk   # inspect
keytool -printcert -jarfile example.apk                 # cert details

# re-sign after modifying:
keytool -genkey -v -keystore my.keystore -alias mykey -keyalg RSA -keysize 2048 -validity 10000
zipalign -v 4 modified.apk aligned.apk
apksigner sign --ks my.keystore --ks-key-alias mykey aligned.apk
```

---

## Hardening/packer fingerprints

Packers change the standard structure. Recognizing them early saves effort:

| Hardening type | Tell-tale sign |
|----------------|----------------|
| DEX encryption | tiny `classes.dex` (shell only); real DEX hidden encrypted in `assets/` |
| DEX extraction | method bodies emptied, filled at runtime |
| SO hardening | key logic moved into `.so`; Java is a thin wrapper |
| VMP | bytecode converted to a custom VM's instructions |
| resource obfuscation | `res/` filenames mangled (`res/a/b.xml`) |
| string encryption | strings encrypted, decrypted at runtime |

Vendor fingerprints (by marker file):

```
assets/libjiagu.so        -> 360 Jiagu
assets/classes.jar (enc)  -> Bangcle
lib/libexec.so            -> Ijiami
lib/libDexHelper.so       -> DexHelper
lib/libprotectClass.so    -> early Bangcle
assets/libchaosvmp.so     -> Nagapt
Application = com.stub.StubApp  -> generic shell replaced the real Application
```

When you only see a shell stub in jadx, you are dealing with a packer — hand off to the `android-unpacking` skill (frida-dexdump) to recover the real DEX from memory.

---

## Tool summary

| Tool | Purpose | Type |
|------|---------|------|
| jadx | DEX → Java | free |
| apktool | APK decompile/recompile | free |
| JEB | pro Android RE | commercial |
| IDA Pro | `.so` disasm/decompile | commercial |
| Ghidra | `.so` analysis (NSA, OSS) | free |
| Frida | dynamic hooking | free |
| objection | Frida-based automation | free |
| dex2jar | DEX → JAR | free |
| baksmali | DEX → Smali | free |
| apksigner | signing | free |
| Charles | HTTPS capture | commercial |
