# USB detection — capability register

**Scope:** How FlashPilot finds and classifies a device on the USB bus, and what
is still missing. Read-only review of `src/usb/`; no device was touched.

---

## 1. Executive summary

- Detection is **bus-wide**, not port-by-port: `libusb` enumeration plus an ADB
  merge, so a device is found whether it presents as BROM, EDL, download mode,
  fastboot, ADB or MTP.
- Classification is **interface-aware**: VID/PID tables give the vendor and
  stage, and descriptor classes (ADB 255/66/1, MTP class 6, HID class 3)
  disambiguate the rest.
- The remaining gaps are descriptor-level quirks (port reset before enumerate)
  and the fact that the PID table is only as good as the pairs actually
  observed.

---

## 2. Tables

### 2.1 Recognised phone vendor IDs (`src/usb/filtering.rs`)

| Vendor | VID | Note |
|---|---|---|
| Samsung | `0x04E8` | Odin, ADB, MTP, HID |
| Qualcomm | `0x05C6` | EDL, DIAG, modem |
| MediaTek | `0x0E8D` | BROM, preloader, DA |
| Spreadtrum/Unisoc | `0x1782` | download mode |
| Google | `0x18D1` | ADB, fastboot, MTP |
| Apple | `0x05AC` | normal/recovery/DFU |

### 2.2 MediaTek OEM VIDs

An MTK preloader or BROM frequently re-enumerates under an OEM VID rather than
`0x0E8D`. These are treated as MTK flashing stages even when the device exposes
no strings or interfaces at all, so a bare stage is never dropped:

`0x0E8D`, `0x0FCE` (Sony), `0x1004` (LG), `0x22D9` (Oppo), `0x9BB5` (InFocus).

### 2.3 Generic Android VIDs

`0x18D1` (Google), `0x0BB4` (HTC), `0x2717`/`0x2A70` (Xiaomi), `0x12D1`
(Huawei), `0x22D9` (ZTE), `0x2AE5` (OnePlus), `0x22B8` (Motorola).

### 2.4 Qualcomm PIDs (`src/qualcomm/sahara.rs`)

| Group | PIDs | Meaning |
|---|---|---|
| EDL | `0x9008`, `0x900E`, `0x901D`, `0x9025`, `0x9046`, `0x9066`, `0x90DB` | Sahara/Firehose programmable |
| DIAG | `0x9006`, `0x9026` | diag composites — never get a Sahara hello |
| Broad | `0x9091`, `0x903A`, `0x6000` | DIAG, modem |

The EDL/DIAG split matters: sending a Sahara hello to a `0x9006` composite
wedges the port.

### 2.5 Samsung PIDs (`src/usb/mod.rs`)

| Group | PIDs | Meaning |
|---|---|---|
| Download mode | `0x6601`, `0x685D`, `0x68C3`, `0x68EF`, `0x4EEE`, `0x4EEF` | Odin |
| ADB composite | `0x685E`, `0x68A3`, `0x6868` | ADB without an explicit 255/66 interface |
| Special | `0x685C` | Samsung BROM |
| MTP | `0x6860` | MTP |

`0x685D` is also used by normal-boot ADB composites, so the coarse hint says
`samsung-odin` while the Python layer re-checks the ADB signature.

---

## 3. Classification

Mode labels emitted by `mode_hint` / `classify_mode`:

| Label | Condition |
|---|---|
| `mediatek-brom` | `0x0E8D:0x0003` |
| `mediatek-preloader` | `0x0E8D:0x2000` |
| `mediatek-da` | `0x0E8D:0x0004` / `0x1004` |
| `mediatek` | other `0x0E8D`, or any MTK OEM VID |
| `qualcomm-edl` | `0x05C6` + EDL PID |
| `qualcomm-diag` | `0x05C6` + DIAG PID |
| `qualcomm` | other `0x05C6` |
| `spd` | `0x1782` |
| `apple` | `0x05AC` |
| `samsung-odin` | `0x04E8` + download PID, no ADB interface |
| `samsung-brom` | `0x04E8:0x685C` |
| `samsung-hid` | `0x04E8` + HID class 3 |
| `motorola` / `motorola-adb` / `motorola-mtp` | `0x22B8` |
| `android-adb` | ADB interface 255/66, any VID |
| `android-mtp` | MTP class 6, any VID |
| `fastboot` | `0x18D1:0x4EE0` / `0xD00D` |
| `google` | `0x18D1`, not ADB/MTP |
| `other` | everything else |

### Detection methods

1. **Bus enumeration** — `libusb` scan of every device, with descriptor walk.
2. **ADB merge** — `adb devices -l` rows are parsed and merged into the bus list
   by serial/VID/PID, so the same phone does not appear twice.
3. **Interface-based classification** — ADB (`255/66/1`), MTP (class 6), HID
   (class 3) checked before falling back to VID alone.
4. **Name keywords** — `android`, `phone`, and the Transsion/vendor names are a
   last-resort phone signal for devices with no matching VID.
5. **Hotplug / re-enumeration** — the bridge is re-invoked after a reset or
   exploit; the caller re-scans rather than holding a stale handle.

---

## 4. Gaps

| Gap | Impact | Effort |
|---|---|---|
| No port-reset retry on enumeration failure | Some devices only appear after a `usb_reset` | S |
| PID table only as good as observed pairs | Unknown PIDs fall to vendor-only labels | S (ongoing) |
| No USB descriptor quirk database | Devices with malformed descriptors can misclassify | M |
| No permission preflight in the GUI | A missing udev rule surfaces as "no device" rather than "no access" | S |
| Multi-device ambiguity | `find_mtk_dev("auto")` refuses an ambiguous bus (good) but the GUI has no picker | M |

## 5. Recommendations

1. **Fall back to a port reset and re-enumerate** when a scan finds nothing and
   a device was previously present.
2. **Surface permission errors** distinctly from "no device" — check the udev
   rule for the VID before reporting absence.
3. **Add a device picker** for the ambiguous-bus case instead of refusing.
4. **Keep collecting observed VID/PID pairs** into the table; every pair should
   carry a comment naming the device it was observed on.
5. **Add a descriptor-quirk table** only when a real device demands it — not
   speculatively.

## 6. Conclusion

Detection is comprehensive for the transports FlashPilot implements. The
remaining work is error-path polish (permissions, reset-and-retry, ambiguous
bus), not new protocol coverage.
