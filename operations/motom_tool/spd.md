# spd.md — Spreadtrum/UNISOC alanı (Moto-M Tool)

Moto-M Tool 4.2.2 SPD/UNISOC nasıl yapıyor. İki yol: **exploit CLI**
(`spd.dll` alt süreçte FDL enjeksiyonu) ve daha yeni profiller için **.NET DLL**
(`MToolSPD.dll` via pythonnet, sınıf `SpdClient`).

## Profiller ve model eşlemesi (`SPDConnector.__init__`, L9089)

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

motorola_dll_profile_map = {'Moto G35': 'Tiger T760_64'}   # G35 unlock için DLL yolu
```

## FDL/exploit adresleri (L9127–9139)

```python
processor_fdl_map = {            # (FDL1 yükleme adresi, FDL2 yükleme adresi)
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

- `payload_3ee8.bin`, `payload_65015f08.bin`, `payload_65012f48.bin` ARM bellek bozulma payload'larıdır; isimleri hedefledikleri exploit adresindendir (0x3EE8 = eski FDL malloc bölgesi; 0x65015f08 / 0x65012f48 = Tiger-T FDL'lerindeki return-address slotları).
- Yükleyiciler `Resources/Special/Loader/<profile>/` altında gelir (`fdl1-dl.bin`, `fdl2-dl.bin`, `cboot.bin`), sunucu anahtarıyla Fernet şifre çözülür (`GET /get-loader-key` → `{'key': ...}`).

## Exploit komut satırı (`build_command`, L9651)

```
"spd.dll" exec_addr 0x65015f08 fdl "temp_decrypted/T606/fdl1-dl.bin" 0x65000800                     fdl "temp_decrypted/T606/fdl2-dl.bin" 0x9efffe00 exec
```

Yani `exec_addr <exploit_addr>`, FDL1'i addr1'e yükle, FDL2'yi addr2'ye yükle, sonra `exec` çalıştır. 5 aşamalı ilerleme senkronizasyonu (`execute_connection_with_progress`, L9682): init → FDL1 gönder → FDL1 yapılandır → FDL2 gönder → son yapılandır.

## SPD seri protokolü (saf-Python uygulama, `spd_do_handshake` L8958)

```
open: serial.Serial(port, 115200, timeout=0.01, write_timeout=1)   # retries
write b'~' → version byte SPD_VER = 129 (0x81); 0.15 s arayla dene
send spd_pkt(0) → expect SPD_ACK = 128 (0x80)

packet framing (spd_pkt, L8929):
  b'~' + esc(struct.pack('>HH', cmd, len(data)) + data + pack('>H', crc)) + b'~'
CRC = XMODEM CRC-16-CCITT (spd_crc_xmodem, L8901)
escaping: '}' → '}]',  '~' → '}^'   (spd_esc/spd_unesc, L8915/8922)

USB kimlikleri: SPD_VID='1782', SPD_PID='4D00'   (L509–510)
```

İptal → süreç stdin'e `reset
` yazar (L12281).

## DLL yolu (daha yeni profiller) — `execute_dll_connection_with_progress` (L9703)

```
profile = resolve_dll_profile(model)          # dll_profiles içinde olmalı
_load_dll()                                  # clr → SpdClient class
_authorize_dll(client):
    hwid  = get_hwid_from_registry().strip().lower()
    token = GET /get-spd-session-token → {'token'}     # timeout 10
    SpdClient.Authorize(hwid, token)                   # must be True
_inject_dll_loaders(client, profile):
    path  = Resources/Special/SPD/{profile}.MTool      # Fernet 7z arşivi
            (eksik → GET /get-spd-loader-link?cpu={profile} → download)
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

Python'dan kullanılan SpdClient arayüzü: `Authorize(hwid, token)`,
`InjectResource(name, Array[Byte])`, `ReadPartitionTables(profile,
read_info, bool)`, `ReadPartition(idx, dir)`, `ErasePartition(idx)`,
`Reboot()`, olay `ProgressReceived(float)`, sonuç `.Ok/.Error/.Logs`, bölüm alanları `.Index/.Name/.Offset/.Length`.

## SPD bölüm yöneticisi (`SPDPartitionManager`, L11964)

Kurucu: `(selected_model, root, progress_bar, progress_label,
command_type, file_names, repartition_file, multi_commands)`.
`use_dll = connector.is_dll_profile(selected_model)` motoru seçer.

- `erase_frp_spd` (L9923): yalnızca `['persist']` siler.
- `erase_frp_and_userdata` (L9935): `['persist', 'userdata',
  'metadata', 'cache']` siler.
- `process_partitions_dll` (L12305): indeks bazlı seçilmiş bölümler —
  `ReadPartition(idx, dir)` / `ErasePartition(idx)`; başarı/başarısız listeleri;
  ardından `Reboot()`.
- `process_multi_commands` (`run()` L12372 aracılığıyla): command_type `'multi'`
  sunucu tarafından sağlanan komut dizilerini çalıştırır.
- Treeview UI: sütunlar select/id/name/start_lba/end_lba/size_bytes/size.

## SPD .bat → flashfile XML ayrıştırma (L3518–3651)

`_patcher_parse_update_flash_bat_to_flashfile` (L3651),
Spreadtrum `update_flash.bat` dosyasını Moto flashfile XML formatına dönüştürür:

- Regex odaklı: tırnaklı `flash` adımları, `erase`, `set active`, `reboot`,
  `oem`; `%~dp0` yol çözümü; `|| fallback` temizleme
  (`_spd_bat_strip_comment/_command_part/_local_filename/_resolve_dp0_path/_parse_command`).
- Adım filtresi (L3628): erase/reboot çıkarılır (ayrı işlenir), `'nv'` içeren tüm bölümler atlanır (RF-cal),
  `boot|boot_a|super|vbmeta|vbmeta_a` atlanır (fastbootd içinde ayrı yazılır).
- Üretilen adımlar `MD5="00000000000000000000000000000000"` placeholder ile gelir.

## Fastboot üzerinden SPD fabrika sıfırlama

```
spd: fastboot erase cache
     fastboot erase metadata
     fastboot reboot
```

(`run_reset_mtk_and_spd_commands`, L8695 içinde; mtk yarısı `mtk.img`'yi userdata'ya yazar — bkz. [mtk.md](./mtk.md)).

## Kaynak varlıkları

| Varlık | Anlam |
|---|---|
| `Resources/Special/Loader/<profile>/fdl1-dl.bin, fdl2-dl.bin, cboot.bin` | şifresi çözülen SoC bazlı FDL'ler (sunucu anahtarı) |
| `Resources/Special/SPD/<profile>.MTool` | Fernet ile şifrelenmiş 7z loader arşivi (isteğe bağlı indirilir) |
| `Resources/payload_*.bin` | hedef adresine göre exploit payload'ları |
| `Resources/spd.dll / spd2.dll / spd3.dll` | exploit CLI (ana/yedek varyantlar) |
| `Resources/Channel.ini` | SPD DLL log konfigürasyonu (Level=3, Type=0x4000) |
| `Log/` | SPD DLL log çıktıları (başlangıçta temizlenir) |
| `partition_N.xml` | SPD DLL bölüm dökümleri (başlangıçta temizlenir) |

`CHECKED_RESOURCE_DLLS = ('MToolMTK.dll', 'MToolSPD.dll')` — `POST /check-resources` ile taze tutulur
(sha256 eşleşmesi → akışlı indirme → atomik replace, L1266).

## SPD unlock hash türetimi

`_fetch_unlock_hash` (L9283): `POST /spd-derive-unlock-key`
`{'token': token_hex}`; T760 varyantı ek olarak
`{'variant': 't760_pandora_aes', 'profile': 'Tiger T760_64', 'model': ''}` içerir.
Cevap: `{'hash'}` veya `{'blob'}` = DLL tarafından kullanılan unlock hash.
