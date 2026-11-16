Language switcher: [English](../../frp/INDEX.md) · [Français](../../fr/frp/INDEX.md) · [Español](../../es/frp/INDEX.md) · [Deutsch](../../de/frp/INDEX.md) · [简体中文](../../zh/frp/INDEX.md) · **Русский** · [Português](../../pt/frp/INDEX.md) · [日本語](../../ja/frp/INDEX.md) · [العربية](../../ar/frp/INDEX.md) · [हिन्दी](../../hi/frp/INDEX.md) · [Türkçe](../../tr/frp/INDEX.md)

> English is the canonical source. This page is a translation; help wanted — see [`../../../docs/TRANSLATION.md`](../../../docs/TRANSLATION.md).

# operations/frp/ — Factory Reset Protection (только Android)

> Устройства Apple FRP не имеют (Apple использует Activation Lock / iCloud вместо него) —
> см. `operations/apple/`.

Эта директория хранит **деревья документации по движкам** для обхода FRP.
Фактический код живёт в `src/flows.rs` (Rust). Когда у вас есть настоящий
рецепт для устройства (чип, пара FDL, смещения разделов и т. д.), вы кладёте
короткую исследовательскую заметку в `devices/<brand>/<model>.md`. README в корне
этого файла сопоставляет каждый FRP-поток в codebase с тем, где он живёт
и что ему нужно.

## Карта движков

| Движок | Когда использовать | Код | Bridge CLI |
|---|---|---|---|
| **Generic (ADB)** | Первая попытка на любом телефоне с включённой USB-отладкой | Rust потоки (`adb_frp`, `frp_*` строки в `src/flows.rs`) | `flow-run adb_frp` / `adb shell ...` через `bridge.adb_shell` |
| **MTK BROM** | MediaTek (Helio / Dimensity / MT6765) — выключить → держать Vol-/+ → вставить USB | Rust потоки (`mtk_*` строки в `src/flows.rs`) | `flow-run mtk_brom_info` (CLI: `mtk-detect`, `mtk-da-upload`, `mtk-frp`, `mtk-bypass`) |
| **MTK DA** | MTK BROM, переживший загрузку DA (lock-state чипы) | Rust потоки (`mtk_brom_backup`, `mtk_auth_flash`) | `flow-run mtk_brom_backup` |
| **Qualcomm EDL** | 9008 emergency download (Snapdragon) | Rust потоки (`edl_*`, `qcom_*` строки) | `flow-run edl_frp` (CLI: `qcom-*`) |
| **Samsung Exynos** | A14 (Exynos 850/1330), A15/A16 — режим Odin download только прошивка, НЕ для FRP | Rust `frp_*` строки (Samsung account-bypass) | (в основном on-device, без моста) |
| **Samsung MTK (A05/A06)** | A05/A06 с Helio G85 — использует MTK BROM (см. выше) | Rust потоки (`mtk_brom_info`, `mtk_brom_backup`) | `flow-run mtk_brom_backup` |
| **UNISOC/SPD** | 1782:4d00 FDL1+FDL2 (SC9863A, T606/UMS9230) | Rust потоки (`spd_*` строки) + `src/spd.rs` | `flow-run spd_detect_info` (CLI: `spd-detect`, `spd-frp`, `spd-format`, `spd-magic-pack`) |
| **HiSilicon Kirin** | 12d1 — открытого потока пока нет (не отреверсировано) | (нет пока) | (нет) |

(Старые модули движков `python/core/flows/*.py` никогда не поставлялись; `mtk-brom-backup` — это строка потока `mtk_brom_backup`. Проверяйте любой ключ с помощью `flow-list`.)

## Карта поток-ключ → функция

Каждый поток, который могут вызвать FRP-действия GUI. Ключи — строки registry Rust
(`src/flows.rs`; проверяйте через `flow-list`); GUI маршрутизирует по
(job, mode), а мост выполняет через `flow-run <key> [target]`.

| Ключ потока | Движок | Что делает |
|---|---|---|
| `adb_frp` | Generic ADB | `settings put secure frp 0` + отключение setup wizards + очистка данных GMS |
| `frp_browser` | Generic ADB | Открыть `chrome://settings/` on-device через intent |
| `frp_emergency` | Generic ADB | Открыть Settings через dialer экстренного вызова (on-device) |
| `frp_settings` | Generic ADB | Открыть Settings через путь notification-shade (on-device) |
| `frp_fake_login` (+`_testdpc`, `+_adp`) | Generic ADB | QR-провижининг с device-owner DPC, затем очистка FRP |
| `at_info` | Samsung MTP/AT | Чтение режима + devconinfo по AT-каналу (Samsung pre-Android 8) |
| `at_method` | Samsung MTP/AT | AT+DEBUGLVC для включения ADB поверх diag-порта |
| `download_frp` | Samsung download mode | Снятие FRP через CSC/Combination firmware (PIT safety contract) |
| `odin_enable_adb` | Samsung download mode | Включить ADB из download mode через Odin tarball |
| `mtk_combo_flash` | MTK Download | Combo firmware flash (PIT + DA) |
| `mtk_recovery_reset` | MTK Download | Factory reset в recovery mode |
| `mtk_brom_info` | MTK BROM | Чтение chip id / handshake (нужно перед любым BROM flash) |
| `mtk_brom_backup` | MTK BROM | Дамп разделов через BROM DA |
| `edl_frp` | Qualcomm EDL | Sahara + Firehose erase (05c6:9008) |
| `qcom_detect_info` | Qualcomm EDL | Detect + info (read-only) |
| `frp_qr_provision` | Generic ADB | QR provisioning (пусть TestDPC) |

(Архивированы: старые имена с префиксом `flow_*` и
`python/core/flows/*.py` никогда не поставлялись — ключи не имеют префикса `flow_`.)

## Как паттерн per-model recipe попадает сюда

1. **Запустите реальный дамп устройства** (ADB-путь — `scripts/dump-connected.sh`, для BROM-пути UNISOC — `flashpilot-bridge spd-format`). Дамп goes в `build/cache/dumps/<model>_<codename>/`.
2. **Из дампа определите** движок + чип + имя FRP-раздела (на Android 11+ почти всегда `frp`, `frp_a` или `userdata`).
3. **Добавьте запись устройства** в `python/gui/supported_devices.json` под нужный brand, с `actions: ["frp", "info", "backup", "flash"]` и `status: "researched"`. (Существующий поток по движку подхватит автоматически — новый поток нужен только если движок сам отсутствует.)
4. **Положите короткую исследовательскую заметку** в `operations/frp/devices/<brand>/<model>.md` с чипом, движком, разделом, build fingerprint и однострочником, подтверждающим рецепт (напр. "mmcblk0p4 = frp, instant BROM DA erase, no combo needed"). Формат: `operations/frp/devices/nokia/nokia_g20.md`.
5. **Если у движка нет потока** для этого чипсета, зарегистрируйте поток в `src/flows.rs` (строка `flow!(...)`) и добавьте CLI dispatch в `src/<engine>.rs` + `src/main.rs`.

## Почему per-chip файлы исчезли

Ранние рефакторы разбили гигантский `frp.py` на per-chip файлы под `operations/frp/chips/` и per-engine под `operations/frp/{mtk,qualcomm,unisoc,samsung}_frp/`. Старая ревизия этого INDEX заявляла dead docstubs и dispatch `python/core/flows/brom.py` — тот модуль никогда не поставлялся. Реальный per-chip dispatch — реестр Rust-потоков (`src/flows.rs`: строки `mtk_*`/`qcom_*`/`spd_*`, проверяйте через `flow-list`); INDEX.md — карта, чтобы новый dev знал, где реально живёт engine-specific код.

## Почему per-engine Python shims исчезли

`operations/frp/mtk_frp/mtk_frp.py` (и 4 собрата) импортировал функции из `python.core.flows.brom` и re-экспортировал их под **вторым** `FLOWS = {}` dict, который GUI никогда не читает. Они коллидировали с canonical `FLOWS` в `python/core/flows/__init__.py` и могли бы маскировать настоящие, если бы GUI когда-нибудь их читал. Заменены README в каждой engine-папке, указывающим на реальные Python-модули.