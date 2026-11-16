# MediaTek BROM exploit engine — design notes and gap register

How FlashPilot's MTK path works (`src/mtk*.rs`), what the alternative
pointer-overwrite technique reaches that kamakiri2 does not, and the concrete
work needed to close the difference. No device was touched and no source was
modified while writing this.

Two public references carry most of the technical content here:
`bkerler/mtkclient` (the authority for register tables) and
`chaanel/bypass_utility` (MIT — the authority for the pointer-overwrite
technique and its per-SoC parameter set).

## 0. Two ways to get into the BROM

| | Pointer overwrite (bypass_utility) | kamakiri2 (FlashPilot) |
|---|---|---|
| Primitive | overwrite the BROM's USB-send routine pointer at `watchdog + 0x50`, then stream a payload with `0xE0` | CVE-2020-11152, a 4-byte overflow in the CDC line-coding buffer that corrupts the same class of pointer |
| Per-SoC data needed | `watchdog`, `payload_address`, `var_0`, `var_1` | `send_ptr`, `brom_reg_ptr` |
| Trigger | vendor control transfer with `wIndex = var_1` | implicit — the corrupted pointer redirects the next write |
| Payload | headerless ARM shellcode that replaces the BROM handler | shellcode/DA written through `ram_write` |
| After the exploit | 4-byte magic handshake, then a BootROM dump | arbitrary RAM read/write |
| Era | pre-2020 through ~2021 | 2020+ (CVE-2020-11152 and later) |

FlashPilot implements the second. The first is worth implementing as a second
path because it covers the SoCs kamakiri2 cannot reach (§4.1).

---

## 1. The pointer-overwrite technique, end to end

### 1.1 Discovery

The technique is COM-port oriented: enumerate serial ports whose hardware ID
contains `0E8D`, then diff the set on a short poll interval so that a
*newly appeared* port wins. Two weaknesses are inherent to that model:

- A port that is not PID `0x0003` is assumed to be preloader. Any `0E8D` device
  with an unexpected PID is therefore misclassified.
- A device must be pinned explicitly when several are attached; there is no
  ambiguity resolution.

FlashPilot avoids both by enumerating the USB bus directly (§3).

### 1.2 Identity and target config

```
handshake   A0/0A/50/05 with echo checks  (5F/F5/AF/FA)
0xFD        -> 2-byte hw_code + 2-byte status
0xFC        -> hw_sub, hw_ver, sw_ver + status
0xD8        -> target config: bit0 SBC, bit1 SLA, bit2 DAA
```

Only `secure_boot`, `serial_link_authorization` and
`download_agent_authorization` are consumed by the pointer-overwrite path; the
other target-config bits (`epp`, `cert`, `memread`, `memwrite`, `cmd_c8`) are
ignored. FlashPilot decodes all of them (`src/mtk.rs:720-733`).

### 1.3 Preloader crash loop

A preloader entry is crashed, the port re-enumerated, and the handshake repeated
as many times as needed. Three crash methods exist:

| Method | Payload | Call |
|---|---|---|
| `0` (default) | `00 01 9F E5 10 FF 2F E1` (`ldr r0,[pc]; bx r0`) + `0x110` zero pad → jumps to 0 | `send_da(0, len, 0, payload)` + `jump_da(0)` |
| `1` | `0x100` zero bytes | `send_da(0, len, 0x100, payload)` + `jump_da(0)` |
| `2` | none | `read32(0)` |

A `DAA_SIG_VERIFY_FAILED` from `send_da` on a protected preloader is swallowed
and the loop continues. Method `2` matters because it needs no `SEND_DA` at all,
so it works on preloaders that reject `0xD7` outright.

### 1.4 Watchdog disable — before the exploit

```python
write32(watchdog_address, 0x22000064)
```

Unconditional, immediately after the preloader loop and **before** the exploit.
`0x22000064` is the WDT mode/interval register value (disable + ~`0x64` reload).
FlashPilot does not write it at all today (§4.3).

### 1.5 Auth gate

```
if serial_link_authorization or download_agent_authorization:
        exploit()
else:
        insecure path: send_da + jump_da
```

Note the inversion: `secure_boot` (bit 0) is **not** part of the gate, so an
SBC-only device takes the insecure path.

### 1.6 The exploit

```python
addr = watchdog_address + 0x50
write32(addr, payload_address)              # 1. point BROM's send ptr at our buffer
if var_0:                                   # 2. prime the USB cache
    read32(addr - var_0, (var_0 + 4) // 4)
else:
    for i in range(15): read32(addr - (15-i)*4, 15-i+1)
echo(0xE0)                                  # 3. upload command
echo(len(payload), 4)
status = read(2); assert status == 0
write(payload)                              # 4. payload lands at payload_address
read(4)                                     # 5. drain
ctrl_transfer(0xA1, 0, 0, var_1, 0)         # 6. trigger: wIndex = var_1
dev.timeout = 1
pattern = read(4)                           # 7. 4-byte result magic
```

Mechanism: the BROM keeps its "send to USB" routine pointer in a RAM structure at
`watchdog + 0x50`. Writing `payload_address` there and streaming via `0xE0`
makes the BROM copy the host bytes into `payload_address`. The vendor control
transfer `bRequest=0`, `wIndex=var_1` flips the BROM into executing the patched
pointer — `var_1` is the **per-SoC trigger index** into that handler table.

`var_0` is the cache-priming window: when set, the host reads `(var_0+4)/4`
dwords ending at `addr+4`; when unset it walks 15 descending reads ending at
`addr-4`.

### 1.7 Payload format

Payloads are **headerless ARM shellcode** that re-implements the BROM USB handler
and answers the host directly:

```
generic_dump_payload.bin  (228 B)
  01 30 8F E2   add r3, pc, #1     ; ARM/Thumb switch
  13 FF 2F E1   bx  r3
  ... contains the literal sync bytes  A0 0A 50 05  at offset 0xC4
  ... last dword  00 70 00 10 = 0x10007000   <- watchdog base, patched by host
mt6765_payload.bin (612 B) ... last 8 bytes: 94 59 10 00 | ED CA 00 00
generic_loader_payload.bin (64 B) ... ends EF BE AD DE
```

The payload is prepared by rewriting the **last** dword when it equals
`0x10007000` (watchdog) and the **second-to-last** when it equals `0x11002000`
(UART base), then padding to a multiple of 4. Only the generic dump payload still
carries `0x10007000` in its tail; per-SoC payloads bake their own base in, so the
substitution is a no-op for them.

### 1.8 Result handshake

| 4-byte reply | Meaning | Action |
|---|---|---|
| `A1 A2 A3 A4` | protection disabled | done |
| `C1 C2 C3 C4` | payload has `send_dword` | dump BootROM, 0x20000 bytes |
| `00 00 C1 C2` then `C1 C2 C3 C4` | word-mode dump | dump BootROM in word mode |
| empty | payload silent | logged, not fatal |
| other | — | `RuntimeError` |

**The pointer-overwrite path never uploads a Download Agent.** It ends with a
BootROM dump; flashing is a separate closed-source stage in tools that use it.

### 1.9 Insecure-device path

```python
payload_address = 0x200D00
payload += b'\x00' * 0x100
send_da(0x200D00, len(payload), 0x100, payload)
jump_da(0x200D00)
result = read(4)                            # expect A1A2A3A4
```

`sig_len = 0x100` plus a `0x100` zero pad is the trick that makes the BROM's
signature check pass on an unsigned payload — the trailing "signature" region is
zeros.

### 1.10 Bringing up a new SoC

On failure: close the port, `var_1 += 1`, re-find, re-crash, re-handshake,
re-exploit. Unbounded. This is how the per-SoC `var_1` values were originally
discovered, and it is a useful template for adding a new chip — but it must be
bounded in a shipped tool.

---

## 2. Per-SoC parameters (published bypass_utility set)

Defaults when a key is absent:

| Field | Default | Notes |
|---|---|---|
| `watchdog_address` | `0x10007000` | |
| `uart_base` | `0x11002000` | no per-SoC override in the published set |
| `payload_address` | `0x100A00` | |
| `var_0` | `None` | |
| `var_1` | `0xA` | |
| `crash_method` | `0` | no per-SoC override either |
| `payload` | required | |

Overrides actually published (33 entries):

| hw_code | SoC | watchdog | var_0 | var_1 | payload_addr | ptr_usbdl | ptr_da |
|---|---|---|---|---|---|---|---|
| `0x6261` | MT6261 | `0xA0030000` | – | `0x28` | – | – | – |
| `0x6572` | MT6572 | – | – | – | `0x10036A0` | `0x40ba68` | `0x40befc` |
| `0x6580` | MT6580 | – | – | `0xAC` | – | `0xb60c` | `0xba94` |
| `0x321` | MT6735 | `0x10212000` | `0x10` | `0x28` | – | `0x95f8` | `0x9a94` |
| `0x335` | MT6737 | `0x10212000` | `0x10` | `0x28` | – | `0x9608` | `0x9aa4` |
| `0x699` | MT6739 | – | `0x20` | `0xB4` | – | `0xdf1c` | `0xe3e8` |
| `0x337` | MT6753 | `0x10212000` | – | `0x28` | – | `0x9668` | `0x9b04` |
| `0x717` | MT6761 | – | – | `0x25` | – | `0xbc8c` | `0xc158` |
| `0x690` | MT6763 | – | – | `0x7F` | – | `0xd66c` | `0xdb38` |
| `0x766` | MT6765 | – | `0x2C` | `0x25` | – | `0xbdc0` | `0xc28c` |
| `0x707` | MT6768 | – | `0x2C` | `0x25` | – | `0xc190` | `0xc650` |
| `0x788` | MT6771 | – | `0x20` | – | – | `0xdebc` | `0xe388` |
| `0x813` | MT6785 | – | – | – | – | `0xe2a4` | `0xe764` |
| `0x279` | MT6797 | – | – | – | – | `0x9eac` | `0xa354` |
| `0x816` | MT6885 | – | – | – | – | `0xe6b8` | `0xebbc` |
| `0x8163` | MT8163 | – | – | `0xB1` | – | `0xc12c` | `0xc5c8` |
| `0x8167` | MT8516 | – | – | `0xCC` | – | `0xd2e4` | `0xd7ac` |
| `0x8172` | MT8173 | – | – | – | `0x120A00` | `0xa0e4` | `0xa580` |
| `0x562` | MT6799 | `0x10211000` | – | – | – | `0xf5ac` | `0xfa78` |
| `0x1066` | MT6781 | – | – | – | – | `0xe5d8` | `0xea94` |

(20 representative rows of the 33; the remainder are the same shape.)

Counts: `var_1` on 12 SoCs, `var_0` on 6, `watchdog_address` on 5,
`payload_address` on 2, `ptr_usbdl`/`ptr_da` on all 33.

**`ptr_usbdl` / `ptr_da` are dead config for this technique.** Nothing in the
published engine reads them; they belong to the DA/loader path. They are also
**not** mtkclient's `send_ptr`/`brom_register_access` — see §7.1 for why the two
must not be mixed.

### Orphaned payloads

38 per-SoC `mt*_payload.bin` files versus 33 config entries. Five payloads have
**no hw_code entry**, so they are unreachable: `mt2601`, `mt6758`, `mt6877`,
`mt6893`, `mt8512`.

---

## 3. FlashPilot's equivalent stages

| Stage | FlashPilot | Location |
|---|---|---|
| Discovery | libusb enumeration by VID `0x0e8d`, PID→stage map (`0x0003` brom, `0x2000` preloader, `0x0004/0x1004` DA, `0x0a0a` adb) | `src/mtk.rs:8-42`, `src/mtk.rs:803-837` |
| Handshake | `a0 0a 50 05` one byte at a time, expects complement echo, 5 retries, extra wake byte only for non-BROM PIDs | `src/mtk.rs:44-52`, `src/mtk.rs:599-681` |
| Identity | `0xFD` hw code, `0xD8` target config (10 bits), `0xFE` BL ver, `0xFF` BROM ver, `0xFC` hw/sw ver, `0xE1` ME_ID, `0xE7` SOC_ID | `src/mtk.rs:737-801`, `src/mtk_exploit.rs:393-437` |
| Preloader crash | 2 attempts, both `ldr r0,[pc]; bx r0`: target `0x0`, then `0x0020_0d00` | `src/mtk_exploit.rs:751-824` |
| Watchdog | **never written** | `grep -rn watchdog src/` → only `mtk_exploit.rs:29,44,55,296,300`, `mtk.rs:736` |
| Exploit | kamakiri2 line-coding overflow → `brom_register_access` (0xDA) → arbitrary RAM RW | `src/mtk_exploit.rs:250-377`, `src/mtk.rs:501-560` |
| Payload/DA | `SEND_DA` (0xD7) with checksum + optional SLA, `JUMP_DA` (0xD5) | `src/mtk.rs:478-495`, `src/mtk_da.rs:292-313` |
| DA containers | native V5/V6 parse, 50 + 9 entries, `0xC0` loader sync | `src/mtk_daloader.rs:80-171`, `src/mtk_da.rs:1389-1503` |
| SLA | RSA signing with 37 keys, triggered by `0x1D0D` in `send_da` | `src/mtk_sla.rs:16-61`, `src/mtk_sla_keys.rs:11`, `src/mtk.rs:433-495` |

---

## 4. Gap analysis

### 4.1 SoC coverage

Pointer-overwrite path: 33 hw_codes across feature-phone → tablet/TV. FlashPilot:
17 entries (16 unique — `0x6781` duplicates `0x1066`).

| Family | Pointer overwrite | FlashPilot |
|---|---|---|
| MT6261 (feature phone) | `0x6261` | — |
| MT65xx (6572/6580/6582/6592/6595) | 5 | — |
| MT67xx budget (6735/6737/6739/6753/6755/6757/6761/6763/6765/6768/6771/6779/6781/6785) | 14 | 7 (`699, 766, 707, 788, 725, 1066/6781, 813`) |
| MT67xx high (6795/6797/6799) | 3 | — |
| MT68xx (6833/6853/6873/6885) | 4 | 4 (`989, 996, 886, 816`) |
| Tablet / TV (8127/8163/8167/8173/8590/8695) | 6 | — |
| Newer Dimensity | — | `0x950` (6891/6893), `0x959` (6877), `0x1129` (6855), `0x1209` (6835V), `0x6899` (6899) |
| **Total** | **33** | **16 unique** |

Overlap: 11 hw_codes (`699, 766, 707, 788, 725, 1066, 813, 989, 996, 886, 816`).

Unreachable today (22): `6261, 6572, 6580, 6582, 6592, 6595, 321, 335, 337, 326,
551, 717, 690, 6795, 279, 8127, 8163, 8167, 8172, 8695, 562, 8590`.

FlashPilot-only (5 unique): `950, 959, 1129, 1209, 6899`.

**Verdict:** FlashPilot is deeper on 2021+ Dimensity, which the pointer-overwrite
table cannot touch (it stops at MT6885/MT6781), and much narrower on
legacy/budget/tablet SoCs — including the extremely common MT6735/6737/6753 and
MT6580/6582 families.

### 4.2 Exploit technique — different, not just different parameters

| Aspect | Pointer overwrite | kamakiri2 (FlashPilot) |
|---|---|---|
| Primitive | overwrite the USB send pointer at `watchdog+0x50`, `0xE0`-stream the payload into RAM | CVE-2020-11152 4-byte overflow in the CDC line-coding buffer, corrupting the send pointer so `0xDA` routes through arbitrary RAM (`mtk_exploit.rs:282-294`) |
| Per-SoC needs | `watchdog`, `payload_address`, `var_0`, `var_1` | `send_ptr` (read + 8), `brom_reg_ptr` |
| Trigger | control transfer with `wIndex=var_1` | implicit — the corrupted pointer redirects the next write (`mtk_exploit.rs:362-369`) |
| Cache priming | one read of `(var_0+4)/4` dwords or 15 descending reads | `brom_register_access(0,0,1)` then `read32(watchdog+0x50,1)` (`mtk_exploit.rs:298-301`) |
| Payload type | headerless shellcode that **replaces** the BROM handler | shellcode/DA written through `ram_write`, then `ptr_send+8 := payloadaddr` |
| Capability after exploit | 4-byte magic handshake + BootROM dump | full arbitrary RAM read/write (`ram_read`/`ram_write`) |

Consequences:

- The pointer-overwrite approach needs **no pointer table** beyond one field per
  SoC, which is why it covers 22 SoCs kamakiri2 cannot.
- FlashPilot's approach is **strictly more powerful after the exploit**
  (arbitrary RAM RW), but needs two correct per-SoC pointers and a
  `0x1A1D`-prone cache dance.
- The two are complementary. Implementing pointer-overwrite as a second path
  would unlock the 22 missing SoCs with ~4 extra table fields per chip, and the
  `var_0`/`var_1` values are already published.

### 4.3 Watchdog disabling — the clearest functional gap

| | Pointer overwrite | FlashPilot |
|---|---|---|
| Writes `0x22000064` to the WDT | **yes**, unconditionally, right after the preloader loop, before the exploit | **no** — no WDT write anywhere in `src/` |
| WDT address source | per-SoC override (5 published: `0xA0030000`, `0x10212000` ×3, `0x10211000`) | `MtkChipConfig.watchdog`, only ever **read** at `watchdog+0x50` for cache priming (`mtk_exploit.rs:300`) |

Why it matters: `dump_preloader` walks up to 4 MiB through `ram_read` in
512-byte steps (`mtk_exploit.rs:231-240`) — hundreds of round-trips. If the BROM
watchdog is armed, the SoC can reset mid-dump and the session dies with no
diagnostic. Disabling it first removes that risk. The value and the five per-SoC
addresses are known, so this is a small, low-risk addition
(`session.write32(cfg.watchdog, 0x22000064)` after `read_chip`).

### 4.4 Payload / DA handoff

| | Pointer overwrite | FlashPilot |
|---|---|---|
| Protected path | shellcode replaces the BROM handler; **no DA at all** | kamakiri2 → then still `SEND_DA` + `JUMP_DA` (`mtk_exploit.rs:564-575`) |
| Insecure path | `send_da(0x200D00, len, sig_len=0x100)` + `0x100` zero pad + `jump_da` | `upload_da_bytes` with `sig_len = 0` (`mtk_da.rs:297`), address from `parse_preloader` (default `0x201000`, `mtk_exploit.rs:113`) |
| Checksum | read but ignored | validated; device checksum `0` rejected unless `MTK_ALLOW_ZERO_CHECKSUM=1` (`mtk.rs:389-397`, `mtk.rs:420-424`) |
| Result check | 4-byte magic (`A1A2A3A4` / `C1C2C3C4`) | none — success = no error from `SEND_DA`/`JUMP_DA` |
| DA containers | 3 AllInOne (`5.1420`/`5.1824`/`5.2136`, 12/30/35 entries) | `MTK_DA_V5.bin` (50 entries) + `MTK_DA_V6.bin` (9 entries), parsed natively (`mtk_daloader.rs:80-171`) |
| Preloader blobs | **835** per-model blobs as a DA-path fallback | none |
| Per-SoC payload blobs | 38 + 7 generic | none |
| Loader sync | n/a (no DA) | `0xC0` on the same connection (`mtk_da.rs:1488-1503`) |

Two FlashPilot defects found while comparing:

1. `upload_da_bytes` sets `hw_code` from the **target-config bitfield**, not the
   SoC code — `self.set_hw_code(tc.raw)` at `mtk_da.rs:301-303` where `tc` is
   `MtkTargetConfig`. Any later use of `DaSession.hw_code` is garbage.
2. `brom_run_payload` passes the **whole file** (including any `MMM\x01`
   preloader header) to `k2.exploit`, while headerless shellcode payloads are the
   norm — `parse_preloader` splits header/payload for the *address* but not for
   the bytes it writes (`mtk_exploit.rs:545,568`).

### 4.5 SLA (Secure Lock Authentication)

| | Pointer overwrite | FlashPilot |
|---|---|---|
| SLA handling in code | **none** — no `0xE3`, no keys, no `0x1D0D` handling | full: `0xE3` challenge/response, 37 RSA keys, `customized_sign`, word-swapped PKCS#1 v1.5 (`mtk_sla.rs:16-56`, `mtk_sla_keys.rs:11`) |
| How it avoids SLA | the exploit bypasses the auth check entirely; `send_da` only inspects the 2-byte status | `send_da` intercepts status `0x1D0D` and runs `handle_sla` inline (`mtk.rs:485-490`) |
| Robustness | n/a | challenge length capped at 4096 to stop a hostile BROM forcing a 4 GiB alloc (`mtk.rs:450-452`); `0x7017` treated as already-authenticated (`mtk.rs:438-441`) |

**FlashPilot is clearly ahead here.** The pointer-overwrite path only works on
chips its exploit covers; on any SoC outside its 33-entry table it cannot
authenticate at all, whereas FlashPilot can fall back to a real SLA signature.
Conversely, it never needs a leaked key — the 37 keys are a legal/ethical
liability FlashPilot carries and the other technique avoids.

### 4.6 Capabilities the pointer-overwrite path has that FlashPilot does not

1. **Disables the watchdog before the exploit.** §4.3.
2. **Dumps the BootROM** (0x20000 bytes) once the payload reports `send_dword`.
   FlashPilot has no MTK BootROM dump at all — `grep -ri bootrom src/` only hits
   a doc comment (`mtk_exploit.rs:736`) and SPD. BootROM dumps are how new SoC
   offsets are discovered, so this is a research-capability gap.
3. **22 additional SoCs** (§4.1), including all of MT65xx and the tablet/TV
   parts.
4. **Three preloader crash methods**, including `crash_method 2` (`read32(0)`)
   which needs no `SEND_DA` at all — useful on preloaders that reject `0xD7`.
   FlashPilot only has the `ldr/bx` variant, and only two target addresses
   (`mtk_exploit.rs:788-801`).
5. **A crash retry loop** — FlashPilot crashes once; `wait_mtk_brom` then sleeps
   4 s and re-enumerates once (`flows.rs:4102-4140`).
6. **A `var_1` sweep harness** for bringing up a new SoC. FlashPilot's `var1`
   field exists but is never used (`mtk_exploit.rs:37,50,61` — definition and
   construction only), and there is no equivalent search loop.
7. **835 per-model preloader blobs** as a fallback firmware corpus.
8. **Per-SoC payload blobs** (38) that need no user-supplied DA. FlashPilot
   requires `MTK_DA` or the two generic containers (`flows.rs:4074-4081`).

### 4.7 What FlashPilot does better

1. **Real SLA implementation** with 37 keys and a hardened challenge path
   (§4.5).
2. **Arbitrary RAM read/write** after the exploit (`ram_read`/`ram_write`,
   `mtk_exploit.rs:304-358`), enabling preloader dumping on protected devices.
   The pointer-overwrite path can only dump the BootROM.
3. **Preloader security patching** — 11 byte-patches for DA1 and 8 for DA2,
   ported from mtkclient (`mtk_exploit.rs:118-164`).
4. **DA container parsing** — native V5/V6 reader with marketing-dacode fallback
   and overflow-checked region slicing (`mtk_daloader.rs:58-171`).
5. **Checksum validation** on `SEND_DA`/`upload_data`, including refusing a
   device-reported `0` (`mtk.rs:389-429`). Ignoring the checksum means a corrupt
   DA upload goes unnoticed.
6. **Cross-platform libusb** (`rusb`, no COM ports). The other technique is
   Windows-COM-bound by construction.
7. **Multi-device safety** — `find_mtk_dev("auto")` refuses an ambiguous bus
   (`mtk_da.rs:903-921`) instead of grabbing whichever port diffed in.
8. **Handshake diagnostics** — distinguishes "device echoed our own byte
   verbatim" (wrong entry mode) from a plain timeout (`mtk.rs:651-658`).
9. **Verify-after-write (SHA-256)** and a read-only backup flow
   (`flows.rs:2035`, `flows.rs:4222-4262`).
10. **Unit tests** for the exploit path: table coverage, patch application,
    `parse_preloader` truncation, BE→LE swap, dump windowing, checksum policy
    (`mtk_exploit.rs:583-735`, `mtk.rs:882-963`,
    `mtk_daloader.rs:174-255`).
11. **Graceful degradation** on an unknown hw_code — identity-only report with a
    note (`mtk_exploit.rs:471-480`) instead of a hard `NotImplementedError`.

### 4.8 FlashPilot dead code / stubs found during the comparison

Worth flagging because they make the engine look more complete than it is:

| Item | Evidence |
|---|---|
| `MtkChipConfig.brom_payload_addr`, `da_payload_addr`, `misc_lock`, `var1` are never read | `mtk_exploit.rs:30-37,45-61`; grep shows no other uses |
| `mtk_brom_exploit()` is a logging stub — no exploit, no upload | `mtk_da.rs:1660-1720` |
| `mtk_bypass_unified()` returns JSON strings describing modes; the `BromExploit` arm only probes | `mtk_da.rs:1798-1860` |
| `mtk_auth_flash` flow claims "auth-bypass flash" but calls the stub above, then falls through to a GPT FRP wipe | `flows.rs:4151-4220` |
| `upload_da_bytes` derives `hw_code` from the target-config bitfield | `mtk_da.rs:301-303` |
| `brom_run_payload` still issues `SEND_DA` after kamakiri2 already redirected the pointer | `mtk_exploit.rs:564-575` |

---

## 5. Prioritised recommendations

| # | Change | Payoff | Effort |
|---|---|---|---|
| 1 | Add the WDT disable (`write32(cfg.watchdog, 0x22000064)`) right after `read_chip`, gated on a config flag | removes a whole class of mid-dump resets | S |
| 2 | Add `payload_addr`, `var_0`, `var_1` to `MtkChipConfig` and implement pointer-overwrite (`watchdog+0x50` write → `0xE0` upload → `ctrl_transfer(wIndex=var_1)`) as an alternative to kamakiri2 | unlocks the 22 unreachable SoCs (MT65xx, MT6735/37/53, tablets) | M |
| 3 | Import the published bypass_utility parameter table as the new SoC source; drop the unused `brom_payload_addr`/`da_payload_addr`/`misc_lock` fields or wire them | +22 SoCs with published, field-tested parameters | S |
| 4 | Add BootROM dump (0x20000 via the payload's `send_dword` protocol) as a research CLI | enables offset discovery for new SoCs | S |
| 5 | Fix `upload_da_bytes` `hw_code` sourcing | correctness of `DaSession` state | S |
| 6 | Add `crash_method 2` (`read32(0)`) and a bounded crash retry loop | more preloaders reach BROM | S |
| 7 | Do **not** adopt checksum-ignoring `send_da` | FlashPilot's validation is a safety feature | — |

## 6. Citation index

FlashPilot: `src/mtk.rs:8-52,122-127,175-182,254-274,302-324,328-361,
366-383,389-429,433-495,501-560,565-585,599-681,720-733,737-801,803-837` ·
`src/mtk_exploit.rs:26-94,98-164,190-243,250-377,393-437,441-534,539-581,
583-735,751-824` · `src/mtk_sla.rs:16-61` · `src/mtk_sla_keys.rs:11-48` ·
`src/mtk_daloader.rs:58-171,174-255` ·
`src/mtk_da.rs:292-313,1355-1375,1389-1503,1660-1720,1798-1860,1863-1889,
1963-1970` · `src/flows.rs:81-82,145,2035,2136-2171,4074-4081,4102-4140,
4151-4220,4222-4262` · `src/main.rs:346-413` · `root/tools/mtk/README.md`.

External: `chaanel/bypass_utility` (MIT) `exploit.py` and its config, payload
`mt*_payload.bin` set; `bkerler/mtkclient` `mtkclient/config/brom_config.py`.

---

## 7. Addendum — register-table verification against upstream mtkclient

`bkerler/mtkclient` `mtkclient/config/brom_config.py` (main) is the authority.

### 7.1 MT6885 `send_ptr` — FlashPilot matches upstream

| Source | Field | Value |
|---|---|---|
| mtkclient `0x816` | `send_ptr[1]` | `0xE6FC` |
| mtkclient `0x816` | `brom_register_access[1]` | `0xebbc` |
| FlashPilot `src/mtk_exploit.rs:84` | `send_ptr` | `0xE6FC` ✅ |
| FlashPilot `src/mtk_exploit.rs:84` | `brom_reg_ptr` | `0xebbc` ✅ |
| bypass_utility config `0x816` | `ptr_usbdl` | `0xe6b8` |
| bypass_utility config `0x816` | `ptr_da` | `0xebbc` |

Two separate points:

1. `ptr_usbdl` is **not** mtkclient's `send_ptr`. The fields are not comparable
   1:1, which is why a naive `0xE6FC` vs `0xE6b8` comparison looks like a table
   error. `ptr_usbdl`/`ptr_da` are consumed only by the DA/loader path.
2. Against the actual mtkclient field, **FlashPilot already matches upstream**.
   Do not "fix" it to the `ptr_usbdl` value.

### 7.2 MT6899 (`0x6899`) watchdog disagrees with upstream

| Source | `watchdog` |
|---|---|
| mtkclient `0x6899` | `0x1C00B000` |
| FlashPilot `src/mtk_exploit.rs:89` | `0x1C010000` |

Caveat: upstream currently **comments out** `send_ptr`, `brom_register_access`,
`cqdma_base` and the blacklist for `0x6899` ("new crypto hw", Xiaomi 15T), so
mtkclient does not drive kamakiri2 on this part today. The FlashPilot entry is
speculative either way. Since `watchdog` is used as `watchdog + 0x50` in
`Kamakiri2::prime()`, a wrong value silently prevents the exploit from sticking —
this needs a device test before being changed.

**Recommendation:** leave the value but add a comment citing the discrepancy, or
change it to `0x1C00B000` and gate MT6899 behind an experimental flag. Do not
change it without hardware confirmation.

### 7.3 Overlap check across the whole table

Of FlashPilot's 17 SoCs, 5 appear in the upstream extraction with pointer data:
`0x813`, `0x816`, `0x1129`, `0x1209`, `0x6899`. The first four match upstream
exactly on `send_ptr`, `brom_reg_ptr`, `watchdog` and `var1`. Only `0x6899`'s
watchdog differs (§7.2). The remaining 12 FlashPilot entries are not present in
upstream's pointer-bearing set and could not be cross-checked this pass.
