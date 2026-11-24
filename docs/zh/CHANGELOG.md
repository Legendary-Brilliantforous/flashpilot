# 变更日志

Language switcher: [English](../../CHANGELOG.md) · [Français](../fr/CHANGELOG.md) · [Español](../es/CHANGELOG.md) · [Deutsch](../de/CHANGELOG.md) · **简体中文** · [Русский](../ru/CHANGELOG.md) · [Português](../pt/CHANGELOG.md) · [日本語](../ja/CHANGELOG.md) · [العربية](../ar/CHANGELOG.md) · [हिन्दी](../hi/CHANGELOG.md) · [Türkçe](../tr/CHANGELOG.md)

> English is the canonical source. This page is a translation; help wanted — see [`../TRANSLATION.md`](../TRANSLATION.md).

## 1.2.2（自动更新、10 种语言、Rockchip + 调制解调器安全多设备）

*合并 1.2.2 → 1.3.2 开发周期笔记 —— 自 1.2.1 以来发布的所有内容。*

### 自动更新与 What's New（新增）
- 更新自动安装：下载的 `.deb` 在后台经 sudo 安装，应用重启，并在首次启动时显示一个一次性的"新增或变更了什么"窗口展示新版本的 changelog（当设置 → 更新中关闭自动安装时，手动 "Install Now" 提示仍然保留）。

### 10 语言 UI + 实时语言切换（新增）
- 整个 UI 以 10 种附加语言发布（Français、Español、Deutsch、简体中文、Русский、Português、日本語、العربية、हिन्दी、Türkçe）：设置、设备磁贴、页面与控制台字符串。
- 切换 UI 语言即时生效 —— 无需重启；布局按真实字体度量收缩，长翻译换行而不是裁剪控件。
- 基于键的 JSON 翻译目录带覆盖率验证；CI 对已安装目录做冒烟测试。

### Rockchip + 更智能的检测（新增）
- 新 Rockchip 品牌页：经 fastboot 模式覆盖 RK28xx–RK35xx 家族。
- 检测识别型号、品牌与形态因子 —— 不只是芯片。
- 每个刷机阶段都被捕获（TFT 对等）：MediaTek BROM/preloader/DA 覆盖完整阶段 PID 集与 OEM VID（含 preloader VCOM 0x2000/0x2001）、扩展的 Qualcomm EDL download-PID 家族、SPD download-PID 并集，以及作为独立模式命名的 Qualcomm HS-USB Diagnostics。
- 模式 badge 跟随 *选中* 的设备并命名实际 USB 协议（ADB/MTP/PTP/DIAG/storage/RNDIS）而非 OTHER：只有刷机 PID 认领 low-level MediaTek 标签，Qualcomm EDL 保留自己的 badge chip，'MEDIATEK'/'download' 子串掉落问题已修复。

### Motorola FRP（新增）
- CVE-2016-10277 fastboot FRP 链、own-DPC 假登录 QR 配置（TestDPC / Device Policy / Adobe）、带刷写 + 重启循环的分阶段 fastboot FRP，以及 factory-bootmode ADB 循环。

### 真实引擎路径（新增）
- Rust 核心中的真实 MTK/QCOM/Unisoc/Samsung 刷机、FRP 与锁路径。
- odin4 移除：原生 Rust Odin 引擎处理完整 tar 流水线、PIT 与每一类已知 odin4 问题；Apple usbmuxd/lockdown 迁移到 Rust；核心仅 Rust（所有 Python 设备/协议回退已移除）。

### 调制解调器安全 ADB（已修复）
- 轮询/监视/显示路径为 zero-touch（`adb-devices --no-probe`）：循环中无 open/claim/handshake —— USB 调制解调器不再每周期重新枚举（实测：MSM8916 调制解调器上 114 个安静轮询周期）。
- claim 争用走委派阶梯：原生 → Rust 服务器传输（显式 serial）→ 主机二进制 → 救援 kill（最后手段），因此在系统服务器持有接口时 ADB 操作也能成功。
- USB-ADB 合并修复（行字符串被解析，所以行真正携带 ADB 状态）、busy 持有者救援 + 瞬态重试 + 诚实的 busy 状态、babble/overflow 守卫、claim 测试隔离命令、现代 adb CNXN 值，且 QCOM/MTK 角落像兄弟分支一样显示 ADB 遮罩。

### 多设备可靠性（已修复）
- Device pick 带 settle-retry：当扫描瞬态未命中正在重新枚举的设备时，每个工具 runner 在 2.5 秒后重试一次，而非在 GUI 显示 connected 时以 "no device" 拒绝。
- ADB AUTH 在 token 轮次中保持 SHA-256 在场（奇数轮 SHA-256，偶数 SHA-1），丢失 round-1 签名不再筑成假 "not authorized" 之墙；`_wait_for_adb` 容忍瞬态扫描失败。
- 目标身份绑定：占用已复用 bus:addr 的被替换设备被拒绝（zero-touch serial 检查）—— 传输绝不跟随到不同手机。
- 设备列表切换：第二次扫描丢掉设备时连接栏重建会重试，切换设备不再回退到第一台手机，USB 选择未命中时 ADB 工具回退到 ADB daemon row（"显示 connected 但 actions 说 no adb"）。
- 设备分类 + 选择器：不匹配的设备报告 USB 而非错误的 MTP 标签，未命中的 USB 选择提供 daemon-row 选择器（"Run on this device" / "Cancel"）而非拒绝。

### 诚实结果与 GUI 打磨（已修复）
- FRP 流程要求经过验证的 flags 与真实 shell 退出状态；非零 bridge 退出以日志尾部抛出失败 —— 不再有假的 "completed" toast。
- GUI：每行任务 chip、窗口记忆、toast 上限、键盘导航、设备感知 STOP（一个任务取消该设备）、kg_unlock 移到工作线程（30 秒链条不再冻结窗口）、splash 跟踪真实构建、延迟页面保持可重试、toast 清出顶栏。

### 安全与健壮性
- 默认私有输出、防符号链接的临时名、symlink 检查。
- 固件默认写后校验 + 型号门控 + 数值修复。
- FRP：DPC 签名证书原生读取，provisioning 校验和已修复。
- HIL 硬件测试套件：真实硬件上的多设备 / 设备替换 / USB 风暴回归；ADB 监视退避测试变得确定。
- 公开着陆页（`website/`），带能力矩阵与协议控制台。

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