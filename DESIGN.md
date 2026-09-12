# USB Detection & Merging: Python → Rust Migration

## Problem Statement

The USB device filtering and ADB merging logic currently lives in **Python** (`python/core/devices.py`), which means:

1. **Volatile identity** — every USB re-enumeration changes bus:addr, breaking stored device keys
2. **Filtering duplication** — `is_phone()` re-checks VID/PID/interfaces each time the UI polls
3. **Merging complexity** — Python reconstructs the same USB→ADB serial map on every call
4. **FUS firmware detection issue** — The USB FUS mode (Firmware Upload Service) isn't properly classified before Python tries to merge it, leading to duplicate device rows

## Solution: Move to Rust

Move the entire USB device classification, filtering, and USB↔ADB merging pipeline into the Rust bridge as a **single deterministic operation** that outputs a merged device list in one call.

---

## Architecture

### 1. **Rust-Side Changes** (`src/usb.rs` + new `src/usb/filtering.rs`)

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

#### FUS Firmware Detection

```rust
pub fn classify_mode(vid: u16, pid: u16, interfaces: &[InterfaceInfo]) -> String {
    // Existing logic + FUS detection
    
    match vid {
        0x04e8 => {  // Samsung
            // FUS (Firmware Upload Service) PIDs
            if pid == 0x685D {  // Common FUS PID
                if !interfaces.iter().any(|i| i.class == 255 && i.subclass == 66) {
                    // Not ADB, likely FUS download mode
                    return "samsung-fus".to_string();
                }
            }
            
            if SAMSUNG_ODIN_PIDS.contains(&pid) {
                return "samsung-odin".to_string();
            }
            
            let has_adb = interfaces.iter().any(|i| i.class == 255 && i.subclass == 66);
            if has_adb {
                return "android-adb".to_string();
            }
            
            let has_mtp = interfaces.iter().any(|i| i.class == 6);
            if has_mtp {
                return "android-mtp".to_string();
            }
            
            let has_hid = interfaces.iter().any(|i| i.class == 3);
            if has_hid {
                return "samsung-hid".to_string();
            }
            
            return "samsung".to_string();
        }
        
        // ... other VIDs
        _ => { /* ... */ }
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
            // Usage: flashpilot-bridge detect-merged [--vid 0x04e8] [--adb-timeout 5000]
            // Output: JSON array of MergedDeviceInfo
            let merged = usb::detect_merged(None)?;  // Or with vid filter
            println!("{}", merged);
        }
        
        // NEW: low-level raw calls (for testing)
        "list-phones-only" => {
            // USB only, filtered
            let devices = usb::collect_devices(None)?;
            let phones = usb::filter_phones(&devices);
            println!("{}", serde_json::to_string_pretty(&phones)?);
        }
        
        _ => { /* ... */ }
    }
}
```

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

def detect_merged(timeout=30):
    """Unified USB + ADB device list.
    
    Returns [{key, label, usb, adb, transports}] for all phones,
    with USB+ADB entries merged by serial and standalone ADB entries appended.
    """
    return json.loads(_run(["detect-merged"], timeout=timeout))
```

---

## Benefits

| Aspect | Before | After |
|--------|--------|-------|
| **Filtering logic** | Python ✗ (re-runs on each poll) | Rust ✓ (native, deterministic) |
| **USB↔ADB merging** | Python ✗ (reconstructed each call) | Rust ✓ (single atomic operation) |
| **Device stability** | Volatile (bus:addr changes) | Stable (`usb:<ports>` per slot) |
| **FUS detection** | Missing | ✓ Proper classification in Rust |
| **Re-enumeration handling** | Manual, fragile Python logic | Native, robust Rust design |
| **Performance** | Multiple bridge calls + Python overhead | Single bridge call, native perf |
| **Testability** | Tests split across Python/Rust | ✓ Unit tests in Rust |
| **Code maintenance** | Duplicate logic across stacks | Single source of truth (Rust) |

---

## Migration Path (Staged)

### Phase 1: Build Rust side (this PR)
- [ ] Add `src/usb/filtering.rs` with `is_phone()`, `normalize_serial()`, `device_key()`, `classify_mode()`
- [ ] Implement `merge_devices()` + `detect_merged()` 
- [ ] Add `detect-merged` CLI command
- [ ] Add comprehensive unit tests in Rust
- [ ] **Keep Python side unchanged** (detect_all → detect-merged under the hood later)

### Phase 2: Wire Python wrapper (follow-up PR)
- [ ] Update `python/core/bridge.py` with `detect_merged()` method
- [ ] Migrate `python/core/devices.py` to use `detect_merged()`
- [ ] Run full test suite (no behavioral change)
- [ ] **Kill the old Python filtering/merging code**

### Phase 3: GUI integration (follow-up PR)
- [ ] Update `gui/` device monitor to use new keys
- [ ] Verify USB re-enumeration handling
- [ ] Test FUS firmware detection in the GUI

---

## Testing Strategy

### Rust Unit Tests (in src/usb.rs)

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
    fn test_classify_mode_fus_detection() { ... }
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
            # Check FUS mode is classified
            if device['usb']['pid'] == 0x685D:
                # Should be samsung-fus or similar
                pass
```

---

## Files to Create/Modify

### Create
- `src/usb/filtering.rs` — New filtering & merging module

### Modify
- `src/usb.rs` — Add `detect_merged()` CLI command + new types
- `src/main.rs` — Wire `detect-merged` CLI subcommand
- `python/core/bridge.py` — Add `detect_merged()` function
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
A: The `detect-merged` command can take an ADB timeout param (e.g., `--adb-timeout 2000` ms). If ADB probe is too slow, we poll ADB in a background thread.

**Q: How do I test this locally?**  
A: `cargo build --release` → `./target/release/flashpilot-bridge detect-merged | jq`

