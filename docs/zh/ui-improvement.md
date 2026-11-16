# FlashPilot 密集 UI 改进计划

Language switcher: [English](../../ui-improvement.md) · [Français](../fr/ui-improvement.md) · [Español](../es/ui-improvement.md) · [Deutsch](../de/ui-improvement.md) · **简体中文** · [Русский](../ru/ui-improvement.md) · [Português](../pt/ui-improvement.md) · [日本語](../ja/ui-improvement.md) · [العربية](../ar/ui-improvement.md) · [हिन्दी](../hi/ui-improvement.md) · [Türkçe](../tr/ui-improvement.md)

> English is the canonical source. This page is a translation; help wanted — see [`../TRANSLATION.md`](../TRANSLATION.md).

## 目标
将 PyQt6 GUI 从功能性的单体架构转变为精致、可维护、高性能的工作台，同时保留所有由 Rust 支撑的流程与多设备行为。

## 当前状态
- `python/gui/qt_app.py`（约 15k 行代码）是单体窗口。
- 主题系统（`theme.py`）已集中化，但 QSS 在某些地方较大且重复。
- 连接栏、导航栏、每个芯片的页面、控制台、设置都在同一文件中。
- 已经存在很强的视觉标识（玻璃卡片、10 种强调色、电缆场景）。

## 原则
1. Python 中不得包含协议逻辑；UI 仅负责渲染并调用桥接。
2. 保持 Rust 为流程/任务/模式的真相来源。
3. 提高性能：把重活移出 UI 线程，减少组件 churn。
4. 可访问性：键盘导航、聚焦环、屏幕阅读器标签。
5. 可维护性：将 `qt_app.py` 拆分为功能模块。

## Phase 0 — 窗口外壳、logo、启动画面（新增）
- 将当前 logo 替换为专业的矢量/SVG 标记（单色 + 强调色变体，尺寸 16/32/64/128/256px，加 `.ico`/`.icns`）。
- 启动画面：动画品牌标记、进度阶段（初始化 Rust 桥接、扫描设备、加载主题）、版本号、无闪烁；淡入/淡出 200ms。
- 窗口渲染：支持 compositor 的带 alpha 无边框半透明窗口、圆角、投影、DPI 感知缩放、多显示器位置记忆。
- 流畅度：启用 Qt `AA_UseHighDpiPixmaps`，设置表面格式（OpenGL/RGBA），vsync 友好动画，减少布局 thrash；目标 60fps 交互。
- 品牌：标题栏、任务栏、关于对话框、安装器中使用一致的 logo。
- 可调整外壳列：**设备面板 | 页面** 边界是可拖拽的水平分隔条（默认 232px，可拖拽范围 228–420px，记录在 `layout/device_panel_width`）。页面保留自身自然宽度，并位于无框滚动区域中，因此压窄它时横向滚动而非重新流式布局其标签/网格；面板宽度在窗口尺寸变化时保持不变，除非用户拖动它。_用户决策：此前是硬编码的 `setFixedWidth(232)`。_

## Phase 1 — 架构拆分（无视觉变化）
- 将页面构建器提取到 `python/gui/pages/`：
  - `samsung.py`、`mtk.py`、`qc.py`、`spd.py`、`battery.py`、`network.py`、`settings.py`、`quick.py`。
- 将共享小组件提取到 `python/gui/widgets/`：`metric_card.py`、`collapsible.py`、`console.py`、`device_picker.py`。
- 保留 `qt_app.py` 作为外壳：窗口 chrome、导航、路由、信号。
- 验收：应用启动，所有标签渲染，测试通过。

## Phase 2 — 性能
- 虚拟化设备列表与控制台日志（`QAbstractListModel` + `QListView`），避免 O(n) 的小组件创建。
- 批量日志更新（每 50ms 或 100 行 flush 一次）。
- 每主题缓存渲染后的 QSS；仅在强调色变化时重新生成。
- 延迟加载重页面（首次访问时构建）。
- 验收：10k 日志行无 UI 卡顿；滚动保持 60fps。

## Phase 3 — 视觉打磨
- 设计令牌：间距比例（4/8/12/16/24）、圆角比例、elevation。
- 一致的卡片 elevation/投影；悬停/聚焦状态。
- 动效：页面淡入 120ms、按钮按下缩放、Toast 滑入。
- 图标系统：用 SVG 图标替换 emoji（品牌字形）。
- 设备检测的空状态与骨架屏。
- 高对比度模式 + 减少动态效果开关。

## Phase 4 — UX 流程
- 统一设备选择器对话框：搜索/过滤、传输 badges。
- 操作进度：带勾选标记的步骤列表、ETA、按设备取消。
- 错误展示：可操作的卡片，带“重试 / 打开文档 / 复制日志”。
- 设置：可搜索、分组、支持恢复默认。
- 控制台：按级别/设备过滤、导出、查找。

## Phase 5 — 可访问性 & i18n
- 完整的 Tab 顺序、可见聚焦、ARIA-like 标签。
- 应用内文档化的键盘快捷键。
- 字符串提取以支持翻译（小组件中无硬编码用户字符串）。

## Phase 6 — 测试
- 使用 pytest-qt 的 GUI 冒烟测试（headless）。
- 每个页面/主题的视觉回归截图。
- 日志/设备渲染的性能基准。

## 交付物
- `python/gui/pages/*`、`python/gui/widgets/*`
- 更新后的 `theme.py` 令牌系统
- `tests/test_gui_smoke.py`
- README/INDEX 的文档更新。

## 风险
- 15k LOC 单体；需要增量提取。
- PyQt 线程规则；所有小组件操作必须在主线程。
- 保留多设备作用域与取消语义。

## 建议的首个任务
将 `_build_console` 与 `_build_conn_bar` 提取到 `widgets/console.py` 与 `widgets/connection_bar.py`，采用基于 signal 的 API；不改变行为。

## Phase 7 — 流程与任务渲染（新增）
### 发现的问题
- `_add_job_flows` 把所有模式展平为每个 job 一个按钮列表；模式仅出现在 tooltip，造成混淆。
- 跨页面重复按钮（Quick、chip ops sections、Unlock tabs），门禁不一致。
- 实验性/破坏性按钮仅靠颜色/边框区分；没有图例。
- 无搜索/过滤、无最近使用、无收藏。
- 长流程标签在 `FlowLayout` 中不可预测地溢出/换行。
- 没有按风险视觉分组（只读 vs 刷写 vs 实验性）。

### 提议的渲染模型
- **Job → Mode → Method** 三级导航：
  - 左：Job 列表（动词优先，带图标）。
  - 中：Mode tabs（ADB、MTP 等）带计数。
  - 右：方法卡片（名称、风险徽章、实验性徽章、tooltip）。
- 单一真相来源：`core.modes_for` / `core.methods_for`；页面中无重复列表。
- 按 `(job, mode, key)` 全局去重；芯片页面按支持的模式过滤，而不是重新运行 `_add_job_flows`。
- 方法卡片状态：按设备能力门禁启用/禁用、运行中（spinner）、最近结果（ok/fail）。

### 待迁移内容
- 把按钮构造从 `_add_job_flows` 迁入 `widgets/flow_button.py` + `widgets/method_card.py`。
- 把模式/job 枚举迁入 `FlowRegistryView` 模型（轻量，无逻辑）供 UI 绑定。
- 把破坏性/实验性确认逻辑迁入可复用的 `ConfirmDialog`。

### 待合并内容
- Quick 页面与芯片操作页面合并，使用同一 `FlowBrowser` 小组件并带 `modes` 过滤。
- 实验性警告处理合并进卡片徽章 + 对话框。

### 待移除 / 去重
- 移除重复同一作业流程的逐页 `_add_job_flows` 调用；替换为过滤后的 `FlowBrowser`。
- 移除重复的 `Flow` 实例（同一 key 在多个模式下）并按卡片分组模式。
- 用带计数的 section 标题替换原始 `QLabel(job.upper())` 标题。

### 新功能
- 搜索框按 job/mode/method 名称与 key 过滤。
- 收藏/最近使用持久化在 settings 中。
- 风险图例：只读（绿色，`read`）、中等（琥珀色，`medium`）、高（红色，`high`）、实验性（琥珀色虚线，`experimental`）。
- 批量选择：复选框排队多个方法（按步骤顺序运行，每步可取消）。
- 收藏拖拽排序。

### 验收
- 所有页面使用一致的 flow browser。
- 同一 `(job, mode, key)` 不再有重复方法按钮。
- 280 行搜索过滤 <50ms。
- 能力门禁在视觉上禁用方法，并用 tooltip 给出原因。

### Phase 7 — status（已实现部分）
- **选定形态：页内升级。** 现在就引入单一渲染路径，并在原地升级——`FlowBrowser`（视图）+ `MethodCard`（按钮）+ `flow_meta`（路由/风险）——目前 **尚未** 引入 Job → Mode → Method 三栏导航。页面保留当前布局；`_add_job_flows` 构建行并经由 `FlowBrowser` 渲染，点击经由 `flow_meta.route_for` 路由。

- **派生风险模型**（`flow_meta.risk_for`，徽章唯一可读取的来源）：`experimental` = key 在 `_EXPERIMENTAL_FLOW_MAP` 中；`high` = key 在 `_DESTRUCTIVE_CONFIRM` 中，因此 **恰好是 UI 已经要求确认的流程**（徽章不能在没有对话框时声称 `high`，也不能在非只读时声称 `read`）；`read` = 仅针对 `READ_ONLY_JOBS`（`{"Read Device Info", "Detect Devices"}`）；其余全部，包括未知 key/job，都 fail closed 到 `medium`。

- **Slice B1 — 分组的流程渲染（本切片）。** `FlowBrowser.set_rows` 现在对所渲染内容进行分组，修复了三个具名问题：
  - 作业标题现在是 `{"REMOVE FRP"} · 6` —— 原始 `QLabel(job.upper())` 增加了方法 **计数**（使用 `border_hi` 令牌弱化，名称保留现有的 11px / 800 / 1px 处理）。
  - 在每个作业内，卡片按 **传输模式** 分组，前面带一个小的模式子标题（`— ADB`），而不是按作业平铺列表且模式仅在 tooltip 中。行从 `_flow_rows` 按 mode-major 到达，因此相同模式的连续行是一个分组；模式从不会展开为额外卡片。
  - 每个 `MethodCard` 在 `_btn_ghost()` 之上绘制语义化的 **左边缘**（`ok` 只读、`warn` 中等、`err` 高、`experimental` 实验性），使风险与现有图例一眼可见。实验性卡片保留其琥珀色 **虚线** 边框——现在由 `MethodCard.set_risk(level)` 拥有；`set_state` 保持惰性。
  - 构造上不变：渲染的行集、去重规则（每个作业 “first mode wins”）、按钮文本（`btn_sha`）、每个 tooltip 字符串、点击路由、确认/实验性覆盖层，以及门禁注册表（`job=`/`mode=`，从不 `command=`）。仅添加了分组/标签小组件。

- **此处有意重新生成 golden。** 本切片使用 `REGEN_INVENTORY=1` 重建了 `tests/ui_inventory_golden.json`。**唯一** 差异是每页的 **组件计数**（新增的模式子标题标签；五个流程密集页面共 +113 个小组件）。`gated_count`、`gated_unique_triples`、`gated_triples_sha256`、`core_flows`、`action_meta`，以及每个页面的 `buttons` / `acts` / `btn_sha` 都 byte-identical——门禁注册表和点击表面没有变化。

- **Slice B2 — 设备模型板（纵向动作卡片）（本切片）。** 模型页面的每动作行现在是 `ActionRow` 卡片（`python/gui/widgets/action_row.py`），而不是带 monkeypatch 的 `mousePressEvent` 的 50px 手工 `QFrame`：
  - 具有 **3px 语义左边缘**（破坏性/擦除动作用 `err`，否则用 `accent_hi`）——与流程浏览器中 `MethodCard.set_risk` 绘制的是同一套风险边缘语言；
  - 具有 **40x40 图标块**、**13px / 800** 标题和 **单行省略** 的描述。这修正了计划中“长流程标签不可预测地溢出/换行”的问题：描述省略而非换行，因此长标签永远不能让板宽于其面板，也不会读作参差的多行文本块；
  - 可选的引擎/模式 **chip** 和暗淡的 **`›` chevron**；悬停/按下/焦点由小组件自主管理（QSS 动态属性 + focus ring）。chip 由 `common._mode_chip` 已返回的强调色绘制为 **单色调药丸**（强调色轻填、强调色文本、强调色细边框），让所有徽章读作一个家族；
  - **键盘可达**——`StrongFocus` + Enter / Return / Space 发射 `activated` 信号（取代 monkeypatch 的 `mousePressEvent`）。板保留其 `flow_act` / `flow_tip` 标签，只是连接 `activated`，路由不变；
  - 分组容器现在携带作业的动作 **计数**（`FRP REMOVE · 4`）——与流程浏览器的作业标题相同的“名称 + 计数”语言。

- **不变量保持。** `_ACTION_META` 仍为 **62** 条；每个 `dev_*` 页面的 `acts` 与 `btn_sha` 都 byte-identical（没有动作行、按钮文本或按钮被添加/移除/重命名）；`gated_count` **418**，`gated_triples_sha256` `c89acce…7d75`，`gated_unique_triples` **61**，`core_flows` **116**，`stack_count` **25**。页面栈的自然最小宽度仍为 **699px**，证明省略后的标签没有加宽任何内容。

- **此处有意重新生成 golden。** 本切片使用 `REGEN_INVENTORY=1` 重建了 `tests/ui_inventory_golden.json`：唯一差异是每页的 **组件计数**（`dev_apple` 59→63、`dev_motorola` 85→99——两个已研究板面新增的卡片/标签）。B2 之后的临时 golden md5 为 `929f428638e91a42865ddde1ac96dd19`。本文件切片后续的润色（单色调 chip 家族与 device-panel 首次显示拆分）没有改变任何页面的组件计数，因此 golden **无需** 再次 regen。

- **Slice B4 — 模型板占满页面高度（本切片）。** 在 设备 → 模型板（`devices.build_brand_page`）上，两栏 split 行没有拿到页面高度，因此在 **两栏下方** 留下一大片空白带。在 1600x951 窗口下（外层页面视口 `878x717`），面板测量为 `left 250x313 / right 598x333`，下方有 **333px 死区**，动作板只拿到 `333` / `717`px。根因：split 行被以 stretch 1 添加到 `outer`，**且** 紧随其后又加了一个 trailing `outer.addStretch(1)`——两个拉伸项各分走约一半剩余垂直空间，而且没有任一面板的垂直策略为 `Expanding`，因此没有任何面板吸收它。修正（仅在 `build_brand_page` 中、外科手术式）：移除竞争的 trailing stretch（split 行现在拿走 **全部** 剩余高度），并给左侧 `list_col` 与右侧 `right_stack` 明确设置垂直 `Expanding` 策略，使内层 `lscroll` 与当前模型页面的内层 `_scroll` 接收完整高度并拥有自己的滚动条。左侧行仍顶部对齐（`lv2.addStretch(1)` 未动），列表增长时滚动。修正后：`left 250x646 / right 598x665`，死区 **1px**（仅布局的 8px 底部边距），右侧板展示更多流程且其余内容内部滚动（`vscroll_max` 900 → 557），shell 的外层 `_page_scroll` 保持隐藏（`verticalScrollBar().maximum() == 0`）。为支撑用户未来的需求，内存中额外增加 40 个模型会让 **左侧** 列表的滚动范围增长（`vscroll_max > 0`），而两个面板的高度都不变。
  - 新测试：`tests/test_device_board_layout.py` ——
    `TestBrandPageFillsHeight::test_no_dead_band_below_split`、
    `::test_both_panes_get_the_real_height`、
    `::test_right_board_scrolls_its_own_content`、
    `::test_more_devices_scroll_left_without_growing_the_panes`。两个几何测试在修正前先被确认 **失败**（H=640 时死区 295px；左面板 275px，低于 412px 地板）。
  - **没有添加或移除任何小组件**（仅 changed 了尺寸策略并移除了一个 stretch spacer），因此没有页面的组件计数移动，`tests/ui_inventory_golden.json` **无需** regen——仍为 `929f428638e91a42865ddde1ac96dd19`。

- **Slice C — 设备板上的完整流程注册表（已回滚）。**
  本切片增加了一个最终的 `MORE FLOWS · N` 分组，将 device engine 由 Rust 完整流程注册表以 `ActionRow` 卡片渲染，加上文本/模式过滤栏。它按 **engine + transport mode** 划定范围，这与 *该设备的功能* 并不相同：任何暴露 ADB 的手机都会拉取注册表里所有 ADB 已注册的流程，因此 Motorola 板面提供了仅 Samsung 的作业（`knox_bypass`、`kg_remove`、`odin_flash_tar`）、`imei_repair_spd`、`apple_icloud_*` 和 `huawei_frp_guide`。更糟的是，Motorola 型号带有 **按型号的引擎**（`Moto G13` = `spd`、`G24` = `mtk`、`G6` = `qcom`），因此 `planned` 型号为尚未完成的工作展示了整个 SPD/MTK 注册表，而 motorola/apple 品牌板面按设计绕过 `researched` 门禁。已全部回滚：注册表分组、过滤栏、`_ENGINE_MODES`、首次显示延迟和 `tests/test_device_flows.py` 都已移除；板面再次精确地等同于按设备的 curated actions。inventory golden 在全程 byte-identical（`929f428638e91a42865ddde1ac96dd19`），因为分组是 lazy 构建的，回滚无需再 regen。
  - 对任何重试的教训：应按 **型号自身声明的 `actions`**（`supported_devices.json`）限定范围，只扩展这些动真格会分发到的流程——永远不要按 engine + mode。
  - 存活并可复用的 vetted 事实：`win._route_flow_activation(job, mode, key, label)` 是唯一应用 destructive confirm 与 EXPERIMENTAL 所有权 ack 的 sink；`_dispatch`/`start_model_action` 不是（它的 experimental 检查只是狭窄的 `devices._EXPERIMENTAL_ACTS` 集合，因此例如 `emmc_raw` 会未经 ack 运行）。

- **仍延期：** 搜索框 / 模式过滤 chips 作用于按设备的流程列表、收藏/最近使用（settings 持久化）、批量选择队列（复选框 + 顺序运行）、拖拽排序、Job → Mode → Method 三栏导航、把某个 job 的模式变体展开为额外卡片（每个 `(job, mode, key)` 一张卡片是刻意的后续决定——本切片 **不会** 展开模式）、以及可复用的 `ConfirmDialog`（确认/实验性覆盖层仍由窗口拥有的模态框）。

## Phase 8 — 专业打磨与差异化（新增）
### 视觉标识
- 有签名的“工坊”暗色主题：微妙的 grain/noise 纹理与柔软 vignette。
- 品牌标记 + monogram；所有动作使用一致的图标（Lucide 风格）。
- 设备 hero 卡：型号图像轮廓、芯片、传输 badges、上次出现。
- 连接场景升级动画：真实电缆脉冲、按设备的状态点。

### 信息密度
- 可折叠审查器面板：选中设备详情、分区、PIT 摘要、日志。
- 按设备的操作时间线视图（开始/结束、时长、结果）。
- 刷写前的 PIT/分区变更 diff 视图。

### 安全与信任
- 破坏性操作前的预检清单卡片（设备、固件、PIT 匹配）。
- 清晰的风险阶梯：颜色 + 图标 + 文本；永远不只用颜色。
- 实验性动作的审计日志查看器，支持导出。

### 生产力
- 命令面板（Ctrl+K）搜索流程、设备、设置。
- 跨日志与设备的全局搜索。
- 键盘优先导航；快捷键覆盖层（?）。
- 会话恢复：重新打开上次设备 + 页面。

### Linux 原生体验
- 原生文件对话框、系统主题感知、Wayland/X11 处理。
- 长操作的桌面通知；带进度的托盘图标。
- 将固件文件拖放到刷写页面。

### 新手引导
- 首次运行向导：udev setup、桥接构建状态、设备测试。
- 带插图与下一步的空状态。
- 上下文帮助抽屉，每个流程的文档来自 `operations/`。

### 品牌资产
- 新 logo set、启动画面、安装器图形、应用图标。
- README 截图刷新以匹配新 UI。

## Phase 9 — 控制台 / 终端重设计（新增）
### 目标
让日志控制台感觉像一等公民的 Linux 终端（UEFI-shell/TTY 美学），而不是一个局促的文本框。

### 布局
- 水平分隔条中的 **右侧** dock（页面左、控制台右）；可调整大小，可折叠为细条。默认宽度 420px，最小 360px（按 dock 自身的控制行度量，因此不会裁剪）。_用户决策：控制台保持在右侧——本 phase 的早期草案说“底部 dock / 35% 高度”；该决定已被取代。_
- 宽敞的等宽终端：舒适的 padding（16px）、行高 1.45。
- 可选全屏终端模式（F11），最小 chrome。
- 按设备的 tabs 或过滤 chips，避免日志交错。

### 样式
- 暗色 TTY 调色板：黑背景、绿/琥珀/青文本，可选微妙 scanline。
- ANSI 颜色支持桥接输出；粗体标题、暗淡时间戳。
- 行号 / 时间戳开关。
- 选择 + 复制；右键菜单（复制、保存、清除、过滤）。

### 行为
- 流式传输带背压；10k+ 行无 UI 冻结。
- 搜索支持 regex，高亮匹配，上一个/下一个跳转。
- 导出到文件；会话日志自动保存。
- 设备过滤与级别过滤（info/warn/error/step）。

### 不允许被挤占
- 最小宽高约束；响应式换行；长行横向滚动。
- 时间戳/级别/设备的可调整列宽。

## Phase 10 — 控制台消息与 toast 系统（新增）
### 控制台消息
- 结构化日志条目：时间戳、设备 key、级别、消息。
- 按级别配色：info（slate）、success（green）、warn（amber）、error（red）、step（cyan）。
- 可折叠多行输出（stack trace、JSON）带“show more”。
- 刷写步骤的内联进度条；每步状态图标。
- 可点击的设备 key 以聚焦设备；可点击的流程 key 打开文档。

### Toasts
- 非阻塞、堆叠的 toasts，带图标、标题、消息、动作按钮。
- 自动消失带进度条；悬停时暂停。
- 严重级别样式（info/success/warn/error）使用一致的调色板。
- 队列上限（最多 3 个可见），带溢出计数器。
- 位置选项（右上/右下）与减少动态效果支持。
- 错误时可选声音/触觉反馈。

## Phase 12 — HiProTool parity research（新增）
### 状态
- 此环境在线搜索不可用（HTTP 402）。需要手动研究。

### 研究任务
- 收集 HiProTool 功能列表（FRP、MDM、屏幕锁、运营商、IMEI、刷写）。
- 将每种方法映射到引擎（ADB、download mode、BROM、EDL、fastboot、SPD）。
- 识别按设备的快捷方式与前提条件。
- 在 `operations/` 中附带验证步骤与安全说明进行记录。
- 优先处理高价值、低风险的方法。

## Phase 14 — Next features（新增）
### 目标功能
- IMEI blacklist removal（研究 + 按设备 playbooks）。
- Carrier unlock improvements（SIM lock、NVDATA/QCN 路径）。
- MDM unlock improvements（device owner、QR provisioning、recovery）。
- FRP improvements（按芯片/按 Android 版本的方法）。
- Screen lock removal improvements（ADB、recovery、download、EDL）。
- Samsung Knox Guard removal（EXPERIMENTAL，审计记录）。
- Apple MDM enrollment removal（profile/DEP）。
- Samsung Knox management tools。
- Android Enterprise enrollment handling。
- Zero-touch enrollment handling。
- Apple Activation Lock removal（checkm8/DFU 范围，诚实限制）。
- SIM PUK retrieval to unlock SIM PIN。
- Biometric lock removal（研究、设备限制）。

### 备注
- 每个功能都必须由 Rust 支撑，并在风险时作为 EXPERIMENTAL 门禁。
- 在 `operations/` 中附带验证与安全说明进行记录。

## Phase 15 — Documentation audit & cleanup（新增）
### 发现的陈旧引用（历史/已退役）
- `operations/*/README.md` 提到已退役的 Python 模块（`knox.py`、`qcn.py`、`health.py`、`apple.py`、`flows/*.py`）作为上下文；可以接受，但应明确标记为历史。
- `INDEX.md` 之前引用了缺失的 `SPLIT_PLAN.md`（已修复）。
- `README.md` 仓库布局之前列出了不存在的模块（已修复）。
- `DESCRIPTION.md` 有错误的传输/任务计数（已修复）。

### 剩余文档任务
- 将所有“已退役”备注规范化为每个文件的单一“History”章节。
- 在每个 operations README 顶部添加 “Current architecture” 备注。
- 移除或归档过时的迁移计划（`DESIGN.md` → 新版本）。
- 保持 `operations/` 仅用于研究；代码指针必须说 `src/flows.rs`。
