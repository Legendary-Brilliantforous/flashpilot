/*
 * Site content.
 *
 * Numbers here are counted from the repository itself (src/flows.rs,
 * python/gui/supported_devices.json, the Rust sources and the Python
 * sources) rather than copied from marketing copy, so the page cannot drift
 * silently.
 */

export const REPO = 'https://github.com/Legendary-Brilliantforous/flashpilot'
export const BRANCH = 'dev'

export const repoLink = (path = '') => `${REPO}/blob/${BRANCH}${path}`

export const FIGURES = {
  /** flow!() rows in src/flows.rs */
  flows: 280,
  /** distinct job names in the flow registry */
  jobs: 13,
  /** transport modes the registry covers */
  modes: 9,
  /** brands in the device catalogue */
  brands: 22,
  /** device models in the catalogue */
  models: 732,
  /** models with a verified, wired-up action set */
  researched: 650,
  /** Rust core lines */
  rustLoc: 41295,
  /** Python GUI and core lines */
  pythonLoc: 29071,
}

/* ---------- transport modes ---------- */

export type Transport = {
  name: string
  desc: string
  usb: string
}

export const TRANSPORTS: Transport[] = [
  {
    name: 'ADB',
    desc: 'Android Debug Bridge — any phone with USB debugging, for FRP, MDM, screen lock, battery and network work.',
    usb: 'per vendor',
  },
  {
    name: 'MTP',
    desc: 'Media Transfer Protocol sessions, including the AT channel Samsung exposes for FUS and EFS.',
    usb: 'USB class 6',
  },
  {
    name: 'Download mode',
    desc: 'Samsung Odin protocol: firmware slots, PIT tools, EFS backup, carrier unlock.',
    usb: '04e8:685d',
  },
  {
    name: 'Samsung BROM',
    desc: 'Samsung boot ROM access for low-level work that sits below the download-mode agent.',
    usb: '04e8:…',
  },
  {
    name: 'MTK',
    desc: 'MediaTek preloader and download agent: scatter tables, GPT, DA upload, backups.',
    usb: '0e8d:2000',
  },
  {
    name: 'MTK BROM',
    desc: 'MediaTek boot ROM direct, including crash-to-BROM and the BROM exploits.',
    usb: '0e8d:0003',
  },
  {
    name: 'Fastboot',
    desc: 'Native fastboot transport, one raw command at a time — no vendor SDK in the way.',
    usb: 'per device',
  },
  {
    name: 'EDL',
    desc: 'Qualcomm Emergency Download: Sahara handshake into Firehose programming.',
    usb: '05c6:9008',
  },
  {
    name: 'SPD',
    desc: 'Spreadtrum and UNISOC serial loader: FDL download, PAC extract and repack.',
    usb: '1782:…',
  },
]

/* ---------- what it replaces ---------- */

export type ComparisonRow = {
  tool: string
  constraint: string
  replacement: string
}

export const COMPARISONS: ComparisonRow[] = [
  {
    tool: 'Odin, Smart Switch',
    constraint: 'Windows only, GUI only, closed source',
    replacement: 'The Odin session protocol reimplemented in Rust, with PIT tools alongside it',
  },
  {
    tool: 'MTK flash tools',
    constraint: 'Windows only, the download agent is closed',
    replacement: 'BROM and DA flashing and backup, scatter plus GPT, agent upload included',
  },
  {
    tool: 'Qualcomm EDL tools',
    constraint: 'Windows only, scattered across forums',
    replacement: 'Sahara and Firehose implemented in one auditable codebase',
  },
  {
    tool: 'SPD and UNISOC tools',
    constraint: 'Windows only, undocumented',
    replacement: 'A clean-room BSL download implementation',
  },
  {
    tool: 'FRP and lock tools',
    constraint: 'Paid, grey-market, no source',
    replacement: 'Transparent ADB and download-mode flows, plus MDM unlock',
  },
]

/* ---------- capability matrix ---------- */

export type Cell = {
  text: string
  tone: 'yes' | 'no'
}

export type Capability = {
  name: string
  samsung: Cell
  mediatek: Cell
  qualcomm: Cell
  spd: Cell
  adb: Cell
}

const yes = (text: string): Cell => ({ text, tone: 'yes' })
const no = (): Cell => ({ text: '—', tone: 'no' })

export const CAPABILITIES: Capability[] = [
  {
    name: 'Detect and read device info',
    samsung: yes('Model, serial, region, carrier'),
    mediatek: yes('Plus crash preloader to BROM'),
    qualcomm: yes('Sahara handshake'),
    spd: yes('Chip type and UID'),
    adb: yes('Battery, network, storage'),
  },
  {
    name: 'Flash firmware',
    samsung: yes('Odin, native Rust'),
    mediatek: yes('Scatter and GPT'),
    qualcomm: yes('Firehose'),
    spd: yes('FDL and regions'),
    adb: no(),
  },
  {
    name: 'Back up partitions',
    samsung: yes('EFS'),
    mediatek: yes('Scatter partitions'),
    qualcomm: yes('Firehose read'),
    spd: yes('Flash read'),
    adb: no(),
  },
  {
    name: 'Remove FRP',
    samsung: yes('ADB and download mode'),
    mediatek: yes('ADB and download mode'),
    qualcomm: yes('EDL'),
    spd: yes('ADB and download mode'),
    adb: yes('Any device'),
  },
  {
    name: 'Remove screen lock',
    samsung: yes('Recovery'),
    mediatek: yes('Recovery'),
    qualcomm: yes('EDL'),
    spd: no(),
    adb: yes('Any device'),
  },
  {
    name: 'Remove MDM',
    samsung: yes('ADB, QR, recovery'),
    mediatek: no(),
    qualcomm: no(),
    spd: no(),
    adb: no(),
  },
  {
    name: 'Knox warranty bypass — experimental',
    samsung: yes('Acknowledged, audit logged'),
    mediatek: no(),
    qualcomm: no(),
    spd: no(),
    adb: no(),
  },
  {
    name: 'QCN and IMEI work — experimental',
    samsung: no(),
    mediatek: yes('NVRAM'),
    qualcomm: yes('NV 550 and 682'),
    spd: yes('BSL NV'),
    adb: no(),
  },
  {
    name: 'Partition tools',
    samsung: yes('PIT read, write, flash'),
    mediatek: yes('GPT'),
    qualcomm: yes('GPT'),
    spd: yes('PAC extract and pack'),
    adb: no(),
  },
  {
    name: 'Low-level access',
    samsung: yes('HID and BROM'),
    mediatek: yes('BROM exploit, SLA keys'),
    qualcomm: yes('Sahara'),
    spd: yes('BSL'),
    adb: no(),
  },
  {
    name: 'Battery and network repair',
    samsung: no(),
    mediatek: no(),
    qualcomm: no(),
    spd: no(),
    adb: yes('Any device with debugging on'),
  },
]

/* ---------- device catalogue ---------- */

export type Brand = {
  name: string
  models: number
}

export const BRANDS: Brand[] = [
  { name: 'Samsung', models: 71 },
  { name: 'Xiaomi, Redmi, Poco', models: 112 },
  { name: 'Oppo', models: 80 },
  { name: 'Realme, Narzo', models: 68 },
  { name: 'Tecno', models: 66 },
  { name: 'Vivo, iQOO', models: 70 },
  { name: 'Infinix', models: 47 },
  { name: 'Huawei, Honor', models: 40 },
  { name: 'TCL, Alcatel, ZTE', models: 34 },
  { name: 'itel', models: 24 },
  { name: 'Motorola', models: 17 },
  { name: 'Lava', models: 15 },
  { name: 'Nokia', models: 15 },
  { name: 'Lenovo', models: 13 },
  { name: 'Rockchip', models: 13 },
  { name: 'BLU', models: 10 },
  { name: 'Others', models: 10 },
  { name: 'OnePlus', models: 7 },
  { name: 'Wiko', models: 7 },
  { name: 'Apple', models: 6 },
  { name: 'Meizu', models: 4 },
  { name: 'Asus, Sharp', models: 3 },
]

/* ---------- screenshots ---------- */

export type Shot = {
  file: string
  title: string
  caption: string
}

export const SHOTS: Shot[] = [
  {
    file: 'img/samsung.png',
    title: 'Samsung',
    caption: 'The Samsung hub: Odin flash, unlock, advanced flash and info tools, with the device list on the left.',
  },
  {
    file: 'img/mtk.png',
    title: 'MediaTek',
    caption: 'The MediaTek workbench: scatter tables, download-agent upload, BROM tools and partition backups.',
  },
  {
    file: 'img/spd.png',
    title: 'UNISOC',
    caption: 'The SPD workbench: FDL binaries and base addresses, chip UID reads and PAC handling.',
  },
  {
    file: 'img/battery.png',
    title: 'Battery and network',
    caption: 'The ADB-only side: fuel-gauge health, current draw, radio reset — no vendor hardware involved.',
  },
]

/* ---------- quick start ---------- */

export type InstallStep = {
  text: string
  command: string
}

export const INSTALL: InstallStep[] = [
  {
    text: 'Build the Rust bridge. The first build compiles vendored libusb from source, so there is nothing to install system-wide.',
    command: 'cargo build --release',
  },
  {
    text: 'Install the USB udev rules, so a phone in download mode is reachable without sudo.',
    command: 'sudo bash root/setup-usb.sh',
  },
  {
    text: 'Create the Python environment and install the GUI dependencies.',
    command: 'python3 -m venv .venv && .venv/bin/pip install -r requirements.txt',
  },
  {
    text: 'Launch the studio.',
    command: '.venv/bin/python -m python.main',
  },
]

/* ---------- safety ---------- */

export type SafetyItem = {
  title: string
  text: string
}

export const SAFETY: SafetyItem[] = [
  {
    title: 'Only on devices you own or are authorised to service',
    text: 'Work on your own phone, or on a customer phone with consent. Bypassing FRP or MDM on a device you do not own can be illegal where you live.',
  },
  {
    title: 'Back up before you flash',
    text: 'EFS, PIT, QCN, modem and userdata first. Every flashing session can wipe data, and a wrong image can leave a phone that will not boot.',
  },
  {
    title: 'Experimental flows stay experimental',
    text: 'Knox, QCN and IMEI work, and raw eMMC and UFS access, sit behind an amber gate, need a typed acknowledgement on every run, and are audit logged.',
  },
  {
    title: 'Linux is the supported platform',
    text: 'Windows and macOS are not supported today. That is a deliberate choice, not an oversight — and the USB layer is isolated so a port stays additive.',
  },
]

/* ---------- footer links ---------- */

export const DOC_LANGUAGES: { code: string; label: string }[] = [
  { code: 'fr', label: 'Français' },
  { code: 'es', label: 'Español' },
  { code: 'de', label: 'Deutsch' },
  { code: 'zh', label: '简体中文' },
  { code: 'ru', label: 'Русский' },
  { code: 'pt', label: 'Português' },
  { code: 'ja', label: '日本語' },
  { code: 'ar', label: 'العربية' },
  { code: 'hi', label: 'हिन्दी' },
  { code: 'tr', label: 'Türkçe' },
]
