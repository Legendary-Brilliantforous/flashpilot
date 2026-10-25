# Host Environment Setup

Everything that goes on the **host** (your PC) to reverse Android apps: JDK, Android SDK Platform Tools, and a traffic-capture proxy with its CA certificate. Frida has its own document (`frida-setup.md`).

> Use placeholders for personal paths. Examples below use generic paths like `C:\platform-tools`.

---

## 1. JDK

Most Android tooling needs Java.

- **JDK 8** — required by some legacy tools (older jadx builds, parts of the Android toolchain).
- **JDK 17+** — modern jadx and current tooling.

### Installing JDK 8 (Adoptium Temurin, no account required)

1. Download page: <https://adoptium.net/temurin/releases/?os=windows&arch=x64&package=jdk&version=8> (or the marketplace page for other versions).
2. Choose **Windows / x64 / JDK (not JRE) / 8 - LTS**, the **.msi** installer (the `.msi` auto-configures environment variables).
3. During install, tick **"Set JAVA_HOME variable"** and **"Add to PATH"**.
4. **Open a new terminal** (so the updated PATH applies) and verify:
   ```powershell
   java -version
   javac -version
   ```
   Expect `openjdk version "1.8.0_xxx"`, 64-bit.

> JDK 8 only accepts `-version` (single dash); `java --version` errors with "Unrecognized option".

### Common JDK issues

| Symptom | Fix |
|---------|-----|
| `'java' is not recognized` | PATH not set or terminal not restarted. Re-run installer → Modify, or add `JAVA_HOME\bin` to PATH manually. |
| Wrong version reported | Another JDK is earlier on PATH. Check `where java` and `echo %JAVA_HOME%`; point `JAVA_HOME` at the intended JDK. |
| `javac` missing | You installed a JRE, not a JDK. Re-download the **JDK** package. |

---

## 2. Android SDK Platform Tools (adb / fastboot)

The official Google CLI bundle. Download, extract to a stable path (e.g. `C:\platform-tools`), and add it to the system `PATH`:

```
Settings → System → About → Advanced system settings → Environment Variables → edit Path → add the extracted folder
```

Verify:

```bash
adb devices       # "<serial>    device" = connected
fastboot devices  # only lists a device when it is in fastboot mode
```

Drivers: on Windows install the Google USB Driver (ships with Platform Tools), a vendor driver, or a universal ADB installer so the device is recognized in both adb and fastboot modes.

See `adb-cheatsheet.md` for day-to-day adb usage.

---

## 3. Traffic capture proxy (Charles)

Charles is an HTTP/HTTPS capture proxy used to inspect API requests/responses while reversing an app's network layer. (mitmproxy is a free CLI alternative; the certificate concepts below apply to both.)

### Install

1. Download from <https://www.charlesproxy.com/download/latest-release/> (Windows x86_64, `.msi` or `.appx`).
2. Install with the wizard; default path `C:\Program Files\Charles\`.

> The trial limits sessions to 30 minutes. Use a properly licensed copy.

### Basic proxy config

- Charles sets itself as the system proxy on launch; default listen port **8888** (Proxy → Proxy Settings to change).
- **Phone capture**: put phone and PC on the **same LAN**, find the PC IP (`ipconfig`), then on the phone Wi-Fi set a manual proxy → host = PC IP, port = 8888. Click **Allow** on the Charles connection prompt.

#### Multi-subnet gotcha

If the PC and phone are on different subnets (e.g. PC on `192.168.1.x` via Ethernet, phone on `192.168.2.x` via a different router) they cannot reach each other. Fix: disable the PC's Ethernet (`Win+R` → `ncpa.cpl` → right-click Ethernet → Disable) and connect the PC over Wi-Fi to the phone's router so both share a subnet. The PC IP will change — recheck `ipconfig` and update the phone proxy.

### HTTPS capture — installing the CA certificate

HTTPS bodies are encrypted until Charles's CA cert is trusted:

- **PC side**: Help → SSL Proxying → Install Charles Root Certificate → install into "Trusted Root Certification Authorities".
- **Phone side**: Help → SSL Proxying → Install Charles Root Certificate on a Mobile Device. On the phone, browse to `chls.pro/ssl` to download, then install via Settings → Security → Encryption & credentials → Install a certificate → CA certificate.
- **Enable SSL proxying**: Proxy → SSL Proxying Settings → tick **Enable SSL Proxying** and add `*:443` (all HTTPS) or specific hosts.

### Android 7+ system-certificate requirement (must-read for app capture)

From Android 7.0, **apps trust only system CA certificates, not user-installed ones**. So a user-installed Charles cert works in Chrome but **fails for normal apps**.

| Context | User cert valid? |
|---------|------------------|
| Chrome browser | Yes |
| Normal app | No — capture fails |

**Fix (requires root / Magisk):** promote the user cert to a system cert.

1. Install the Charles user CA cert as above.
2. Install the **`MagiskTrustUserCerts`** module (Magisk app → Modules → Install from storage → pick the `.zip`).
3. **Reboot.** After reboot the user cert is treated as a system cert and all apps trust it.

> For apps that pin certificates (Certificate Pinning), trusting the CA is not enough — you must bypass pinning with Frida/objection (see `frida-setup.md` and the `objection-runtime` skill). Capturing app traffic end-to-end is the job of dedicated skills (`mitm-capture`, `frida-mitm-capture`).

---

## 4. scrcpy (optional, screen mirror/control)

Host-side tool that mirrors and controls the device over adb (nothing installed on the phone). Download the Windows zip from the scrcpy releases, extract, add to PATH, and run `scrcpy`.

---

## Setup checklist

- [ ] `java -version` / `javac -version` succeed (right version, 64-bit)
- [ ] `adb devices` lists the device as `device`
- [ ] `fastboot devices` lists it when in fastboot mode
- [ ] Charles/mitmproxy installed; CA cert installed on PC and phone
- [ ] On Android 7+: user CA promoted to system via MagiskTrustUserCerts (rooted device)
- [ ] Frida set up — see `frida-setup.md`
