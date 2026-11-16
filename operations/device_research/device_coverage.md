# Device catalogue research — coverage vs FlashPilot's device database

This directory holds FlashPilot's own device/protocol research corpus: a
normalized 1,396-row device catalogue, per-engine gap registers, and the MTK
chip/payload matrix. Everything here comes from parsing the catalogue and
FlashPilot's shipped database (`python/gui/supported_devices.json`). Nothing
was measured on hardware.

Companion file: [`device_catalogue.json`](./device_catalogue.json) — 1,396
normalized `{brand, model, engine, connection, storage}` rows. It carries no
per-row provenance: the catalogue **is** the research input, and the shipped
product database (`python/gui/supported_devices.json`) is the FlashPilot-branded
output.

## TL;DR

| Metric | Value |
|---|---|
| Catalogue rows | **1,396** |
| Distinct brands | **35** |
| Engine split | MTK 739 (53%), QCOM 280 (20%), SPD/UNISOC 94 (7%), Odin 71 (5%), unknown 212 (15%) |
| FlashPilot device database | **719 models / 21 brand buckets** (650 researched, 69 planned) |
| Catalogue rows represented in the database | **745 (53%)** |
| Catalogue rows not yet imported | **651 (47%)** |
| MTK scatter layouts analysed | 28 real scatters → 33 storage layouts, 7 SoCs, 166 distinct partition names |

The catalogue is a 2016–2022 mass-market device map (Samsung A-series up to
A71, Redmi Note up to 11, Tecno Spark up to 8, Oppo A up to A96). FlashPilot's
database is 719 entries biased toward 2023–2025 hardware. They are not
supersets of each other: roughly half the catalogue has been folded into the
database, and the residual gap is concentrated in pre-2020 Samsung, legacy
MediaTek budget parts, Kirin-era Huawei, and 12 brands with no bucket at all.

## 1. How the catalogue was assembled

The raw corpus arrived as 27 export files (16 brand JSON files plus 11 plain
text model lists). It was normalized to one row per device with five fields:

| Field | Source |
|---|---|
| `brand` | Device-name prefix, not the file name (one export was a 21-brand catch-all) |
| `model` | Marketing name, with model codes kept inline where the export had them |
| `engine` | Transport flags first (`Edl` → qcom, `spd` → spd, `Odin` → odin, `Brom`/`auth`/`Preloader` → mtk), platform family as fallback |
| `connection` | Verbatim transport hints, `; `-joined when a row carried several |
| `storage` | Verbatim note field — **not** reliable as a storage type (see §3) |

Export-side totals:

| Metric | Value |
|---|---|
| JSON export files | 16 |
| Raw objects | 1,280 |
| Header/placeholder rows (`Devices : Auto`, etc.) | 13 |
| Actual device rows | 1,267 |
| Unique `(brand, model)` pairs | **1,184** (6.3% duplication) |
| `.txt` model lists | 11 files, 303 rows |
| `.txt` rows not present in the JSON | **216** raw → **212** after in-list dedupe |
| **Catalogue total** | **1,396** (1,184 + 212) |

Duplicate rate is low; the pairs that repeat are Meizu (present in two exports)
and Asus (present in two exports). A stricter full-tuple dedupe yields 1,210
instead of 1,184; the catalogue uses the `(brand, model)` basis so that rows
with different transport flags are not silently merged.

### Composition notes that affect any import

- **One export was a catch-all, not a brand file.** 262 of its rows are the only
  source for iTel, Alcatel, TCL, Lava, BLU, HTC, Motorola, Allview, Coolpad,
  Micromax, Wiko, Ulefone, Yezz, Blackview, ZTE, Amazon, Archos, T-Mobile,
  OnePlus and Symphony. Brand must be derived from the device-name prefix.
- **19 Huawei rows are SoC records, not phones** (`HiSilicon kirin 620` …
  `kirin 970 v3`). They carry real platform/FRP information, so they stay in the
  catalogue, but they must not be counted as device coverage.
- **Realme is split along SoC lines, not brand lines.** The Oppo export holds
  more Realme rows (62) than the Realme export (43), and the Realme export is
  MediaTek-only. One row is mis-cased (`Realme7i`) and needs prefix
  normalization before it can be classified.
- **Five JSON files begin with a UTF-8 BOM and one contains a raw control
  character.** A naive `json.load` silently drops them; parse with
  `utf-8-sig` / `strict=False` or the corpus looks 30% smaller than it is.

## 2. Schema quirks of the raw exports

Keys are inconsistent between files. Union across all 1,267 device rows:

| Key | Rows | Meaning |
|---|---:|---|
| `Devices` | 1264 | product name (with brand prefix) |
| `Models` | 1264 | model code(s) — sometimes a codename (`dandelion`), sometimes a comma list |
| `Platform` | 1264 | SoC string, free-form (`MT6765`, `Helio G85`, `Snapdragon 662`, `kirin 970`) |
| `Conn` | 888 | `auth` (554), blank (258), `enable adb` (55), `usb 1.0` (19), `SAVE`, `Harmony` |
| `Brom` | 844 | `Brom` (730), blank (103), `Preloader` (11) |
| `Edl` | 220 | Qualcomm EDL available |
| `Beta` | 182 | `Beta` (49), `Sideload` (49), `FS` (37), `TP` (29), `[SIDELOAD]` (18) |
| `spd` | 94 | Spreadtrum/UNISOC |
| `Storage` | 82 | `UFS` (30), `FRP` (17), `TP` (16), `Test` (10), `eMMC 5.1` (3), junk values |
| `Odin` | 56 | Samsung Odin |
| `""` (empty key) | 67 | malformed trailing comma in the export |

`Storage` is **not** a storage field in practice — `FRP`, `TP`, `Test`,
`factory` and `MIUI 12` all appear in it. Treat it as free text. The real
transport hints are `Conn`/`Brom`/`Edl`/`spd`/`Odin`, and those are what the
`engine` column is derived from in the catalogue.

## 3. Per-brand coverage

`Catalogue` = rows in `device_catalogue.json` for that brand. Engine columns are
rows carrying that transport. `In DB` = catalogue rows that resolve to a model in
`python/gui/supported_devices.json` (§6). `Gap` = rows not yet represented.

| Brand | Catalogue rows | MTK | QCOM | SPD | Odin | Unknown | In DB | Gap |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Xiaomi | 210 | 44 | 111 | 0 | 0 | 55 | 132 | 78 |
| Oppo | 157 | 81 | 66 | 0 | 0 | 10 | 93 | 64 |
| Huawei | 135 | 47 | 13 | 0 | 19 | 56 | 30 | 105 |
| Samsung | 131 | 26 | 36 | 5 | 52 | 12 | 88 | 43 |
| Vivo | 116 | 55 | 39 | 0 | 0 | 22 | 69 | 47 |
| itel | 107 | 0 | 0 | 65 | 0 | 42 | 29 | 78 |
| Tecno | 85 | 79 | 0 | 6 | 0 | 0 | 63 | 22 |
| Realme | 71 | 49 | 9 | 9 | 0 | 4 | 67 | 4 |
| Infinix | 56 | 52 | 0 | 4 | 0 | 0 | 47 | 9 |
| LG | 38 | 35 | 0 | 0 | 0 | 3 | 0 | 38 |
| Honor | 35 | 29 | 6 | 0 | 0 | 0 | 28 | 7 |
| Lenovo | 33 | 31 | 0 | 0 | 0 | 2 | 17 | 16 |
| Alcatel | 31 | 31 | 0 | 0 | 0 | 0 | 0 | 31 |
| Meizu | 20 | 20 | 0 | 0 | 0 | 0 | 4 | 16 |
| TCL | 17 | 17 | 0 | 0 | 0 | 0 | 10 | 7 |
| Lava | 16 | 14 | 0 | 2 | 0 | 0 | 15 | 1 |
| Nokia | 16 | 12 | 0 | 2 | 0 | 2 | 10 | 6 |
| BLU | 13 | 13 | 0 | 0 | 0 | 0 | 10 | 3 |
| HTC | 13 | 13 | 0 | 0 | 0 | 0 | 0 | 13 |
| Motorola | 11 | 11 | 0 | 0 | 0 | 0 | 10 | 1 |
| Allview | 10 | 10 | 0 | 0 | 0 | 0 | 0 | 10 |
| Coolpad | 9 | 9 | 0 | 0 | 0 | 0 | 0 | 9 |
| Micromax | 9 | 9 | 0 | 0 | 0 | 0 | 0 | 9 |
| Vsmart | 9 | 5 | 0 | 0 | 0 | 4 | 0 | 9 |
| Wiko | 8 | 8 | 0 | 0 | 0 | 0 | 7 | 1 |
| Ulefone | 7 | 7 | 0 | 0 | 0 | 0 | 7 | 0 |
| Yezz | 6 | 6 | 0 | 0 | 0 | 0 | 0 | 6 |
| Asus | 5 | 5 | 0 | 0 | 0 | 0 | 0 | 5 |
| Blackview | 5 | 5 | 0 | 0 | 0 | 0 | 1 | 4 |
| ZTE | 5 | 5 | 0 | 0 | 0 | 0 | 4 | 1 |
| Amazon | 4 | 4 | 0 | 0 | 0 | 0 | 0 | 4 |
| Archos | 3 | 3 | 0 | 0 | 0 | 0 | 0 | 3 |
| OnePlus | 2 | 2 | 0 | 0 | 0 | 0 | 2 | 0 |
| T-Mobile | 2 | 2 | 0 | 0 | 0 | 0 | 2 | 0 |
| Symphony | 1 | 0 | 0 | 1 | 0 | 0 | 0 | 1 |
| **Total** | **1,396** | **739** | **280** | **94** | **71** | **212** | **745** | **651** |

Note that `In DB` counts *catalogue rows*, so a single database entry can absorb
several SKU rows (e.g. one `itel A14` entry covers `A14`, `A14 Max` and
`A14 Plus`).

Twelve brands have **no FlashPilot bucket at all** (148 rows): LG 38, Alcatel 31,
HTC 13, Allview 10, Coolpad 9, Micromax 9, Vsmart 9, Yezz 6, Asus 5, Amazon 4,
Archos 3, Symphony 1. LG is deliberately excluded — the brand exited the phone
business — and the rest are cheap additions because they are almost all
single-transport MediaTek rows. A further 18 rows are partial gaps in brands that
*do* have a bucket (Meizu 16, Blackview 4, BLU 3, …).

## 4. MediaTek scatter research

28 real MediaTek scatter layouts were analysed (plus six Qualcomm FlashTool XML
wrappers that are discussed in §4.3). Five scatters contain **two storage layouts
each** (eMMC + UFS blocks in one file), giving **33 layouts** total.

The header `storage:` line of a scatter is unreliable: one layout declares
`storage: UFS` in its header while 23 of its 24 partitions are
`HW_STORAGE_EMMC`. Only the per-partition `storage:` key can be trusted.

| File | Platform | Project | Storage | Partitions |
|---|---|---|---|---:|
| `01c.txt` | MT6739 | — | EMMC | 49 |
| `02.txt` | MT6739 | — | EMMC | 51 |
| `03s.txt` | MT6765 | `AndroidBate` | EMMC | 52 |
| `10s.txt` | MT6765 | `s96116ca1` | EMMC | 42 |
| `12.txt` | MT6765 | `k65v1_64_bsp_titan_rat` | EMMC | 52 |
| `22.txt` | MT6768 | — | EMMC | 51 |
| `Android_scatter.txt` | MT6580 | `mtk_android` | UFS (header) / EMMC (23 of 24 parts) | 24 |
| `MT6735_Android_scatter.txt` | MT6735 | — | EMMC + UFS | 1 + 1 |
| `_Android_scatter.txt` | *(blank)* | — | EMMC + UFS | 1 + 1 |
| `ambio.txt` | MT6765 | `k65v1_64_bsp` | EMMC | 58 |
| `aqibong.txt` | MT6765 | `k65v1_64_bsp` | EMMC | 58 |
| `biji.txt` | MT6768 | `lancelot` | EMMC | 50 |
| `brow.txt` | MT6765 | `cereus` | EMMC | 44 |
| `crew.txt` | MT6765 | `2022.08.17.2` | EMMC | 57 |
| `dualima.txt` | MT6877 | `k6877v1_64_k419` | EMMC + UFS | 65 + 65 |
| `due.txt` | MT6765 | `oppo6765_18511` | EMMC | 43 |
| `empat.txt` | MT6765 | `oppo6765_19451` | EMMC | 45 |
| `engkah.txt` | MT6765 | `oppo6765` | EMMC | 50 |
| `kak.txt` | MT6785 | `rosemary` | EMMC + UFS | 65 + 65 |
| `kanjut.txt` | MT6765 | `dandelion` | EMMC | 46 |
| `lime.txt` | MT6765 | `oppo6765` | EMMC | 50 |
| `mayan.txt` | MT6785 | `begonia` | EMMC + UFS | 50 + 50 |
| `pipit.txt` | MT6765 | `oppo6765_19581` | EMMC | 45 |
| `raqib.txt` | MT6765 | `angelica` | EMMC | 46 |
| `sca.txt` | MT6768 | `k69v1_64_k419` | EMMC | 54 |
| `seke.txt` | MT6765 | `oppo6765` | EMMC | 51 |
| `toket.txt` | MT6768 | `merlin` | EMMC | 50 |
| `tri.txt` | MT6765 | `oppo6762_18540` | EMMC | 45 |

### 4.1 SoC coverage

| SoC | Files | Partition counts |
|---|---:|---|
| MT6765 (Helio P35/G35) | 16 | 42–58 |
| MT6768 (Helio P65/G85) | 4 | 50–54 |
| MT6739 | 2 | 49–51 |
| MT6785 (Helio G95) | 2 | 50/65 (×2 storages) |
| MT6580 | 1 | 24 |
| MT6735 | 1 | 1 (stub) |
| MT6877 (Dimensity 900) | 1 | 65 (×2 storages) |
| *(blank)* | 1 | 1 (stub) |

**Only seven SoCs**, and the distribution is extremely lopsided: 16 of 28 scatters
are MT6765. This is a Helio P35/G35/G85 corpus, not a Dimensity one.

### 4.2 Stub scatters

`_Android_scatter.txt` and `MT6735_Android_scatter.txt` are **stubs** — a single
`preloader` entry with a hardcoded absolute Windows path that does not exist in
this project. They are templates, not device layouts, and must not be counted as
coverage.

### 4.3 Partition layout signal

33 layouts, **166 distinct partition names**. The invariant core (present in
≥85% of layouts) is only 10 names:

```
preloader  pgpt  para  expdb  metadata  protect1  protect2  seccfg  proinfo  userdata
```

Everything else is OEM/SoC-specific. Notable groups:

| Group | Partitions | Where seen |
|---|---|---|
| Retrofit dynamic | `super` (20/33), `vbmeta` (22/33), `vbmeta_system` (13/33), `vendor_boot` (4/33), `dtbo` (21/33) | Android 10+ layouts |
| A/B slots | `boot_a`/`boot_b` (5/33), `vbmeta_a`/`vbmeta_b`, `lk_a`/`lk_b`, `tee_a`/`tee_b` | `kak.txt` (17 `_a` pairs), `ambio`/`aqibong`/`crew` (14 each), `dualima` |
| Oppo/Realme reserves | `opporeserve1/2/3` (7 files), `oplusreserve1/2/3` (3 files), `oppo_custom`, `oplus_custom` | `due/empat/engkah/lime/pipit/seke/tri` (oppo), `ambio/aqibong/crew` (oplus) |
| Samsung-derived | `md_udc` (18/33), `gsort` (8), `ffu` (6), `cust` (9), `countrycode` (2), `blk1` (2), `rescue` (2) | MT6785/MT6877 layouts |
| MTK NV/security | `nvram`, `nvdata`, `nvcfg`, `protect1/2`, `seccfg`, `proinfo`, `otp`, `efuse`, `sec1` | ubiquitous |
| FRP target | `frp` (27/33) | ubiquitous |

Practical consequence for FlashPilot: **a generic MTK partition map cannot be
assumed.** `frp` is present in 27/33 layouts, but the surrounding layout differs
enough (`opporeserve*` vs `oplusreserve*` vs Samsung `md_udc`/`gsort`) that the
MTK flow must keep resolving partitions by name at runtime rather than by index.

### 4.4 Qualcomm side

Six `rawprogram*.txt` files are **not** Qualcomm rawprogram XML despite the
name — they are MediaTek FlashTool `<flashtool-config version="2.0">` wrappers
that point back at the scatters above:

| File | Chip | Storage | Scatter referenced |
|---|---|---|---|
| `rawprogram1.txt` | MT6739 | EMMC | `01c.txt` |
| `rawprogram2.txt` | MT6739 | EMMC | `02.txt` |
| `rawprogram3.txt` | MT6765 | EMMC | `03s.txt` |
| `rawprogram4.txt` | — | — | corrupt 1,332-byte blob (not XML) |
| `rawprogram5.txt` | MT6765 | EMMC | `12.txt` |
| `rawprogram6.txt` | MT6768 | EMMC | `22.txt` |

The catalogue's 280 Qualcomm rows are therefore **not** backed by any
rawprogram/patch XML in this corpus; they rely on user-supplied Firehose
programmers.

## 5. The plain-text model lists

11 text lists, 303 rows, **216 rows that appear in no JSON export** (212 after
removing 4 in-list duplicates). They are not duplicates — they are a separate,
older list (mostly 2016–2020 Huawei/Honor, Xiaomi/Redmi and iTel).

| List | Rows | Brand | Notes |
|---|---:|---|---|
| `H.txt` | 59 | Huawei / Honor | Model codes only (`lld-al10`, `BKL-AL20`, `ANE-LX1`), some tablets (`Mediapad`, `Meta 7/8/9/10/20` — "Mate" misspelled) |
| `X.txt` | 64 | Xiaomi / Redmi / POCO | Mixes marketing name + codename (`Redmi NOTE 7 (violet)`, `POCO X3 Pro (vayu)`) |
| `itel.txt` | 60 | iTel | Clean marketing names, `Select Model...` placeholder on line 1 |
| `V.txt` | 38 | Vivo / iQOO | Marketing names + `PD####` codes; one `Vivo NEX` duplicated with trailing space |
| `S.txt` | 28 | Samsung | `Samsung A03 SM-A035F SPD` — the only place a transport is spelled out in a text list |
| `Oppo.txt` | 27 | Oppo **+ Realme** | Mixed: `OPPO A76 (CPH2375)` … `REALME 9 (RMX3521)` |
| `O.txt` | 14 | Oppo | Overlaps `Oppo.txt`; also carries 2 Realme rows (one misspelled `Relme Q3 Pro 5G`) |
| `VS.txt` | 4 | Vsmart | `V140A`, `V430A`, `V620A`, `V640A` |
| `L.txt` | 5 | LG | `Q51`, `Stylo 6`, `K51`, `V50 ThinQ`, `V60 ThinQ` |
| `N.txt` | 2 | Nokia | `3.2`, `3.4 TA-1288/TA-1283` |
| `I.txt` | 3 | iTel | `S42`, `A22`, `A22 Pro` |

Cross-check: only **39 of 303** rows share a model code with the JSON exports.
The text lists are complementary, not redundant, and are included in
`device_catalogue.json` with `engine: "unknown"` where no platform is given.

## 6. FlashPilot's device database

`python/gui/supported_devices.json` — 21 brand buckets, **719 models** (650
`researched`, 69 `planned`):

| Bucket | Models | Engines |
|---|---:|---|
| xiaomi | 112 | mtk 90, qcom 22 |
| oppo | 80 | mtk 48, qcom 32 |
| samsung | 71 | qcom 31, mtk 30, odin 6, spd 4 |
| vivo | 70 | mtk 49, qcom 21 |
| realme | 68 | mtk 49, spd 10, qcom 9 |
| tecno | 66 | mtk 59, spd 7 |
| infinix | 47 | mtk 42, spd 5 |
| huawei | 40 | mtk 33, qcom 7 |
| tcl_zte | 34 | mtk 32, spd 2 |
| itel | 24 | spd 24 |
| motorola | 17 | mtk 12, qcom 3, motorola 1, spd 1 |
| nokia | 15 | mtk 9, spd 4, qcom 2 |
| lava | 15 | mtk 13, spd 2 |
| lenovo | 13 | mtk 13 |
| blu | 10 | mtk 10 |
| others | 10 | mtk 10 (Blackview, T-Mobile, Ulefone) |
| oneplus | 7 | qcom 5, mtk 2 |
| wiko | 7 | mtk 7 |
| apple | 6 | apple 6 |
| meizu | 4 | mtk 4 |
| asus_sharp | 3 | qcom 3 |

Engine split of the database: **mtk 512, qcom 135, spd 59, odin 6, apple 6,
motorola 1**.

## 7. Coverage comparison

### 7.1 Matching method and its limits

Matching was deliberately conservative, in this order:

1. **Model code** — normalize `SM-A155F`, `CPH2219`, `RMX3081`, `TA-1277`,
   `LM-K520`, `PD1901` (strip punctuation/case) and require an exact
   intersection. Strongest signal.
2. **Exact product name** — brand prefix, model code and noise words
   (`dual`, `sim`, `5G`, `Pro`) removed, then exact match on the remainder.
3. **Token-prefix** — one name is a complete token-prefix of the other, with no
   unmatched *number* between them (so `A14` ≠ `A14 Plus` is rejected, but
   `Y5p` = `Y5P (DRA-LXX)` is accepted).

Brand keys are mapped explicitly (Honor→`huawei`, Lenovo/Motorola→`motorola` and
`lenovo`, TCL/ZTE→`tcl_zte`, Asus→`asus_sharp`, dead brands→`others`).

Limits, stated plainly:

- Catalogue names are `Devices` + `Models` concatenations
  (`Samsung Galaxy A5 2016 (SM-A510F)`); the database uses short names
  (`Galaxy A15`). A human would match more; the script does not guess.
- The database has **one entry per generation**, the catalogue has **one entry
  per SKU**. `Galaxy A15` therefore corresponds to no single catalogue row,
  because the catalogue's newest Samsung A-series row is the A71/A52.
- 212 text-only rows have no platform and often no model code, so they can only
  be matched by name — and most are pre-2020 devices absent from the database.
- 19 HiSilicon pseudo-rows and 2 stub scatters are not devices. Huawei's 135
  catalogue rows are therefore ~116 phones + 19 SoC rows.

Result: **745 of 1,396 catalogue rows (53%) resolve to a database model**, via
719 database entries. Of the 651 remaining rows: MTK 276, unknown-platform 181,
QCOM 101, SPD 49, Odin 44. The 181 unknown-platform rows are almost entirely
text-list entries (§5) that were never given a chip.

### 7.2 Structurally interesting remaining gaps

Not just "more of the same":

| Gap | Catalogue evidence | Why it matters for FlashPilot |
|---|---|---|
| **Pre-2020 Samsung A/M/C/J series** | 131 Samsung rows; modern end stops at A71/A52, huge A3/A5/A7/A9 2016–2018 and C5/C7/C9 coverage | FlashPilot's Samsung bucket is 2023–2025 heavy. These are the devices a repair shop actually sees. |
| **Tecno/Infinix MTK volume** | Tecno 85 (79 MTK), Infinix 56 (52 MTK) — Camon 11–18, Spark 2–8, Hot 6–12, Note 3–11 | 22 + 9 rows still unimported despite per-row SoC strings. |
| **Oppo/Realme MTK layouts** | Oppo 157 (81 MTK), Realme 71 (49 MTK) with `opporeserve*` partition sets | Directly informs the MTK flow's partition resolver on Oppo/Realme FRP (which partitions to avoid). |
| **iTel SPD breadth** | 107 iTel rows, 65 SPD (SC7731/SC7731E/SC9832E/SC9863A), 42 unknown-platform text rows | The full A12–A60 / Vision / S-series map; 78 rows still missing. |
| **Huawei/Honor Kirin FRP** | 19 HiSilicon chip-level rows (kirin 620–970) + 116 Huawei/Honor phones | FlashPilot's Huawei bucket is MediaTek/Qualcomm only. The Kirin TP/FRP path is uncovered. |
| **12 brands with no bucket** | 148 rows across LG, Alcatel, HTC, Allview, Coolpad, Micromax, Vsmart, Yezz, Asus (legacy), Amazon, Archos, Symphony | Almost all MediaTek with the platform already given — lowest-risk imports. |
| **Qualcomm EDL breadth** | 280 rows with an `Edl` flag, 215 explicit `Edl:Edl` | 101 QCOM rows not yet in the database form a ready-made EDL candidate set. |

### 7.3 What FlashPilot covers that the catalogue does not

Grouped, for the 69 `planned` models plus the curated core:

| Category | Count | Examples |
|---|---:|---|
| 2023–2025 Samsung | 8 | Galaxy A05, A06, A14, A15, A15 5G, A16, A16 5G |
| Apple (all) | 6 | iPhone 6s → iPhone 12, SE 2020 — the catalogue has **no Apple data at all** |
| 2023+ Xiaomi/Redmi/POCO | 8 | Redmi 12, 13C, Note 12, Note 13 4G/5G, Poco C65/M6/X6 |
| 2023+ Oppo/Realme | 10 | Oppo A17/A18/A38/A58, Reno 10/11, Realme C53/C55/Note 50/11 Pro |
| 2023+ Tecno/Infinix | 9 | Tecno Pop 8, Spark 10/10C/20, Camon 20; Infinix Hot 30i/40, Smart 8, Note 30 |
| OnePlus | 5 | Nord N20/N30/CE3, 11R, 12R — the catalogue has only 2 OnePlus rows |
| Motorola modern | 6 | Moto G13/G24/G34/G84, Edge 40 |
| ZTE Blade / TCL 2023 | 5 | ZTE Blade A54/A72, TCL 40 SE, 305 |
| Asus/Sharp 2022+ | 3 | Zenfone 9/10, Aquos sense7 |
| Nokia 2021+ | 4 | G21, G42, C32, 3.4 |

Two honest caveats:

- **The catalogue is older, but wider.** Its newest rows are ~2022 (Oppo Reno 6,
  Redmi Note 11, Tecno Camon 18). FlashPilot's `planned` list is newer. Neither
  is a superset.
- **Some "gaps" are naming artifacts.** `Galaxy A15` vs `Galaxy A71` is a real
  generation gap; `Nokia G21` vs `Nokia G20` is adjacent but a different device.
  A few are pure spelling (`Pocophone` vs `Poco`, `Relme`, `Meta` for Mate). A
  human-curated pass closes the spelling cases but not the generation gaps.

### 7.4 Generation ceilings (sanity check)

Highest model number per family in the catalogue — the clearest statement of how
old the data is:

| Family | Catalogue ceiling | FlashPilot's newest |
|---|---:|---|
| Samsung Galaxy A | A71 | A16 |
| Samsung Galaxy M | M32 | (no M-series entries) |
| Redmi Note | Note 11 | Note 13 |
| Redmi (numeric) | 9 (plus 10X/20X) | 13C |
| Oppo A | A96 | A58 |
| Oppo Reno | Reno 6 | Reno 11 |
| Vivo Y | Y95 | Y36 |
| Realme C | C35 | C55 |
| Tecno Spark | Spark 8 | Spark 20 |
| Tecno Camon | Camon 18 | Camon 20 |
| Infinix Hot | Hot 12 | Hot 40 |
| Infinix Note | Note 11 | Note 30 |
| itel A | A60 | A70 |
| Nokia G | G20 | G42 |
| Honor | Honor 50 | Honor 90 |

## 8. Import rules used for the database

- **Engine** from transport flags: `Edl` → `qcom`, `spd` → `spd`, `Odin` →
  `odin`, otherwise `mtk`. `Conn=auth`/`Brom` stay as per-row connection state.
- **Identity**: cleaned device line as `model`, model codes kept in parentheses;
  `vid` fixed by engine (mtk `0e8d`, qcom `05c6`, spd `1782`, odin `04e8`).
  Samsung MediaTek rows keep a dual `04e8|0e8d`.
- **Excluded on import**: dead-brand rows (LG/HTC/BlackBerry/…), 2016–2017-era
  SoCs (MT65xx/MT6735/6737/MT6750/53/55/679x, SD410/425/430/450/615/625,
  SC7731x), Exynos/Odin rows, and UI placeholder lines (`* : Auto`).
- **Status**: imported rows are `researched` because the engine-level flows are
  wired; per-model `actions` still ride the row for the model-page tooltip.
- **No `source` field.** The database deliberately carries no per-row
  provenance; the catalogue is the research input, the database is the product.

## 9. What to do next

Ordered by value per unit of work:

1. **Import the remaining 148 rows from the 12 unbucketed brands** as
   `status: "planned"`. They are almost all MediaTek, the platform is given per
   row, and there is no naming-collision risk. Lowest risk, largest brand-count
   gain.
2. **Use the catalogue's per-row `Platform` as the chip field** for
   Tecno/Infinix/iTel/Oppo/Realme. This is the single most useful column in the
   corpus: nearly every device row carries a concrete SoC string (only a handful
   are blank), versus 719 hand-written database `chip` values.
3. **Adopt the `opporeserve*` / `oplusreserve*` partition sets** into the MTK
   flow's partition-resolver tests. These are real Oppo/Realme layouts, and the
   A/B + `super` layouts cover the Android 10+ case.
4. **Do not trust `Storage`.** It contains `FRP`, `TP`, `Test`, `factory`,
   `MIUI 12`. Storage must come from the scatter, not from the export.
5. **Treat the two stub scatters as templates only** — a single `preloader` row
   with a dead absolute path is not a device layout.
6. **Ignore the `rawprogram*` files for Qualcomm.** They are MediaTek FlashTool
   XML; the corpus ships no Qualcomm rawprogram XML.
7. **Do not import the 19 HiSilicon rows as devices** — they are chip-level
   FRP/TP entries. Useful as `chip` metadata, wrong as `model`.

## 10. Validation

```bash
python3 -c "import json;json.load(open('operations/device_research/device_catalogue.json'))"
```

Counts in this document were regenerated against the catalogue at the time of
writing: 1,396 catalogue rows, 35 brands, 719 database models, 745 matched rows.
