# spd.md — Spreadtrum/UNISOC domain (Moto-M Tool)

How Moto-M Tool 4.2.2 does SPD/UNISOC. Two paths: an **exploit CLI**
(`spd.dll` child process with FDL injection) and a **.NET DLL**
(`MToolSPD.dll` via pythonnet, class `SpdClient`) for newer profiles.

## Profiles and model mapping (`SPDConnector.__init__`, L9089)

```python
dll_profiles = ['SC7731E', 'SC9832E', 'SC9863A', 'SC9863A_64',
    'Tiger T310_64', 'Tiger T606_64', 'Tiger T606_64_V2', 'Tiger T610_64',
    'Tiger T612_64', 'Tiger T616_64', 'Tiger T616_64_V2', 'Tiger T700_64',
    'Tiger T760_64']

model_processor_map = {          # UI model → exploit profile
    'Moto G14': 'T616',  'Moto E32': 'T606',  'Moto E20': 'T606',
    'Moto E13': 'T606',  'Moto G04': 'T616',  'Moto G04s': 'T616',
    'Moto E14': 'T616',  'Moto G20': 'T700',  'Moto E40': 'T700',
    'Moto G35': 'T760',  'Tiger T618_64': 'T618' }

motorola_dll_profile_map = {'Moto G35': 'Tiger T760_64'}   # DLL path for G35 unlock
```

## FDL/exploit addresses (L9127–9139)

```python
processor_fdl_map = {            # (FDL1 load addr, FDL2 load addr)
    'T606': ('0x65000800', '0x9efffe00'),
    'T616': ('0x65000800', '0x9efffe00'),
    'T618': ('0x5500',     '0x9efffe00'),
    'T700': ('0x5500',     '0x9efffe00'),
    'T760': ('0x65000800', '0xB4FFFE00') }

processor_exploit_map = {        # payload exec address (payload_NNNNNNNN.bin)
    'T606': '0x65015f08',
    'T616': '0x65015f08',
    'T618': '0x3ee8',
    'T700': '0x3ee8',
    'T760': '0x65012f48' }
```

- `payload_3ee8.bin`, `payload_65015f08.bin`, `payload_65012f48.bin` are
  ARM memory-corruption payloads named after the exploit address they
  target (0x3EE8 = older FDL malloc region; 0x65015f08 / 0x65012f48 =
  return-address slots in Tiger-T FDLs).
- Loaders come from `Resources/Special/Loader/<profile>/`
  (`fdl1-dl.bin`, `fdl2-dl.bin`, `cboot.bin`), Fernet-decrypted with the
  server key (`GET /get-loader-key` → `{'key': ...}`).

## Exploit command line (`build_command`, L9651)

```
"spd.dll" exec_addr 0x65015f08 fdl "temp_decrypted/T606/fdl1-dl.bin" 0x65000800 \
                    fdl "temp_decrypted/T606/fdl2-dl.bin" 0x9efffe00 exec
```

i.e. `exec_addr <exploit_addr>`, upload FDL1 → addr1, FDL2 → addr2,
then `exec`. The 5-phase progress sync (`execute_connection_with_progress`,
L9682): init → send FDL1 → config FDL1 → send FDL2 → config final.

## SPD serial protocol (pure-Python impl, `spd_do_handshake` L8958)

```
open: serial.Serial(port, 115200, timeout=0.01, write_timeout=1)   # retries
write b'~' → expect version byte SPD_VER = 129 (0x81); 0.15 s between tries
send spd_pkt(0) → expect SPD_ACK = 128 (0x80)

packet framing (spd_pkt, L8929):
  b'~' + esc(struct.pack('>HH', cmd, len(data)) + data + pack('>H', crc)) + b'~'
CRC = XMODEM CRC-16-CCITT (spd_crc_xmodem, L8901)
escaping: '}' → '}]',  '~' → '}^'   (spd_esc/spd_unesc, L8915/8922)

USB IDs: SPD_VID='1782', SPD_PID='4D00'   (L509–510)
```

Cancel → write `reset\n` to the process stdin (L12281).

## DLL path (newer profiles) — `execute_dll_connection_with_progress` (L9703)

```
profile = resolve_dll_profile(model)          # must be in dll_profiles
_load_dll()                                  # clr → SpdClient class
_authorize_dll(client):
    hwid  = get_hwid_from_registry().strip().lower()
    token = GET /get-spd-session-token → {'token'}     # timeout 10
    SpdClient.Authorize(hwid, token)                   # must be True
_inject_dll_loaders(client, profile):
    path  = Resources/Special/SPD/{profile}.MTool      # Fernet 7z archive
            (missing → GET /get-spd-loader-link?cpu={profile} → download)
    key   = GET /get-spd-loader-key → {'key'}
    bytes = Fernet(key).decrypt(archive) → py7zr in-memory extract
    for each member, alias it under all of:
      {name}, loader_{profile}_{type}.bin, {profile}_{type}.bin, {type}.bin
      type ∈ {payload, preloader0..2, loader1/2, fdl1, fdl2}   # fdl1→loader1, fdl2→loader2
      SpdClient.InjectResource(alias, Array[Byte](bytes))
cerrar_puertos_spd() → detectar_puerto_spd() → spd_do_handshake(port)
client = SpdClient(...); attach ProgressReceived event
ptable = client.ReadPartitionTables(profile, read_info, True) → .Ok / .Partitions
```

SpdClient surface used from Python: `Authorize(hwid, token)`,
`InjectResource(name, Array[Byte])`, `ReadPartitionTables(profile,
read_info, bool)`, `ReadPartition(idx, dir)`, `ErasePartition(idx)`,
`Reboot()`, event `ProgressReceived(float)`, result `.Ok/.Error/.Logs`,
partition fields `.Index/.Name/.Offset/.Length`.

## SPD partition manager (`SPDPartitionManager`, L11964)

Constructor: `(selected_model, root, progress_bar, progress_label,
command_type, file_names, repartition_file, multi_commands)`.
`use_dll = connector.is_dll_profile(selected_model)` picks the engine.

- `erase_frp_spd` (L9923): erase `['persist']` only.
- `erase_frp_and_userdata` (L9935): erase `['persist', 'userdata',
  'metadata', 'cache']`.
- `process_partitions_dll` (L12305): per selected partition by index —
  `ReadPartition(idx, dir)` / `ErasePartition(idx)`; success/fail lists;
  then `Reboot()`.
- `process_multi_commands` (via `run()` L12372): command_type `'multi'`
  runs server-provided command sequences.
- Treeview UI: columns select/id/name/start_lba/end_lba/size_bytes/size.

## SPD .bat → flashfile XML parsing (L3518–3651)

`_patcher_parse_update_flash_bat_to_flashfile` (L3651) converts
Spreadtrum `update_flash.bat` into the Moto flashfile XML format:

- Regex-driven: quoted `flash` steps, `erase`, `set active`, `reboot`,
  `oem`; `%~dp0` path resolution; `|| fallback` stripping
  (`_spd_bat_strip_comment/_command_part/_local_filename/_resolve_dp0_path/_parse_command`).
- Step filter (L3628): drop erase/reboot (handled separately), drop any
  partition containing `'nv'` (RF-cal), skip
  `boot|boot_a|super|vbmeta|vbmeta_a` (flashed separately in fastbootd).
- Generated steps get `MD5="00000000000000000000000000000000"` placeholder.

## SPD factory reset via fastboot

```
spd: fastboot erase cache
     fastboot erase metadata
     fastboot reboot
```

(part of `run_reset_mtk_and_spd_commands`, L8695; the mtk half flashes
`mtk.img` to userdata — see [mtk.md](./mtk.md)).

## Resource artifacts

| Artifact | Meaning |
|---|---|
| `Resources/Special/Loader/<profile>/fdl1-dl.bin, fdl2-dl.bin, cboot.bin` | decrypted per-SoC FDLs (server key) |
| `Resources/Special/SPD/<profile>.MTool` | Fernet-encrypted 7z loader archive (downloaded on demand) |
| `Resources/payload_*.bin` | exploit payloads keyed by target address |
| `Resources/spd.dll / spd2.dll / spd3.dll` | exploit CLI (main/backup variants) |
| `Resources/Channel.ini` | SPD DLL log config (Level=3, Type=0x4000) |
| `Log/` | SPD DLL log output (wiped on start) |
| `partition_N.xml` | SPD DLL partition dumps (wiped on start) |

`CHECKED_RESOURCE_DLLS = ('MToolMTK.dll', 'MToolSPD.dll')` — kept fresh
via `POST /check-resources` (sha256 match → streamed download → atomic
replace, L1266).

## SPD unlock hash derivation

`_fetch_unlock_hash` (L9283): `POST /spd-derive-unlock-key`
`{'token': token_hex}`; T760 variant adds
`{'variant': 't760_pandora_aes', 'profile': 'Tiger T760_64', 'model': ''}`.
Response: `{'hash'}` or `{'blob'}` = the unlock hash used by the DLL.
