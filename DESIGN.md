# USB Detection & Merging: Python → Rust Migration

## Problem Statement

The USB device filtering and ADB merging logic currently lives in **Python** (`python/core/devices.py`), which means:

1. **Volatile identity** — every USB re-enumeration changes bus:addr, breaking stored device keys
2. **Filtering duplication** — `is_phone()` re-checks VID/PID/interfaces each time the UI polls
3. **Merging complexity** — Python reconstructs the same USB→ADB serial map on every call
4. **Download-mode classification** — Samsung download-mode (`samsung-odin`) phones must be recognized as phones so the FUS/flash workflows can target them; mis-classification previously produced duplicate or dropped rows. (FUS itself is a *server* protocol for fetching Samsung firmware — there is no "USB FUS mode". The device-side marker for firmware work is Odin download mode.)

## Solution: Move to Rust

Move the entire USB device classification, filtering, and USB↔ADB merging pipeline into the Rust bridge as a **single deterministic operation** that outputs a merged device list in one call.

---

## Architecture

### 1. **Rust-Side Changes** (`src/usb/mod.rs` + new `src/usb/filtering.rs` + `src/devices.rs`)

> Module layout note: `src/usb.rs` became `src/usb/mod.rs` so the filtering
> engine can live at `src/usb/filtering.rs`. Filtering/classification/merging
> (the engine) lives in `usb::filtering`; the GUI-facing row schema
> (`DeviceRow`, `list_devices_filtered`) lives in `src/devices.rs`.

#### New Types

```rust
/// Device filtering criteria
pub struct FilterCriteria {
    pub require_serial: bool,        // Only phones with serial numbers
    pub min_interfaces: usize,       // Min # of interfaces (e.g., 0 for EDL)
    pub vendor_ids: Option<Vec<u16>>, // Whitelist VIDs (None = all)
}

/// Merged device entry (USB + ADB + metadata)
#[derive(Serialize, Clone, Debug)]
pub struct MergedDeviceInfo {
    pub key: String,              // Stable: adb:<serial> or usb:<ports> or usb:vid:pid@bus:addr
    pub label: String,            // Short display label
    pub usb: Option<DeviceInfo>,  // USB info (if on USB)
    pub adb: Option<AdbDevice>,   // ADB info (if reachable via ADB)
    pub transports: Vec<String>,  // ["ADB", "Download mode", "MTK", ...]
}

#[derive(Serialize, Clone, Debug)]
pub struct AdbDevice {
    pub serial: String,
    pub state: String,  // "device", "offline", "unauthorized", ...
    pub extra: String,
}
```

#### Key Functions

```rust
// In src/usb.rs:

/// Filter USB devices by phone criteria (reject hubs, HID keyboards, etc.)
pub fn filter_phones(devices: &[DeviceInfo]) -> Vec<DeviceInfo> { ... }

/// Detect & classify device mode (samsung-odin, edl, mediatek, etc.)
pub fn classify_mode(vid: u16, pid: u16, interfaces: &[InterfaceInfo]) -> String { ... }

/// Generate a stable device key (adb:<serial> or usb:<ports> or usb:vid:pid@bus:addr)
pub fn device_key(usb: Option<&DeviceInfo>, adb: Option<&AdbDevice>) -> String { ... }

/// Merge USB list + ADB list into unified rows, handling duplicates & serial matching
pub fn merge_devices(
    usb_devices: &[DeviceInfo],
    adb_devices: &[AdbDevice],
) -> Vec<MergedDeviceInfo> { ... }

/// Full pipeline: detect USB + fetch ADB + filter + merge in one call
pub fn detect_merged(vid_filter: Option<u16>) -> Result<String> { ... }  // JSON output
```

#### Filtering Logic

**`is_phone()` — moved to Rust**

```rust
const KNOWN_PHONE_VIDS: &[u16] = &[0x04E8, 0x05C6, 0x0E8D, 0x1782, 0x18D1, 0x05AC];
const ANDROID_GENERIC_VIDS: &[u16] = &[0x18D1, 0x0BB4, 0x2717, 0x2A70, 0x12D1, 0x22D9, 0x2AE5];
const PHONE_NAME_KEYWORDS: &[&str] = &[
    "android", "phone", "tecno", "infinix", "itel", "xiaomi", "redmi",
    "oppo", "vivo", "oneplus", "realme", "pixel", "nexus", "motorola",
    "lenovo", "huawei", "honor", "asus", "transsion", "spark", "smartphone",
];

pub fn is_phone(d: &DeviceInfo) -> bool {
    // Check known VIDs
    if KNOWN_PHONE_VIDS.contains(&d.vid) { return true; }
    
    // Check for ADB interface (255/66/*)
    if d.interfaces.iter().any(|i| i.class == 255 && i.subclass == 66) { return true; }
    
    // Check for MTP (class 6)
    if d.interfaces.iter().any(|i| i.class == 6) { return true; }
    
    // Check generic Android VIDs
    if ANDROID_GENERIC_VIDS.contains(&d.vid) { return true; }
    
    // Check product/manufacturer keywords
    let prod_lower = d.product.as_ref().map(|s| s.to_lowercase()).unwrap_or_default();
    let mfr_lower = d.manufacturer.as_ref().map(|s| s.to_lowercase()).unwrap_or_default();
    for keyword in PHONE_NAME_KEYWORDS {
        if prod_lower.contains(keyword) || mfr_lower.contains(keyword) {
            return true;
        }
    }
    
    false
}
```

#### Serial Normalization

```rust
pub fn normalize_serial(s: Option<&str>) -> String {
    let s = (s.unwrap_or("")).trim();
    if s.is_empty() || matches!(s.to_lowercase().as_str(), "null" | "none" | "unknown" | "?") {
        return String::new();
    }
    s.to_string()
}
```

#### Device Key Generation

```rust
pub fn device_key(usb: Option<&DeviceInfo>, adb: Option<&AdbDevice>) -> String {
    // Prefer serial (ADB > USB)
    if let Some(adb) = adb {
        if !adb.serial.is_empty() {
            return format!("adb:{}", adb.serial);
        }
    }
    if let Some(usb) = usb {
        if let Some(serial) = &usb.serial {
            if !serial.is_empty() {
                return format!("adb:{}", serial);
            }
        }
        
        // Fallback to port numbers (stable across re-enum)
        if !usb.port_numbers.is_empty() {
            return format!("usb:{}", usb.port_numbers);
        }
        
        // Last resort: volatile VID:PID@BUS:ADDR
        return format!("usb:{:04x}:{:04x}@{}:{}", usb.vid, usb.pid, usb.bus, usb.address);
    }
    
    // Standalone ADB (no USB present)
    if let Some(adb) = adb {
        return format!("adb:{}", adb.serial);
    }
    
    String::new()
}
```

#### Merging Logic

```rust
pub fn merge_devices(
    usb_list: &[DeviceInfo],
    adb_list: &[AdbDevice],
) -> Vec<MergedDeviceInfo> {
    let mut rows = Vec::new();
    let mut claimed_adb = std::collections::HashSet::new();
    
    // First pass: USB devices, merged with matching ADB entries
    for usb in usb_list {
        if !is_phone(usb) {
            continue;  // Skip hubs, keyboards, etc.
        }
        
        let usb_serial = normalize_serial(usb.serial.as_deref());
        let adb_match = if !usb_serial.is_empty() {
            adb_list.iter().find(|a| normalize_serial(Some(&a.serial)) == usb_serial)
        } else {
            None
        };
        
        if let Some(adb) = adb_match {
            claimed_adb.insert(adb.serial.clone());
        }
        
        let key = device_key(Some(usb), adb_match);
        let transports = compute_transports(usb, adb_list);
        let label = compute_label(Some(usb), adb_match);
        
        rows.push(MergedDeviceInfo {
            key,
            label,
            usb: Some(usb.clone()),
            adb: adb_match.cloned(),
            transports,
        });
    }
    
    // Second pass: Standalone ADB entries (TCP, emulator, etc.)
    for adb in adb_list {
        if claimed_adb.contains(&adb.serial) {
            continue;  // Already merged above
        }
        
        let key = format!("adb:{}", adb.serial);
        
        rows.push(MergedDeviceInfo {
            key,
            label: format!("{} [{}]", adb.serial, adb.state),
            usb: None,
            adb: Some(adb.clone()),
            transports: vec!["ADB".to_string()],
        });
    }
    
    rows
}
```

#### Download-Mode Classification (Python-compatible mode strings)

> Terminology: there is no "USB FUS mode" — FUS is the Samsung *server*
> protocol (Firmware Upload Service), and it is consumed host-side by the
> FUS tab. The device-side marker for firmware work is Odin **download
> mode**: `0x685D` IS an Odin PID. Classifying it as a distinct
> `samsung-fus` mode would mislabel every download-mode phone with a string
> no GUI code understands, so `classify_mode()` emits
> Python-compatible strings (`samsung-odin`, `mediatek-brom`, ...) and the
> FUS tab consumes `samsung-odin` rows.

```rust
pub fn classify_mode(vid: u16, pid: u16, interfaces: &[InterfaceInfo]) -> String {
    let has_adb_iface = interfaces.iter().any(|i| i.class == 255 && i.subclass == 66);

    match vid {
        0x04E8 => {  // Samsung
            if SAMSUNG_ODIN_PIDS.contains(&pid) && !has_adb_iface {
                return "samsung-odin".to_string();  // 0x685D lands here
            }
            if pid == 0x685C {
                return "samsung-brom".to_string();
            }
            if pid == 0x6860 {
                return "android-mtp".to_string();
            }
            if has_adb_iface {
                return "android-adb".to_string();
            }
            if interfaces.iter().any(|i| i.class == 3) {
                return "samsung-hid".to_string();
            }
            "samsung".to_string()
        }
        0x0E8D => match pid {
            // MTK stage comes from PIDs, NOT mode strings: mode_hint()
            // returns "mediatek" for every 0x0e8d PID (verified in
            // usb/mod.rs tests), so string-keyed transport detection
            // never fires. PIDs: 0x0003=brom, 0x2000=preloader,
            // 0x0004/0x1004=DA (matches Python's pid_stage).
            0x0003 => "mediatek-brom".to_string(),
            0x2000 => "mediatek-preloader".to_string(),
            0x0004 | 0x1004 => "mediatek-da".to_string(),
            _ => "mediatek".to_string(),
        },
        0x05C6 if pid == 0x9008 => "qualcomm-edl".to_string(),
        0x18D1 => "fastboot".to_string(),
        0x1782 => "spd".to_string(),
        0x05AC => "apple".to_string(),
        _ if has_adb_iface => "android-adb".to_string(),
        _ if interfaces.iter().any(|i| i.class == 6) => "android-mtp".to_string(),
        _ => "other".to_string(),
    }
}
```

---

### 2. **Bridge CLI Commands**

Implement new CLI subcommand:

```rust
// In main.rs / bridge CLI handler:

pub async fn main_bridge() {
    match args[1] {
        // Existing: "detect", "detect-all", "mtk-detect", etc.
        
        // NEW: merged device detection (filters + merges in one call)
        "detect-merged" => {
            // Usage: flashpilot-bridge detect-merged [--vid 0x04e8]
            // Output: JSON array of DeviceRow (GUI schema, src/devices.rs):
            //   {key, label, transports, vid, pid, bus, address, serial,
            //    is_adb, adb_state}
            let merged = devices::list_devices_filtered_vid(vid_filter)?;  // Or None
            println!("{}", merged);
        }
        
        _ => { /* ... */ }
    }
}
```

> ADB merge note: the Rust bridge speaks ADB natively
> (`adb::devices_json()` returns `"SERIAL\tstate extras"` lines in the same
> contract as `adb devices -l`); `devices.rs` parses those lines into
> `AdbDevice`s before merging. No external `adb` binary is needed.
>
> Monitor cadence note: `detect-merged` is heavier than `detect-all`
> (the native ADB probe costs up to ~6s per ADB-mode device), so the GUI
> monitor must call it on change-detection (keyed off last-seen device
> keys), not on every 3s poll. USB-only refreshes can stay cheap.

---

### 3. **Python-Side Changes** (`python/core/devices.py` → thin wrapper)

**OLD:** 300+ lines of filtering, keying, merging logic  
**NEW:** 50 lines calling the Rust bridge

```python
def list_devices():
    """Unified device list across USB + ADB.
    
    NOW calls the Rust bridge's detect-merged command, which does all
    the work atomically and deterministically.
    """
    from . import bridge as _bridge
    
    try:
        # Single atomic call to Rust
        merged = _bridge.detect_merged()  # Returns JSON string
    except _bridge.BridgeError:
        return []
    
    if not isinstance(merged, list):
        return []
    
    return merged  # Already in the right shape


# Delete these helper functions entirely:
# - is_phone(d)                 → moved to Rust
# - device_key(d)               → moved to Rust
# - _norm_serial(s)             → moved to Rust
# - _usb_transports(d, adb)     → moved to Rust
# - _usb_label(d, state_map)    → moved to Rust
# Keep only:
# - device_scope context manager (thread-local device selection)
# - current_key() and resolve_usb_target() for legacy compat
```

**New bridge method:**

```python
# In python/core/bridge.py:

def list_merged(vid_filter=None, timeout=30):
    """Unified, phone-filtered USB + ADB device rows (Rust core).

    Returns a list of dicts, each: {key, label, transports, vid, pid, bus,
    address, serial, is_adb, adb_state}. Phones and ADB entries are merged by
    serial; classes/modes are classified by the Rust bridge.
    """
    args = ["detect-merged"]
    if vid_filter is not None:
        args.append(f"--vid={vid_filter:04x}")
    return json.loads(_run(args, timeout=timeout))
```

---

## Benefits

| Aspect | Before | After |
|--------|--------|-------|
| **Filtering logic** | Python ✗ (re-runs on each poll) | Rust ✓ (native, deterministic) |
| **USB↔ADB merging** | Python ✗ (reconstructed each call) | Rust ✓ (single atomic operation) |
| **Device stability** | Volatile (bus:addr changes) | Stable (`usb:<ports>` per slot) |
| **FUS targeting** | Missing | ✓ `samsung-odin` rows drive the FUS/flash workflows |
| **Re-enumeration handling** | Manual, fragile Python logic | Native, robust Rust design |
| **Performance** | Multiple bridge calls + Python overhead | Single bridge call, native perf |
| **Testability** | Tests split across Python/Rust | ✓ Unit tests in Rust |
| **Code maintenance** | Duplicate logic across stacks | Single source of truth (Rust) |

---

## Migration Path (Staged)

### Phase 1: Build Rust side (this PR)
- [x] Add `src/usb/filtering.rs` with `is_phone()`, `normalize_serial()`, `device_key()`, `classify_mode()`
- [x] Implement `merge_devices()` + `detect_merged()`
- [x] Add `detect-merged` CLI command
- [x] Add comprehensive unit tests in Rust
- [x] **Keep Python side unchanged** (detect_all → detect-merged under the hood later)

### Phase 2: Wire Python wrapper (follow-up PR)
- [x] Update `python/core/bridge.py` with `list_merged()` method
- [x] Migrate `python/core/devices.py` to use `list_merged()` (legacy path kept as rollback)
- [x] Run full test suite (no behavioral change)
- [ ] Old Python filtering/merging code stays until Phase 3 (rollback path)

### Phase 3: GUI integration (follow-up PR)
- [ ] Update `gui/` device monitor to use new keys (on change-detection, not every poll)
- [ ] Verify USB re-enumeration handling
- [ ] Test download-mode (`samsung-odin`) targeting in the FUS/flash GUI
- [ ] **Kill the old Python filtering/merging code** once merged-output parity is proven on test devices

---

## Testing Strategy

### Rust Unit Tests (in src/usb/filtering.rs)

```rust
#[cfg(test)]
mod tests {
    #[test]
    fn test_is_phone_samsung() { ... }
    
    #[test]
    fn test_is_phone_rejects_hub() { ... }
    
    #[test]
    fn test_device_key_prefers_serial() { ... }
    
    #[test]
    fn test_device_key_fallback_to_ports() { ... }
    
    #[test]
    fn test_merge_usb_adb_by_serial() { ... }
    
    #[test]
    fn test_classify_mode_samsung_odin() { ... }
}
```

### Python Integration Tests (tests/test_devices.py)

Update existing test stubs to verify the new merged output:

```python
def test_detect_merged_merges_usb_adb():
    merged = bridge.detect_merged()
    assert isinstance(merged, list)
    # Check Samsung + ADB serial match
    keys = {r['key'] for r in merged}
    assert any(k.startswith('adb:') for k in keys)
    
def test_fus_mode_classification():
    merged = bridge.detect_merged()
    for device in merged:
        if device['usb'] and device['usb']['vid'] == 0x04e8:
            transports = device['transports']
            # 0x685D is an Odin download-mode PID: should be "Download mode"
            # (samsung-odin), NOT a separate samsung-fus mode
            if device['usb']['pid'] == 0x685D:
                assert "Download mode" in transports or "MTP" in transports
```

---

## Files to Create/Modify

### Create
- `src/usb/filtering.rs` — New filtering & merging module

### Modify
- `src/usb.rs` → renamed `src/usb/mod.rs` — declares `pub mod filtering;` (pure rename, all `crate::usb::` paths unchanged)
- `src/main.rs` — Wire `detect-merged` CLI subcommand (→ `devices::list_devices_filtered_vid`)
- `python/core/bridge.py` — Add `list_merged()` wrapper over `detect-merged`
- `python/core/devices.py` — Rewrite `list_devices()` to call Rust (Phase 2)
- `tests/test_devices.py` — Add test cases for merged output

### (Later phases)
- `gui/` — Update device monitor for new key format

---

## Rollback Plan

If issues arise:
1. Keep `detect`, `detect-all` endpoints functional
2. Python can fall back to old logic if `detect-merged` fails
3. Feature-flag the new code during Phase 1 (Rust-side only)

---

## FAQ

**Q: Why not keep merging in Python?**  
A: Because Python re-runs the logic on every poll. The Rust side is deterministic and can cache results.

**Q: Will this break existing device keys?**  
A: Only if users switch midway. After Phase 2 stabilizes, the new key format is the canonical one.

**Q: What about ADB detection latency?**  
A: The Rust bridge speaks ADB natively (no external `adb` binary); the ADB probe costs up to ~6s per ADB-mode device, so the GUI monitor should call `detect-merged` on change-detection rather than on every poll.

**Q: How do I test this locally?**  
A: `cargo build --release` → `./target/release/flashpilot-bridge detect-merged | jq`

