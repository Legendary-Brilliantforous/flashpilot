# motom_tool/ — Moto-M Tool v4.2.2 research notes

Reverse-engineering notes for **Moto-M Tool 4.2.2** (by "Maiky",
`studiomaiky.com`), a commercial Windows Android flashing/repair suite.
Extracted and analyzed on 2026-09-29 from `Moto-M Tool Setup.exe`
(123 MB, Inno Setup 6.6.1). Purpose: interoperability research — the
protocol knowledge below feeds FlashPilot's MTK/SPD/Samsung/FRP/MDM
engines. Use it on devices you own or are authorized to service.

## What the tool actually is

Not a native app. The stack is:

| Layer | Tech | Notes |
|---|---|---|
| Installer | Inno Setup 6.6.1 (LZMA) | AppId `E8A3A650-81D6-48FD-948F-B83091909F51` |
| Main exe | PyInstaller (Python 3.11, `pyiboot01_bootstrap`) | 56 MB onefile; `Moto-M Tool_MTK_Dll_V2.py` is the whole app (~12.9k lines decompiled) |
| Obfuscation | PyArmor 8 (`pyarmor_runtime_004990`, product `MotoMTool`) | AES-128-CBC armored bytecode; statically unpacked (see "How it was unpacked") |
| GUI | CustomTkinter (dark theme `#1a1a1a`) | 6 tabs: Fastboot Operations, SPD Module, Support Area, Patcher Module, ADB Module, MTK Module (Beta) |
| MTK engine | .NET DLL `MToolMTK.dll` via **pythonnet** (`clr`) | Class `SharpMTKClient.MtkDllSession`; DLL does BROM/DA protocol |
| SPD engine | .NET DLL `MToolSPD.dll` via pythonnet + external `spd.dll` CLI | Exploit-based FDL injection |
| Bundled tools | adb/fastboot (platform-tools), busybox, sqlite3, mke2fs/make_f2fs, etc1tool, hprof-conv | Shells out to these |

Everything sensitive (Fernet keys, unlock codes, patched LK images,
loader archives) is **server-mediated** against `https://studiomaiky.com`
— the client is a thin orchestrator. See [server_protocol.md](./server_protocol.md).

## Files in this tree

| File | Contents |
|---|---|
| [mtk.md](./mtk.md) | MediaTek domain: MtkDllSession bridge, crash-to-BROM, payloads, unlock flows |
| [spd.md](./spd.md) | Spreadtrum/UNISOC domain: BSL handshake, exploit payloads, FDL addresses, unlock |
| [samsung.md](./samsung.md) | Samsung: KG lock/bypass, PayJoy MDM, Exynos boot repair (DVIF), AT commands |
| [motorola_unlock.md](./motorola_unlock.md) | Official Motorola web unlock, Valeria LK-swap, ROM patcher, firmware mirrors |
| [server_protocol.md](./server_protocol.md) | All endpoints, auth/licensing model, HWID fingerprint, resource updates |
| [dll_protocol.md](./dll_protocol.md) | Shipped DLL internals: MTool_EROFS decompile (EROFS/ext4/F2FS patcher API), native spd.dll CLI command set |

## Implemented in FlashPilot

Knowledge from this tree already landed in the code:

| Knowledge | Where |
|---|---|
| PenangF unlock (`oem get_key` → external credential → `oem key` + `flashing unlock`) | Research note only — never implemented (no such flow; verify with `flow-list`) |
| Motorola fastboot factory reset (`oem fb_mode_set` → erase userdata/cache/**debug_token** → `oem fb_mode_clear`) | Research note only — never implemented as a flow (factory reset runs via the `factory_reset` ADB flow / fastboot erase rows) |
| MTK OEM VIDs (Sony 0x0fce, LG 0x1004, OPPO 0x22d9, InFocus 0x9bb5) under which an MTK preloader/BROM re-enumerates | Partially: `find_mtk()` in `python/core/mtk.py`; no `MTK_OEM_VIDS` table exists |
| PenangF note + unlock-data URL order (0/3/2) in the standard token flow | Retired with the token flow (`moto_oem_unlock_token` removed); kept here as protocol reference |
| Samsung DVIF download-mode read (115200 8N1, `DVIF` query, `KEY=VALUE` pairs) | Research note only — never implemented (no `dvif` code exists) |
| MTK model→SoC mapping (G14→T616, G35→T760, G54→MT6855, ...) | `supported_devices.json` motorola entries |
| Stock firmware mirrors (lolinet, year-based) | `operations/flashing/mediatek/README.md` |

Tests: the old `tests/test_moto_tool_flows.py` was removed; coverage lives in the per-area suites (`tests/test_frp_flow.py`, `tests/test_devices.py`, cargo `flows::tests`). Not implemented (needs external
per-device assets or their paid server): Valeria patched/stock LK images,
KG exploit binary, `mtk.img` reset image, SPD loader archives, unlock
candidates, EROFS patcher, ExynosCli presets.

## How it was unpacked (for future re-analysis)

```bash
# 1. Inno Setup 6.6.1 — innoextract 1.9 is too old; use innounp-2 under Wine
#    (jrathlev/InnoUnpacker-Windows-GUI release "innounp-2.zip")
wine innounp2/innounp.exe -x -dZ:\\home\\<u>\\motom "Z:\\...\\Moto-M Tool Setup.exe"

# 2. PyInstaller (Python 3.11) — pyinstxtractor.py (extremecoders-re)
python3 pyinstxtractor.py "Moto-M Tool.exe"

# 3. Fix pyc headers (extraction leaves zero-filled 16-byte headers)
#    Python 3.11 magic: a7 0d 0d 0a + 12 zero bytes

# 4. PyArmor 8 static unpack (Lil-House/Pyarmor-Static-Unpack-1shot)
#    PATCH required: oneshot/detect.py raises body_len cap >0xFFFFF to
#    0x10000000 (the 1.2 MB armored blob exceeds the default cap)
python3 oneshot/shot.py <extracted_dir> -o unpacked
#    → *.1shot.cdc.py (decompiled) + *.1shot.das (bytecode disassembly)
#    Runtime facts: AES key 124a39ad996db52f6662215344b403c8, nonce 692e4d6f746f4d546f6f6cdb

# 5. src/auto_crash is a Cython .pyd (compressed strings) — not decompilable;
#    protocol inferred from exported symbols + call sites.
```

Working scratch copy of the full decompile lives outside the repo at
`/home/elijah/motom_research/unpacked/` (12,879 lines, `.1shot.cdc.py`).

## Source references

Line numbers below point into
`Moto-M Tool_MTK_Dll_V2.pyc.1shot.cdc.py` (the decompiled module).
`das` references point into the `.1shot.das` bytecode disassembly where
the decompile was incomplete. Decompiled code can be incomplete — the
`.das` file is the ground truth for control flow.
