# mtk.md — MediaTek domain (Moto-M Tool)

How Moto-M Tool 4.2.2 does MediaTek. The real protocol lives in a .NET
DLL (`MToolMTK.dll`, namespace `SharpMTKClient`, class `MtkDllSession`)
loaded in-process via pythonnet; Python does auth, port detection,
payload selection and orchestration.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ Python GUI (customtkinter)                                  │
│   MTKPartitionManager  (orchestrator, L9966)                │
│   MTKConnector         (arg builder, L8720)                 │
└──────┬──────────────────────────────┬───────────────────────┘
       │ 1. auth (HTTPS)              │ 2. crash/handshake (serial)
       ▼                              ▼
 https://studiomaiky.com        src.auto_crash (Cython .pyd:
 (JWT + HWID + version-hash)    crash_to_brom, preloader_handshake_only)
       │                              │
       │ 3. pythonnet clr              ▼
       ▼                        MTK port (VID 0E8D etc.)
 MToolMTK.dll → MtkDllSession         │
   .Authorize(jwt) → challenge        ▼
   .AnswerChallenge(hmac)       MtkDllSession.Boot()
   .Configure(argv)             (DLL talks BROM/DA protocol)
   .Boot() → partition ops
```

## USB port detection

MTK VIDs matched UPPERCASE against COM-port `hwid` strings
(`auto_crash.MTK_VIDS`, fallback list in `das` 136678):

```
0E8D   MediaTek
0FCE   (Sony/Google)
1004   (LG)
22D9   (OPPO)
9BB5   (InFocus)
```

The classic BROM handshake (`0xA0 0x0A 0x50 0x05` @ 115200) happens
inside the DLL — Python only polls `serial.tools.list_ports.comports()`
(`_wait_and_log_mtk_device`, L10098).

## The connect/boot core — `_spawn_gpt_session` (L10112)

```
_spawn_gpt_session(preloader_path)
├─ DEADLINE = time.monotonic() + 180          # 3-minute hard timeout
├─ _ensure_jwt()                              # JWT + 32-byte session key
├─ _ensure_payload_ready()                    # Resources/MToolMTK.dll must exist
├─ cancel_event; auto_crash.set_cancel_event(cancel_event)
│
├─ BRANCH:
│   ├─ var_detect_only → _wait_and_log_mtk_device, then poll
│   │     auto_crash._get_mtk_state() → (kind, port)   # 'brom'|'preloader'
│   ├─ var_crash_preloader (checkbox) → _crash():
│   │     wait for PRELOADER port
│   │     (ok, info) = crash_to_brom()                 # ← EXPLOIT
│   │     ok → wait ≤8 s for BROM port re-enumeration → 'Handshake: Ok'
│   └─ else → _handshake():
│         wait for PRELOADER port
│         (ok, info, _) = preloader_handshake_only()  # benign handshake
│
├─ MODE RESOLUTION:
│   if auto_crash.brom: effective_model = 'Universal Device'  # forced universal
│   tokens = connector.modelExtraArgsMap[effective_model].split()
│   tokens = connector._apply_user_overrides(tokens, model_preloader)
│   if var_patch_da: tokens += ['--xmlcar']
│
├─ FINAL DLL ARGS:
│   ['--cli','--mode','universal','--sla','auto'] + tokens + ['--skip-handshake']
│
├─ AUTH BRIDGE:
│   os.environ['SMTK_AUTH'] = jwt; os.environ['SMTK_SKIP_HANDSHAKE'] = '1'
│   cls = clr → SharpMTKClient.MtkDllSession
│   session = cls(Action[str,str] log_cb, Action[float] progress_cb)
│   challenge = session.Authorize(jwt)              # base64 challenge
│   sig = HMAC-SHA256(session_key, b64decode(challenge))
│   session.AnswerChallenge(b64encode(sig)) → must be True
│
├─ session.Configure(Array[str](args))
├─ boot_result = session.Boot()     # DLL does the actual BROM/DA protocol
├─ fail → Dispose() → "Can't boot device."
└─ finally: cancel_event.set(); auto_crash.set_cancel_event(None)
```

### Server→JWT→DLL auth chain (`get_cli_token_and_k_from_payload`, L1346)

```
version_hash = SHA256(Resources/MToolMTK.dll)      # 1 MiB chunks
hwid         = HKLM\SOFTWARE\Microsoft\Cryptography\MachineGuid
headers      = {'HWID': hwid, 'TIMESTAMP': str(int(time.time())),
                'VERSION-HASH': version_hash,
                'Authorization': 'Bearer ' + client_access_token}
GET /auth/cli-token (timeout 10)
 200 → jwt;  session_key = b64decode(jwt_payload['k'])   # exactly 32 bytes
 426 → out of date (server returns latest_version_link)
 403 → HWID unauthorized
```

JWT expiry checked with a 15 s skew (`_jwt_is_expired`, L9950).
`sign_cmd_line(body, key)` (L1375) = `CMD:{body}\tSIG:{b64(HMAC-SHA256)}\n`
(signed command-line envelope for the DLL pipe protocol).
`hkdf_derive` (L1016) exists but is **dead code** in this build.

## MtkDllSession API surface (as called from Python)

```
MtkDllSession(Action[str,str] log_cb, Action[float] progress_cb)
.Authorize(jwt) -> base64 challenge            # das 138628
.AnswerChallenge(b64_hmac_answer) -> bool      # das 138667
.Configure(Array[str] cli_args)                # das 138736
.Boot() -> bool                                # das 138760
.Stop() / .Dispose()
.Reboot('normal')
.ListPartitions() -> [Index, Name, StartBytes, SizeBytes]
.GenerateScatter(out_dir)
.ReadPartition(name|idx, out_dir)
.ErasePartition(name|idx)
.ErasePartitionRsc(name, False) / .WritePartitionRsc(path, part, False)
.WritePartition(path, part_name, False)
.ScatterFlash(scatter_path, 'download', Array[str] parts)
.Repartition(xml_path) / .BlankFlash(dir) / .Unlock(True)
```

CLI flags understood by the DLL: `--cli --mode universal --sla auto
--skip-handshake --patchda on|off --xmlcar --scatter X --da X --da1 X
--da2 X --ida`. Custom DA forces `--patchda off` (L8827). Per-model
extra args + allowed-action sets come from server config
(`modelAllowedActionsMap` / `modelExtraArgsMap`).

Default allowed actions (`getAllowedActions`, L8741): `remove_frp,
read_partitions, erase_partitions, flash_scatter_fw, write_partitions,
factory_reset_frp, unlock_bootloader`.

## MTK exploit/bypass logic

1. **Crash-to-BROM** — "crash preloader" checkbox → wait preloader port
   → `crash_to_brom()` → wait ≤8 s for BROM re-enumeration → force
   `'Universal Device'` (no model DA, `--sla auto`).
2. **Bootloader unlock** — with GPT session alive:
   `MtkDllSession.Unlock(True)`; then `Reboot('normal')`
   (`_mtk_unlock_flow`, L11310).
3. **Preloader-backup unlock** (G05/G06/G15 special, `unlock_preloader_backup_flow`, L10541):
   ```
   if already in BROM: unlock in Universal session → done
   else:
     1) GPT session → r preloader → Resources/Backup/MTK/{Model}_Unlock_Bootloader_Backup_{ts}/
     2) e preloader + e preloader_backup
     3) Reboot + sleep 3
     4) Universal session with --preloader=<backup file>
     5) unlock → w preloader (restore backup) → Reboot
   ```
   Done tokens: `read part done`, `erase part done`. Error tokens:
   `timeout, unexpected, failed, device removed, not exist, ...`.
4. **v6 blank flash** (`run_v6_blankflash_flow`, L11279): Fernet-decrypt
   `Resources/v6.MTool` (server key from `/get-loader-key`) → GPT
   session → `BlankFlash(tmp_dir)` (timeout 180).
5. **Moto E15 unlock** (`unlock_moto_e15_flow`, L10904) — BROM+fastboot hybrid:
   ```
   0) Fernet-decrypt Resources/tmp_rsc.MTool → extract 1.bin/2.bin/3.bin
   1) GPT session (BROM/preloader)
   2) WritePartitionRsc: 1.bin→frp, 2.bin→oem_mfd, 3.bin→proinfo
   3) user reboots to FASTBOOT manually → wait ≤240 s
   4) fastboot getvar facmode — must be 'yes'
   5) fastboot flashing unlock (user confirms, ≤180 s)
      FAILED → fastboot flash frp 1.bin → reboot bootloader → retry once
   6) cleanup
   ```
   The `1`–`5` files in the app root are tiny patch payloads; file `2`
   embeds `androidboot.secure_hardware=0` (cmdline patch), file `1`
   embeds `factory`.

## FRP / misc patch files (L859–936)

- `edit_file_frp`: `GET /get-patch-byte` → **single raw byte**; rewrite
  last byte of FRP file in place. "Patched FRP" file = all `0x00` with
  the last 31 positions filled with the hex-of-hex string
  `"4d6f746f2d4d546f6f6c506f776572"` (double-hex decodes to
  **"Moto-M Tool Power"**) + the server patch byte as final byte.
- `edit_file_hex` (misc partition): 139-byte Android **BCB** template —
  `boot-recovery` + zero padding + `recovery\n--wipe_data\n
  --reason=MasterClearConfirm,2022-11-15T05:19:09Z\n--locale=es-MX\n`.
  Flashing it forces recovery wipe → factory reset. Same template ships
  as `Resources/reset.binary`.
- **vbmeta** (`flash_vbmeta_devices`, L12822):
  `fastboot --disable-verity flash vbmeta "Firmpatch/<codename>/vbmeta.img"`.

## MTK factory reset via fastboot (`run_reset_mtk_and_spd_commands`, L8695)

```
mtk: fastboot oem fb_mode_set
     fastboot flash userdata mtk.img       # prebuilt reset userdata image
     fastboot erase debug_token            # wipes Motorola debug token
     fastboot oem fb_mode_clear
     fastboot reboot
```

## Progress parsing (`FastbootProgressParser`, L2073)

Regexes on fastboot stdout, one line at a time:

```
SEND_RE          ^(Sending|Writing)\s+'([\w\-.]+)'
SEND_SPARSE_RE   ^Sending\s+sparse\s+'(super)'\s+(\d+)/(\d+)\s+\([^)]+\)\s+OKAY
WRITING_RE       ^Writing\s+'([\w\-.]+)'\s+OKAY
OKAY_RE          \bOKAY\b
FAILED_RE        \bFAILED\b|\berror:\b
FINISHED_RE      ^Finished\.\s+Total time:
REDUNDANT_ERROR_RE ^fastboot:\s+error:\s+Command failed$
```

Simple action: `Sending` → 33 %, `Writing OKAY` → 66 % → 100 %.
Sparse super: total steps = parts × 2 (send + write each); progress =
step_idx / total_steps. FAILED/error → partition-level error status;
redundant `fastboot: error: Command failed` after a failure is suppressed.

## Reference index

MTKPartitionManager: `__init__` 9969 · `_ensure_jwt` 10057 ·
`_spawn_gpt_session` 10112 · `request_partitions` 10280 ·
`_parse_scatter_file` 10345 · `_unlock_current_session` 10471 ·
`unlock_preloader_backup_flow` 10541 · `fetch_loader_key` 10797 ·
`_prepare_encrypted_mtool_dir` 10822 · `unlock_moto_e15_flow` 10904 ·
`run_v6_blankflash_flow` 11279 · `_mtk_unlock_flow` 11310 ·
`scatter_flash` 11399 · `process_partitions` 11743 · `unlock` 11928.

MTKConnector: `__init__` 8729 · `getAllowedActions` 8741 ·
`_apply_user_overrides` 8780 · `apply_xmlcar_arg` 8859.

Support: `decode_session_key_from_jwt` 1325 · `get_cli_token_and_k_from_payload`
1346 · `sign_cmd_line` 1375 · `get_hwid_from_registry` 1219 ·
`spd_do_handshake` 8958.
