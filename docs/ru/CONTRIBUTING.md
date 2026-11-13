# 🧑‍💻 Вклад в FlashPilot

Language switcher: [English](../../CONTRIBUTING.md) · [Français](../fr/CONTRIBUTING.md) · [Español](../es/CONTRIBUTING.md) · [Deutsch](../de/CONTRIBUTING.md) · [简体中文](../zh/CONTRIBUTING.md) · **Русский** · [Português](../pt/CONTRIBUTING.md) · [日本語](../ja/CONTRIBUTING.md) · [العربية](../ar/CONTRIBUTING.md) · [हिन्दी](../hi/CONTRIBUTING.md) · [Türkçe](../tr/CONTRIBUTING.md)

> English is the canonical source. This page is a translation; help wanted — see [`../TRANSLATION.md`](../TRANSLATION.md).

Спасибо, что заглянули! Проект построен на протоколах, полученных через реверс-инжиниринг, и на открытом знании — каждый вклад делает его более мощным, надёжным и ближе к платным Windows-пакетам. Вам не нужно быть экспертом по прошивке, чтобы помочь.

## Содержание

- [Кодекс поведения](#кодекс-поведения)
- [Как организован проект](#как-организован-проект)
- [Способы помочь](#способы-помочь)
- [Начало работы](#начало-работы)
- [Миграция с более старого чекаута](#миграция-с-более-старого-чекаута-прочитайте-это-сначала-если-вы-возвращаетесь)
- [Архитектурный тур (10 минут)](#архитектурный-тур-10-минут)
- [Как добавить новый поток](#как-добавить-новый-поток)
- [Добавление нового USB-протокола / команды Rust](#добавление-нового-usb-протокола--команды-rust)
- [Правила GUI](#правила-gui)
- [Тестирование](#тестирование)
- [Чек-лист pull request](#чек-лист-pull-request)
- [Платформенная политика](#платформенная-политика-прочитайте-перед-портингом)
- [Дорожная карта и идеи](#дорожная-карта-и-идеи)
- [Участники](#участники)
- [Вопросы?](#вопросы)

---

## Кодекс поведения

См. [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md). Будьте уважительны, исходите из добрых намерений и держите обсуждения техническими и полезными. Это любительский проект, который стал серьёзным: мы рады и новичкам, и ветеранам. Травля, гейткипинг или коммит секретов/учётных данных недопустимы. Payload'ы протоколов приветствуются при условии задокументированной происхождения и лицензии.

---

## Как организован проект

Две половины работают вместе:

| Слой | Расположение | Язык | Роль |
|---|---|---|---|
| **Core / protocol engine** | `src/` | Rust | Raw USB, все протоколы бутлоадеров (`flashpilot-bridge` CLI) |
| **Registry потоков** | `src/flows.rs` | Rust | Строки `flow!` macro → `FLOWS` / `JOBS` / `MODES` (источник истины) |
| **Shim потоков** | `python/core/core.py` | Python | Тонкие `_RustFlow`-обёртки + fallback `JOBS`; делегирует в `bridge flow-run` |
| **Идентификация устройства** | `python/core/devices.py` | Python | Стабильные ключи, список устройств, повторное разрешение цели, thread scope |
| **FRP-поверхность** | `python/core/frp.py` | Python | FRP-only re-export (имя == ответственность) |
| **GUI studio** | `python/gui/` | Python / PyQt6 | Workbench (`qt_app.py`), страницы (`devices.py`), тема, анимации |

Python никогда не обращается к USB напрямую. Он вызывает `target/release/flashpilot-bridge` (Rust-бинарь), который возвращает JSON/text. GUI получает обновления только из сигналов рабочих потоков — никогда не обращайтесь к виджетам из фонового потока.

---

## Способы помочь

Не умеете программировать? Не проблема:

- **Тестирование на реальном железе** — сообщайте, на каких устройствах/прошивках работает поток.
- **Документация** — улучшайте README, этот файл и описания потоков.
- **Firmware / DA / combo archives** — ссылки на легальные, свободно распространяемые бинарники.
- **Переводы и темы** — GUI тематизируется; новые акцентные пакеты — лёгкая победа.
- **UI/UX** — мокапы, проходы по доступности, дизайн горячих клавиш.
- **Баг-репорты** — используйте [шаблон баг-репорта](https://github.com/Legendary-Brilliantforous/flashpilot/issues/new?labels=bug&template=bug_report.yml): шаги, логи, вывод `flashpilot-bridge detect`, модель устройства + версия прошивки.
- **Код** — см. ниже.

> 💡 **Новичок?** Ищите метку **`good first issue`** в трекере — отобранные, дружелюбные к новичкам задачи со скоординированным скоупом, безопасные для взятия.

---

## Начало работы

```bash
# 1. Собрать Rust-мост
cargo build --release

# 2. (Рекомендуется) USB udev правила
sudo bash root/setup-usb.sh

# 3. Создать venv + запустить
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m python.main
```

Приложение откроет нативное PyQt6-окно. На странице **Settings → Tools** можно увидеть, собран ли мост и обнаружен ли ADB.

---

## Миграция с более старого чекаута (прочитайте это сначала, если вы возвращаетесь)

Кратко о перетряхивании: между 1.2.0 и сейчас мы переименовали центральный модуль, расщепили один god-file на сфокусированные модули, переименовали каждый job и добавили дюжину файлов. Это ломает старые импорты, ссылки в документации и любые внешние скрипты, написанные против `python.core.frp`. Извините за это — это был единственный способ убить god-file, исправить путаницу с MTK PID и сделать multi-device возможным без наслоения костылей. Эта секция — полное руководство по адаптации; тут нет «устарело постепенно», всё изменилось разом, поэтому пройдите таблицу один раз и вы в курсе.

### Переименованные пути

| Было | Стало | Что менять |
|---|---|---|
| `python/core/frp.py` (god file: registry + все потоки) | `python/core/core.py` | `from python.core import frp` → `from python.core import core`; `frp.FLOWS` → `core.FLOWS`, и т. д. |
| *(ничего — FRP жил внутри god file)* | `python/core/frp.py` (новый, только FRP) | Если нужны только FRP-потоки, импортируйте отсюда вместо `core`. |
| *(ничего)* | `python/core/devices.py` (новый) | Идентификация устройства, `list_devices()`, `resolve_usb_target()`, `device_scope()`. |
| *(ничего)* | `python/core/imei.py` (новый) | Ремонт/смена IMEI для MTK/SPD. |
| *(ничего)* | `python/core/experimental.py` (новый) | EXPERIMENTAL-гейты + audit log. |
| *(ничего)* | `python/core/{knox,qcn,emmc,pac,apple,health,compat,device_info,fastboot,integrity,safety,spd_adb}.py` (новые) | Доменная логика, ранее встроенная в god file или отсутствующая. |
| *(ничего)* | `tests/test_devices.py` (новый) | Тесты multi-device + cancel scope. |
| *(ничего)* | `CHANGELOG.md` (новый) | Сгруппированные по релизам изменения; проверяйте его первым. |

### Переезд в Rust (текущая архитектура — таблица выше это история)

После разделения выше движки переехали в Rust, а Python-сторона стала тоньше. Текущая правда:

- **Потоки живут в `src/flows.rs`** (registry + `flow-run <key> [target] [--code/--partition/--file/--dpc ...]`). `flow-list` — источник истины — проверяйте ключ потока там, прежде чем ссылаться на него в документации.
- **`python/core/core.py` — тонкий shim** (~450 строк): `_RustFlow` делегирует в `bridge flow-run`, registry приходит от моста с fallback `JOBS`. 16 доменных модулей движков (`knox`, `qcn`, `emmc`, `imei`, `apple`, `ofp`, `pac`, `health`, `flashing`, `spd_adb`, `integrity`, `fastboot`, `usb_watch`, `compat`, `updater`, `safety`) удалены — не ссылайтесь на них в новой документации.
- **GUI остаётся Python** (`python/gui/qt_app.py` + `devices.py`); потребляет Rust-registry через `bridge.flow_list()`.
- Старые тест-файлы для удалённых Python-потоков удалены вместе с ними; покрытие — per-area suites + cargo `flows::tests`.

### Изменения API, которые нужно учесть

- **Резолверы принимают `key=None`.** `find_samsung()`, `_download_mode_device()`, `_wait_for_adb()`, `_wait_mtk_brom_target()`, `_mtk_retry()`, `wait_clean_download_mode()`, `pit_contract()` принимают опциональный стабильный ключ устройства (по умолчанию ambient thread scope — старые call sites продолжают работать, поведение first-match сохраняется без ключа).
- **Отмена per-device.** `request_cancel()` / `clear_cancel()` / `cancel_requested()` в `flow.py` и `bridge.py` принимают `key=None`. Бездомный `request_cancel()` по-прежнему вещает (global STOP); бездомные проверки консультируют ambient scope, затем broadcast bus.
- **Run-guard per-device.** `_flow_start(label, destructive, key=None)` / `_flow_end(key=None)` / `_flow_busy_msg(key=None)` в `qt_app.py`; старые глобалы `_FLOW_LOCK` / `_FLOW_LABEL` исчезли (заменены на per-key dicts + `_flows_running()`).
- **Runners принимают `device_key=None`.** `_run_ops_flow()` / `_run_job_flow()` показывают device picker, когда совпало несколько телефонов, затем ставят `ctx["device_key"]` (+ `ctx["target"]` где разрешимо) и работают внутри `devices.device_scope()`.
- **Новый режим транспорта `"SPD"`** в `MODES` (VID `0x1782`); новые jobs: `Knox / Warranty`, `QCN / Modem`, `IMEI Repair / Change`, `eMMC / UFS`.
- **Имена Job verb-first** (`Remove FRP`, не `FRP bypass`; см. README). Если ваша ветка ссылается на старые имена — переименуйте.
- **MTK PID'ы по соглашению mtkclient**: `0e8d:0003` = BROM, `0e8d:2000` = preloader. Несколько старых комментариев/logs меняли их местами; доверяйте `mtk.pid_stage()` / Rust `boot_stage_for()`, а не старым строкам.

### Если у вас открыт PR до реструктуризации

1. Rebase на новое дерево; конфликты ожидаются в импортах и блоках `JOBS`/`FLOWS`.
2. Запустите чек-лист ниже — `pytest` тут же ловит устаревшие ссылки на ключи/имена (registry tests assert каждый метод `JOBS` разрешим).
3. Если PR трогал `flows/` (удалённый split-package эксперимент): этой директории нет, перенесите изменение на `core.py` + доменный модуль.

---

## Архитектурный тур (10 минут)

1. **`src/main.rs`** — CLI из 80+ команд. Каждое `match`-плечо — одна команда (`detect`, `mtk-flash`, `mtk-crash-brom`, `qcom-firehose`, `spd-format`, `odin-pit`, ...).
2. **`src/usb.rs`** — ищет устройства по VID/PID, отдаёт endpoints (плюс стабильные `port_numbers` для re-enumeration-proof адресации).
3. **`src/odin.rs`** — Samsung download mode (реверс-инженеренный протокол Odin 3, Heimdall-производный). Читает/пишет PIT, прошивает разделы (incl. persistent `odin-agent` session multiplexer).
4. **`src/mtk*.rs`** — MediaTek BROM (`0e8d:0003`) → preloader (`0e8d:2000`) → handshake Download Agent, парсинг scatter, работа с GPT-разделами, SLA-ключи, эксплойты BROM, crash-to-BROM. ⚠️ Конвенция PID mtkclient-style: `0003`=BROM, `2000`=preloader — не путайте.
5. **`src/qualcomm/`** — рукопожатие Sahara (EDL) и сессии Firehose.
6. **`src/spd.rs`** — Spreadtrum/UNISOC BSL: загрузка FDL, форматирование, FRP, бэкап, PAC extract/pack.
7. **`src/flows.rs`** — **сердце приложения**. Строки `flow!(key, label, job, mode)` строят registry `FLOWS` / `JOBS` / `MODES` (~280 строк, 13 jobs, 9 modes incl. `SPD`). `python/core/core.py` только зеркалирует его для lookup в GUI.
8. **`python/core/devices.py`** — идентичность multi-device. Стабильные ключи (`adb:<serial>` → `usb:<port-path>` → volatile fallback), `list_devices()`, `resolve_usb_target()` и thread-local `device_scope()`, несущий выбранный телефон в резолверы.
9. **`python/gui/qt_app.py`** — строит все секции (Samsung / MTK / QC / SPD / Battery / Network / Settings) и sub-tab workbench'и, а также per-operation device picker и per-device run-guard.

### Поток данных

```
click button
  → _choose_device(job, mode)          # молча при 0-1 совпавших телефонах, иначе picker
  → _run_ops_flow(job, mode, method, name, device_key)
  → per-device _flow_start(key) + device_scope(key) + ctx["device_key"]
  → core.flow_for(...) -> Flow (list of Steps)
  → каждый Step идёт в worker thread, вызывая bridge._run([...])
  → bridge спавнит target/release/flashpilot-bridge ...
  → Rust делает USB I/O, печатает JSON/text
  → Python парсит + эмитит _ui.line() сигналы (tagged [device-key])
  → GUI обновляет console / status / progress безопасно
```

---

## Как добавить новый поток

Самая простая фича, которую можно отгрузить. Откройте `src/flows.rs` и добавьте одну строку:

```rust
flow!("my_method", "My method", "Remove FRP", "ADB"),
```

Ключ — короткий snake_case (без префикса `flow_`). Python автообнаружит его через `bridge.flow_list()`, а drill-down job/mode/method GUI подхватит автоматически; выполнение идёт через `flashpilot-bridge flow-run my_method`.

Затем (только если нужны новые низкоуровневые изменения протокола) добавьте bridge-команду в `src/<concern>.rs` + `src/main.rs`. Job/mode wiring уже в строке потока.

Всё — поток появится в dropdown/sub-tab GUI автоматически и будет доступен из CLI. **Это область с наивысшим value/lowest-entry.**

> Используйте `log(...)` внутри шагов для вывода в консоль, `ctx` для состояния между шагами, `bridge._run(...)` для всего, что бьёт в Rust-бинарь. Держите шаги кооперативными с `cancel_requested()` там, где уместно, чтобы работал Stop (отмена ограничена per-device — см. ниже).

### Правила, которым должен следовать каждый поток

- **Никогда не берите «то» устройство.** Принимайте `key=None` (ambient thread scope) в любом новом резолвере и фильтруйте по нему — см. `devices.device_key()`, `devices.match_key()`, `devices.device_scope()`. GUI ставит scope per operation; headless caller'ы могут тоже.
- **Имена Job verb-first** (`Remove FRP`, `Flash Firmware`, `Unlock Carrier`). **Ключи потоков — короткий snake_case** (`adb_frp`, не `flow_adb_frp`); единственный исторический алиас (`fastboot_read`) удалён — не добавляйте алиасы.
- **Конвенция MTK PID mtkclient-style**: `0e8d:0003` = BROM (held), `0e8d:2000` = preloader. Rust, Python, GUI labels и docs должны согласовываться.
- **EXPERIMENTAL writes** (Knox/IMEI/QCN/eMMC) идут через `experimental.check_gate_strict()` с per-run ack — сохранённый ack не должен auto-pass. GUI-гейтят через `_EXPERIMENTAL_FLOW_MAP` + паттерн янтарного схлопываемого блока на owning chip page (никогда не глобальная LAB page).
- **Bridge targets волатильны** (`vid:pid@bus:addr` меняется при re-enumeration). Повторно разрешайте от стабильного ключа перед открытием сессий (`devices.resolve_usb_target()`); одиночный odin4 закрепляется через `-d /dev/bus/usb/BBB/AAA`.

---

## Добавление нового USB-протокола / команды Rust

1. Добавьте модуль под `src/` (напр. `src/myproto.rs`).
2. Добавьте `mod myproto;` в `src/main.rs` и новый `match` arm + usage-строку.
3. Возвращайте `Result<T>` через `crate::error` и используйте `serde_json` для структурированного вывода.
4. Экспортируйте из Python в `python/core/bridge.py` как обёртку вокруг `_run([...])`.
5. Соберите `Flow` в `core.py`, который его вызывает (уважайте правила потоков выше).
6. Добавьте тест, если можете — unit-тесты живут в `src/*.rs` (`#[test]`) и `tests/`.

**Protocol hygiene:** указывайте источник (форумы, clean-room разборы, другие OSS проекты) в docstring модуля. Мы не включаем проприетарные blob'ы — только реализацию протокола.

---

## Правила GUI

- **Только PyQt6.** Никаких других Qt-биндингов, никаких дополнительных UI-зависимостей (см. `requirements.txt`).
- Следуйте существующему визуальному языку: `_btn_ghost()`, `_btn_primary()`, `_card_qss()`, `SectionTitle`, `C[...]` theme colors, `FlowLayout` для сеток кнопок.
- **Theme tokens, не raw accent:** заливки могут использовать `C['accent'/'grad_a'/'grad_b']`, но focus rings, selected-tab borders и checkboxes ДОЛЖНЫ использовать нейтральные `C['focus_ring']` / `C['sel_border']` — иначе красные accent-темы (Crimson, Sunset) протекают красным в focus-состояния. Никогда не хардкодьте hex для chrome.
- **Thread rule:** фоновая работа идёт в `threading.Thread`; GUI-обновления происходят только через `self._ui.*` сигналы (`.line`, `.status`, `.toast`, `.ui`, `.progress`).
- **Animations:** `Motion.shake()` / `Motion.rubber()` взаимоисключены per widget (guard по `_anim_lock`) — никогда не запускайте обе одновременно; call sites должны сериализоваться через `QTimer.singleShot`. Ни одна не должна оставлять за собой `setFixedSize`, рестyled borders или отключённые лэйауты; `cleanup()` восстанавливает всё.
- Держите долго живущие UI-ряды скроллируемыми — chip pages оборачивают контент в `QScrollArea`, чтобы они не сжимались на маленьких окнах.
- Новые sub-tab'ы переиспользуют `SamsungSubTabs` + `QStackedWidget` (см. `_build_chip_ops_section`).
- Кнопки действий — `NoFocus` (без sticky focus ring); checkable tab pills сохраняют `checked`-стиль для активного состояния.

---

## Тестирование

```bash
cargo test                      # Rust unit tests (incl. MTK stage mapping, SLA, PIT)
.venv/bin/python -m pytest tests/   # Python suite (currently 173 passed, 4 skipped)
```

Устройство тестового набора:

- `tests/test_frp_flow.py` — выполнение `Flow`/`Step` + кооперативная отмена + per-device run-guard.
- `tests/test_mtk.py` — логика MediaTek (scatter, DA, boot-stage helpers, BROM wait/crash-retry).
- `tests/test_devices.py` — стабильные ключи устройств, фильтрация телефонов, target re-resolution, scoped cancel.
- `tests/test_carrier_lock.py` — вердикт SIM-lock + MTK patch gating + DA discovery.
- `tests/test_odin_safety.py` — tar.md5 verification, BL gates, odin4 flag negotiation.
- `tests/test_pit.py` — парсинг Samsung PIT.
- `tests/test_bridge_io.py`, `tests/test_fus.py` — bridge I/O + Samsung firmware downloader.

Если добавляете Rust-логику — добавьте `#[test]`-модули в том же файле. Если добавляете потоки — добавьте pytest, запускающий поток с fake/offline context где возможно. Новые резолверы должны принимать `key=None`; новые тесты должны покрывать multi-device фильтрацию (см. `test_devices.py`) вместо предположения об одном телефоне.

---

## Чек-лист pull request

- [ ] `cargo build --release` проходит.
- [ ] `cargo test` проходит (или пометка, почему незапускаемо).
- [ ] `.venv/bin/python -m pytest tests/` проходит.
- [ ] Новый поток: подключён в `JOBS` (job + mode), чтобы был достижим в GUI.
- [ ] Новый резолвер: принимает `key=None` (ambient scope) и покрыт multi-device тестом.
- [ ] Новая Rust-команда: добавлена в usage-текст `main.rs` + wrapper в `bridge.py`.
- [ ] GUI-изменения: themed colors (нейтральные focus-токены!), signal-based updates, scroll-safe layouts.
- [ ] В репо не добавлены секреты/бинарники/device-identifying данные.
- [ ] Обновлена feature matrix в README, если добавлена возможность.

Держите PR сфокусированными. Один feature или фикс на PR — идеально; ссылайтесь на номер issue.

---

## Платформенная политика (прочитайте перед портингом)

**Linux — единственная поддерживаемая платформа.** Разработка, аппаратное тестирование и релизы таргетят Linux. Windows/macOS issue'и будут закрыты как unsupported — если только не придут в виде кода, как описано ниже.

**Почему:** `odin4` Linux-only; USB в Windows требует per-mode драйверов (Zadig / QDLoader / Samsung), которые нельзя отладить удалённо; macOS требует подписи/нотаризации при ничтожном спросе. См. секцию README «Platform support» для полного reasoning'а и открытого приглашения его оспорить.

**Как всё-таки применить порт (принятая форма):**

1. НЕ раскидывайте проверки `sys.platform` по потокам или GUI.
2. Добавьте `python/core/platform.py` с backend-функциями — `open_file_manager()`, `detach_kernel_drivers(target)`, `usb_device_path(bus, addr)`, `needs_udev_setup()`, `kernel_module_loaded(name)` — Linux реализован, остальные бросают `NotImplementedError` с полезным сообщением.
3. Перенесите существующие Linux-only call sites (`xdg-open`, `rmmod cdc_acm`, `/dev/bus/usb`, `lsmod`, udev docs) на него, по одному PR на группу call-site'ов.
4. PR порта Windows/macOS должен включать: реализацию backend'а, обновления docs и CI или подтверждение maintainer'ом ручного тестирования. Core-команда не владеет non-Linux test-железом — порт-PR'ы живут или умирают за счёт способности автора доказать их.

**PySide6 vs PyQt6:** миграция на PySide6 (LGPL, MIT-совместимый — PyQt6 GPLv3) желательна, но заблокирована на GUI smoke-test coverage. Если берётесь: конвертируйте `pyqtSignal→Signal`, `pyqtProperty→Property`, `PyQt6.sip→shiboken6` механически, расширьте offscreen window/picker/guard smoke-тесты в `tests/` и сохраните поведение pixel-identical. Сначала обсудите в Discussions.

## Дорожная карта и идеи

Мы будем рады, если кто-то за них возьмётся:

- **Порты и пакетирование:** Flatpak / AppImage / AUR, CI-матрица (Linux дистры), `pip`/`cargo` release flow.
- **MediaTek:** больше вариантов DA, scatter edge cases, eMMC/UFS backup dumps, новые `hw_code` в `CHIP_NAMES` (с цитируемым источником — никогда не угадывайте hex-коды).
- **Qualcomm:** граничные случаи rawprogram/patch XML, комбинации fh-loader, больше chip PID'ов.
- **Samsung:** дополнительные HID download-mode полезные нагрузки по SoC, полировка Odin multi-partition UX.
- **Multi-device:** per-device console tabs/progress, per-device STOP granularity (STOP сейчас вещает), корреляция `port_numbers` для экзотических хабов.
- **Новые секции:** TEE/keyboard FRP, profiles carrier (де-блоатинг), EDL-only утилиты.
- **Community:** переводы, device-compatibility wiki, воспроизводимый firmware-archive каталог.
- **Безопасность:** dry-run режим, автоматический pre-flash backup, brick-recovery docs.

---

## Участники

Все, кто helps — code, docs, device reports или tested combo — listed здесь и celebrated. Откройте PR, добавив себя (по алфавиту username, одна link-строка):

```md
- [@your-github](https://github.com/your-github) — what you did
```

Первые contributor'ы этого проекта сделали его реальностью. Be next.

---

**Questions?** Откройте discussion/issue. Спасибо за помощь в продвижении free, open flashing software на Linux. 🚀