# 🔧 FlashPilot

Language switcher: [English](../README.md) · [Français](../fr/README.md) · [Español](../es/README.md) · [Deutsch](../de/README.md) · [简体中文](../zh/README.md) · **Русский** · [Português](../pt/README.md) · [日本語](../ja/README.md) · [العربية](../ar/README.md) · [हिन्दी](../hi/README.md) · [Türkçe](../tr/README.md)

> English is the canonical source. This page is a translation; help wanted — see [`../TRANSLATION.md`](../TRANSLATION.md).

> **Открытый рабочий стол для прошивки и ремонта firmware Samsung под Linux — альтернатива Odin / Heimdall для прошивки телефонов Galaxy (режим Download/Odin), устройств MediaTek (BROM/DA), Qualcomm (EDL) и Spreadtrum/UNISOC.**

**Ключевые слова поиска:** Samsung flashing tool · Odin alternative · Android firmware flashing Linux · Heimdall GUI · Galaxy phone repair · MTK BROM flash · Qualcomm EDL · FRP unlock · UNISOC flashing · device firmware tool · mobile repair · Android bootloader · USB flashing · Linux flashing suite · proprietary tool alternative

[![Rust](https://img.shields.io/badge/Rust-1.70+-orange?logo=rust&logoColor=white)](https://www.rust-lang.org)
[![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python&logoColor=white)](https://www.python.org)
[![PyQt6](https://img.shields.io/badge/UI-PyQt6-41cd52)](https://www.riverbankcomputing.com/software/pyqt/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)
[![CI](https://github.com/Legendary-Brilliantforous/flashpilot/actions/workflows/ci.yml/badge.svg)](https://github.com/Legendary-Brilliantforous/flashpilot/actions)
[![Good First Issues](https://img.shields.io/github/issues/Legendary-Brilliantforous/flashpilot/good%20first%20issue)](https://github.com/Legendary-Brilliantforous/flashpilot/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22)
[![Contributors](https://img.shields.io/github/contributors/Legendary-Brilliantforous/flashpilot)](https://github.com/Legendary-Brilliantforous/flashpilot/graphs/contributors)

**Что это?** Linux-нативный аналог платных Windows-пакетов для прошивки — единый инструмент, который общается напрямую с bootloader'ом устройств **Samsung, MediaTek, Qualcomm и Spreadtrum/UNISOC**. Реверс-инжиниринг протоколов + нативная производительность Rust + красивый интерфейс PyQt6 = открытая альтернатива Odin, Heimdall и дорогим коммерческим инструментам.

---

## ✨ Почему этот проект важен

Мир ремонта Android держится на закрытых коммерческих инструментах только для Windows. Их протоколы реверс-инженерятся небольшим сообществом энтузиастов — и большая часть этих знаний заперта внутри платных пакетов или разбросана по форумам в неполном виде.

**Этот проект — наш ответ.** Он превращает эти реверс-инженеренные протоколы в чистую, аудируемую кодовую базу под лицензией MIT, которую каждый может читать, запускать, расширять — и поставлять как собственный пакет для прошивки.

| Коммерческий инструмент | Только Windows, закрытый код | Этот проект |
|---|---|---|
| Odin / Smart Switch | Windows, только GUI | Открытый протокол Odin (Rust, нативный) + инструменты PIT |
| MTK flash tools | Windows, закрытый DA | Прошивка и бэкап MTK BROM/DA (scatter + GPT) |
| Qualcomm EDL tools | Windows | Реализация протокола Sahara + Firehose |
| SPD/UNISOC tools | Windows | Реализация BSL в режиме clean-room |
| FRP / lock tools | Платные, серый рынок | Прозрачные потоки ADB + режим download, разблокировка MDM |

---

## 🚀 Особенности — 1.2.1 Stable (0 предупреждений)

- **9 режимов транспорта** — ADB, MTP, режим Samsung Download, Samsung BROM, MTK, MTK BROM, Fastboot, Qualcomm EDL, SPD.
- **13 категорий job'ов** — Прошивка firmware, Удаление FRP, Снятие блокировки экрана, Снятие MDM, Разблокировка оператора, Чтение информации об устройстве, Обнаружение устройств, Перезагрузка, Ремонт настроек, плюс per-chip EXPERIMENTAL: Knox / гарантия (Samsung), QCN / модем (Qualcomm), ремонт/смена IMEI (MTK/SPD/Qualcomm), eMMC / UFS.
- **Multi-device** — подключите несколько телефонов: панель подключения перечисляет каждый, каждая операция спрашивает, к какому телефону применяется (или выполняется молча, если совпадает только один), и разные телефоны могут выполнять операции параллельно (одна операция на устройство, STOP транслируется всем).
- **Rust-ядро (`flashpilot-bridge`, ~9.3k LOC) — 0 предупреждений `cargo check`** — raw USB с *встроенными libusb* (без системных зависимостей), реальные реализации протоколов (+ 18 подключённых мёртвых путей, trim ltcg -80KB).
  - **Samsung**: реверс-инженеренный протокол сессии Odin (на основе Heimdall), HID-полезные нагрузки режима download, чтение/запись/прошивка PIT — контекст `AT` сохраняется, чанкирование `EndpointConfig`.
  - **MediaTek**: рукопожатие BROM / preloader / DA, scatter & GPT, эксплойты BROM, ключи SLA — реальные проценты `ProgressReporter`.
  - **Qualcomm**: Sahara `ProtocolError` + Firehose `QcomDeviceInfo`, подключённые через таймауты `Duration`.
  - **SPD/UNISOC**: clean-room BSL — все `BSL_CMD/REP`, `iface`, `flush/read_flash/chip_uid/power_off` подключены.
  - Плюс **MTP**, **AT-команды** и полная сантехника **ADB**.
- **GUI уровня студии** — frameless translucent окно, 10 акцентных тем, анимированная сцена кабель/статус, живая консоль.
  - **Иконки брендов и разные фоны кнопок** — чёткие иконки брендов (Samsung Ⓢ, Apple красное яблоко 🍎, Motorola Ⓜ, LG Ⓛ и т. д.) и подобранные цвета фона бренда на каждой OEM-кнопке верхней панели чипов.
  - **Горизонтальные представления для Motorola и Apple** — платы действий моделей по умолчанию используют чистые горизонтальные табы.
  - **Микро-взаимодействия и glassmorphism** — плавные анимации появления страниц за 160 мс, моноширинная типографика бейджей метаданных (`Consolas`, `Monaco`) и улучшенные границы карточек glassmorphic.
  - **Большие центрированные диалоги (620px, перетаскиваемые, ✕)** — бета-гейт + стабильные `UPDATE/AHEAD/PATCH` + подтверждения flash/FRP, цвета чипов `MTK amber` `QCOM red` `SPD violet` `SAMSUNG blue`, высококонтрастный текст.
  - **Per-chip EXPERIMENTAL схлопываемые блоки** — Knox (Samsung), QCN/IMEI (Qualcomm), IMEI (MTK/SPD): янтарный баннер, чекбокс подтверждения владения при каждом запуске, `I UNDERSTAND` вводом текста для смены IMEI, запись в audit-лог.
  - **⏹ STOP** в заголовке останавливает все запущенные операции; блокировки per-device позволяют другим телефонам продолжать работать.

---

## 📸 Скриншоты

| Операции Samsung | Workbench MediaTek | Ремонт батареи | Загрузка SPD |
|---|---|---|---|
| ![Samsung](docs/samsung.png) | ![MediaTek](docs/mtk.png) | ![Battery](docs/battery.png) | ![SPD](docs/spd.png) |

---

## 🧩 Матрица возможностей

| Возможность | Samsung | MediaTek | Qualcomm | SPD/UNISOC | Любой ADB |
|---|---|---|---|---|---|
| Обнаружение / информация | ✅ | ✅ (+ crash preloader→BROM) | ✅ (Sahara) | ✅ | ✅ |
| Прошивка firmware | ✅ (Odin, нативный Rust) | ✅ (scatter + GPT) | ✅ (Firehose) | ✅ (FDL/regions) | — |
| Бэкап разделов | ✅ (EFS) | ✅ | ✅ | ✅ | — |
| Обход FRP | ✅ (ADB + download) | ✅ | ✅ (EDL) | ✅ | ✅ |
| Снятие блокировки экрана | ✅ | ✅ | ✅ (EDL) | — | ✅ |
| Разблокировка MDM | ✅ (ADB, QR, recovery) | — | — | — | — |
| Knox гарантия/обход (EXPERIMENTAL) | ✅ | — | — | — | — |
| QCN бэкап/восстановление + ремонт/смена IMEI (EXPERIMENTAL) | — | ✅ (NVRAM) | ✅ (NV 550/682) | ✅ (BSL NV) | — |
| Инструменты разделов | ✅ (PIT) | ✅ (GPT) | ✅ | ✅ (PAC extract/pack) | — |
| Низкоуровневые эксплойты | ✅ (HID/BROM) | ✅ (эксплойт BROM, SLA) | ✅ (Sahara) | ✅ (BSL) | — |
| Ремонт батареи / сети | — | — | — | — | ✅ |

> 💡 Разделы **Батарея** и **Сеть** работают на *любом* Android-устройстве с включённой USB-отладкой — никакого вендорного оборудования не требуется.

---

## 🖥️ GUI

Frameless, translucent окно с radius-карточками, живым **connection banner** (сцена компьютер → кабель → телефон с анимированным импульсом данных) над левым **nav rail** и правым **console/log pane**.

- **Connection bar** — живой список устройств (одна строка на телефон: модель · серийный · транспорты); клик по строке — инспекция. Кнопки операций спрашивают, какой телефон, если совпадает несколько.
- **Samsung** — подвкладки хаба Samsung: `ODIN FLASH · UNLOCK · ADVANCED FLASH · INFO & TOOLS`, плюс слоты firmware (AP/BL/CP/CSC/USERDATA), утилиты Odin и схлопываемый блок `KNOX — EXPERIMENTAL`.
- **MediaTek / Qualcomm / SPD** — выделенные workbench'и с нативными низкоуровневыми инструментами (scatter/DA + crash-to-BROM, programmer/XML + QCN/IMEI, бинари FDL + базовые адреса + IMEI), каждый со своим схлопываемым блоком `— EXPERIMENTAL`.
- **Battery** — здоровье fuel-gauge в %, температура/напряжение/ток, топ-потребители; ремонт в один клик.
- **Network** — состояние SIM, флаги данных/Wi-Fi, режим DNS; сброс радио и повторная регистрация.
- **Settings** — интервал автоскана, пути по умолчанию, автоочистка консоли, 10 акцентных тем, анимации (тогглы shake/rubber/cable/bubble), свечение окна, статус движка и встроенный `cargo build`.

**Горячие клавиши:** `F5` повторное сканирование · `Ctrl+Enter` запуск · `Ctrl+L` очистка консоли · `Ctrl+S` сохранение лога · `Ctrl+F` поиск.

---

## 📦 Быстрый старт

**Требования:** toolchain Rust, Python 3.10+, Linux-десктоп. Всё — libusb встроен.

```bash
# 1. Собрать Rust-мост (первая сборка компилирует libusb из исходников)
cargo build --release

# 2. (Рекомендуется) установить USB udev правила, чтобы телефоны работали без sudo
sudo bash root/setup-usb.sh

# 3. Окружение Python
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 4. Запуск
.venv/bin/python -m python.main        # или: python3 main.py
```

Прошивка Samsung в режиме download нативная (Rust Odin протокол) — никакой проприетарный бинарь odin4 не загружается, не поставляется и не требуется. Samsung combo firmware следует получать со страниц официальной поддержки Samsung или из доверенных архивов firmware.

---

## 🖥️ Поддержка платформ — нам важны ваши слова

**Linux — поддерживаемая платформа.** FlashPilot намеренно *Linux-нативный ответ на Windows-only пакеты прошивки* — разработка, тестирование и релизы ориентированы на Linux, и это не изменится.

**Windows / macOS сегодня не поддерживаются** по практическим причинам:

- USB в Windows — ад драйверов на каждый режим телефона (Zadig/WinUSB, QDLoader, драйверы Samsung мешают друг другу); большинство отчётов «телефон не обнаружен» невозможно отладить удалённо.
- macOS добавляет расходы на подпись/нотаризацию при почти нулевом спросе в ремонтных мастерских.
- Стек *портативен* (Rust + rusb, Python, Qt), так что это решение о сопровождении, а не техническая невозможность.

**Но это открытый вопрос, а не вердикт.** Если вам нужна поддержка Windows/macOS — или вы хотите навсегда отстаивать Linux-only — скажите нам:

- 💬 Откройте **[Discussion](https://github.com/Legendary-Brilliantforous/flashpilot/discussions)** с вашим кейсом (мастерская? лаборатория? какая ОС? какие телефоны?).
- 🔧 Код говорит громче: план — абстракция `python/core/platform.py` (`open_file_manager()`, `detach_kernel_drivers()`, `usb_device_path()`, `needs_udev_setup()`) с Linux как единственным бэкендом, чтобы порты становились аддитивными PR, а не форками. PR в этом направлении приветствуются уже сейчас.
- 🎨 Связано: контрибьюторы предложили **PySide6** (LGPL, лицензионно совместим с этим MIT-проектом) вместо PyQt6 (GPLv3). Высказывайтесь в той же Discussion — миграция механична, но сначала нужна GUI smoke-test coverage.

Никакое решение не примут без голосов контрибьюторов. Приходите и будьте одним из них.

### CLI / мост

```bash
./target/release/flashpilot-bridge detect          # all USB + Samsung filter (JSON)
./target/release/flashpilot-bridge fastboot-devices  # USB devices with a fastboot interface (JSON)
./target/release/flashpilot-bridge fastboot-cmd 22b8:2e80@2:16 20000 getvar securestate  # one raw fastboot command
./target/release/flashpilot-bridge mtk-detect      # MediaTek BROM (0e8d:0003) / preloader (0e8d:2000) / DA
./target/release/flashpilot-bridge mtk-crash-brom <bus:addr>  # crash preloader into held BROM
./target/release/flashpilot-bridge qcom-detect     # Qualcomm EDL
./target/release/flashpilot-bridge spd-detect      # Spreadtrum/UNISOC (VID 0x1782)
./target/release/flashpilot-bridge odin-pit 04e8:xxxx@bus:addr  # read PIT
./target/release/flashpilot-bridge at-send <t> ATI # AT over CDC ACM
./target/release/flashpilot-bridge adb-devices     # adb devices -l as JSON
```

---

## 📁 Структура репозитория

```
flashpilot/
├── src/                      # Rust bridge (~13k LOC) — ALL flows live here
│   ├── main.rs               #   command-line entry (80+ commands) + flow-run dispatch
│   ├── flows.rs              #   THE registry: FLOWS / JOBS / MODES (flow! macro, ~280 rows)
│   ├── usb/                  #   USB enumeration / interfaces / filtering (mod.rs + filtering.rs)
│   ├── devices.rs            #   merged USB+ADB device rows
│   ├── sam_download.rs       #   Samsung Download/Odin protocol (odin-* commands)
│   ├── mtk.rs mtk_da.rs      #   MediaTek BROM/DA flashing
│   ├── mtk_exploit.rs        #   BROM exploits (bypass/kamakiri2/crash-to-BROM)
│   ├── mtk_sla.rs            #   MediaTek SLA key handling
│   ├── qualcomm/             #   Sahara + Firehose + GPT (EDL)
│   ├── spd.rs                #   Spreadtrum/UNISOC BSL protocol (+ PAC)
│   ├── pac.rs                #   SPD PAC extract/pack
│   ├── pit.rs                #   Samsung PIT parser
│   ├── mtp.rs at.rs adb.rs   #   MTP, AT command, ADB plumbing
│   ├── fastboot.rs           #   native fastboot transport
│   ├── moto_flash.rs         #   Motorola staged fastboot FRP
│   ├── apple.rs              #   Apple usbmuxd/lockdown
│   ├── hid.rs bulk.rs        #   HID + bulk helpers
│   ├── fwtar.rs sparse.rs    #   firmware tar + sparse handling
│   ├── imgtools.rs           #   boot/vbmeta surgery
│   ├── hostinfo.rs           #   host eMMC/UFS health
│   ├── sam_*.rs              #   Samsung helpers (errors/setup)
│   └── config.rs error.rs util.rs
├── main.py                   # app entry (venv-safe launcher → python.gui.qt_app)
├── python/
│   ├── core/
│   │   ├── core.py           #   thin shim: mirrors Rust FLOWS/JOBS/MODES via bridge.flow_list()
│   │   ├── frp.py            #   FRP-only re-export surface (name == responsibility)
│   │   ├── devices.py        #   multi-device identity: stable keys, list, resolve, transport mapping
│   │   ├── bridge.py         #   talks to the Rust binary (+ per-key cancel)
│   │   ├── flow.py           #   Flow/Step primitives + cancellation
│   │   ├── jobs.py           #   FlashJob lifecycle (isolated job layer)
│   │   ├── cancel.py         #   cooperative cancellation registry
│   │   ├── mtk.py            #   MTK PIDs/stages/chips (0003=BROM, 2000=preloader)
│   │   ├── mtp.py            #   Samsung MTP/AT (multi-sequence ADB enable)
│   │   ├── pit.py pitstore.py  # Samsung PIT parser + cache
│   │   ├── adb.py            #   ADB helpers
│   │   ├── device_info.py    #   live device identity
│   │   ├── actions.py        #   action helpers
│   │   ├── experimental.py   #   per-run ack gates + audit log
│   │   ├── fus.py            #   Samsung FUS helpers
│   │   └── (no flows/ dir)   #   flows live in src/flows.rs; Python only delegates
│   └── gui/
│       ├── qt_app.py         #   the PyQt6 studio (~12k LOC)
│       ├── devices.py        #   brand→model→action drill-down pages
│       ├── nav.py            #   nav rail + OEM chip bar
│       ├── theme.py          #   tokens (accent vs focus_ring/sel_border) + QSS
│       ├── animations.py     #   Motion (shake/rubber serialized, no stuck state)
│       ├── toast.py          #   toast notifications
│       └── supported_devices.json  #   brand/model/chip research table
├── operations/               # per-operation docs + research (frp/mdm/flashing/…)
├── docs/                     # screenshots (fresh) + logo
├── root/                     # udev rules + setup-usb.sh
├── scripts/                  # dump-connected.sh, validate_mtp_at.py
├── INDEX.md CHANGELOG.md     # engineering index + release changelog
└── tests/                    # pytest suite (flow, MTK, PIT, odin safety, devices…)
```

---

## 🧑‍💻 Вклад

**Этот проект становится лучше только с вами.** Нам нужны сопровождающие, хакеры протоколов, GUI-дизайнеры, авторы документации и тестировщики.

- **[CONTRIBUTING.md](CONTRIBUTING.md)** — всё необходимое для старта.
- **Начните с лейбла [`good first issue`](https://github.com/Legendary-Brilliantforous/flashpilot/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22)** — отобранные задачи, дружелюбные к новичкам.
- Используйте шаблоны **[отчёта об ошибке](https://github.com/Legendary-Brilliantforous/flashpilot/issues/new?labels=bug&template=bug_report.yml)** / **[запроса функции](https://github.com/Legendary-Brilliantforous/flashpilot/issues/new?labels=enhancement&template=feature_request.yml)**.
- **Задачи для новичков** — каждая строка потока в `src/flows.rs` — возможность: добавьте строку `flow!(...)`, настройте последовательность команд, подключите новый комбо устройств. Python автообнаружит через `bridge.flow_list()`.
- **Фреймворк потоков (`src/flows.rs`) предельно прост** — новый метод — одна строка:

```rust
flow!("my_method", "My method", "Read Device Info", "ADB"),
```

Он автоматически появится в GUI. Вся петля вклада: **напишите строку потока — поставьте функцию.**
- **Правило multi-device** — никогда не берите «то» устройство; принимайте `key=None` (ambient scope) и фильтруйте по нему. См. `python/core/devices.py` и `CONTRIBUTING.md`.
- **Правила именования** — jobs идут глаголом вперёд (`Remove FRP`, а не `FRP bypass`); ключи потоков короткие snake_case (без префикса `flow_` в `FLOWS`); MTK PID'ы `0003`=BROM / `2000`=preloader (соглашение mtkclient — не меняйте их местами).

**Идеи, в которых мы хотели бы помощи:**
- Новые модели устройств / комбо firmware в таблицах потоков.
- Варианты DA MediaTek, scatter/GPT quirks.
- Граничные случаи rawprogram & patch XML Qualcomm.
- Дополнительные методы FRP / снятия блокировок по версиям Android.
- Пакетирование (Flatpak, AppImage, AUR, `cargo` + `pip`), CI, unit-тесты.
- Больше протоколов ODIN, инструменты eMMC/UFS, утилиты iCloud-adjacent и EDL.
- Переводы, темы и доступность.

---

## 🛡️ Безопасность и легальность

Инструмент общается напрямую с bootloader'ами и может стереть данные или превратить устройство в кирпич при misuse.

- Используйте только на **устройствах, которыми вы владеете или авторизованы обслуживать** (мастерские, обслуживающие телефоны клиентов с согласия).
- Всегда читайте предупреждения на экране и **делайте бэкап разделов** перед прошивкой.
- Обход FRP/MDM на устройстве, которое вам не принадлежит, может быть **незаконным в вашей юрисдикции** — вы отвечаете за то, как используете это ПО.
- FlashPilot поставляет payload'ы протоколов, необходимые для операций (MTK DA/BROM payloads, Qualcomm firehose programmers, Unisoc FDL1/FDL2, Samsung bootloaders), так же, как коммерческие пакеты прошивки. Образы firmware для конкретного телефона по-прежнему поступают от пользователя или вендора.

---

## 📄 Лицензия

MIT — см. [LICENSE](LICENSE). Константы протокола Odin происходят из проекта Heimdall (MIT), а справка BSL SPD — из clean-room описаний протокола (spd_cmd.h / доки Opus-Spreadtrum).

---

**Поставьте ⭐ этому репозиторию, откройте issue, пришлите PR — и давайте вместе соберём лучший открытый пакет для прошивки на Linux.**