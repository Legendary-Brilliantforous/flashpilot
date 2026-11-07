# mtk.md — MediaTek alanı (Moto-M Tool)

Moto-M Tool 4.2.2 MediaTek'i nasıl kullanıyor. Asıl protokol bir .NET DLL içinde yaşıyor
(`MToolMTK.dll`, namespace `SharpMTKClient`, sınıf `MtkDllSession`),
process içindeki pythonnet aracılığıyla yüklenir; Python kimlik doğrulama, port tespiti,
pload seçimi ve orkestrasyonu yapar.

## Mimari

```
┌─────────────────────────────────────────────────────────────┐
│ Python GUI (customtkinter)                                  │
│   MTKPartitionManager  (orkestratör, L9966)                │
│   MTKConnector         (arg oluşturucu, L8720)                 │
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
   .Configure(argv)             (DLL BROM/DA protokolünü konuşur)
   .Boot() → partition ops
```

## USB port algılama

MTK VIDs, COM-port `hwid` dizeleriyle büyük harf eşleşmesi yapar
(`auto_crash.MTK_VIDS`, yedek liste `das` 136678):

```
0E8D   MediaTek
0FCE   (Sony/Google)
1004   (LG)
22D9   (OPPO)
9BB5   (InFocus)
```

Klasik BROM el sıkışması (`0xA0 0x0A 0x50 0x05` @ 115200) DLL içinde olur — Python yalnızca `serial.tools.list_ports.comports()` sorgular (`_wait_and_log_mtk_device`, L10098).

## Bağlantı/boot çekirdeği — `_spawn_gpt_session` (L10112)

```
_spawn_gpt_session(preloader_path)
├─ DEADLINE = time.monotonic() + 180          # 3 dakikalık sert zaman aşımı
├─ _ensure_jwt()                              # JWT + 32 bayt oturum anahtarı
├─ _ensure_payload_ready()                    # Resources/MToolMTK.dll mevcut olmalı
├─ cancel_event; auto_crash.set_cancel_event(cancel_event)
│
├─ DAL:
│   ├─ var_detect_only → _wait_and_log_mtk_device, then poll
│   │     auto_crash._get_mtk_state() → (kind, port)   # 'brom'|'preloader'
│   ├─ var_crash_preloader (checkbox) → _crash():
│   │     wait for PRELOADER port
│   │     (ok, info) = crash_to_brom()                 # ← EXPLOIT
│   │     ok → wait ≤8 s for BROM port re-enumeration → 'Handshake: Ok'
│   └─ else → _handshake():
│         wait for PRELOADER port
│         (ok, info, _) = preloader_handshake_only()  # zararsız el sıkışma
│
├─ MOD RESOLÜSYONU:
│   if auto_crash.brom: effective_model = 'Universal Device'  # forced universal
│   tokens = connector.modelExtraArgsMap[effective_model].split()
│   tokens = connector._apply_user_overrides(tokens, model_preloader)
│   if var_patch_da: tokens += ['--xmlcar']
│
├─ SON DLL ARGÜMANLARI:
│   ['--cli','--mode','universal','--sla','auto'] + tokens + ['--skip-handshake']
│
├─ AUTH KÖPRÜSÜ:
│   os.environ['SMTK_AUTH'] = jwt; os.environ['SMTK_SKIP_HANDSHAKE'] = '1'
│   cls = clr → SharpMTKClient.MtkDllSession
│   session = cls(Action[str,str] log_cb, Action[float] progress_cb)
│   challenge = session.Authorize(jwt)              # base64 challenge
│   sig = HMAC-SHA256(session_key, b64decode(challenge))
│   session.AnswerChallenge(b64encode(sig)) → must be True
│
├─ session.Configure(Array[str](args))
├─ boot_result = session.Boot()     # DLL asıl BROM/DA protokolünü yapar
├─ fail → Dispose() → "Can't boot device."
└─ finally: cancel_event.set(); auto_crash.set_cancel_event(None)
```

### Sunucu→JWT→DLL kimlik doğrulama zinciri (`get_cli_token_and_k_from_payload`, L1346)

```
version_hash = SHA256(Resources/MToolMTK.dll)      # 1 MiB parça
hwid         = HKLM\SOFTWARE\Microsoft\Cryptography\MachineGuid
headers      = {'HWID': hwid, 'TIMESTAMP': str(int(time.time())),
                'VERSION-HASH': version_hash,
                'Authorization': 'Bearer ' + client_access_token}
GET /auth/cli-token (timeout 10)
 200 → jwt;  session_key = b64decode(jwt_payload['k'])   # tam 32 bayt
 426 → out of date (sunucu latest_version_link döndürür)
 403 → HWID yetkisiz
```

JWT süresi 15 s kayma ile kontrol edilir (`_jwt_is_expired`, L9950).
`sign_cmd_line(body, key)` (L1375) = `CMD:{body}\tSIG:{b64(HMAC-SHA256)}\n`
(karşıya DLL boru hattı protokolü için imzalanmış komut satırı zarfı).
`hkdf_derive` (L1016) mevcut ama bu derlemede **ölü kod**.

## MtkDllSession API yüzeyi (Python tarafından çağrılanlar)

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

DLL tarafından tanınan CLI bayrakları: `--cli --mode universal --sla auto
--skip-handshake --patchda on|off --xmlcar --scatter X --da X --da1 X
--da2 X --ida`. Özel DA zorla `--patchda off` (L8827). Model bazlı ek argümanlar ve izinli eylem setleri sunucu konfigürasyonundan gelir
(`modelAllowedActionsMap` / `modelExtraArgsMap`).

Varsayılan izinli eylemler (`getAllowedActions`, L8741): `remove_frp,
read_partitions, erase_partitions, flash_scatter_fw, write_partitions,
factory_reset_frp, unlock_bootloader`.

## MTK exploit/bypass mantığı

1. **Crash-to-BROM** — "crash preloader" onay kutusu → preloader portu bekle
   → `crash_to_brom()` → ≤8 s içinde BROM yeniden numaralanmasını bekle → `'Universal Device'` zorla (model DA yok, `--sla auto`).
2. **Bootloader unlock** — GPT oturumu açıkken:
   `MtkDllSession.Unlock(True)`; ardından `Reboot('normal')`
   (`_mtk_unlock_flow`, L11310).
3. **Preloader-yedek unlock** (G05/G06/G15 özel, `unlock_preloader_backup_flow`, L10541):
   ```
   if already in BROM: unlock in Universal session → done
   else:
     1) GPT session → r preloader → Resources/Backup/MTK/{Model}_Unlock_Bootloader_Backup_{ts}/
     2) e preloader + e preloader_backup
     3) Reboot + sleep 3
     4) Universal session with --preloader=<backup file>
     5) unlock → w preloader (restore backup) → Reboot
   ```
   Yapılan tokenlar: `read part done`, `erase part done`. Hata tokenları:
   `timeout, unexpected, failed, device removed, not exist, ...`.
4. **v6 blank flash** (`run_v6_blankflash_flow`, L11279): Fernet ile şifre çözülmüş
   `Resources/v6.MTool` (sunucu anahtarı `/get-loader-key` üzerinden) → GPT
   oturumu → `BlankFlash(tmp_dir)` (timeout 180).
5. **Moto E15 unlock** (`unlock_moto_e15_flow`, L10904) — BROM+fastboot hibriti:
   ```
   0) Fernet ile şifresi çözülmüş Resources/tmp_rsc.MTool → 1.bin/2.bin/3.bin çıkar
   1) GPT oturumu (BROM/preloader)
   2) WritePartitionRsc: 1.bin→frp, 2.bin→oem_mfd, 3.bin→proinfo
   3) kullanıcı el ile FASTBOOT'a yeniden başlatır → ≤240 s bekle
   4) fastboot getvar facmode — 'yes' olmalı
   5) fastboot flashing unlock (kullanıcı onayı, ≤180 s)
      BAŞARISIZ → fastboot flash frp 1.bin → reboot bootloader → tekrar dene
   6) temizleme
   ```
   Uygulama kökünde `1`–`5` dosyalar çok küçük patch yükleri; `2` dosyası `androidboot.secure_hardware=0` içerir (cmdline patch), `1` dosyası `factory` içerir.

## FRP / çeşitli patch dosyaları (L859–936)

- `edit_file_frp`: `GET /get-patch-byte` → **tek ham bayt**; FRP dosyasının son baytını yerinde değiştirir. "Patched FRP" dosyası tüm `0x00` ve son 31 konum, hex-hesaplanmış metin "4d6f746f2d4d546f6f6c506f776572" ile doludur (çift hex kod çözüldüğünde **"Moto-M Tool Power"** çıkar) + son bayt sunucu patch byte'dır.
- `edit_file_hex` (diğer bölüm): 139 baytlık Android **BCB** şablonu —
  `boot-recovery` + sıfır dolgu + `recovery\n--wipe_data\n\n  --reason=MasterClearConfirm,2022-11-15T05:19:09Z\n--locale=es-MX\n`.
  Bunu yazmak recovery wipe -> fabrika sıfırlama tetikler. Aynı şablon `Resources/reset.binary` olarak gelir.
- **vbmeta** (`flash_vbmeta_devices`, L12822):
  `fastboot --disable-verity flash vbmeta "Firmpatch/<codename>/vbmeta.img"`.

## Fastboot üzerinden MTK fabrika sıfırlama (`run_reset_mtk_and_spd_commands`, L8695)

```
mtk: fastboot oem fb_mode_set
     fastboot flash userdata mtk.img       # önceden derlenmiş reset userdata görüntüsü
     fastboot erase debug_token            # Motorola debug token'ını siler
     fastboot oem fb_mode_clear
     fastboot reboot
```

## İlerleme ayrıştırma (`FastbootProgressParser`, L2073)

Fastboot çıktısı tek satır tek satır regex ile okunur:

```
SEND_RE          ^(Sending|Writing)\s+'([\w\-.]+)'
SEND_SPARSE_RE   ^Sending\s+sparse\s+'(super)'\s+(\d+)/(\d+)\s+\([^)]+\)\s+OKAY
WRITING_RE       ^Writing\s+'([\w\-.]+)'\s+OKAY
OKAY_RE          OKAY
FAILED_RE        FAILED|error:
FINISHED_RE      ^Finished\.\s+Total time:
REDUNDANT_ERROR_RE ^fastboot:\s+error:\s+Command failed$
```

Basit eylem: `Sending` → %33, `Writing OKAY` → %66 → %100.
Sparse super: toplam adım sayısı = bölüm × 2 (her biri için send + write); progress = adım_sayısı / toplam_adım. FAILED/error → bölüm düzeyi hata durumu; başarısızlıktan sonra gereksiz `fastboot: error: Command failed` bastırılır.

## Referans indeksi

MTKPartitionManager: `__init__` 9969 · `_ensure_jwt` 10057 ·
`_spawn_gpt_session` 10112 · `request_partitions` 10280 ·
`_parse_scatter_file` 10345 · `_unlock_current_session` 10471 ·
`unlock_preloader_backup_flow` 10541 · `fetch_loader_key` 10797 ·
`_prepare_encrypted_mtool_dir` 10822 · `unlock_moto_e15_flow` 10904 ·
`run_v6_blankflash_flow` 11279 · `_mtk_unlock_flow` 11310 ·
`scatter_flash` 11399 · `process_partitions` 11743 · `unlock` 11928.

MTKConnector: `__init__` 8729 · `getAllowedActions` 8741 ·
`_apply_user_overrides` 8780 · `apply_xmlcar_arg` 8859.

Destek: `decode_session_key_from_jwt` 1325 · `get_cli_token_and_k_from_payload`
1346 · `sign_cmd_line` 1375 · `get_hwid_from_registry` 1219 ·
`spd_do_handshake` 8958.
