# dll_protocol.md — .NET DLL + native CLI iç yapıları

Moto-M Tool'un MTK/SPD motorları bir .NET derlemesi
(`MToolMTK.dll`/`MToolSPD.dll`, isteğe bağlı indirilir — yükleyici içinde gelmez) ve bir native x86 CLI (`spd.dll`) üzerine kuruludur. Burada gerçekten teslim edilen ve decompile edilenler:

- `MTool_EROFS.dll` — .NET, tam decompile edildi (ILSpy 8.2) → `MTool.EROFS`
  + `SuperExt4Reader` (63 kaynak dosya)
- `spd.dll` / `spd2.dll` / `spd3.dll` — native PE32 CLI, string analizi

## MToolErofsApi (teslim edilen EROFS patcher)

```csharp
public static class MToolErofsApi {
    static MToolPatchResult PatchBuild(string imagePathOrChunk, string signature = null);
    static MToolPatchResult PatchHosts(string imagePathOrChunk, string rulesPath);
    static MToolPatchResult RemoveApks(string imagePathOrChunk, string apkListJsonPath);
    static MToolRomPatchResult PatchRom(string imagePathOrChunk, string signature = null,
                                        string hostsRulesPath = null, string apkListJsonPath = null);
}
```

### PatchBuild — build.prop imza enjeksiyonu

- Varsayılan imza: `"Moto-M Tool Power"`.
- `BuildPropPatcher.Scan(explorer, signature)` → `ro.build.id`
  / `ro.build.display.id` satırları için tüm bölümlerde eşleşmeler bulur.
- `AnalyzeSettingsDisplaySource` → `android.os.Build.DISPLAY` nereden geldiğini bulur: ya statik bir `ro.build.display.id` özelliği (doğrudan seçilir) ya da bir **çalışma anı ataması** (`ro.build.display.id` çalışma anında atanır — sonra `PatchRuntimeDisplayAssignments` besleyen kaynak özelliği yamalar).
- `Patch(explorer, scan, allowCompressedErofs: true)` — özelliği sıkıştırılmış EROFS içinde bile yeniden yazar (okuyucu EROFS + ext4 + F2FS yönetir).
- Sonuç: `MToolPatchResult { Operation: "patch-build", Success, Error,
  Signature, SelectedTarget: "<partition>:<file> <key>", FileSystem,
  PatchedFiles[], Warnings[] }`.

### PatchHosts — /etc/hosts yeniden yazma

- `HostsPatcher.Analyze(explorer, rulesPath, "127.0.0.1")` → her `<partition>:<file>` için hedef planı (genelde `/system/etc/hosts`).
- `Patch(explorer, plan, allowCompressed: true, patchAllTargets: false)`
  — varsayılan olarak ilk hedefi yamalar; `patchAllTargets` hepsini yapar.
- Kural dosyası klasik reklam engelleme/yönlendirme hosts formatıdır
  (`127.0.0.1 alan`), sunucu tarafından teslim edilir (`get_assets` → `hosts_rules`).

### RemoveApks — sistem imajından toplu APK kaldırma

- Girdi JSON: `{ "<partition>": ["path/to/app.apk", ...], ... }`.
- `ApkBatchRemover.Scan` → adayları bulur; `Delete` → toplu kaldırma
  (EROFS/ext4). Sonuç kaldırılan vs uyarı + bulunamayan listelerini döndürür.

### OpenExplorer — görüntü/parça işleme

```
Directory OR '*sparsechunk.*' dosyası
    → PartitionExplorer.OpenMultiChunk(
          MultiChunkSparseStream.FindAndSortChunks(path))   # sparse set sıralı indeks
plain image file
    → new PartitionExplorer(path)
```

`SuperExt4Reader` iç yapıları (teslim edilmiş, decompile edilmiş): EROFS süper bloğu +
compact/extended inode + LZ4 küme yapılandırmaları (`ZErofsLz4Cfgs`), ext4 okuyucu, F2FS yardımcıları,
`PartitionExplorer` çoklu bölüm süper imajları için, `GetFileLayoutInfo(partition, path).FileSystem` dosyanın hangi FS'te olduğunu bildirir.

Bu, "özel imza" ROM yamalama bilgisidir
(bkz. [motorola_unlock.md](./motorola_unlock.md) § ROM patcher): imza `ro.build.display.id` içinde görünür (muhtemelen sıkıştırılmış-EROFS) süper imajda yer alır, hosts yönlendirilir ve listelenen APK'lar kaldırılır — tüm bunlar imajı diske asla çıkarmadan yapılır.

## spd.dll — native exploit CLI (komut kümesi)

`spd.dll` (aynı zamanda `spd2/3.dll` yedek varyasyonları) native x86
Spreadtrum/UNISOC exploit çalıştırıcısıdır; alt süreç olarak çağrılır (bkz.
[spd.md](./spd.md)). İkili dosyanın tam komut yüzeyi:

```
fdl FILE addr                    FDL aşamasını yükleme adresine yükler
exec                             FDL2 çalıştırır
exec_addr ADDR                   adreste exploit çalıştırır
erase_part part_name/part_id     bölümü siler
write_part part_name/part_id F   bölüme yazar
read_parts partition_list_file   bölümleri okur
write_parts save_location        tüm bölümleri yazar
partition_list FILE              XML bölüm listesi
preset_modem                     modem ön ayarı
chip_uid                         çip UID oku
reset                            cihazı sıfırlar
```

İkili içindeki protokol işaretleyicileri (BSL konuşması):

```
CMD_CONNECT bootrom / CMD_CONNECT FDL1    # bağlantı aşamaları
CHECK_BAUD FDL1 / CHANGE_BAUD FDL1 to %d  # baud anlaşması
KEEP_CHARGE FDL1                          # şarj-only bayrağı
EXEC FDL2 / "FDL2 ALREADY EXECUTED, SKIP"
"BOOT COMPLETED: Device is now in FDL2 mode."
BSL_REP_VER / BSL_REP_LOG / BSL_REP_READ_CHIP_UID
enable_write_raw_data / disable_write_raw_data in SPRD4
"Warning: disable dm-verity needs a write-verification-disabled FDL2"
```

Çıktı formatları: bölüm tabloları olarak
`%-3d %-20s 0x%08llX 0x%08llX 0x%010llX %.2f MB` + `[END_OF_PARTITIONS]`,
XML dökümleri (`partition_%lld.xml`), bölüm bazlı ilerleme
(`Write Part Done: %s, target: 0x%llx, written: 0x%llx`).
Checksum kontrolleri: `bad checksum (0x%04x, expected 0x%04x [or 0x%04x])`.

Kaçış/çerçeveleme ve CRC detayları bu protokolün [spd.md](./spd.md) içinde anlatılmıştır
(saf-Python `spd_do_handshake` üzerinden).

## Burada decompile edilemeyenler

- `MToolMTK.dll` / `MToolSPD.dll` — sunucu tarafından indirilir (kimlik doğrulamalı), yükleyicide gelmez. Python tarafı API yüzeyi [mtk.md](./mtk.md) / [spd.md](./spd.md) içinde belgelenmiştir.
- `Channel9.dll` — native PE32, küçük (log kanal yardımcı programı).
- `src/auto_crash` — Cython derlenmiş (sıkıştırılmış dizeler); sembol yüzeyi [mtk.md](./mtk.md) içinde belgelenmiştir.
