# MTK yonga destek matrisi

FlashPilot'in MTK yonga kapsama alanını genişletme planı kaydı; üst akış
`bkerler/mtkclient` (`mtkclient/config/brom_config.py`, ana dal) ve MIT lisanslı
`chaanel/bypass_utility` projesi tarafından yayınlanan SoC bazlı parametre setiyle
karşılaştırılarak hazırlanmıştır.

| | Yonga |
|---|---|
| Önce | 17 |
| Eklendi — kamakiri2 (Grup A) | 17 |
| Eklendi — bypass_utility (Grup B) | 18 |
| **Sonra** | **52** |

Şimdi her yonga için iki exploit motoru seçilir:

- **kamakiri2** — CVE-2020-11152 satır kodlama taşması; `send_ptr` ve
  `brom_reg_ptr` gerektirir. 2020 dönemi ve sonrası SoC'leri kapsar.
- **bypass_utility** — watchdog'a bitişik işaretçi yazımı + `0xE0` yükleme + USB
  kontrol transfer atlaması. `chaanel/bypass_utility` (MIT) portu. CVE-2020-11152
  öncesi daha eski SoC'leri kapsar.

`MtkChipConfig::exploit` motoru seçer; `payload`, `BypassUtility` tarafından
kullanılan paketlenmiş BootROM payload'ını adlandırır.

---

## Mevcut 17 (kamakiri2, değişmeden)

| hw | Ad | watchdog |
|---|---|---|
| `0x699` | MT6739/MT6731/MT8765 | `0x10007000` |
| `0x766` | MT6765/MT8768T | `0x10007000` |
| `0x707` | MT6768/MT6769 | `0x10007000` |
| `0x788` | MT6771/MT8385/MT8183/MT8666 | `0x10007000` |
| `0x725` | MT6779 | `0x10007000` |
| `0x1066` | MT6781 | `0x10007000` |
| `0x813` | MT6785 | `0x10007000` |
| `0x989` | MT6833 | `0x10007000` |
| `0x996` | MT6853 | `0x10007000` |
| `0x886` | MT6873 | `0x10007000` |
| `0x816` | MT6885/MT6883/MT6889/MT6890 | `0x10007000` |
| `0x950` | MT6891/MT6893 | `0x10007000` |
| `0x959` | MT6877/MT8791N | `0x10007000` |
| `0x1129` | MT6855 | `0x1c007000` |
| `0x1209` | MT6835V | `0x1C007000` |
| `0x6899` | MT6899 | `0x1C010000` ⚠ not: bakınız |
| `0x6781` | MT6781 | `0x10007000` |

> ⚠ **MT6899 watchdog** üst akışla çelişiyor (`0x1C00B000`). Üst akış ayrıca
> `send_ptr`/`brom_register_access` için yorum satırı ekliyor; bu giriş her iki
yönde de spekülatiftir. Donanım doğrulaması gerekiyor — bkz.
> `mtk_gap_analysis.md` §7.2.

---

## Grup A — 17 ekleme, kamakiri2

Tüm `send_ptr`/`brom_reg_ptr` değerleri üst akış mtkclient ile doğrulandı.
Dört tanesi (`0x717`, `0x8127`, `0x8163`, `0x8590`) ayrıca bypass_utility'nin
yayınlanmış konfigürasyonunda da aynı değerlerle yer alıyor; diğer 13 tanesi
yalnızca üst akıştan geliyor.

| hw | Ad | watchdog | send_ptr | brom_reg_ptr | var1 | Karşılaştırma |
|---|---|---|---|---|---|---|
| `0x717` | MT6761/MT6762/MT3369/MT8766B/MT8761/AC8259/AC8257 | `0x10007000` | `0xbc8c` | `0xc158` | `0x25` | üst akış + bypass_utility |
| `0x8127` | MT8127/MT3367/AC8227L | `0x10007000` | `0xb2b8` | `0xb740` | `0xA` | üst akış + bypass_utility |
| `0x8163` | MT8163 | `0x10007000` | `0xc12c` | `0xc5c8` | `0xB1` | üst akış + bypass_utility |
| `0x8590` | MT8590/MT7683/MT8521/MT7623 | `0x10007000` | `0xbbe4` | `0xc06c` | `0xA` | üst akış + bypass_utility |
| `0x571` | MT0571 | `0x10007000` | `0xba68` | `0x40befc` | `0xA` | üst akış |
| `0x1172` | MT6895 | `0x1c007000` | `0xE79C` | `0xec5c` | `0xA` | üst akış |
| `0x1203` | MT6897 | `0x1c007000` | `0xE79C` | `0xec5c` | `0xA` | üst akış |
| `0x1208` | MT6789/MT8781V | `0x10007000` | `0xE79C` | `0xfa0c` | `0xA` | üst akış |
| `0x1229` | MT6886 | `0x1c007000` | `0xE79C` | `0xfa0c` | `0xA` | üst akış |
| `0x1236` | MT6989W | `0x1C00B000` | `0xE79C` | `0xfa0c` | `0xA` | üst akış |
| `0x1296` | MT6985 | `0x1C007000` | `0xE79C` | `0xfa0c` | `0xA` | üst akış |
| `0x1357` | MT6991 | `0x1c010000` | `0xE79C` | `0xec5c` | `0xA` | üst akış |
| `0x1375` | MT6878 | `0x1C00A000` | `0xE79C` | `0xfa0c` | `0xA` | üst akış |
| `0x1471` | MT6993 | `0x1c010000` | `0xE79C` | `0xfa0c` | `0xA` | üst akış |
| `0x2625` | MT2625 | `0x10007000` | `0xba68` | `0x40befc` | `0xA` | üst akış |
| `0x6516` | MT6516 | `0x10003000` | `0x40ba68` | `0x40befc` | `0xA` | üst akış |
| `0x8512` | MT8512 | `0x10007000` | `0xcc44` | `0xd194` | `0xA` | üst akış |

---

## Grup B — 18 ekleme, bypass_utility

Bunlar CVE-2020-11152 öncesi cihazlardır; bu nedenle kamakiri2 bunlara
ulaşamaz.

| hw | Ad | watchdog | payload_addr | var1 | var0 | payload |
|---|---|---|---|---|---|---|
| `0x279` | MT6797/MT6767 | `0x10007000` | `0x100A00` | `0xA` | — | `mt6797_payload.bin` |
| `0x321` | MT6735/MT8735A | `0x10212000` | `0x100A00` | `0x28` | `0x10` | `mt6735_payload.bin` |
| `0x326` | MT6755/MT6750 | `0x10007000` | `0x100A00` | `0xA` | — | `mt6755_payload.bin` |
| `0x335` | MT6737M/MT6735G | `0x10212000` | `0x100A00` | `0x28` | `0x10` | `mt6737_payload.bin` |
| `0x337` | MT6753 | `0x10212000` | `0x100A00` | `0x28` | `0x10` | `mt6753_payload.bin` |
| `0x551` | MT6757/MT6757D | `0x10007000` | `0x100A00` | `0xA` | — | `mt6757_payload.bin` |
| `0x562` | MT6799 | `0x10211000` | `0x100A00` | `0xA` | — | `mt6799_payload.bin` |
| `0x690` | MT6763 | `0x10007000` | `0x100A00` | `0x7F` | — | `mt6763_payload.bin` |
| `0x6261` | MT6261/MT2503 | `0xA0030000` | `0x100A00` | `0x28` | — | `mt6261_payload.bin` |
| `0x6572` | MT6572 | `0x10007000` | `0x10036A0` | `0xA` | — | `mt6572_payload.bin` |
| `0x6580` | MT6580 | `0x10007000` | `0x100A00` | `0xAC` | — | `mt6580_payload.bin` |
| `0x6582` | MT6582/MT6574/MT8382 | `0x10007000` | `0x100A00` | `0xA` | — | `mt6582_payload.bin` |
| `0x6592` | MT6592/MT8392 | `0x10007000` | `0x100A00` | `0xA` | — | `mt6592_payload.bin` |
| `0x6595` | MT6595 | `0x10007000` | `0x100A00` | `0xA` | — | `mt6595_payload.bin` |
| `0x6795` | MT6795 | `0x10007000` | `0x100A00` | `0xA` | — | `mt6795_payload.bin` |
| `0x8167` | MT8167/MT8516/MT8362 | `0x10007000` | `0x100A00` | `0xCC` | — | `mt8167_payload.bin` |
| `0x8172` | **MT8173** | `0x10007000` | `0x120A00` | `0xA` | — | `mt8173_payload.bin` |
| `0x8695` | MT8695 | `0x10007000` | `0x100A00` | `0xA` | — | `mt8695_payload.bin` |

> **`0x8172` adı:** bazı Windows ayar tabloları payload'ı `mt8172_payload.bin`
> olarak adlandırır ve hiç göndermez. Üst akış `0x8172` hw kodunu MT8173'e
> eşleyip `mt8173_payload.bin` yükler; bu eşleme burada kullanılır.

---

## bypass_utility dizisi

`chaanel/bypass_utility` `src/exploit.py` dosyasından taşındı:

```text
addr = watchdog + 0x50
write32(addr, payload_address)

# BROM okuma yolunu hazırla
if var0 is Some(v):
    read32(addr - v, (v + 4) / 4)          # tek okuma
else:
    for i in 0..15:
        n = 15 - i
        read32(addr - n*4, n + 1)          # 15 azalan okuma,
                                           # ilk (addr-60, 16), son (addr-4, 2)

echo(0xE0)
echo_dword(payload.len())
status = read_exact(2)                     # mutlaka 00 00 olmalı
write(payload)
read_exact(4)                              # temizlemeyi atla
control_transfer(0xA1, 0, 0, var1, len 0)  # atlama
read_exact(4)                              # başarı deseni
```

Priming dizisi saf bir yardımcı işlev olarak uygulandı; böylece adres/sayı
daritmetiği donanım olmadan birim testi yapılabilir.

---

## Payload kaynağı ve lisans

- Payload'lar **`bkerler/mtkclient`** kaynağından gelen `mt*_payload.bin` /
  `generic_*_payload.bin` dosyalarıdır (GPLv3).
- Bunlar `payloads/mtk/` altında ayrı katkılar olarak toplanır; MIT lisanslı
  crate'e bağlanmazlar. Bakınız `payloads/mtk/README.md`.
- Çözümleme sırası: `MTK_PAYLOAD_DIR` →
  `$XDG_DATA_HOME/flashpilot/payloads/mtk` (veya
  `~/.local/share/flashpilot/payloads/mtk`, root gerekmez) →
  `<exe_dir>/payloads/mtk`.
- `.deb` paketi bundle'ı `/usr/lib/flashpilot/payloads/mtk` konumuna kurar;
  `build.rs` bunu `target/<profile>/` yanına kopyalar, böylece yayın derlemeleri
  build makinesinin yolunu kodlamaz.
- `flashpilot-bridge mtk-payload-check` her bypass yongasını ve payload çözünürlüğünü
  listeler — cihaz gerekmez. Korunan bir yongada eksik payload hard hata (exit 1)
  verir; dosya adını ve üç düzeltme yolunu belirtir; korunmayan bir yonga için
  auth bypass gerektirmediği için çalışmaya devam eder.
- FlashPilot hala DA/loader görselleri teslim etmez; bunlar kullanıcı tarafından
  sağlanır.

## Uyarılar

1. **Donanım doğrulaması yok.** Eklenen her girdi üst akış mtkclient ve
   bypass_utility'den alınan tablo verileridir. Exploit motorları kendi
   başlarına kamakiri2 tarafında değişmeden kalır; bypass_utility yolu yeni ve
   donanım üzerinde kanıtlanmamıştır.
2. **MT6899 watchdog** çözülmedi (§7.2).
3. **Daha eski SoC'ler daha fazla işaretçiye ihtiyaç duyabilir.** 2014 öncesi
   bazı parçalar ayrıca blacklist patch'i veya farklı bir crash yöntemi de
   gerektirir; tablo yalnızca bypass_utility konfigürasyonunda kullanılan
   verileri taşır.
4. Windows ayar tablolarındaki `ptr_usbdl`/`ptr_da` alanları kasıtlı olarak
   **ithal edilmedi** — bunlar mtkclient'in `send_ptr`/`brom_register_access`
   soyutlamasından farklı bir kavramdır ve bunları karıştırmak exploit'i sessizce
   bozar.
