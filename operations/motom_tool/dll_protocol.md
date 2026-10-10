# dll_protocol.md — .NET DLL + native CLI internals

The MTK/SPD engines of Moto-M Tool ride on a .NET assembly
(`MToolMTK.dll`/`MToolSPD.dll`, downloaded on demand — not shipped) and a
native x86 CLI (`spd.dll`). What IS shipped and decompiled here:

- `MTool_EROFS.dll` — .NET, fully decompiled (ILSpy 8.2) → `MTool.EROFS`
  + `SuperExt4Reader` (63 source files)
- `spd.dll` / `spd2.dll` / `spd3.dll` — native PE32 CLI, strings-analyzed

## MToolErofsApi (the shipped EROFS patcher)

```csharp
public static class MToolErofsApi {
    static MToolPatchResult PatchBuild(string imagePathOrChunk, string signature = null);
    static MToolPatchResult PatchHosts(string imagePathOrChunk, string rulesPath);
    static MToolPatchResult RemoveApks(string imagePathOrChunk, string apkListJsonPath);
    static MToolRomPatchResult PatchRom(string imagePathOrChunk, string signature = null,
                                        string hostsRulesPath = null, string apkListJsonPath = null);
}
```

### PatchBuild — build.prop signature injection

- Default signature: `"Moto-M Tool Power"`.
- `BuildPropPatcher.Scan(explorer, signature)` → matches of `ro.build.id`
  / `ro.build.display.id` lines across all partitions in the super image.
- `AnalyzeSettingsDisplaySource` → finds where `android.os.Build.DISPLAY`
  comes from: either a static `ro.build.display.id` prop (selected
  directly) or a **runtime assignment** (`ro.build.display.id` set at
  runtime — then `PatchRuntimeDisplayAssignments` patches the source
  props feeding it).
- `Patch(explorer, scan, allowCompressedErofs: true)` — rewrites the
  prop **inside compressed EROFS** too (the reader handles
  EROFS + ext4 + F2FS).
- Result: `MToolPatchResult { Operation: "patch-build", Success, Error,
  Signature, SelectedTarget: "<partition>:<file> <key>", FileSystem,
  PatchedFiles[], Warnings[] }`.

### PatchHosts — /etc/hosts rewrite

- `HostsPatcher.Analyze(explorer, rulesPath, "127.0.0.1")` → plan with
  targets per `<partition>:<file>` (the usual `/system/etc/hosts`).
- `Patch(explorer, plan, allowCompressed: true, patchAllTargets: false)`
  — patches the FIRST target by default; `patchAllTargets` for all.
- The rules file is the classic ad-block/redirect hosts format
  (`127.0.0.1 domain`), delivered by the server (`get_assets` →
  `hosts_rules`).

### RemoveApks — batch APK removal from the system image

- Input JSON: `{ "<partition>": ["path/to/app.apk", ...], ... }`.
- `ApkBatchRemover.Scan` → candidates; `Delete` → batch removal
  (EROFS/ext4). Result lists removed vs warned + not-found.

### OpenExplorer — image/chunk handling

```
Directory OR '*sparsechunk.*' file
    → PartitionExplorer.OpenMultiChunk(
          MultiChunkSparseStream.FindAndSortChunks(path))   # sparse set sorted by index
plain image file
    → new PartitionExplorer(path)
```

`SuperExt4Reader` internals (shipped, decompiled): EROFS super block +
compact/extended inodes + LZ4 cluster configs (`ZErofsLz4Cfgs`), ext4
reader, F2FS utils, `PartitionExplorer` for multi-partition super
images, `GetFileLayoutInfo(partition, path).FileSystem` to report which
FS a file lives in.

This is the "custom signature" ROM patching knowledge
(see [motorola_unlock.md](./motorola_unlock.md) § ROM patcher): the
signature ends up in `ro.build.display.id` inside the (possibly
compressed-EROFS) super image, hosts get redirected, and listed APKs
are stripped — all without ever unpacking the image to disk.

## spd.dll — native exploit CLI (command set)

`spd.dll` (also `spd2/3.dll` backup variants) is the native x86
Spreadtrum/UNISOC exploit runner invoked as a child process (see
[spd.md](./spd.md)). Full command surface from the binary:

```
fdl FILE addr                    upload FDL stage to load address
exec                             execute FDL2
exec_addr ADDR                   exploit exec at address
erase_part part_name/part_id     erase partition
write_part part_name/part_id F   write partition
read_parts partition_list_file   read partitions
write_parts save_location        write all partitions
partition_list FILE              XML partition list
preset_modem                     modem preset
chip_uid                         read chip UID
reset                            reset device
```

Protocol markers in the binary (the BSL conversation):

```
CMD_CONNECT bootrom / CMD_CONNECT FDL1    # connection phases
CHECK_BAUD FDL1 / CHANGE_BAUD FDL1 to %d  # baud negotiation
KEEP_CHARGE FDL1                          # charge-only flag
EXEC FDL2 / "FDL2 ALREADY EXECUTED, SKIP"
"BOOT COMPLETED: Device is now in FDL2 mode."
BSL_REP_VER / BSL_REP_LOG / BSL_REP_READ_CHIP_UID
ENABLE_WRITE_RAW_DATA / DISABLE_WRITE_RAW_DATA in SPRD4
"Warning: disable dm-verity needs a write-verification-disabled FDL2"
```

Output formats: partition tables as
`%-3d %-20s 0x%08llX 0x%08llX 0x%010llX %.2f MB` + `[END_OF_PARTITIONS]`,
XML dumps (`partition_%lld.xml`), per-part progress
(`Write Part Done: %s, target: 0x%llx, written: 0x%llx`).
Checksum checks: `bad checksum (0x%04x, expected 0x%04x [or 0x%04x])`.

The escaping/framing and CRC details of this protocol are documented in
[spd.md](./spd.md) (from the pure-Python `spd_do_handshake`).

## Not decompilable here

- `MToolMTK.dll` / `MToolSPD.dll` — server-downloaded (auth-gated), not
  shipped in the installer. Their Python-side API surface is documented
  in [mtk.md](./mtk.md) / [spd.md](./spd.md).
- `Channel9.dll` — native PE32, minor (log channel helper).
- `src/auto_crash` — Cython-compiled (compressed strings); symbol
  surface documented in [mtk.md](./mtk.md).
