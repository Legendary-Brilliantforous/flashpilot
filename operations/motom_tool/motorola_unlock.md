# motorola_unlock.md — Motorola unlock, Valeria, patcher, firmware

How Moto-M Tool 4.2.2 does the official Motorola bootloader unlock, the
server-driven "Valeria" LK-swap unlock/FRP, the ROM patcher, firmware
mirrors, and QR-based ADB enrollment.

## Official Motorola web unlock (`start_unlock`, L2643)

### Flow

```
start_unlock
 └─ update_labels(state_mode='locked')          # fills device_info, sets is_penangf_device
 └─ data = get_unlock_data(is_penangf_device)   # must have ≥4 segments
 ├─ [PenangF] → start_penangf_unlock(data)      # see below
 └─ [Normal Motorola]
     1. GET https://en-us.support.motorola.com/cc/productRegistration/
              verifyPhone/{data[0]}/{data[3]}/{data[2]}/
        headers: {'Cookie': '; '.join(f'{k}={v}')}     # session cookies
        200 + 'Phone qualifies' in body → OK; 'Not qualified' → abort
     2. cookies = load_cookies()                       # GitHub blob + Fernet
     3. send_request_and_set_timestamp (thread):
        - sync_time_windows()                          # Windows NTP resync
        - request_timestamp = now(UTC)
        - GET .../unlockPhone/{data[0]}/{data[3]}/{data[2]}/ with Cookie header
        - 200 → success_timestamp = now
     4. POST https://studiomaiky.com/get-unlock-candidates
        {"server_id": 1, "request_timestamp": <epoch>, "success_timestamp": <epoch>,
         "consume": true}
        ← {'candidates': [{'code': ...}, ...]} → dedupe, strip, upper
     5. for each code (0.3 s pause on failure):
        fastboot oem unlock <code>
        success = ('successful' AND 'unlocked') in output OR 'already unlocked'
```

### Key facts

- The URL templates use data order **0/3/2** (not 0/1/2) from the
  4-segment `#`-split of `fastboot oem get_unlock_data` output
  (`get_unlock_data`, L2490; regex `^\(bootloader\)\s(.*)$` MULTILINE,
  strip `Unlock data:`, split `#`).
- **IMAP is dead code**: `IMAP_SERVER = 'imap.gmail.com'` (L77) and
  `load_config()` (Fernet-encrypted Gmail `email`+`app_password`, L2302)
  are never called in v4.2.2. Older versions read OTP e-mail via IMAP;
  v4.2.2 replaced that with the paid `/get-unlock-candidates` call. An
  open-source reimplementation can read the OTP mail directly via IMAP
  with a user-supplied app password.
- Cookies come from
  `https://raw.githubusercontent.com/Maikyxd/Cookie/main/cookies_moto3.json`
  (fallback `cookies_moto1.json`), Fernet-decrypted with the server key
  (`GET /get-key` → `{'key': ...}`), then `json.loads` (`load_cookies`, L2331).
- PenangF devices (Moto G23/G13, `ro.product.device == 'penangf'`)
  use `fastboot oem get_key` instead (`get_unlock_data(is_penangf_device)`).

### PenangF unlock (`start_penangf_unlock`, L4062)

```
key = unlock_data.strip()                # exactly 32 hex chars
POST /generate-oem-key  {"key": "<32-char>"}  ← {'oem_key': '...'}
fastboot oem key <oem_key>               # must print OKAY
fastboot flashing unlock                 # must print OKAY
fastboot reboot
```

## Valeria — server-driven LK-swap unlock/FRP (`run_valeria_operation`, L3325)

Endpoint: `POST https://studiomaiky.com/val-protocol` with
`{'action': <action>, **payload}`, public headers
(`HWID/TIMESTAMP/VERSION-HASH`).

### Payload (all actions)

```python
{'operation': 'unlock'|'frp'|'unlock_frp',
 'serialno': <fastboot getvar serialno>,
 'codename': device_info['Codename'], 'model': device_info['Model'],
 'android_version': ..., 'secure_state': ..., 'frp_active': ...,
 'noise': {                       # anti-abuse fingerprint (L2891)
   'cid_prov_req': fastboot oem cid_prov_req output (last 4000 chars),
   'unlock_data':  fastboot oem get_unlock_data output,
   'read_sv':      fastboot oem read_sv output }}
```

### Actions

| Action | Sent | Received |
|---|---|---|
| `quote` | payload | `{'operation_id', 'cost'/'required_credits', ...}` (timeout 180); UI confirm dialog |
| `check_credits` | payload | `{'required_credits', 'available_credits'}` |
| `patched_lk` | payload | **raw binary patched LK** (streamed, 256 KB chunks) |
| `frp_command` | payload | `{'command': 'fastboot ...', 'charged_credits'}` |
| `unlock_key` | payload | `{'key': '...', 'charged_credits'}` |
| `original_lk` | payload | **raw binary stock LK** (for restore) |
| `upload_log` | `{'operation_id', 'log_text', 'status'}` | best-effort (timeout 30) |

### Operation flow

```
1. update_labels (fastboot device info)
2. Guards:
   - unlock & already unlocked → stop; unlock & not locked → stop
   - frp & unlocked bootloader → stop; frp & FRP not active → stop
   - MTK gate: fastboot oem partition → must contain 'nvram'   (L2820)
3. quote → check_credits → patched_lk
4. flash patched LK → lk_a/lk_b/lk (pick by current-slot; L3144)
5. fastboot reboot bootloader (wait ≤90 s)
6. [frp]      frp_command → run server command (120 s) → check frp-state;
              still active → restore original LK + reboot; else success
   [unlock*]  unlock_key → fastboot oem unlock <key> (user: Vol-down + power)
              tolerance on success strings ('bootloader is unlocked',
              'rebooting to fastboot' etc., L3206) → wait disconnect ≤8 s,
              reconnect ≤90 s → check state → not unlocked → restore LK
7. restore original_lk on EVERY exit path (_valeria_restore_original, L3240)
8. upload_log (logs/valeria_{ts}.log)
```

LK flashing uses pyfastboot streaming (`_valeria_flash_lk`, L3176):
`_protocol.SendCommand(b'download', b'%08x' % size)` +
`HandleDataSending(source, size, info_cb)` + `Flash(partition)` —
effectively `fastboot download` + `fastboot flash lk_a` without RAM blowup.

State sets (L2769): `VALERIA_UNLOCKED_STATES = {'1','yes','true','enable',
'unlocked','engineering','oem_unlocked','flashing_unlocked','non-secure'}`;
`VALERIA_LOCKED_STATES = {'0','no','false','locked','secure','oem_locked',
'flashing_locked'}`.

**Design point**: the patched LK (which bypasses signature verification)
is flashed only transiently — stock LK is restored on every path. The
patched/stock LK images come from the server per-device.

## ROM patcher (`_patcher_patch_rom_flow`, L3859)

```
1. _load_erofs_api('MTool_EROFS.dll')    # pythonnet reflection → MToolErofsApi
2. find super image: super.img|super.bin, or super.img_sparsechunk.N series
3. workdir = source_folder (patch in place) OR <dest>/<name>_patched (copytree)
4. xml = flashfile.xml — find, else generate from scatter.txt (MTK) or
   update_flash.bat (SPD) (_patcher_ensure_flashfile_xml, L3719)
5. _patcher_normalize_boot_gki: rename boot-gki.img → boot.img (L3700)
6. _patcher_clean_unused_files: delete files not referenced in <step> (L3744)
7. POST /patcher-rom {'action': 'get_assets'}
   ← {'hosts_rules': str, 'apk_list_json': str, 'default_signature': str}
8. signature = custom or default or 'Moto-M Tool Power'
9. MToolErofsApi.PatchRom(target_super, signature, hosts_path, apk_list_path)
   # .NET EROFS patch: injects hosts file + APKs + signature into super
10. POST /patcher-rom {'action': 'register', 'codename', 'signature'}
   ← {'rom_id', 'decrypt_key': '<hex>'}
11. encrypt modified files (super chunks only) with AES key from decrypt_key
12. write mtool_rom.json = {'rom_id': ..., 'encrypted_files': [basenames]}
```

### Encryption scheme (`_patcher_encrypt_file_in_place`, L3817)

- **AES-256-CTR**, fresh `os.urandom(16)` nonce written as the **first
  16 bytes** of the file, then raw ciphertext; streamed in 4 MiB chunks
  (`_PATCHER_AES_CHUNK_SIZE = 4194304`); atomic `os.replace`.
- Inverse (`_patcher_decrypt_file_chunks`, L3844): read 16-byte nonce →
  CTR decryptor → chunked decrypt.
- Flash patched ROM (`_patcher_flash_rom_flow`, L4011): require
  `mtool_rom.json` → `POST /patcher-rom {'action': 'get_key', 'rom_id',
  'codename'}` → `{'decrypt_key'}` → flash all flashfile.xml steps in
  order via pyfastboot streaming; super chunks re-packed as sparse
  streaming (`_produce_super_subimages`, L7295).

### Generated flashfile XML (scatter → flashfile, L3443)

```xml
<flashing><header>
  <phone_model model="Moto-M_Tool"/>
  <software_version version="Moto-M_Tool_Power"/>
  <cid_value value="0x0032"/>
  <sparsing enabled="true" max-sparse-size="536870912"/>   <!-- 512 MiB -->
  <interfaces><interface name="AP"/></interfaces>
  <steps interface="AP"> flash steps from scatter (skip lk, lk_a)
        + <step operation="erase" partition="userdata"/>
        + <step operation="erase" partition="metadata"/> </steps>
```

Sparse image constants (L6983): magic `0xED26FF3A`, 28-byte file header,
12-byte chunk header, chunk types RAW=51905, FILL=51906, DONTCARE=51907,
CRC32=51908.

## Firmware mirrors (`get_base_url`, L6270)

By model year (from model name like "Moto G54 5G" → year parsed from
codename):

```
≥2022:  https://mirrors.lolinet.com
2020–2021: https://mirrors-obs-1.lolinet.com
≤2019:  https://mirrors-obs-2.lolinet.com
```

`download_firmware` (L6296): workdir `./Cleanfirm`; carriers tried in
order `[<device carrier>, 'RETUS', 'RETAIL']`; index URL
`{base}/firmware/lenomola/{year}/{codename}/official/{carrier}/`;
BeautifulSoup scrape → `a[href$='.zip']`; build-version regex
`([A-Za-z0-9]+\.[A-Za-z0-9]+(?:-[A-Za-z0-9]+)+)` else oldest; aiohttp
download with Range resume (`sync_download_with_aiohttp`, L715).

Blankflash (L6507): `{base}/firmware/lenomola/{year}/{codename}/blankflash/`
→ pick newest by `lastmod` → download to `./Blankflash/<codename>/` →
extract (zip/py7zr) → run `blank-flash.bat` via `cmd /c` → after 5 s
thread fires `fastboot reboot`.

## QR code / ADB enrollment (`generate_qr`, L6688; `get_temporary_link`, L6653)

```
GET /get-download-link  → {'url': '<temporary APK link>'}
```

QR payload (Android device-owner provisioning JSON):

```json
{"android.app.extra.PROVISIONING_DEVICE_ADMIN_COMPONENT_NAME":
    "com.motomtool.motomtool/.Hubris",
 "android.app.extra.PROVISIONING_DEVICE_ADMIN_PACKAGE_DOWNLOAD_LOCATION": "<temporary link>",
 "android.app.extra.PROVISIONING_DEVICE_ADMIN_PACKAGE_CHECKSUM": "1Rt3KUAT4o46zO7pWaQa6j_GNb_UDgNhdgHFglp2zwU",
 "android.app.extra.PROVISIONING_SKIP_ENCRYPTION": true,
 "android.app.extra.PROVISIONING_LEAVE_ALL_SYSTEM_APPS_ENABLED": true,
 "android.app.extra.PROVISIONING_ADMIN_EXTRAS_BUNDLE": {}}
```

The checksum is a hardcoded base64url SHA-256 of the enrolled APK.
`generate_qr`: `qrcode.QRCode(box_size=10, border=2)`, colors from the
two dominant colors of `motoicon.ico`, icon centered at ¼ size, 500×500
output. Window titles: "Scan to Enable ADB" / "Scan In Setup Wizard".

FlashPilot's own MDM QR flow lives in `python/gui/` + `build/mdm_qr/`
— same provisioning-keys idea, own app.

## CVE-2016-10277 / initroot — the fastboot FRP strategy (FlashPilot, own research)

The unlock-token path is retired: the 20-char code is per-device,
server-issued (Motorola portal), and cannot be generated or generalized —
a tool-level token strategy is a dead end for real devices.

The strategy instead uses **CVE-2016-10277** (public research:
alephsecurity/initroot — Roee Hay / Aleph Research, HCL Technologies;
kernel cmdline injection in the Motorola bootloader via the unprotected
`fsg-id` UTAG):

```
1. fastboot oem config fsg-id ""                       # read UTAG — gate
2. fastboot oem config fsg-id "a initrd=<ADDR>,<SIZE>"  # cmdline injection
3. fastboot flash foo initroot-<device>.cpio.gz         # buffers at ADDR
   (write "fails" with Invalid partition name — EXPECTED: the payload
   stays resident in the bootloader's download buffer)
4. fastboot continue                                    # boots the injection
   → kernel loads the injected initramfs → ADB daemon as root (uid 0),
   no authorization prompt, dm-verity disabled
5. root ADB: dd if=/dev/zero of=/dev/block/bootdevice/by-name/frp
   + reboot → FRP gone
```

Honest gates implemented in `flow_moto_frp_fastboot` (Rust):

- **Version gate**: `getvar version-bootloader` — the injection targets the
  Kernel-3.10/3.18 bootloader family (Moto G4/G5/X/Z era). Newer bootloaders
  (G6 and later) commonly protect the UTAG; the flow reads it and reports.
- **UTAG liveness gate**: `oem config fsg-id` must read back
  `protected="false"`, or the flow stops and says the CVE is patched here.
- **No shipped exploit images**: the per-device initramfs
  (`initroot-<device>.cpio.gz`) is NEVER distributed with the app — the flow
  requires `--file <initramfs> --partition <scratch_addr>` and points at the
  public research for producing one (scratch addresses are device-specific:
  0xA2100000 cedric, 0x92000000 athene, per the initroot README).

How the app handles exploit-based strategies (framework for future CVEs):

1. **Stage the chain** — each step is its own flow step in the transcript;
   the user sees every command before it runs.
2. **Gate honestly** — every prerequisite the exploit needs gets an explicit
   check (UTAG protection, bootloader version, per-device payload present);
   a failed gate STOPS with guidance instead of pretending success.
3. **Never ship the payload** — model-specific exploit artifacts stay out of
   the app; flows accept user-supplied paths and document the public source.
4. **Fallback always stated** — when an exploit gate fails, the flow names
   the realistic alternative (e.g. the ADB path once ADB is enabled) and the
   research backlog gets the next vector to validate.

## Fake-login via own DPC (FlashPilot, own implementation)

TestDPC-style flows depend on Google's sample app from the Play Store.
FlashPilot ships its own minimal device-owner app instead:

- Source: `android/FlashPilotDPC/` (`org.flashpilot.dpc`, minSdk 24,
  targetSdk 28 to match the G6 era). No support libs, no resources beyond
  the admin XML — builds with SDK cmdline tools only
  (`android/FlashPilotDPC/build.sh`: aapt2 -> javac -> d8 ->
  zipalign -> apksigner).
- `FpAdminReceiver.completeSetup()` (idempotent) is the "fake login":
  `USER_SETUP_COMPLETE=1` (Secure), `DEVICE_PROVISIONED=1` (Global),
  `ADB_ENABLED=1` (Global), hides `com.google.android.setupwizard` +
  `com.motorola.setupwizard` via `setApplicationHidden`, and calls
  `setUserSetupComplete()`. Runs automatically on
  `ACTION_PROFILE_PROVISIONING_COMPLETE` and manually from the
  MainActivity button.
- Flow `frp_fake_login` (Rust): resolves the APK (`--file` / FRP_DPC_APK
  env / default `mdm_qr/serve/flashpilot-dpc.apk`, honest error with build
  instructions when absent), computes the v1 signing-cert checksum
  (SHA-256, base64url) for the QR, detects the LAN IP for the download URL
  (FRP_DPC_APK_URL overrides), emits the QR via the shared provisioning
  helper, serves the APK dir on :8000 (best-effort, reuses a live server),
  waits up to 10 min for the authorized ADB session the DPC enables, then
  runs the standard FRP-clear steps and reboots.
- GUI: Motorola FRP REMOVE gains a "Fake Login · QR" row dispatching the
  flow under ("Remove FRP", "ADB").

## Three-DPC fake-login (FlashPilot, own implementation)

The software offers three device-owner choices for QR provisioning, all
routed through one flow (`frp_fake_login`, `--dpc ours|testdpc|adp`,
FRP_DPC_CHOICE env, one registry row each):

1. **ours** — `org.flashpilot.dpc/.FpAdminReceiver`
   (`android/FlashPilotDPC/`, APK `mdm_qr/serve/flashpilot-dpc.apk`).
   Performs the fake login itself on enrollment. minSdk 26, targetSdk 28
   (Android 8 through 14): version-guarded calls (suspend with hidden
   fallback, DPM + direct ADB writes, `setUserSetupComplete` only on 28+,
   `android:exported` set for 31+). Email-gated activity: the access email
   is baked at build time (`FP_ACCESS_EMAIL`, default `flashpilot@local`
   -> generated `AccessConfig.java`); the QR carries it in
   `PROVISIONING_ADMIN_EXTRAS_BUNDLE.fp_email` so the app pre-fills it,
   and entering it unlocks provisioning. Device-owner auto-run skips the
   gate (enrollment itself is the authorization).
2. **testdpc** — `com.afwserv.testdpc/.DeviceAdminReceiver`, local
   `mdm_qr/serve/testdpc.apk` preferred (LAN URL + v1 cert checksum),
   Play Store URL fallback when the file is absent.
3. **adp** — `com.google.android.apps.work.oobconfig/.DevAdminReceiver`
   (Android Device Policy), Play Store URL (no local APK, no cert, no
   serve step).

"Set it online on the PC": the flow serves a local APK dir on :8000
(best-effort, reuses a live server) and polls until the port answers
before printing the phone steps, so the download URL is verified live.
Extras merge via FRP_DPC_EXTRAS_JSON (generic, backward-compatible).
