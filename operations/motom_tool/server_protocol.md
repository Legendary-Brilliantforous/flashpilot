# server_protocol.md — Moto-M Tool uç noktaları, kimlik doğrulama, lisanslama

Moto-M Tool 4.2.2'nin her sunucu etkileşimi. Tüm seçenekler
`SERVER_BASE_URL = 'https://studiomaiky.com'` altında (L79). İstemci ince bir orkestratördür — Fernet anahtarları, unlock kodları, yamalanmış LK imajları, loader arşivleri ve komut listeleri tümü bu uç noktalardan gelir.

## Uç nokta tablosu

| Sabit | Uç nokta | Yöntem | Gönderilen | Alınan |
|---|---|---|---|---|
| `SERVER_URL_LINK` | `/get-link` | GET | — | sürüm bağlantısı |
| `SERVER_URL_ROM_PASSWORD` | `/get-rom-password` | GET | codename | ROM zip şifresi |
| `SERVER_URL_KEY` | `/get-key` | GET | — | `{'key'}` = Fernet anahtarı (cookies blob, config.ini) |
| `SERVER_URL_PINOUT` | `/get-pinout-key` | GET | — | `{'key'}` = Fernet anahtarı (`pinout_encrypted.bin`) |
| `SERVER_URL_UPDATE` | `/check-update` | GET | — | güncelleme durumu |
| `SERVER_URL_AUTHORIZE` | `/get-patch-byte` | GET | — | **tek ham bayt** (FRP patch byte) |
| `SERVER_URL_KEYGEN` | `/generate-oem-key` | POST | `{'key': <32-hex>}` | `{'oem_key'}` |
| `SERVER_URL_LOADER` | `/get-loader-key` | GET | — | `{'key'}` = Fernet anahtarı (`*.MTool` arşivleri, tmp_rsc, v6) |
| `SERVER_URL_SPD_SESSION_TOKEN` | `/get-spd-session-token` | GET | — | `{'token'}` → `SpdClient.Authorize(hwid, token)` |
| `SERVER_URL_SPD_LOADER_KEY` | `/get-spd-loader-key` | GET | — | `{'key'}` = Fernet anahtarı (SPD yükleyicileri) |
| `SERVER_URL_SPD_LOADER_LINK` | `/get-spd-loader-link` | GET | `?cpu={profile}` | `{'url'}` → loader indirme |
| `SERVER_URL_SPD_UNLOCK_HASH` | `/spd-derive-unlock-key` | POST | `{'token': hex}` (+`{'variant':'t760_pandora_aes','profile':'Tiger T760_64'}`) | `{'hash'}`/`{'blob'}` |
| `SERVER_URL_CHECK_RESOURCES` | `/check-resources` | POST | `{'resources': {dll: sha256}}` | `{'resources': [{'name','url','hash'}]}` |
| `SERVER_URL_EXYNOS_SESSION` | `/exynos-session` | POST | `{'model', 'need_link'}` | `{'soc','key','url'}` |
| `SERVER_URL_EULA_COMMANDS` | `/get-eula-commands` | GET | `?parte=<part>` | `{'commands': [...]}` |
| `SERVER_URL_KG_LOCK_COMMANDS` | `/get-kg-lock-commands` | GET | `?parte=<part>` | `{'commands': [...]}` |
| `SERVER_URL_MDM_LOCK_COMMANDS` | `/get-mdm-lock-commands` | GET | `?parte=<part>` | `{'commands': [...]}` |
| `SERVER_URL_QR_LINK` | `/get-download-link` | GET | `?exploit=kg` (KG akışı) | `{'url'}` (geçici APK/exploit bağlantısı) |
| `SERVER_URL_VALERIA_LK` | `/val-protocol` | POST | eylem JSON | eylem başına (bkz. motorola_unlock.md) |
| `SERVER_URL_PATCHER_ROM` | `/patcher-rom` | POST | eylem JSON | eylem başına (bkz. motorola_unlock.md) |
| `AUTH_ENDPOINT` | `/auth/cli-token` | GET | aşağıdaki başlıklar | `{'jwt'}` (yük `k` = 32 bayt HMAC anahtarı) |
| `GET_UNLOCK_CANDIDATES_URL` | `/get-unlock-candidates` | POST | `{'server_id', 'request_timestamp', 'success_timestamp', 'consume': true}` | `{'candidates': [{'code', ...}]}` |
| `CREATE_USER_URL` | `/create-user` | POST | hesap JSON | kullanıcı oluşturuldu |
| `LOGIN_URL` | `/login` | POST | e-posta/şifre | tokenlar |
| `REFRESH_TOKEN_URL` | `/refresh-token` | POST | `{'refresh_token'}` | yeni tokenlar |
| `LOGOUT_URL` | `/logout` | POST | `{'refresh_token'}` | — |
| `SEND_CODE_URL` | `/send-code` | GET/POST | e-posta | doğrulama kodu gönderildi |
| `SEND_REGISTER_CODE_URL` | `/send-register-code` | — | e-posta | kayıt kodu |
| `RESET_PASSWORD_URL` | `/reset-password` | — | e-posta+kod+şifre | şifre sıfırlama |

Hata kuralları: `403` = "Unauthorized HWID" (yasak), `426` =
upgrade required with `latest_version_link` gövdede (istemci indirir ve yeni kurucuyu otomatik çalıştırır, ardından `os._exit(0)` yapar, L1508).

## Genel istek başlıkları (`build_public_request_headers`, L2746)

```python
{'HWID': <winreg HKLM\SOFTWARE\Microsoft\Cryptography\MachineGuid>,
 'TIMESTAMP': str(int(time.time())),
 'VERSION-HASH': sha256(sys.executable if frozen else __file__)}   # generate_version_hash L836
```

Kimlik doğrulamalı çağrılara `Authorization: ******`
(`build_internal_headers`, L477) eklenir. Diğer tüm sunucu çağrıları bu üç başlığı kullanır — HWID lisans anahtarıdır.

## Kimlik doğrulama / lisans modeli

- **Giriş** (`LoginLauncher`, L7855): e-posta + şifre + "Remember me";
  kayıt/sıfırlama akışları e-posta kodlarıyla. Rol `cliente`
  (`CLIENT_ROLE`, L113); hesap bilgisi kullanıcı/kredi/gün gösterir
  (`current_account_info`, L129) — **kredi bazlı lisanslama**.
- **Oturum saklama**: `config.ini` `[USUARIO]` bölümü (e-posta,
  DPAPI korumalı şifre, tokenlar); `session.cache` = JSON
  `{'v':1, 'data': 'dpapi:<b64>'}` — Windows **DPAPI**
  (`CryptProtectData` description `'MotoMToken'` ile), dosya `SetFileAttributesW(2)` ile gizlenir
  (`_protect_local_secret` L172 / `_write_cache` L303). Cache klasörü: `%LOCALAPPDATA%\MotoMTool\session.cache`
  (geri dönüş `./MotoMTool/`).
- **Token yenileme**: `POST /refresh-token` ile refresh_token; rol JWT `rol` talebiyle kontrol edilir; expiry skew 15 s
  (`access_token_valid` / `refresh_access_token`, L416–462).
- **JWT oturum anahtarı**: `decode_session_key_from_jwt` (L1325) — yük alanı `k`, `base64.b64decode` → mutlaka **32 bayt** olmalı → HMAC-SHA256 anahtarı, MtkDllSession meydan okumasına cevap vermek için kullanılır.
- **Çıkış**: `POST /logout` + cache temizleme, `atexit` üzerinden kayıtlı (L508).

## HWID parmak izi

İki mekanizma:

1. **Birincil HWID** (`get_hwid_from_registry`, L1219):
   `HKLM\SOFTWARE\Microsoft\Cryptography\MachineGuid` — her sunucu çağrısında ham olarak `HWID` başlığı olarak gönderilir.
2. **Bileşik HWID** (`get_new_hwid_from_registry`, L1473) — WMIC'ten UUID tarzı parmak izi:
   ```
   baseboard serialnumber → BB:<v>
   bios serialnumber      → BIOS:<v>
   cpu processorid        → CPU:<v>
   csproduct uuid         → CSUUID:<v>
   diskdrive serialnumber → DISK<i>:<v>    (tüm diskler)
   fingerprint = sha256('|'.join(parts))
   HWID = fingerprint[0:8]-[8:12]-[12:16]-[16:20]-[20:32]
   ```
   `_clean_hw_value` genel değerleri filtreler (`na, oem, none, default,
   unknown, 1a1a1a00, ffffff..., to be filled by o.e.m., ...`, L1383).
   `_wmic_get_single/_wmic_get_multi` çalıştırır `wmic <args>` ile
   `STARTF_USESHOWWINDOW` (görünmez konsol penceresi).

## Kaynak güncelleme protokolü (`check_and_update_resources`, L1266)

```
for name in CHECKED_RESOURCE_DLLS = ('MToolMTK.dll', 'MToolSPD.dll'):
    local = Resources/<name>; sha = sha256(local) or ''
POST /check-resources {'resources': {name: sha}} (internal headers, timeout 20)
for each {'name','url','hash'}:
    download streamed (256 KiB chunks) → <name>.tmp
    sha256(tmp) != hash → delete (raise 'Invalid hash'); else os.replace
```

`MTool_EROFS.dll`, `tmp_rsc.MTool`, `v6.MTool`, `Exynos.MTool` başka uç noktalardan talep edilip indirilir.

## Uygulama güncelleme kanalı

- `request_update_status` / `check_for_updates` (L7632): başlangıçta ve istenildiğinde
  `SERVER_URL_UPDATE` kontrolü yapar; changelog biçimlendirilir ve gösterilir (`format_changelog`, L7623).
- Zorunlu güncelleme (HTTP 426 herhangi bir yerde):
  `download_installer_to_temp` → `launch_installer_detached`
  (L726–818) → `os._exit(0)`. İndirmeler aiohttp ile ilerleme gösterimiyle yapılır.

## Sürüm hash'i

`generate_version_hash` (L836): çalışan exe'nin (dondurulmuş) veya ana betiğin SHA-256'sı.
`/auth/cli-token` ayrıca `VERSION-HASH: sha256(Resources/MToolMTK.dll)` gönderir — sunucu JWT anahtarını tam DLL derlemesine bağlar (anti-tamper: değiştirilmiş DLL → 426).
