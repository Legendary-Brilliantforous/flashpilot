# motom_tool/ — Moto-M Tool v4.2.2 araştırma notları

**Moto-M Tool 4.2.2** için tersine mühendislik notları ("Maiky",
`studiomaiky.com` tarafından), ticari bir Windows Android flashing/repair
paketi. 2026-09-29 tarihinde `Moto-M Tool Setup.exe` dosyasından
çıkarıldı ve analiz edildi (123 MB, Inno Setup 6.6.1). Amaç: birlikte çalışabilirlik araştırması — aşağıdaki protokol bilgisi FlashPilot'ın MTK/SPD/Samsung/FRP/MDM motorlarını besler. Yalnızca sahip olduğunuz veya servis için yetkilendirildiğiniz cihazlarda kullanın.

## Araç aslında ne?

Yerel uygulama değil. Yığın şu şekilde:

| Katman | Teknoloji | Notlar |
|---|---|---|
| Yükleyici | Inno Setup 6.6.1 (LZMA) | AppId `E8A3A650-81D6-48FD-948F-B83091909F51` |
| Ana exe | PyInstaller (Python 3.11, `pyiboot01_bootstrap`) | 56 MB onefile; `Moto-M Tool_MTK_Dll_V2.py` tüm uygulama (~12.9k satır decompile edilmiştir) |
| Kötü amaçlı/karartma | PyArmor 8 (`pyarmor_runtime_004990`, ürün `MotoMTool`) | AES-128-CBC zırhlı bayt kodu; statik olarak açıldı (bkz. "Nasıl açıldı") |
| GUI | CustomTkinter (koyu tema `#1a1a1a`) | 6 sekme: Fastboot Operations, SPD Module, Support Area, Patcher Module, ADB Module, MTK Module (Beta) |
| MTK motoru | .NET DLL `MToolMTK.dll` via **pythonnet** (`clr`) | Sınıf `SharpMTKClient.MtkDllSession`; DLL BROM/DA protokolü yapar |
| SPD motoru | .NET DLL `MToolSPD.dll` via pythonnet + harici `spd.dll` CLI | Exploit tabanlı FDL enjeksiyonu |
| Dahili araçlar | adb/fastboot (platform-tools), busybox, sqlite3, mke2fs/make_f2fs, etc1tool, hprof-conv | Bunlara kabuk üzerinden erişiyor |

Her şeyin hassas kısmı (Fernet anahtarları, unlock kodları, yamalanmış LK imajları,
loader arşivleri) **sunucu aracılığıyla** `https://studiomaiky.com` üzerinde tutuluyor — istemci ince bir orkestratör. Bkz. [server_protocol.md](./server_protocol.md).

## Bu ağaçtaki dosyalar

| Dosya | İçerik |
|---|---|
| [mtk.md](./mtk.md) | MediaTek alanı: MtkDllSession köprüsü, crash-to-BROM, yükleyiciler, unlock akışları |
| [spd.md](./spd.md) | Spreadtrum/UNISOC alanı: BSL el sıkışması, exploit yükleyiciler, FDL adresleri, unlock |
| [samsung.md](./samsung.md) | Samsung: KG kilit/bypass, PayJoy MDM, Exynos boot repair (DVIF), AT komutları |
| [motorola_unlock.md](./motorola_unlock.md) | Resmî Motorola web unlock, Valeria LK-swap, ROM patcher, firmware mirrors |
| [server_protocol.md](./server_protocol.md) | Tüm uç noktalar, kimlik doğrulama/lisanslama modeli, HWID parmak izi, kaynak güncelleme protokolü |
| [dll_protocol.md](./dll_protocol.md) | Dağıtılan DLL iç yapıları: MTool_EROFS decompile (EROFS/ext4/F2FS patcher API), native spd.dll CLI komut kümesi |

## FlashPilot içinde uygulandı

Bu ağaçtan gelen bilgiler kodda zaten kullanıldı:

| Bilgi | Nerede |
|---|---|
| PenangF unlock (`oem get_key` → harici kimlik → `oem key` + `flashing unlock`) | Sadece araştırma notu — uygulanmadı (öyle bir akış yok; `flow-list` ile doğrulayın) |
| Motorola fastboot fabrika sıfırlama (`oem fb_mode_set` → userdata/cache/**debug_token** silme → `oem fb_mode_clear`) | Sadece araştırma notu — akış olarak uygulanmadı (fabrika sıfırlama `factory_reset` ADB akışı / fastboot erase satırları ile çalışır) |
| MTK OEM VIDs (Sony 0x0fce, LG 0x1004, OPPO 0x22d9, InFocus 0x9bb5) altında MTK preloader/BROM yeniden numaralanır | Kısmen: `find_mtk()` içinde `python/core/mtk.py`; `MTK_OEM_VIDS` tablosu yok |
| PenangF notu + unlock-data URL sırası (0/3/2) standart token akışında | Token akışıyla birlikte emekliye ayrıldı (`moto_oem_unlock_token` kaldırıldı); burada protokol referansı olarak tutuldu |
| Samsung DVIF download-mode okuma (115200 8N1, `DVIF` sorgusu, `KEY=VALUE` çiftleri) | Sadece araştırma notu — uygulanmadı (`dvif` kodu yok) |
| MTK model→SoC eşlemesi (G14→T616, G35→T760, G54→MT6855, ...) | `supported_devices.json` motorola girdileri |
| Stok firmware mirrorları (lolinet, year-based) | `operations/flashing/README.md` |

Testler: eski `tests/test_moto_tool_flows.py` kaldırıldı; kapsam per-area testlerde yaşıyor (`tests/test_frp_flow.py`, `tests/test_devices.py`, cargo `flows::tests`). Uygulanmadı (harici cihaz varlıklarına veya ücretli sunucuya ihtiyaç duyar): Valeria patched/stock LK imajları, KG exploit ikili dosyası, `mtk.img` reset imajı, SPD loader arşivleri, unlock adayları, EROFS patcher, ExynosCli hazır ayarlar.

## Nasıl açıldı (gelecekte yeniden analiz için)

```bash
# 1. Inno Setup 6.6.1 — innoextract 1.9 çok eski; Wine altında innounp-2 kullan
#    (jrathlev/InnoUnpacker-Windows-GUI sürümü "innounp-2.zip")
wine innounp2/innounp.exe -x -dZ:\home\<u>\motom "Z:\...\Moto-M Tool Setup.exe"

# 2. PyInstaller (Python 3.11) — pyinstxtractor.py (extremecoders-re)
python3 pyinstxtractor.py "Moto-M Tool.exe"

# 3. pyc başlıklarını düzelt (çıkarma sıfır dolu 16 bayt başlık bırakır)
#    Python 3.11 sihir: a7 0d 0d 0a + 12 sıfır bayt

# 4. PyArmor 8 statik açma (Lil-House/Pyarmor-Static-Unpack-1shot)
#    PATCH gerekli: oneshot/detect.py vücut_len sınırı >0xFFFFF'yi
#    0x10000000'a yükseltir (1.2 MB zırhlı blob varsayılan sınırı aşar)
python3 oneshot/shot.py <extracted_dir> -o unpacked
#    → *.1shot.cdc.py (decompile) + *.1shot.das (bayt kodu ayrıştırma)
#    Çalışma gerçekleri: AES anahtarı 124a39ad996db52f6662215344b403c8, nonce 692e4d6f746f4d546f6f6cdb

# 5. src/auto_crash bir Cython .pyd (sıkıştırılmış dizeler) — decompile edilemez;
#    protokol dışa aktarılan semboller + çağrı noktalarıyla çıkarıldı.
```

Tam decompilenin çalışma kopyası repo dışında `/home/elijah/motom_research/unpacked/` klasöründe yer alıyor
(12,879 satır, `.1shot.cdc.py`).

## Kaynak referansları

Aşağıdaki satır numaraları `Moto-M Tool_MTK_Dll_V2.pyc.1shot.cdc.py` dosyasına işaret eder
(decompile edilen modül).
`das` referansları `.1shot.das` bayt kodu ayrıştırmasına işaret eder; orada decompile tamamlanmamışsa
tek gerçek kontrol akışı odur. Decompile edilmiş kod eksik olabilir — `.das` dosyası asıl gerçek kaynaktır.
