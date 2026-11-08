# FlashPilot — индекс

Language switcher: [English](../../INDEX.md) · [Français](../fr/INDEX.md) · [Español](../es/INDEX.md) · [Deutsch](../de/INDEX.md) · [简体中文](../zh/INDEX.md) · **Русский** · [Português](../pt/INDEX.md) · [日本語](../ja/INDEX.md) · [العربية](../ar/INDEX.md) · [हिन्दी](../hi/INDEX.md) · [Türkçe](../tr/INDEX.md)

> English is the canonical source. This page is a translation; help wanted — see [`../TRANSLATION.md`](../TRANSLATION.md).

README содержит маркетинг. Этот файл — инженерный индекс: каждая папка, что она делает и с чего начать.

## Запуск

```bash
# GUI
python main.py

# CLI (мост) — тот же протокол, без GUI
./target/release/flashpilot-bridge detect-all
./target/release/flashpilot-bridge spd-detect
```

## Корневая структура (17 записей)

| Запись | Что это | Когда открывать |
|---|---|---|
| `main.py` | Точка входа приложения. Добавляет репозиторий в `sys.path` и вызывает `python.gui.qt_app.main()`. | Чтобы изменить способ запуска приложения. |
| `pyproject.toml` | Метаданные пакета Python (name=flashpilot, deps, build backend). | Чтобы добавить Python-зависимость или повысить версию. |
| `Cargo.toml` / `Cargo.lock` | Ядро на Rust (бинарь `flashpilot-bridge`). | Чтобы изменить CLI моста или добавить протокол. |
| `python/` | Тонкий слой Python над движком Rust: `python/core/` (shim + GUI-хелперы) и `python/gui/` (PyQt6). Все потоки живут в `src/flows.rs`. | GUI и работа с устройствами. |
| `src/` | Исходники Rust. Зеркальная структура `python/core/`. | Когда вы добавляете команду моста или меняете USB-протокол. |
| `tests/` | Набор pytest. ~149 тестов, ~1 с. | Запуск `.venv/bin/python -m pytest tests/ -q`. |
| `scripts/` | Автономные shell-инструменты. Сегодня: `dump-connected.sh`, `validate_mtp_at.py`. | Для пакетной операции вне GUI. |
| `docs/` | Ресурсы README (скриншоты, логотип). | Для README. |
| `packaging/` | Скрипт сборки `.deb` + контрольные файлы. | Чтобы выпустить релиз. |
| `root/` | Правила udev (чтобы телефоны работали без sudo). | Разовая настройка. |
| `operations/` | **Деревья документации по операциям** — см. раздел «operations/» ниже. | Чтобы понять конкретную операцию (FRP, MDM, блокировка экрана и т. д.). |
| `build/` | **Все gitignored артефакты сборки/выполнения** — см. раздел «build/» ниже. | Вы почти никогда это не открываете. |
| `.github/` | CI-воркфлоу, шаблоны issue. | Чтобы изменить CI. |
| `LICENSE` `CODE_OF_CONDUCT.md` `CONTRIBUTING.md` `SECURITY.md` `DESCRIPTION.md` | Стандартные метаданные проекта. | При выпуске. |

## Структура `python/`

```
python/
├── main.py                 <- точка входа (добавляет репозиторий в sys.path, вызывает python.gui.qt_app.main)
├── gui/                    <- приложение PyQt6
│   ├── qt_app.py           <- главное окно + вся UI по режимам (~12k LOC)
│   ├── devices.py          <- data-driven «поддерживаемые устройства» drill-down (бренд -> модель -> действие)
│   ├── theme.py            <- дизайн-токены (цвета, стили кнопок, helpers версии)
│   ├── animations.py       <- нарисованные глифы: сцена соединения, орб статуса и т. д.
│   ├── nav.py              <- главный rail навигации + панель чипов OEM
│   ├── toast.py            <- всплывающие уведомления
│   └── supported_devices.json  <- база данных действий по модели
└── core/                   <- тонкий слой Python (без Qt-зависимостей; делегирует Rust-мосту)
    ├── core.py             <- зеркало FLOWS/JOBS/MODES (хардкод-кэш + Rust flow_list())
    ├── bridge.py           <- диалог с бинарём `flashpilot-bridge`
    ├── flow.py             <- примитивы Flow/Step + отмена
    ├── jobs.py             <- жизненный цикл FlashJob (изолированный слой job)
    ├── cancel.py           <- реестр кооперативной отмены
    ├── devices.py          <- идентичность нескольких устройств (стабильные ключи, список, разрешение, маппинг транспортов)
    ├── frp.py              <- только re-export поверхность FRP (имя == ответственность)
    ├── mtk.py              <- PID/стадии/чипы MTK (0003=BROM, 2000=preloader)
    ├── mtp.py              <- Samsung MTP/AT (многоэтапная активация ADB)
    ├── pit.py pitstore.py  <- парсер PIT Samsung + кэш
    ├── adb.py device_info.py actions.py experimental.py fus.py
    └── (no flows/ dir)     <- потоки живут в src/flows.rs; Python только делегирует через bridge.flow_run()
```

**Потоки живут в Rust.** `python/core/core.py` — тонкий shim: `_RustFlow` делегирует выполнение `bridge flow-run <key>`. Канонический реестр — `src/flows.rs` (макрос `flow!`, ~280 строк); Python отражает его для поиска в GUI.

## Структура `src/` (Rust)

```
src/
├── main.rs                 <- весь CLI-dispatch (eprintln! — канал «log») + flow-run
├── flows.rs                <- РЕЕСТР потоков (макрос flow!; FLOWS/JOBS/MODES)
├── usb/                    <- контекст libusb, парсинг дескрипторов, фильтрация (mod.rs + filtering.rs)
├── devices.rs              <- объединённые строки USB+ADB-устройств
├── sam_download.rs         <- сессия Samsung Download/Odin (команды odin-*)
├── sam_errors.rs sam_setup.rs sam_*.rs  <- хелперы Samsung
├── mtk.rs mtk_da.rs        <- прошивка MediaTek BROM/DA
├── mtk_exploit.rs          <- эксплойты BROM (bypass/kamakiri2/crash-to-BROM)
├── mtk_sla.rs mtk_sla_keys.rs <- Secure Lock Authentication
├── mtk_daloader.rs         <- парсинг контейнера DA
├── qualcomm/               <- EDL: Sahara + Firehose + GPT
├── spd.rs                  <- UNISOC BSL (BSL_CMD_*, BSL_REP_*, FDL1/FDL2)
├── pac.rs                  <- извлечение/упаковка SPD PAC
├── pit.rs                  <- парсер PIT Samsung
├── mtp.rs at.rs adb.rs     <- MTP, AT-команды, ADB-сантехника
├── fastboot.rs             <- нативный транспорт fastboot
├── moto_flash.rs           <- поэтапный fastboot-FRP Motorola
├── apple.rs                <- Apple usbmuxd/lockdown
├── bulk.rs hid.rs          <- хелперы bulk + HID
├── fwtar.rs sparse.rs imgtools.rs <- firmware tar/sparse/boot-vbmeta
├── hostinfo.rs             <- здоровье eMMC/UFS хоста
├── config.rs error.rs util.rs device.rs
└── (no odin.rs)            <- логика Odin живёт в sam_download.rs
```

## `operations/` — деревья документации по операциям

Эти папки содержат **README по операциям**, объясняющие, как работает каждый job, какие ключи потоков использует, какие устройства поддерживает и известные оговорки. Это **не** код — дерево состоит из чистого markdown (в прошлой чистке удалили устаревшие `.py`-shim'ы, которые тут жили; ничто не импортирует `operations/`). Код живёт в `src/flows.rs` (реестр `flow!`; `python/core/core.py` — тонкий shim) и доменных модулях (`knox.py`, `qcn.py`, `imei.py`, `emmc.py`, …). README в `operations/` написаны для конечных пользователей / исследователей коммерческих инструментов; код — источник истины.

| Папка | Что | Реальный код в |
|---|---|---|
| `operations/apple/` | iCloud, блокировка активации, MDM, удаление пароля/режима потеряно | Rust-потоки (`src/flows.rs`: строки `apple_*`, CLI `flow-run`) |
| `operations/frp/` | Обход FRP по движку + исследовательские заметки по устройствам. **Начните с `operations/frp/INDEX.md`**. | Rust-потоки (реестр `src/flows.rs`, CLI `flow-run`); тонкий shim `python/core/core.py` |
| `operations/mdm/` | Разблокировка MDM / device-owner + заметки по брендам | Rust-потоки (реестр `src/flows.rs`, CLI `flow-run`) |
| `operations/screen_unlock/` | Снятие блокировки экрана (ADB / recovery / download / comprehensive) | Rust-потоки (реестр `src/flows.rs`, CLI `flow-run`) |
| `operations/battery/` | Отчёт / ремонт / нагрузочный тест батареи (через ADB) | Rust-потоки (реестр `src/flows.rs`, CLI `flow-run`) |
| `operations/network/` | Состояние SIM, DNS, сброс радиомодуля | Rust-потоки (реестр `src/flows.rs`, CLI `flow-run`) |
| `operations/carrier_unlock/` | Блокировка оператора (Apple, MTK) | Rust-потоки (реестр `src/flows.rs`, CLI `flow-run`) |
| `operations/flashing/` | Руководства по прошивке по вендорам (Samsung Odin, MTK DA, Qualcomm EDL, UNISOC SPD, PIT) | Rust-потоки (реестр `src/flows.rs`, CLI `flow-run`) |
| `operations/usb/` | Заметки по перечислению и детектированию USB | `src/usb/`, `src/devices.rs`, `python/core/devices.py` |

## `build/` — gitignored артефакты сборки/выполнения

| Подпапка | Содержимое | Создаётся |
|---|---|---|
| `build/target/` | Вывод `cargo build` Rust | `cargo build` |
| `build/dist/` | Пакеты `.deb` | `packaging/build-deb.sh` |
| `build/cache/` | TAR-кэши по устройствам и реверс-инженерные дампы | GUI / `scripts/dump-connected.sh` |
| `build/mdm_qr/` | Сгенерированные QR-коды провижининга MDM | GUI-поток MDM |
| `build/pit/` | Кэшированные `.pit`-файлы таблицы разделов | GUI-поток PIT |

**Правило:** никогда не делайте `git add` для чего-либо из `build/`. Если нужно очистить состояние, удалите подпапку — она пересоберётся.

## Как добавить новую функцию (шпаргалка «какой файл трогать?»)

| Вы хотите… | Трогайте |
|---|---|
| Добавить новое устройство в список поддерживаемых | `python/gui/supported_devices.json` |
| Добавить действие по вендору для поддерживаемого устройства | `src/flows.rs` (добавить строку `flow!(...)`); Python автообнаружит через `bridge.flow_list()` |
| Добавить ADB-поток для существующей области | то же (Rust `src/flows.rs`) |
| Добавить новую CLI-команду моста | `src/<область>.rs` + `src/main.rs` (ветка `<cmd>` в match) |
| Добавить новую страницу навигации верхнего уровня | `python/gui/qt_app.py` (`_build_*_page` + `_section_index`) |
| Добавить цвет / стиль кнопки | `python/gui/theme.py` (`C` dict / `_btn_*()`) |
| Задокументировать заметки по job нового устройства | `operations/<job>/<бренд>/<модель>.md` |
| Добавить тест | `tests/test_<область>.py`, по образцу `test_mtk.py` |

## Как работает исполнитель операций (прочитайте один раз)

GUI никогда не вызывает поток напрямую. Выборщик устройства на операцию (`FlashPilotWindow._choose_device`) сначала разрешает стабильный ключ устройства; затем `_run_ops_flow` / `_run_job_flow` вызывают `python.core.core.flow_for(job, mode, method)`, который возвращает объект `Flow()` (список `Step()`), затем `flow.run(ctx, log)` вызывается в рабочем потоке внутри `devices.device_scope(key)` (чтобы каждый резолвер целился в выбранный телефон). Каждый поток пишет в вызываемый `log(line)`, который GUI привязывает к своей консоли. Отмена ограничена устройством (`flow.request_cancel(key)`; вещание без ключа останавливает всё), проверяется в начале каждого `_run`.

Чтобы добавить поток: добавьте строку `flow!("my_op", "My op", "Job Name", "MODE")` в `src/flows.rs`. Python автообнаружит его через `bridge.flow_list()`, и drill-down job/mode/метод GUI подхватит автоматически. CLI Rust `flow-run` выполнит его; резолверы должны принимать целевой serial/`vid:pid@bus:addr` (см. `src/device.rs`).