# APK Packaging Pipeline (forward build)

Understanding the **forward** build pipeline is directly useful for RE, because **reverse engineering is this pipeline run backwards**. Source, resources, native libs, and AIDL are compiled, transformed, merged, and signed into an installable `.apk`.

```
 source(.java/.kt)  res/   assets/   .so   AIDL
       |             |       |        |     |
   javac/kotlinc   aapt2     |        |   aidl -> .java -> javac
       |          compile    |        |     |
       v             v       |        |     |
    .class      aapt2 link   |        |     |
       |        (.arsc,R.java)|       |     |
       +------------+---------+-------+-----+
                    v
                D8 / R8  -> classes.dex
                    v
         APK packager (zipflinger)  ->  unsigned APK
                    v
               zipalign  ->  apksigner  ->  installable APK
```

---

## Step 1: AIDL

AIDL (Android Interface Definition Language) defines IPC interfaces. The `aidl` compiler turns a `.aidl` file into a `.java` interface containing a `Stub` (server-side abstract class) and a `Stub.Proxy` (client proxy).

> RE link: seeing `Stub`/`Proxy` classes in decompiled code means IPC — watch the `transact()` data flow.

---

## Step 2: Resource compilation (aapt2)

Two stages: **compile** then **link**.

```bash
# compile: res files -> intermediate .flat binaries
aapt2 compile --dir res/ -o compiled/

# link: merge .flat + manifest + android.jar -> resources.arsc + R.java + binary XML
aapt2 link compiled/*.flat -I android.jar --manifest AndroidManifest.xml -o output.apk --java gen/
```

Each resource gets a 32-bit **resource ID**:

```
0x 7f 05 0001
   |  |  └ entry (resource index)
   |  └─ type (01=attr, 02=drawable, 03=layout, 05=string, ...)
   └──── package (7f = app itself, 01 = Android framework)
```

> RE link: `0x7fXXXXXX` constants in Smali are resource IDs; resolve them via `resources.arsc`.

---

## Step 3: Java/Kotlin compilation

`javac` / `kotlinc` compile app source plus generated sources (`R.java`, AIDL output, `BuildConfig.java`, DataBinding, annotation-processor output) into `.class` bytecode.

Annotation processors generate code during compilation:

| Library | Annotation | Generates |
|---------|-----------|-----------|
| Dagger/Hilt | `@Inject`, `@Component` | DI factory classes |
| Room | `@Database`, `@Dao` | DB access impls |
| Retrofit | `@GET`, `@POST` | request impls (runtime proxy) |
| Gson/Moshi | `@SerializedName` | JSON adapters |

> RE link: classes named `*_Factory`, `*_Impl`, `*_MembersInjector` are generated glue — don't waste time on them.

---

## Step 4: DEX compilation (D8 / R8) — the key step

The most important step, and the core RE target.

### D8

Google's DEX compiler: `.class` (JVM bytecode) → desugar → `.dex` (Dalvik bytecode), producing `classes.dex`, `classes2.dex`, …

**Desugaring** rewrites Java 8+ features for older Android: lambdas → anonymous classes, `try-with-resources` → `try-finally`, interface default methods → helper classes, `Optional`/`Stream` via core-library desugaring.

> RE link: class names like `-$$Lambda$XXX` are desugared lambdas; jadx usually restores them.

### R8 (release builds: optimize + obfuscate + shrink)

R8 is D8 plus three things, driven by `proguard-rules.pro`:

1. **Tree shaking** — remove unreferenced classes/methods/fields (smaller APK).
2. **Optimization** — inline short methods, dead-code elimination, constant merging.
3. **Obfuscation** — rename classes/methods/fields to `a`, `b`, `c`…

```java
// before                  // after
public class UserManager {  public class a {
  private String token;       private String b;
  boolean isLoggedIn() {}     boolean a() {}
}                           }
```

> RE link:
> - Obfuscation is the first hurdle; `mapping.txt`, if obtained, restores names fully.
> - Tree shaking means the APK contains only code that is actually reachable.
> - `-keep`-protected names stay un-obfuscated — usually the key entry points (Activities, native methods, etc.).

### MultiDex

When methods exceed 65536, classes split across DEX files. The primary `classes.dex` must contain the `Application` class, launch Activities, their direct dependencies, and `MultiDexApplication` classes; the rest load on demand.

---

## Step 5: Package (merge)

`zipflinger` (inside AGP) merges everything into one ZIP/APK: the DEX files, `resources.arsc`, compiled manifest, binary `res/`, `lib/**/*.so`, `assets/` (verbatim), and other files (`kotlin/`, etc.). Output: an **unsigned** APK.

---

## Step 6: Alignment (zipalign)

zipalign aligns uncompressed entries to a **4-byte boundary** so the system can `mmap()` them directly (no copy), reducing runtime memory and speeding resource access.

```bash
zipalign -v 4 unaligned.apk aligned.apk
zipalign -c -v 4 aligned.apk      # verify
```

> With V2+ signing you must **align before signing**, because the signature covers the whole file.

---

## Step 7: Signing (apksigner)

Purpose: authenticate the developer, protect integrity, and gate upgrades (only same-signature APKs may overwrite).

- **V1 (JAR signing)** — per-file SHA digests in `MANIFEST.MF`, signed in `CERT.SF`/`CERT.RSA`. Verifies ZIP entries only (vulnerable to the Janus bug, CVE-2017-13156).
- **V2** — from Android 7.0; signs the entire APK via a signing block before the central directory. Verifies everything, faster, fixes Janus.
- **V3** — from Android 9.0; V2 plus **key rotation** (proof-of-rotation chain).

```bash
keytool -genkeypair -keystore release.keystore -alias myapp \
  -keyalg RSA -keysize 2048 -validity 10000

zipalign -v 4 app-unsigned.apk app-aligned.apk
apksigner sign --ks release.keystore --ks-key-alias myapp \
  --v1-signing-enabled true --v2-signing-enabled true --v3-signing-enabled true \
  app-aligned.apk
apksigner verify --verbose --print-certs app-aligned.apk
```

---

## Gradle orchestration

`./gradlew assembleRelease` runs the chain automatically. Key tasks (★ = mapped to the steps above): `processReleaseManifest`, `processReleaseResources` (aapt2), `compileReleaseKotlin`/`compileReleaseJavaWithJavac`, `minifyReleaseWithR8` (★ obfuscate+optimize+shrink+DEX), `mergeReleaseNativeLibs`, `packageRelease`.

### Debug vs Release

| Aspect | Debug | Release |
|--------|-------|---------|
| Compiler | D8 (no optimization) | R8 (obfuscate+optimize+shrink) |
| Signing | auto `debug.keystore` | custom `release.keystore` |
| `debuggable` | `true` | `false` |
| Logging | kept | often stripped via ProGuard |

---

## AAB vs APK

Since 2021 Google Play requires **AAB** (Android App Bundle) uploads, not APKs:

```
developer:  source -> .aab (all ABIs/languages/densities)
                          | upload
Google Play: .aab -> bundletool -> per-device optimized APKs (split APKs)
```

An AAB's `base/` module holds `manifest/`, `dex/`, `res/`, `assets/`, `lib/`, and `resources.pb` (protobuf, not `.arsc`); plus optional dynamic-feature modules and `BundleConfig.pb`.

> RE link: apps from Play install as **split APKs**; `adb shell pm path <pkg>` shows multiple APK files — pull all of them.

---

## Forward ↔ reverse mapping

| Forward step | Reverse operation | Tools |
|--------------|-------------------|-------|
| Java/Kotlin → .class | .class → Java | JD-GUI, CFR, Procyon |
| .class → DEX | DEX → .class (JAR) | dex2jar |
| .class → DEX | DEX → Smali | baksmali, apktool |
| .class → DEX | DEX → Java | jadx, JEB |
| R8 obfuscation | de-obfuscate | mapping.txt, jadx rename |
| aapt2 compile | decompile resources | apktool |
| binary manifest | text manifest | apktool, axmlprinter |
| NDK → .so | .so → asm/pseudocode | IDA Pro, Ghidra |
| signing | strip/re-sign | apksigner, uber-apk-signer |

### Full repackage flow

```bash
apktool d target.apk -o target_src/          # 1. decompile
# 2. edit Smali / resources / manifest under target_src/
apktool b target_src/ -o modified.apk         # 3. recompile
zipalign -v 4 modified.apk aligned.apk         # 4. align
apksigner sign --ks my.keystore --ks-key-alias mykey aligned.apk   # 5. re-sign
adb install aligned.apk                        # 6. install
```
