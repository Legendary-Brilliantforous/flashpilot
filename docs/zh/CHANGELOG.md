# 变更日志

Language switcher: [English](../../CHANGELOG.md) · [Français](../fr/CHANGELOG.md) · [Español](../es/CHANGELOG.md) · [Deutsch](../de/CHANGELOG.md) · **简体中文** · [Русский](../ru/CHANGELOG.md) · [Português](../pt/CHANGELOG.md) · [日本語](../ja/CHANGELOG.md) · [العربية](../ar/CHANGELOG.md) · [हिन्दी](../hi/CHANGELOG.md) · [Türkçe](../tr/CHANGELOG.md)

> English is the canonical source. This page is a translation; help wanted — see [`../TRANSLATION.md`](../TRANSLATION.md).

## 1.3.2（badge 以 USB 协议命名）

- 模式 badge 不再对已连接设备显示 OTHER：'MEDIATEK' 不包含子串 'MTK'，因此一个通用 MTK 模式标签（'MEDIATEK MODE (VID 0x0E8D PID 0x2008)'）一路掉落到 OTHER。
- 一个正常启动的 MediaTek/Tecno 手机若 PID 不匹配（0e8d:2008，静态图像/MTP 接口，无 ADB 行）不再被认作 low-level MediaTek：只有刷机 PID（BROM/preloader/DA）认领 low-level 标签，其余全部掉落到基于接口的协议命名（ADB/MTP/PTP/DIAG/storage/RNDIS）覆盖 *所有* 设备列表 —— 此前仅 Samsung 设备做协议扫描。
- Rust 传输层：一个不匹配但仍然暴露静态图像（class 6）接口的 PID 报告 MTP 而非 USB；没有 MTP 接口的硬件保留诚实的 USB 标签。
- 连接标签对非刷机 PID 显示 'MediaTek device (normal boot)' 而非 'MediaTek low-level'。
- Qualcomm EDL 保留自己的 badge chip：'EDL MODE (Qualcomm Emergency Download)' 包含子串 'download'，此前会掉落到 DOWNLOAD chip。
- Qualcomm HS-USB Diagnostics（05c6:9006，如 Diag 模式下的 Moto）被命名为 'QUALCOMM DIAG MODE (HS-USB Diagnostics 9006)'，而非折叠进通用 'QUALCOMM DEVICE' 标签。

## 1.3.1（ModeBadge 修复）

- 设备模式 badge（顶栏，靠近 Stop）跟随 *选中* 设备，不再对 Qualcomm 正常设置读作 MTP（子串 'normal' 掉落到 MTP chip）。

## 1.3.0（设备分类 + 选择器）

- 不匹配的设备（厂商专属/diag 复合设备）报告 'USB' 而非错误的 'MTP' 标签。
- 当 USB 选择在 flap 上未命中时，ADB 工具展示 daemon-row 选择器而非拒绝：选择 op 目标设备。

## 1.2.9（显示设备身份）

- 切换设备不再回退到第一台手机：3 秒刷新、live-identity resolver 及所有回退都按显示设备加键；absence 路径保留行的静态磁贴。

## 1.2.8（设备列表切换修复）

- 连接栏重建在第二次扫描丢掉监视器刚看到的设备（re-enumeration 窗口）时重试：两台设备都渲染，flapping 链路上切换正常工作。

## 1.2.7（目标身份绑定）

- 占用已复用 bus:addr 的被替换设备被拒绝（目标处的 zero-touch serial 检查；open 按 vid/pid/bus/addr 匹配，不按 serial）。关闭设备替换场景：传输绝不会跟随到不同设备。

## 1.2.6（daemon-row 回退）

- ADB 工具在 flapping bus 上 USB 扫描 selection 未命中时回退到 ADB daemon row（daemon 基于 TCP，保持 presence 权威）。修复 '显示 connected 但 actions 说 no adb'。

## 1.2.5（MTK 角落 ADB 遮罩）

- `mtk_devs` 角落分支现在像兄弟分支一样显示 ADB 遮罩：一台带已授权 ADB 的 Tecno/MTK 设备在右上角命名传输（此前只显示 'MediaTek low-level' 而 ADB Status 显示 connected）。

## 1.2.4（ADB AUTH 修复）

- AUTH 哈希交替修正：SHA-256 在 token 轮次中保持在场（奇数轮 SHA-256，偶数 SHA-1）。此前在噪声链路上丢失 round-1 签名会重新 token 化成一堆 SHA-1 → 设备已授权却假报 'not authorized'。
- `_wait_for_adb` 容忍等待中途的瞬态扫描失败。

## 1.2.3（selection 弹性）

- Device pick 带 settle-retry：每个工具 runner 在扫描瞬态未命中正在重新枚举的设备时重试一次（等待 2.5 秒），而非在 GUI 显示 connected 时就以 "no device" 拒绝。用户取消的选择器绝不重试。

## 1.2.2（modem-safe ADB + 显示修复）

### ADB 传输（已修复）
- 轮询/监视/显示路径为 zero-touch（`adb-devices --no-probe`、`adb_presence`）：循环中无 open/claim/handshake。修复 USB 调制解调器每周期重新枚举（实测：约 1 Hz 风暴后 MSM8916 调制解调器上 114 个安静轮询周期）。
- claim 争用时的委派阶梯：原生 → Rust 服务器传输（`adb-shell-server`，仅显式 serial）→ 主机二进制 → 救援 kill（最后手段）。ADB op 现在在系统服务器持有接口时也能成功，而非驱逐它。
- USB-ADB 合并修复：解析行字符串（结构反序列化曾静默产出零个 ADB 条目，所以行永远没有 ADB 状态）。
- QCOM 角落现在像兄弟分支一样显示 ADB 遮罩。

### 健壮性（已修复）
- 瞬态 gate 拒绝时的单次 settle-retry（re-enumeration 窗口），带准确消息；所有诊断/工具 shell 使用 `rescue=False` + serial pinning；Firehose FAIL 检测；CLI 输入 panic；分配 clamp；tar 遍历守卫；严格 XML 数值。

## 1.2.1（稳定版发布）

### 多设备支持（新增）
- 插入多部手机：连接栏列出每部（型号 · serial · 传输方式）；点击一行检视。
- 有多台匹配时，每个操作询问作用于哪部手机（0–1 台匹配时静默）。控制台行带 `[device-key]` 标签。
- 每设备一操作：不同手机可并行刷机；同一手机仍串行。全局 STOP 广播给所有 runner。
- 稳定身份（`python/core/devices.py`）：`adb:<serial>` → `usb:<port-path>` → 易失回退。会话打开前重新解析目标，因此 USB 重新枚举不再让刷机掉队（`usb device Fail`）。
- 仅手机设备列表：过滤掉 hub、HID、摄像头与读卡器。
- 新 `SPD` 传输模式 + 只读 Qualcomm/SPD detect 流程。

### 每芯片 EXPERIMENTAL（新增）
- Samsung `Knox / Warranty`、Qualcomm `QCN / Modem`、每芯片 `IMEI Repair / Change`、`eMMC / UFS` —— 橙色折叠区位于所属芯片页面（无全局 LAB 页）。每次运行的 ownership 复选框；IMEI 变更还需键入 `I UNDERSTAND`。审计日志记录；持久化的 ack 绝不自动通过（`check_gate_strict`）。

### MTK BROM（修复 + 改进）
- **PID/阶段映射按 mtkclient 约定修正**（`0e8d:0003`=BROM，`0e8d:2000`=preloader）横跨 Rust、Python、GUI 标签、日志与文档。
- 新 `mtk_crash_brom` bridge 命令 + `MTK crash preloader into BROM` 流程（注册在 MTK BROM 下）。
- `_wait_mtk_brom_target()` 优先稳定持有的 BROM 而非 preloader 窗口；DA 发现拒绝截断（<1KB）二进制。

### Odin / 刷机（强化）
- `_prepare_download_session()`：内核驱动 detach + 跨重新枚举 3× 握手重试；接受所有 Odin PID；刷写前 PIT 缓存预热。
- odin4 固定 `-d /dev/bus/usb/BBB/AAA` + USB 丢失时一次自动重试；`.tar.md5` trailer 锚定到文件尾（流式，无全内存读取）。
- 原生智能刷机按分区分粒度记录 MB/s + ETA。

### 健壮性强化（review 驱动）
- Sahara：HELLO 命令/版本/模式/包大小在解析时校验（曾是：任何 ≥32 字节 blob 都被信任）；transfer-format 自检现 round-trip 结构体而非丢弃字节；关闭失败记录日志；detach 在 claim 之前运行；握手以 JSON 报告 transfer/close/reset 结果而非丢弃（reset 显式且可见）。
- ADB auth：token 轮次间 cap 指数退避；单次 keygen 暂停会公告而非看起来卡住。
- MTK：配置的包大小实际到达 DA 会话（曾计算后丢弃；会话硬编码 64K），clamp 到 512B–1MB。
- 安全备份：失败打印不可错过的 banner，带耗时与 STOP 提示（合约不变：绝不阻塞操作）。
- 实验门控：iCloud + Pixel 流程迁移到严格每轮 ack；GUI ack token 现按 feature 计数并带过期（无跨 feature 串扰、无丢失 ack、无过期授权）。

### GUI 修复
- 顶栏红边 + 按钮收缩追踪到并发 shake/rubber 动画与 accent-tinted focus rings：动画用 `_anim_lock` 序列化 + 完整清理；新增中性 `focus_ring`/`sel_border` 主题 token（红色 accent 不再能泄漏到 focus）。
- `os.system()` → `subprocess` 用于 bridge rebuild / log-dir 打开。
- 重复 SPD "Enable ADB" 存根、`fastboot_unlock` 实验误门控、死 FUS→AP-slot 路径、缺失 `finished` emit 已修复。移除死 LAB/Knox/QCN/PAC 实验面。

### 重构
- `python/core/frp.py`（god file）→ `python/core/core.py`（注册表 + flows）；`frp.py` 现仅 FRP。删除死 `python/core/flows/` 拆分。

- Verb-first job 名（`Remove FRP`、`Flash Firmware` 等）；每个 flow 一个规范 snake_case key；显示名称大小写规范化。

### 文档
- 新截图（`docs/samsung.png`、`mtk.png`、`spd.png`），重写 README 高亮/矩阵/布局，CONTRIBUTING 架构 + flow 规则，本 changelog。

### boot.img + AVB（单原生引擎）
- Rust bridge 新图像手术引擎（`src/imgtools.rs`）：Android boot 头解析、cpio newc 扫描、prop 补丁（pad-in-place 或 magiskboot 风格带头重写 grow）、确定性 gzip（mtime=0，level 9）、AVB vbmeta flags。`boot-info` / `boot-patch-adb` / `vbmeta-patch` CLI。
- Python `spd_adb` repack + `core._patch_vbmeta_flags` 委托，并带本地回退（签名与返回合约不变）。
- 等价工作修了两个真 bug：grow splice 与 reader 对齐相差 2 字节（破坏后续每个 entry —— 双方实现），重补丁每次运行增长 `\n`（双方现已幂等）。gzip 字节故意排除在 parity 之外（zlib 实现差异）；解压内容、尺寸与字段匹配。
- 6 个 Rust 单元测试 + 9 个跨实现测试。

### PAC（单原生引擎 + 接入 GUI actions）
- Rust bridge 新 SPD PAC 引擎（`src/pac.rs`）：按 YGDP 布局 parse/extract/pack，共享 head/slot builders 现也被 `spd-readback` writer 使用（字节相同输出；其历史 doubled slot names 隔离，未传播）。`pac-parse` / `pac-extract` / `pac-pack` CLI。
- Python `pac.*` 委托并带本地回退；新 `flow_pac_extract` / `flow_pac_pack`（纯文件，ofp 风格 env 输入）在 FLOWS 注册并映射 GUI dispatcher —— 之前死的 PAC 按钮现在能跑。
- 等价测试捕获并修了一个真 bug：本地 packer 静默丢弃 product string（slice-copy write）；另加 u32 overflow 守卫，双引擎消息一致。
- 5 个 Rust 单元测试 + 7 个跨实现测试（双向 roundtrip、sanitize parity incl. dir collision、error mapping）。

### PIT（单原生引擎）
- Rust bridge 新 Samsung PIT 引擎（`src/pit.rs`）：parse（28/132 布局）、头/model 字符串、name normalization、find、overlap scan、forensic validation + health verdict —— 真实 dump 与边界 case 上字节完全相同的 messages、summaries 与 verdicts（含 Python-`repr` parity for junk names）。
- `pit-parse` / `pit-health` / `pit-find` / `pit-overlaps` / `pit-model` CLI；Python `pit.*` 原始字节路径委托并带本地回退（binary 缺失时）（合约保留：ValueError/None/never-raise）。
  内存对象路径与显示助手保持本地且快速；共享规则由 11 个跨实现等价测试固定。
- 8 个 Rust 单元测试（布局向量、normalize 表、meta overlap 分类、summary/human-size 形态）。

### ADB（原生传输，无 platform-tools）
- Rust bridge 新原生 ADB 客户端（`src/adb.rs`）：USB 传输（255/66/1）带内核驱动 detach、CNXN handshake、RSA-SHA256/SHA-1 AUTH（复用 `~/.android/adbkey`，缺失时生成）、`shell:` 与 `sync:`（STAT/RECV/SEND）services。
- `adb-devices` 从原生扫描保持 `adb devices -l` 行合约（`device` / `unauthorized` / `no permissions`）；`adb-shell` 接收 serial（`-` = 第一个已授权），加新的 serial-pinned `adb-pull` / `adb-push`。
- Python：`bridge.adb_shell()` 解析 explicit > ambient-scope > first authorized serial（多设备 ADB 现按目标 pin；`adb.py` 委托到 bridge；EFS backup/restore pull/push 走 bridge 而非 unpinned system `adb` 调用。`has_adb()` 现表示 "bridge built"。
- 6 个 Rust 测试（framing、banner、PKCS#1 sign/verify、DER roundtrip、pubkey blob 与 system adb key 字节相同）+ 9 个 Python 测试。

### Fastboot（原生传输 + Motorola universal）
- Rust bridge 新原生 fastboot USB 传输（`src/fastboot.rs`）：`fastboot-devices`（JSON）+ `fastboot-cmd <vid:pid@bus:addr> <ms> <cmd…>` 用于命令阶段（getvar/oem/erase/reboot）带内核驱动 detach。
  设备侧 FAIL 渲染为 `FAILED (remote: …)` 且 exit 0，匹配系统二进制 transcript 形态（含 Moto MBM bootloader 上 OKAY 包里 piggyback 的 lone `getvar` 值）。
- 共享 Python helpers（`_fastboot_run`、`_wait_fastboot`、`_fastboot_getvar`）native-first 带 system-binary 回退；DATA 阶段命令（flash/boot/…）始终用系统二进制，主机侧 `devices` 列表由 native detect 提供。所有 fastboot 流量现按目标 pin（`vid:pid@bus:addr`），关闭 no-`-s` 错手机风险。
- 新品牌级 Motorola flows（`moto_frp_adb`、`moto_frp_fastboot`、`moto_oem_unlock_token`）：ADB provisioning reset、带 lock-state 读 + session resets 的 official unlock-token 流程、只读 token reader。显示在 Motorola → All Motorola / Lenovo（universal）与每个 Moto 型号下；unlock portal URL 已修正（旧 `motorola.com/unlockbootloader` 已死）。
- `python/core/fastboot.py`（Pixel）与 `usb_watch.py`（lsusb scraping）迁移到 bridge；7 个新 `tests/test_fastboot_native.py` 测试。