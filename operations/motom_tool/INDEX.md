# motom_tool/ — index

**Moto-M Tool 4.2.2** için tersine mühendislik notları ("Maiky",
`studiomaiky.com` tarafından, ticari bir Android flashing/repair paketi).
Yalnızca markdown — hiçbir kod bunu içe aktarmıyor. Bilgi FlashPilot'ın
motorlarını besler (MTK/SPD/Samsung/FRP/MDM).

| Dosya | İçerik |
|---|---|
| [README.md](./README.md) | Genel bakış: araç nedir (PyInstaller + PyArmor + CustomTkinter + .NET DLL'ler), nasıl açıldı |
| [mtk.md](./mtk.md) | MediaTek: `MtkDllSession` köprüsü (pythonnet), crash-to-BROM exploit, FDL yükleyiciler, unlock akışları, FRP/misc patch dosyaları, fastboot ilerleme ayrıştırıcısı |
| [spd.md](./spd.md) | Spreadtrum/UNISOC: BSL seri protokolü (çerçeveleme, CRC16, kaçış), exploit komut satırı, SoC başına FDL/exploit adresleri, DLL yükleyici enjeksiyonu, .bat→flashfile ayrıştırma |
| [samsung.md](./samsung.md) | Samsung: KG kilit/bypass, PayJoy MDM, Exynos boot repair (DVIF seri protokol), AT komutları (Android 16), DNS/EULA FRP yöntemleri, Samsung APK'ları |
| [motorola_unlock.md](./motorola_unlock.md) | Resmî Motorola web unlock (verifyPhone/unlockPhone URL'leri, unlock-data sırası 0/3/2), Valeria LK-swap protokolü, ROM patcher (AES-256-CTR şeması), firmware mirrorları, QR ADB kaydı |
| [server_protocol.md](./server_protocol.md) | `studiomaiky.com` üzerindeki tüm ~29 uç nokta, kimlik doğrulama/lisanslama modeli (JWT + DPAPI + kredi), HWID parmak izi, kaynak güncelleme protokolü |
| [dll_protocol.md](./dll_protocol.md) | Dağıtılan DLL iç yapıları: MTool_EROFS decompile (EROFS/ext4/F2FS patcher API: PatchBuild/PatchHosts/RemoveApks), native spd.dll CLI komut kümesi + BSL işaretleyicileri |

## FlashPilot için temel çıkarımlar

1. **Motorola resmî unlock**: URL şablonları
   `verifyPhone/{part0}/{part3}/{part2}/` ve `unlockPhone/{part0}/{part3}/{part2}/`
   `en-us.support.motorola.com/cc/productRegistration/` altında — özel başlıklar dışında oturum çerezleri yeterlidir. PenangF cihazlar `fastboot oem get_key` + `/generate-oem-key` kullanır.
   → araştırma notu: token akışı FlashPilot'da emekliye ayrıldı
   (`moto_oem_unlock_token` GUI ve Rust kaydından kaldırıldı;
   PenangF unlock asla uygulanmadı — `flow_moto_penangf_unlock` yok, işaret etmek için `flow-list` kullanın).
2. **SPD BSL çerçeveleme** (saf-Python `spd_do_handshake`):
   `~` çerçeveli, `>HH` cmd/len + CRC-16-CCITT (XMODEM), kaçış
   `}→}]`, `~→}^`, ACK 0x80 / VER 0x81 @ 115200. → Rust SPD çekirdeğinde.
3. **MTK VIDs**: 0E8D, 0FCE, 1004, 22D9, 9BB5. → kısmen `python/core/mtk.py` içinde (`find_mtk()`); `MTK_OEM_VIDS` tablosu yok.
4. **Valeria deseni**: geçici LK swap (yamalanmış LK içeri -> oem unlock ->
   çıkış yolunda her seferinde stok LK geri yüklenir). → yalnızca belgelenmiştir (cihaz bazlı LK varlıkları gerekir).
5. **Patcher şifreleme**: AES-256-CTR, 16 bayt rastgele nonce ön eki,
   4 MiB parçalar, yalnızca super imajlar. → yalnızca belgelenmiştir (özel DLL).
6. **Sunucu komut deseni**: çoğu ADB işlemi (KG, MDM, EULA) sunucu tarafından getirilen komut listeleri (`?parte=<part>`) — istemci yalnızca canary paketleri değiştirir (`com.google.android.youtube`).
   → FlashPilot'ın kendi MDM akışları bunu yerel komut setleriyle kapsar.
7. **Samsung DVIF download-mode okuma** (115200 8N1, `DVIF` sorgusu,
   `KEY=VALUE` çiftleri, alanlar MODEL/SALES/VER/UN/... ). → araştırma notu (`flow_download_mode_dvif` yok).
8. **Motorola fabrika sıfırlama** (`fb_mode_set` → userdata/cache/
   `debug_token` silme → `fb_mode_clear`). → araştırma notu (`flow_moto_factory_reset_fb` yok).
9. **MTK model→SoC eşlemesi** (G14→T616, G35→T760, G54→MT6855, ...).
   → `supported_devices.json` motorola girdilerinde uygulanmış.

## Decompile nerede bulunur

`/home/elijah/motom_research/unpacked/Moto-M Tool_MTK_Dll_V2.pyc.1shot.cdc.py`
(12,879 satır; `.1shot.das` = bayt kodu gerçeği). Yeniden analiz tarifi [README.md](./README.md) içinde "Nasıl açıldı" bölümünde.
