# Интенсивный план улучшения UI FlashPilot

Language switcher: [English](../../ui-improvement.md) · [Français](../fr/ui-improvement.md) · [Español](../es/ui-improvement.md) · [Deutsch](../de/ui-improvement.md) · [简体中文](../zh/ui-improvement.md) · **Русский** · [Português](../pt/ui-improvement.md) · [日本語](../ja/ui-improvement.md) · [العربية](../ar/ui-improvement.md) · [हिन्दी](../hi/ui-improvement.md) · [Türkçe](../tr/ui-improvement.md)

> English is the canonical source. This page is a translation; help wanted — see [`../TRANSLATION.md`](../TRANSLATION.md).

## Цель
Трансформировать GUI PyQt6 из функционального монолита в отполированный, поддерживаемый и высокопроизводительный workbench, сохранив все Rust-backed потоки и multi-device поведение.

## Текущее состояние
- `python/gui/qt_app.py` (~15k LOC) — одно монолитное окно.
- Система тем (`theme.py`) централизована, но QSS большой и местами дублируется.
- Connection bar, nav rail, per-chip страницы, консоль, настройки — всё в одном файле.
- Сильная визуальная идентичность уже есть (glass cards, 10 акцентов, сцена кабеля).

## Принципы
1. Никакой protocol logic в Python; UI только отрисовывает и вызывает bridge.
2. Rust остаётся source of truth для flows/jobs/modes.
3. Улучшить отзывчивость: выносить тяжёлую работу из UI thread, снижать churn виджетов.
4. Доступность: навигация с клавиатуры, focus rings, screen-reader labels.
5. Поддерживаемость: разбить qt_app.py на feature-модули.

## Phase 0 — Window shell, logo, splash (new)
- Заменить текущий логотип на профессиональную vector/SVG-метку (монохром + accent-варианты, 16/32/64/128/256px + .ico/.icns).
- Splash screen: анимированная brand mark, стадии прогресса (init Rust bridge, scan devices, load theme), версия, без flicker; fade-in/out 200мс.
- Window rendering: frameless translucent окно с compositor-friendly alpha, rounded corners, drop shadow, DPI-aware масштабирование, память placement на нескольких мониторах.
- Smoothness: включить Qt AA_UseHighDpiPixmaps, задать surface format (OpenGL/RGBA), анимации с vsync, снизить layout thrash; цель 60fps взаимодействий.
- Branding: единообразный логотип в title bar, taskbar, about dialog, installer.
- Resizable shell columns: граница **device panel | page** — перетаскиваемый горизонтальный splitter (по умолчанию 232px, перетаскивание 228–420px, запоминается в `layout/device_panel_width`). Страница сохраняет естественную ширину и живёт во frame-less scroll area, поэтому сжатие скроллит её по горизонтали вместо reflow табов/сетки; ширина панели удерживается при resizes окна, пока пользователь её не перетащит. _Decision (user): ранее было жёсткое `setFixedWidth(232)`._

## Phase 1 — Architecture split (no visual change)
- Вынести page builders в `python/gui/pages/`:
  - `samsung.py`, `mtk.py`, `qc.py`, `spd.py`, `battery.py`, `network.py`, `settings.py`, `quick.py`.
- Вынести shared widgets в `python/gui/widgets/`: `metric_card.py`, `collapsible.py`, `console.py`, `device_picker.py`.
- Оставить `qt_app.py` shell: window chrome, nav, routing, signals.
- Критерии приёмки: app boots, all tabs render, tests pass.

## Phase 2 — Performance
- Виртуализовать device list и console log (QAbstractListModel + QListView), чтобы избежать O(n) создания виджетов.
- Пакетировать обновления логов (flush каждые 50мс или 100 строк).
- Кэшировать отрендеренный QSS per theme; перегенерировать только при смене акцента.
- Lazy-load тяжёлых страниц (строить при первом визите).
- Критерии приёмки: 10k строк лога без UI stall; scroll stays 60fps.

## Phase 3 — Visual polish
- Токены дизайна: шкала отступов (4/8/12/16/24), шкала радиусов, elevation.
- Единообразная elevation/shadow карточек; состояния hover/focus.
- Motion: появление страницы 120мс, масштаб нажатия кнопки, выезд toast.
- Система иконок: заменить emoji на SVG-иконки (brand glyphs).
- Empty states и skeletons для device detection.
- Режим высокой контрастности + тоггл reduced-motion.

## Phase 4 — UX flows
- Единый диалог выбора устройства с поиском/фильтром и transport badges.
- Прогресс операций: список шагов с галочками, ETA, отмена per device.
- Представление ошибок: actionable cards с «retry / open docs / copy log».
- Настройки: searchable, сгруппированные, с reset-to-defaults.
- Консоль: фильтр по level/device, экспорт, поиск.

## Phase 5 — Accessibility & i18n
- Полный порядок Tab, видимый focus, ARIA-подобные labels.
- Сочетания клавиш задокументированы в приложении.
- Извлечение строк для переводов (никаких hardcoded user strings в виджетах).

## Phase 6 — Testing
- GUI smoke tests с pytest-qt (headless).
- Visual regression screenshots для каждой страницы/темы.
- Performance benchmarks для рендеринга лога/устройств.

## Deliverables
- `python/gui/pages/*`, `python/gui/widgets/*`
- Обновлённая token-система `theme.py`
- `tests/test_gui_smoke.py`
- Обновление доков в README/INDEX.

## Risks
- 15k LOC монолит; требуется инкрементальная выемка.
- Правила потоков PyQt; все касания виджетов — только в main thread.
- Сохранить multi-device scoping и семантику cancel.

## Suggested first task
Вынести `_build_console` и `_build_conn_bar` в `widgets/console.py` и `widgets/connection_bar.py` с signal-based API; без изменения поведения.

## Phase 7 — Flow & Job Rendering (new)
### Проблемы, которые наблюдаются
- `_add_job_flows` сваливает все режимы в один список кнопок на job; режим есть только в tooltip — путаница.
- Дублирующиеся кнопки по страницам (Quick, chip ops sections, вкладки Unlock) с неконсистентным гейтированием.
- Экспериментальные/деструктивные кнопки различаются только цветом/границей; легенды нет.
- Нет поиска/фильтра, недавно использованных, избранного.
- Длинные flow labels непредсказуемо overflow'ятся/переносятся в FlowLayout.
- Нет визуальной группировки по риску (read-only vs flash vs experimental).

### Предлагаемая модель рендеринга
- **Job → Mode → Method** трёхуровневая навигация:
  - Слева: список Job'ов (глагол на первом месте, иконки).
  - В середине: вкладки Mode (ADB, MTP, …) со счётчиками.
  - Справа: карточки Method (имя, risk badge, experimental badge, tooltip).
- Единый source of truth: `core.modes_for` / `core.methods_for`; никаких дублей списков на страницах.
- Глобальная дедупликация по (job, mode, key); chip-страницы фильтруют по supported modes вместо повторного `_add_job_flows`.
- Состояния карточки Method: enabled/disabled по device capability gates, running (spinner), last result (ok/fail).

### Что вынести
- Построение кнопок перенести из `_add_job_flows` в `widgets/flow_button.py` + `widgets/method_card.py`.
- Перенести перечисление mode/job в модель `FlowRegistryView` (тонкая, без логики) для UI binding.
- Перенести confirm-логику destructive/experimental в переиспользуемый `ConfirmDialog`.

### Что объединить
- Объединить Quick page и chip ops pages так, чтобы они использовали один и тот же виджет `FlowBrowser` с фильтром `modes`.
- Объединить обработку experimental warning в badge карточки + диалог.

### Что убрать / дедуплицировать
- Убрать per-page вызовы `_add_job_flows`, дублирующие одни и те же flow'ы; заменить на отфильтрованный `FlowBrowser`.
- Убрать дублирующиеся экземпляры `Flow` (один key под несколькими modes), группируя modes на карточке.
- Убрать сырые `QLabel(job.upper())` заголовки в пользу section headers со счётчиками.

### Новые возможности
- Поле поиска фильтрует по имени job/mode/method и key.
- Избранное/недавние, сохраняемые в настройках.
- Легенда рисков: read-only (зелёный), medium (янтарный), high (красный), experimental (пунктирный янтарный).
- Пакетный выбор: чекбоксы для постановки в очередь нескольких методов (последовательный запуск с per-step cancel).
- Drag-to-reorder избранного.

### Критерии приёмки
- Единый flow browser на всех страницах.
- Никаких дублирующихся method-кнопок для одного (job, mode, key).
- Поиск фильтрует <50мс для 280 строк.
- Capability gates визуально отключают методы с reason tooltip.

### Phase 7 — статус (реализовано на данный момент)
- **Выбранная форма: in-page upgrade.** Ввести единый путь рендеринга сейчас и обновлять его на месте — `FlowBrowser` (view) + `MethodCard` (button) + `flow_meta` (routing/risk) — *без* трёхпанельной навигации Job → Mode → Method пока. Страницы сохраняют текущую раскладку; `_add_job_flows` строит строки и рендерит их через `FlowBrowser`, а клики маршрутизируются через `flow_meta.route_for`.
- **Производная risk-модель** (`flow_meta.risk_for`, единственный источник, который может читать badge): `experimental` = key в `_EXPERIMENTAL_FLOW_MAP`; `high` = key в `_DESTRUCTIVE_CONFIRM` и поэтому **точно те flow'ы, которые UI уже просит подтвердить** (badge не может заявить `high` без диалога, и не может заявить `read` без read-only); `read` = только для `READ_ONLY_JOBS` (`{"Read Device Info", "Detect Devices"}`); всё остальное, включая неизвестные ключи/job'ы, fail closed в `medium`.
- **Slice B1 — групповой рендеринг потоков (этот slice).** `FlowBrowser.set_rows` теперь группирует то, что рендерит, исправляя три названные проблемы:
  - Заголовок job'а теперь `{"REMOVE FRP"} · 6` — сырой `QLabel(job.upper())` получил **счётчик** методов (приглушённый токеном `border_hi`, имя сохраняет существующую обработку 11px / 800 / 1px).
  - Внутри каждого job карточки группируются по **транспорту** за маленьким sub-heading режима (`— ADB`), вместо одного плоского списка на job с режимом только в tooltip. Строки приходят mode-major из `_flow_rows`, так что прогон равных режимов — одна секция; ни один режим никогда не разворачивается в дополнительные карточки.
  - Каждый `MethodCard` рисует семантический **левой край** (`ok` read-only, `warn` medium, `err` high, `experimental` experimental), наложенный поверх `_btn_ghost()`, так что риск виден с первого взгляда рядом с существующей легендой. Экспериментальные карточки сохраняют янтарную **пунктирную** границу — теперь ей владеет `MethodCard.set_risk(level)`; `set_state` остаётся inert.
  - По конструкции не изменилось: набор отрендеренных строк, правило дедупа ("first mode wins" per job), текст кнопки (`btn_sha`), каждая tooltip-строка, click routing, confirm/experimental overlays и gate registry (`job=`/`mode=`, никогда `command=`). Добавлены только виджеты группировки/меток.
- **Золотой инвентарь сознательно перегенерирован.** `tests/ui_inventory_golden.json` был пересобран с `REGEN_INVENTORY=1` в этом slice. Единственная разница — per-page **количество виджетов** (добавленные mode sub-heading labels; +113 виджетов на пяти flow-heavy страницах). `gated_count`, `gated_unique_triples`, `gated_triples_sha256`, `core_flows`, `action_meta` и `buttons`/`acts`/`btn_sha` каждой страницы байт-идентичны — gate registry и click surface не сдвинулись.
- **Slice B2 — доска модели устройства (вертикальные action cards) (этот slice).** Строки per-action на model page теперь — карточки `ActionRow` (`python/gui/widgets/action_row.py`) вместо 50px hand-rolled `QFrame` с monkeypatched `mousePressEvent`:
  - **3px семантический левый край** (`err` для wipe/destructive действий, иначе `accent_hi`) — тот же язык risk-edge, который `MethodCard.set_risk` рисует в flow browser,
  - **тайл иконки 40x40**, заголовок **13px / 800** и **однострочное elided** описание. Это чинит проблему плана «long flow labels overflow / wrap unpredictably»: описание эллипсисится вместо переноса, так что длинный label никогда не сможет заставить доску шире её панели и не прочитается как рваный многострочный блок,
  - опциональный engine/mode **chip** и тусклый **`›` chevron**; hover / pressed / focus принадлежат виджету (QSS dynamic property + focus ring). Чип рисуется как **single-hue pill** из accent-цвета, который уже возвращает `common._mode_chip` (accent tint fill, accent text, accent hairline border), так что каждый badge читается как одно семейство,
  - **доступность с клавиатуры** — `StrongFocus` + Enter / Return / Space эмитят сигнал `activated` (заменяя monkeypatched `mousePressEvent`). Доска сохраняет свои теги `flow_act` / `flow_tip` и лишь подключает `activated`, так что routing не меняется,
  - group containers теперь несут **счётчик** действий job'а (`FRP REMOVE · 4`) — тот же язык name + count, который используют заголовки job'ов flow browser.
- **Инварианты соблюдены.** `_ACTION_META` всё ещё **62** записи; `acts` и `btn_sha` каждой страницы `dev_*` байт-идентичны (ни одна action row, текст кнопки или кнопка не добавлена/удалена/переименована); `gated_count` **418**, `gated_triples_sha256` `c89acce…7d75`, `gated_unique_triples` **61**, `core_flows` **116**, `stack_count` **25**. Естественная минимальная ширина стека страниц всё ещё **699px**, что доказывает: elided-метки ничего не расширили.
- **Золотой инвентарь сознательно перегенерирован.** `tests/ui_inventory_golden.json` пересобран с `REGEN_INVENTORY=1`: единственная разница — per-page **количество виджетов** (`dev_apple` 59→63, `dev_motorola` 85→99 — добавленные карточки/метки двух исследованных досок). Транзитный md5 золотого после B2 был `929f428638e91a42865ddde1ac96dd19`. Последующая полировка этого slice'а (single-hue chip family и first-show device-panel split) **не меняла** ни одного количества виджетов страниц, поэтому золотому **не нужен** был дальнейший regen.
- **Slice B4 — доска модели заполняет высоту страницы (этот slice).** На device → model board (`devices.build_brand_page`) двухпанельный split row не получал высоту страницы, так что большой пустой бэнд оставался **под обеими панелями**. В окне 1600x951 (внешний viewport страницы `878x717`) панели измерялись `left 250x313 / right 598x333` при **333px мёртвой зоны** снизу, и action board получал только `333` из `717`px. Корневая причина: split row был добавлен в `outer` **со stretch 1** *и* сразу после него добавлен завершающий `outer.addStretch(1)` — два stretched-элемента делили leftover вертикальное пространство ~50/50, и ни одна панель не была вертикально `Expanding`, так что ничего его не поглощало. Фикс (хирургический, только в `build_brand_page`): убрать конкурирующий завершающий stretch (split row теперь забирает **всю** leftover высоту) и задать левой `list_col` и правой `right_stack` явную вертикальную политику `Expanding`, чтобы внутренний `lscroll` и `_scroll` текущей model page получали полную высоту и владели своими scrollbar'ами. Левые строки остаются top-aligned (`lv2.addStretch(1)` нетронут), и скроллятся, когда список растёт. После: `left 250x646 / right 598x665`, мёртвая зона **1px** (только нижний margin layout'а 8px), правая доска показывает far more flows и скроллит остальное внутри (`vscroll_max` 900 → 557), а внешний `_page_scroll` shell остаётся скрытым (`verticalScrollBar().maximum() == 0`). В поддержку будущего требования пользователя, 40 дополнительных in-memory моделей увеличивают **left** scroll range (`vscroll_max > 0`) **без** изменения высоты любой панели.
  - Новые тесты: `tests/test_device_board_layout.py` —
    `TestBrandPageFillsHeight::test_no_dead_band_below_split`,
    `::test_both_panes_get_the_real_height`,
    `::test_right_board_scrolls_its_own_content`,
    `::test_more_devices_scroll_left_without_growing_the_panes`. Оба геометрических теста были подтверждены **падающими** на неисправленном коде сначала (мёртвая зона 295px при H=640; левая панель 275px против floor 412px) до фикса.
  - **Виджет не добавлен и не удалён** (изменилась только size policy и был снят stretch spacer), так что ни одна страница не сдвинула количество виджетов и `tests/ui_inventory_golden.json` **не требовал** regen — всё ещё `929f428638e91a42865ddde1ac96dd19`.
- **Slice C — полный реестр потоков на device board (ОТКАЧЕН).** Этот slice добавлял финальную группу `MORE FLOWS · N`, рендерящую полный flow registry движка устройства как карточки `ActionRow`, плюс text/mode filter bar. Он был scoped по **engine + transport mode**, что не то же самое, что *функции этого устройства*: любой телефон, выставляющий ADB, поэтому вытягивал все ADB-зарегистрированные flow'ы из реестра, так что motorola board предлагал Samsung-only job'ы (`knox_bypass`, `kg_remove`, `odin_flash_tar`), `imei_repair_spd`, `apple_icloud_*` и `huawei_frp_guide`. Хуже того, модели Motorola несут **per-model engines** (`Moto G13` = `spd`, `G24` = `mtk`, `G6` = `qcom`), так что `planned`-модели показывали целый SPD/MTK registry для неготовой работы, а бренды motorola/apple обходят гейт `researched` на доске by design. Откачено целиком: группа реестра, её filter bar, `_ENGINE_MODES`, first-show deferral и `tests/test_device_flows.py` ушли; доска снова — ровно curated actions per-device. Золотой инвентарь был байт-идентичным на всём протяжении (`929f428638e91a42865ddde1ac96dd19`), потому что группа строилась lazily, так что откат не требует regen.
  - Урок для любого повторного захода: scope по **собственным declared `actions` модели** (`supported_devices.json`), расширяя только flow'ы, к которым эти actions реально диспатчат — никогда по engine + mode.
  - Выживший и переиспользуемый веттированный факт: `win._route_flow_activation(job, mode, key, label)` — единственный sink, применяющий destructive confirm и(EXPERIMENTAL ownership ack); `_dispatch`/`start_model_action` — нет (его experimental check — узкий набор `devices._EXPERIMENTAL_ACTS`, так что, напр., `emmc_raw` запустился бы без ack).
- **Отложено (всё ещё):** search box / mode filter chips поверх per-device flow list, favourites/recents (settings-persisted), batch-selection queue (checkboxes + sequential run), drag-to-reorder, трёхпанельная навигация Job → Mode → Method, расширение mode-вариантов job'а в дополнительные карточки (одна карточка на `(job, mode, key)` — сознательное более позднее решение; этот slice НЕ расширяет modes) и переиспользуемый `ConfirmDialog` (confirm/experimental overlays остаются window-owned modals).

## Phase 8 — Professional polish & differentiation (new)
### Визуальная идентичность
- Фирменная «atelier» тёмная тема с тонкой grain/noise-текстурой и soft vignette.
- Brand mark + монограмма; единообразная иконография (Lucide-style) по всем action'ам.
- Hero cards устройств: силуэт изображения модели, chip, transport badges, last-seen.
- Обновлённая анимированная connection scene: реальный импульс кабеля, per-device status dots.

### Информационная плотность
- Схлопываемая inspector panel: детали выбранного устройства, partitions, PIT summary, logs.
- Timeline view операций (start/end, duration, result) per device.
- Diff view для изменений PIT/partition перед прошивкой.

### Безопасность и доверие
- Pre-flight checklist card перед destructive ops (устройство, firmware, совпадение PIT).
- Чёткая risk ladder с цветом + иконкой + текстом; никогда не только цветом.
- Audit log viewer (experimental actions) с экспортом.

### Продуктивность
- Command palette (Ctrl+K) для поиска flows, devices, settings.
- Глобальный поиск по логам и устройствам.
- Навигация keyboard-first; overlay сочетаний (?).
- Session restore: переоткрыть last device + page.

### Linux-native feel
- Нативные file dialogs, system theme awareness, обработка Wayland/X11.
- Desktop notifications для долгих ops; tray icon с прогрессом.
- Drag-and-drop firmware-файлов на flash page.

### Onboarding
- First-run wizard: udev setup, статус bridge build, device test.
- Empty states с иллюстрациями и next steps.
- Contextual help drawer с per-flow docs из `operations/`.

### Branding assets
- Новый набор логотипов, splash, installer graphics, app icon.
- Обновлённые скриншоты README под новый UI.

## Phase 9 — Console / terminal redesign (new)
### Цель
Сделать log console читаться как first-class Linux terminal (эстетика UEFI-shell/TTY) вместо сжатого текстового блока.

### Раскладка
- Выделенный **правый** док в горизонтальном splitter'е (страницы слева, консоль справа); resizable, сворачивается в thin bar. Ширина по умолчанию 420px, минимум 360px (измеряется по собственной control row дока, чтобы ничего не клипалось).
  _Decision (user): консоль остаётся справа — более ранний черновик этой фазы говорил «bottom dock / 35% height»; он устарел._
- Широкий моноширинный terminal с комфортным padding (16px), line height 1.45.
- Опциональный full-screen terminal mode (F11) с минимальным chrome.
- Per-device tabs или filter chips, чтобы логи не перемешивались.

### Стилистика
- Тёмная TTY-палитра: чёрный фон, green/amber/cyan текст, опциональная subtle scanline.
- ANSI color support для bridge output; bold headers, dim timestamps.
- Тоггл line numbers / timestamps.
- Выделение + копирование; right-click menu (copy, save, clear, filter).

### Поведение
- Streaming с backpressure; никакого UI freeze на 10k+ строк.
- Поиск с regex, подсветка совпадений, переход next/prev.
- Экспорт в файл; auto-save session log.
- Фильтр по устройству и уровню (info/warn/error/step).

### Not squeezed
- Минимальные width/height constraints; responsive wrapping; горизонтальный scroll для длинных строк.
- Resizable columns для timestamp/level/device.

## Phase 10 — Console messages & toast system (new)
### Console messages
- Структурированные log entries: timestamp, device key, level, message.
- Color-coded уровни: info (slate), success (green), warn (amber), error (red), step (cyan).
- Схлопываемый multi-line output (stack traces, JSON) с «show more».
- Inline progress bars для шагов прошивки; per-step status icons.
- Кликабельные device keys для фокуса устройства; кликабельные flow keys для открытия docs.

### Toasts
- Неблокирующие, stacked toasts с icon, title, message, action button.
- Auto-dismiss с progress bar; пауза при hover.
- Severity styles (info/success/warn/error) с единообразной палитрой.
- Ограничение очереди (max 3 visible) с overflow counter.
- Позиционирование (top-right/bottom-right) и поддержка reduced-motion.
- Опционально sound/haptic для ошибок.

## Phase 12 — HiProTool parity research (new)
### Статус
- Онлайн-поиск недоступен в этом окружении (HTTP 402). Требуется ручное исследование.

### Research tasks
- Собрать feature list HiProTool (FRP, MDM, screen lock, carrier, IMEI, flashing).
- Сопоставить каждый метод с движком (ADB, download mode, BROM, EDL, fastboot, SPD).
- Выявить device-specific shortcuts и prerequisites.
- Задокументировать в `operations/` с шагами верификации и safety notes.
- Приоритизировать high-value, low-risk методы первыми.

## Phase 14 — Next features (new)
### Целевые фичи
- Удаление IMEI из blacklist (исследование + device-specific playbooks).
- Улучшения carrier unlock (SIM lock, пути NVDATA/QCN).
- Улучшения MDM unlock (device owner, QR provisioning, recovery).
- Улучшения FRP (per-chip/per-Android-version методы).
- Улучшения снятия screen lock (ADB, recovery, download, EDL).
- Удаление Samsung Knox Guard (EXPERIMENTAL, audit-logged).
- Удаление Apple MDM enrollment (profile/DEP).
- Инструменты Samsung Knox management.
- Обработка Android Enterprise enrollment.
- Обработка Zero-touch enrollment.
- Удаление Apple Activation Lock (scope checkm8/DFU, честные лимиты).
- Получение SIM PUK для разблокировки SIM PIN.
- Снятие biometric lock (исследование, device limits).

### Примечания
- Каждая фича должна быть Rust-backed и размечена EXPERIMENTAL там, где рискованна.
- Документировать в `operations/` с верификацией и safety notes.

## Phase 15 — Documentation audit & cleanup (new)
### Найденные устаревшие ссылки (исторические/снятые)
- `operations/*/README.md` упоминают retired Python modules (`knox.py`, `qcn.py`, `health.py`, `apple.py`, `flows/*.py`) как контекст; допустимо, но надо явно пометить historical.
- `INDEX.md` ранее ссылался на отсутствующий `SPLIT_PLAN.md` (исправлено).
- `README.md` repository layout ранее перечислял несуществующие модули (исправлено).
- `DESCRIPTION.md` имел неверные счётчики transport/job (исправлено).

### Оставшиеся doc-задачи
- Нормализовать все заметки «retired» в один раздел «History» per file.
- Добавить заметку «Current architecture» в начале каждого operations README.
- Удалить или заархивировать устаревшие migration plans (DESIGN.md → new version).
- Оставить `operations/` только research; кодовые указатели должны говорить `src/flows.rs`.