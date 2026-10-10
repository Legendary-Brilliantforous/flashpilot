# motom_tool/ — index

Reverse-engineering notes for **Moto-M Tool 4.2.2** (commercial Windows
Android flashing/repair suite by "Maiky", `studiomaiky.com`). Pure
markdown — no code imports this. The knowledge feeds FlashPilot's
engines (MTK/SPD/Samsung/FRP/MDM).

| File | Contents |
|---|---|
| [README.md](./README.md) | Overview: what the tool is (PyInstaller + PyArmor + CustomTkinter + .NET DLLs), how it was unpacked |
| [mtk.md](./mtk.md) | MediaTek: `MtkDllSession` bridge (pythonnet), crash-to-BROM exploit, FDL payloads, unlock flows, FRP/misc patch files, fastboot progress parser |
| [spd.md](./spd.md) | Spreadtrum/UNISOC: BSL serial protocol (framing, CRC16, escaping), exploit command line, FDL/exploit addresses per SoC, DLL loader injection, .bat→flashfile parsing |
| [samsung.md](./samsung.md) | Samsung: KG lock/bypass, PayJoy MDM, Exynos boot repair (DVIF serial protocol), AT commands (Android 16), DNS/EULA FRP methods, Samsung APKs |
| [motorola_unlock.md](./motorola_unlock.md) | Official Motorola web unlock (verifyPhone/unlockPhone URLs, unlock-data order 0/3/2), Valeria LK-swap protocol, ROM patcher (AES-256-CTR scheme), firmware mirrors, QR ADB enrollment |
| [server_protocol.md](./server_protocol.md) | All ~29 endpoints on studiomaiky.com, auth/licensing model (JWT + DPAPI + credits), HWID fingerprinting, resource-update protocol |
| [dll_protocol.md](./dll_protocol.md) | Shipped DLL internals: MTool_EROFS decompile (EROFS/ext4/F2FS patcher API: PatchBuild/PatchHosts/RemoveApks), native spd.dll CLI command set + BSL markers |

## Key takeaways for FlashPilot

1. **Motorola official unlock**: URL templates
   `verifyPhone/{part0}/{part3}/{part2}/` and `unlockPhone/{part0}/{part3}/{part2}/`
   under `en-us.support.motorola.com/cc/productRegistration/` — no
   special headers beyond session cookies. PenangF devices use
   `fastboot oem get_key` + `/generate-oem-key`.
   → implemented: `flow_moto_oem_unlock_token` (URL note),
   `flow_moto_penangf_unlock`.
2. **SPD BSL framing** (from the pure-Python `spd_do_handshake`):
   `~`-framed, `>HH` cmd/len + CRC-16-CCITT (XMODEM), escapes
   `}→}]`, `~→}^`, ACK 0x80 / VER 0x81 @ 115200. → in the Rust SPD core.
3. **MTK VIDs**: 0E8D, 0FCE, 1004, 22D9, 9BB5. → implemented in
   `python/core/mtk.py` (`MTK_OEM_VIDS`).
4. **Valeria pattern**: transient LK swap (patched LK in → oem unlock →
   stock LK restored on every exit path). → documented only (needs
   per-device LK assets).
5. **Patcher encryption**: AES-256-CTR, 16-byte random nonce prefix,
   4 MiB chunks, super images only. → documented only (proprietary DLL).
6. **Server commands pattern**: most ADB operations (KG, MDM, EULA) are
   server-fetched command lists (`?parte=<part>`) — the client only
   substitutes canary packages (`com.google.android.youtube`).
   → FlashPilot's own MDM flows cover this with local command sets.
7. **Samsung DVIF download-mode read** (115200 8N1, `DVIF` query,
   `KEY=VALUE` pairs, fields MODEL/SALES/VER/UN/...). → implemented:
   `flow_download_mode_dvif` in `python/core/core.py`.
8. **Motorola factory reset** (`fb_mode_set` → erase userdata/cache/
   `debug_token` → `fb_mode_clear`). → implemented:
   `flow_moto_factory_reset_fb`.
9. **MTK model→SoC mapping** (G14→T616, G35→T760, G54→MT6855, ...).
   → implemented in `supported_devices.json` motorola entries.

## Where the decompile lives

`/home/elijah/motom_research/unpacked/Moto-M Tool_MTK_Dll_V2.pyc.1shot.cdc.py`
(12,879 lines; `.1shot.das` = bytecode ground truth). Re-analysis
recipe in [README.md](./README.md) § "How it was unpacked".
