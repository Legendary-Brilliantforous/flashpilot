# flashing/rockchip

Holds Rockchip flashing research: brand/VIN discovery, fastboot-mode usage
per RK generation, and verification notes. **No Rust transport exists yet** —
the Android `fastboot` CLI is the flow. No `flow!` rows ship until a
transport lands.

## Generations

| Generation | Representative chips | State of support |
|---|---|---|
| RK3xxx (legacy) | RK2818, RK2918A, RK3026, RK3066, RK3288 | Research notes only — not verified |
| RK3562 | RK3562 | Fastboot/UMS mode documented, no FlashPilot flows |
| RK3528/3566/3568 | RK3528, RK3566, RK3568 | Same |
| RK3576 | RK3576 | Same |
| RK3588 | RK3588, RK3580 | Same |
| RK3399 | RK3399 | Same |

The whole RK3xxx/RK35xx family uses the same USB VID (0x2207) and the same
fastboot protocol; the differences are firmware-side (signed images, loaders) —
verified per device at research time.

## Quick start (flow = `fastboot`)

```
fastboot devices                       # shows 2207:<pid>
fastboot reboot ramdump                # force fastboot from a flashed state
fastboot flash system system.img       # per-image flashes as the board defines
fastboot getvar product
```

Flashes go through the host `fastboot` binary — FlashPilot only recognizes
the mode when classifying: `0x2207 => "rockchip"` (`src/usb/mod.rs`,
`src/usb/filtering.rs`).

## Verification checklist (research phase)

1. **Mode identification:** connect; `fastboot devices` must show
   `2207:<pid>`; note the PIDs for the bootloader build in use.
2. **Read-only:** `fastboot getvar all` — record `product`, `secure`, etc.
3. **Identity:** `adb shell getprop ro.product.device`,
   `ro.build.version.release`.
4. **Readback:** dump a partition and re-flash a byte-identical image.
5. **Loader mode:** check the device also enumerates in BootROM loader mode
   (RKTools variants — note any detection gaps).
6. **Safety** (`.opencode/skills/flashpilot-safety/`): research phase only —
   back up flashable partitions (`fastboot read`) before flashing; a wrong
   image write for a Rockchip board is the highest-risk flash in FlashPilot.
   Only flash devices the requester owns or that are authorized.

See `operations/device_research/` for the normalization notes used when
imported into `python/gui/supported_devices.json`.
