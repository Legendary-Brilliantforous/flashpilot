# server_protocol.md — Moto-M Tool endpoints, auth, licensing

Every server interaction Moto-M Tool 4.2.2 makes. All under
`SERVER_BASE_URL = 'https://studiomaiky.com'` (L79). The client is a
thin orchestrator — Fernet keys, unlock codes, patched LK images, loader
archives and command lists all come from these endpoints.

## Endpoint table

| Constant | Endpoint | Method | Sent | Received |
|---|---|---|---|---|
| `SERVER_URL_LINK` | `/get-link` | GET | — | version link |
| `SERVER_URL_ROM_PASSWORD` | `/get-rom-password` | GET | codename | ROM zip password |
| `SERVER_URL_KEY` | `/get-key` | GET | — | `{'key'}` = Fernet key (cookies blob, config.ini) |
| `SERVER_URL_PINOUT` | `/get-pinout-key` | GET | — | `{'key'}` = Fernet key (pinout_encrypted.bin) |
| `SERVER_URL_UPDATE` | `/check-update` | GET | — | update status |
| `SERVER_URL_AUTHORIZE` | `/get-patch-byte` | GET | — | **single raw byte** (FRP patch byte) |
| `SERVER_URL_KEYGEN` | `/generate-oem-key` | POST | `{'key': <32-hex>}` | `{'oem_key'}` |
| `SERVER_URL_LOADER` | `/get-loader-key` | GET | — | `{'key'}` = Fernet key (`*.MTool` archives, tmp_rsc, v6) |
| `SERVER_URL_SPD_SESSION_TOKEN` | `/get-spd-session-token` | GET | — | `{'token'}` → `SpdClient.Authorize(hwid, token)` |
| `SERVER_URL_SPD_LOADER_KEY` | `/get-spd-loader-key` | GET | — | `{'key'}` = Fernet key (SPD loaders) |
| `SERVER_URL_SPD_LOADER_LINK` | `/get-spd-loader-link` | GET | `?cpu={profile}` | `{'url'}` → loader download |
| `SERVER_URL_SPD_UNLOCK_HASH` | `/spd-derive-unlock-key` | POST | `{'token': hex}` (+`{'variant':'t760_pandora_aes','profile':'Tiger T760_64'}`) | `{'hash'}`/`{'blob'}` |
| `SERVER_URL_CHECK_RESOURCES` | `/check-resources` | POST | `{'resources': {dll: sha256}}` | `{'resources': [{'name','url','hash'}]}` |
| `SERVER_URL_EXYNOS_SESSION` | `/exynos-session` | POST | `{'model', 'need_link'}` | `{'soc','key','url'}` |
| `SERVER_URL_EULA_COMMANDS` | `/get-eula-commands` | GET | `?parte=<part>` | `{'commands': [...]}` |
| `SERVER_URL_KG_LOCK_COMMANDS` | `/get-kg-lock-commands` | GET | `?parte=<part>` | `{'commands': [...]}` |
| `SERVER_URL_MDM_LOCK_COMMANDS` | `/get-mdm-lock-commands` | GET | `?parte=<part>` | `{'commands': [...]}` |
| `SERVER_URL_QR_LINK` | `/get-download-link` | GET | `?exploit=kg` (KG flow) | `{'url'}` (temporary APK/exploit link) |
| `SERVER_URL_VALERIA_LK` | `/val-protocol` | POST | action JSON | per-action (see motorola_unlock.md) |
| `SERVER_URL_PATCHER_ROM` | `/patcher-rom` | POST | action JSON | per-action (see motorola_unlock.md) |
| `AUTH_ENDPOINT` | `/auth/cli-token` | GET | headers below | `{'jwt'}` (payload `k` = 32-byte HMAC key) |
| `GET_UNLOCK_CANDIDATES_URL` | `/get-unlock-candidates` | POST | `{'server_id', 'request_timestamp', 'success_timestamp', 'consume': true}` | `{'candidates': [{'code', ...}]}` |
| `CREATE_USER_URL` | `/create-user` | POST | account JSON | user created |
| `LOGIN_URL` | `/login` | POST | email/password | tokens |
| `REFRESH_TOKEN_URL` | `/refresh-token` | POST | `{'refresh_token'}` | new tokens |
| `LOGOUT_URL` | `/logout` | POST | `{'refresh_token'}` | — |
| `SEND_CODE_URL` | `/send-code` | GET/POST | email | verification code sent |
| `SEND_REGISTER_CODE_URL` | `/send-register-code` | — | email | register code |
| `RESET_PASSWORD_URL` | `/reset-password` | — | email+code+password | password reset |

Error conventions: `403` = "Unauthorized HWID" (banned), `426` =
upgrade required with `latest_version_link` in the body (the client
downloads and auto-runs the new installer, then `os._exit(0)`, L1508).

## Public request headers (`build_public_request_headers`, L2746)

```python
{'HWID': <winreg HKLM\SOFTWARE\Microsoft\Cryptography\MachineGuid>,
 'TIMESTAMP': str(int(time.time())),
 'VERSION-HASH': sha256(sys.executable if frozen else __file__)}   # generate_version_hash L836
```

Authenticated calls add `Authorization: Bearer <access_token>`
(`build_internal_headers`, L477). All other server calls use these
three headers — the HWID is the license key.

## Auth / licensing model

- **Login** (`LoginLauncher`, L7855): email + password + "Remember me";
  register/reset-password flows with email codes. Role `cliente`
  (`CLIENT_ROLE`, L113); account info shows user/credits/days
  (`current_account_info`, L129) — **credit-metered licensing**.
- **Session storage**: `config.ini` `[USUARIO]` section (email,
  DPAPI-protected password, tokens); `session.cache` = JSON
  `{'v':1, 'data': 'dpapi:<b64>'}` — Windows **DPAPI**
  (`CryptProtectData` with description `'MotoMToken'`), file hidden via
  `SetFileAttributesW(2)` (`_protect_local_secret` L172 /
  `_write_cache` L303). Cache dir: `%LOCALAPPDATA%\MotoMTool\session.cache`
  (falls back to `./MotoMTool/`).
- **Token refresh**: `POST /refresh-token` with refresh_token; role
  checked against JWT `rol` claim; expiry skew 15 s
  (`access_token_valid` / `refresh_access_token`, L416–462).
- **JWT session key**: `decode_session_key_from_jwt` (L1325) — payload
  field `k`, `base64.b64decode` → must be **32 bytes** → HMAC-SHA256
  key used to answer the MtkDllSession challenge.
- **Logout**: `POST /logout` + clear cache, registered via `atexit` (L508).

## HWID fingerprinting

Two mechanisms:

1. **Primary HWID** (`get_hwid_from_registry`, L1219):
   `HKLM\SOFTWARE\Microsoft\Cryptography\MachineGuid` — sent raw as the
   `HWID` header on every server call.
2. **Composite HWID** (`get_new_hwid_from_registry`, L1473) — UUID-style
   fingerprint from WMIC:
   ```
   baseboard serialnumber → BB:<v>
   bios serialnumber      → BIOS:<v>
   cpu processorid        → CPU:<v>
   csproduct uuid         → CSUUID:<v>
   diskdrive serialnumber → DISK<i>:<v>    (all disks)
   fingerprint = sha256('|'.join(parts))
   HWID = fingerprint[0:8]-[8:12]-[12:16]-[16:20]-[20:32]
   ```
   `_clean_hw_value` filters generic values (`na, oem, none, default,
   unknown, 1a1a1a00, ffffff..., to be filled by o.e.m., ...`, L1383).
   `_wmic_get_single/_wmic_get_multi` run `wmic <args>` with
   `STARTF_USESHOWWINDOW` (no console window).

## Resource update protocol (`check_and_update_resources`, L1266)

```
for name in CHECKED_RESOURCE_DLLS = ('MToolMTK.dll', 'MToolSPD.dll'):
    local = Resources/<name>; sha = sha256(local) or ''
POST /check-resources {'resources': {name: sha}} (internal headers, timeout 20)
for each {'name','url','hash'}:
    download streamed (256 KiB chunks) → <name>.tmp
    sha256(tmp) != hash → delete (raise 'Invalid hash'); else os.replace
```

`MTool_EROFS.dll`, `tmp_rsc.MTool`, `v6.MTool`, `Exynos.MTool` are
updated/downloaded on demand via the other endpoints.

## App update channel

- `request_update_status` / `check_for_updates` (L7632): checks
  `SERVER_URL_UPDATE` at startup + on demand; changelog formatted and
  shown (`format_changelog`, L7623).
- Forced upgrade (HTTP 426 anywhere):
  `download_installer_to_temp` → `launch_installer_detached`
  (L726–818) → `os._exit(0)`. Downloads are aiohttp with progress.

## Version hash

`generate_version_hash` (L836): SHA-256 of the running exe (frozen) or
the main script. `/auth/cli-token` also sends
`VERSION-HASH: sha256(Resources/MToolMTK.dll)` — the server ties the
JWT key to the exact DLL build (anti-tamper: modified DLL → 426).
