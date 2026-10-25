"""Devices module — data-driven 3-level drill-down (brand -> model -> actions).

Level 1: rail entry per brand (built dynamically from supported_devices.json)
Level 2: brand page — model cards grid
Level 3: model page  — action buttons lit only for what we support

GUI-first: actions render with real labels/tooltips naming the bridge command
that will power them; only "Device Check" is wired now. Wiring lands per step.
"""

import json
import os

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .widgets.action_row import ActionRow


_DATA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "supported_devices.json")


def _load():
    try:
        with open(_DATA_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"brands": []}


_DATA = _load()
BRANDS = _DATA.get("brands", [])
BRAND_BY_KEY = {b["key"]: b for b in BRANDS}


def _tok():
    """Lazy token/style import — avoids circular import with qt_app until
    theme.py extraction lands in a later step."""
    from .theme import C, _btn_ghost, _btn_primary, _btn_danger
    return C, _btn_ghost, _btn_primary, _btn_danger

_ACTION_META = {
    "frp":                  ("FRP Bypass",        "⚡", "Instant FRP using known PIT/offset (bridge: spd-frp / mtk-frp-gpt / odin)"),
    "info":                 ("Device Check",      "ℹ", "Read model/chip info (wired: refresh_device)"),
    "backup":               ("Backup",            "⬇", "Dump critical partitions before any write (spd-readback / mtk-backup / odin efs)"),
    "flash":                ("Flash Firmware",    "⬆", "Write stock firmware for this model (odin-flash-multi / spd-flash)"),
    "adb_enable":           ("ADB Enable",        "⚙", "Enable USB debugging without Settings (magic64 / *#*#49#*#*)"),
    "screen_lock":          ("Screen Lock Remove","🔓", "Remove PIN/pattern/password via ADB locksettings or SPD/MTK BROM (screen_lock_locksettings / spd-frp / mtk)"),
    "kg_unlock":            ("KG Unlock",         "◈", "KnoxGuard state reset via AT chain (at-kg-unlock)"),
    "tecno_frp_adb":         ("FRP Remove · ADB", "⚡", "Reverse-engineered for the specific firmware. Settings flags + Google setup + GMS + account DB (TECNO Spark 10/20/10C)"),
    "tecno_frp_brom":        ("FRP Remove · BROM","🛠", "SPD/BSL erase of userdata/cache/frp. Routes to SPD tab (TECNO Spark 20/10C)"),
    "tecno_screen_lock_adb": ("Screen Lock · ADB","🔓", "locksettings set-disabled + clear --old. Reversed for the specific firmware (TECNO Spark 10/20/10C)"),
    "tecno_screen_lock_brom":("Screen Lock · BROM","🛠", "SPD/BSL wipe of userdata. Routes to SPD tab (TECNO Spark 20/10C)"),
    "tecno_mdm_adb":         ("MDM Remove · ADB", "👤", "dpm/cmd device_policy + Transsion/OEM package sweep (TECNO Spark 10/20/10C)"),
    "tecno_mdm_brom":        ("MDM Remove · BROM","🛠", "SPD/BSL wipe. Routes to SPD tab (TECNO Spark 20/10C)"),
    "tecno_device_info":     ("Device Check",     "ℹ", "Getprop dump + OEM fingerprint + lock state (TECNO Spark 10/20/10C)"),
    "tecno_enable_adb":      ("Enable ADB",       "⚙", "On-device secret code *#*#49#*#* (UMS9230) + BROM fallback (TECNO Spark 10/20/10C)"),
    "moto_frp_adb":          ("FRP Remove · ADB", "⚡", "Any Motorola/Lenovo on authorized ADB: zero frp flag + provision + disable Google/Moto setup wizards"),
    "moto_frp_fastboot":     ("FRP Fastboot Remove", "🛠", "CVE-2016-10277 (initroot): fsg-id cmdline injection → per-device initramfs → root ADB → wipe FRP. Needs --file initramfs + --partition scratch addr"),
    "moto_edl_adb":          ("(retired — no EDL on this model)", "🚫", "Retired stub: this model has no EDL path; use moto_fb_frp (fastboot staged) instead"),
    "moto_fb_frp":           ("Fastboot Staged FRP", "🛠", "Signed stock flash (MD5-verified) → reboot → up to 3 cycles acting per mode seen → ADB wipe when authorized. Needs --firmware-dir"),
    "moto_fb_factory_adb":   ("Factory-Mode ADB Cycle", "🔁", "Moto-M shape: oem fb_mode_set → reboot → act per mode seen (x3) → wipe over authorized ADB → fb_mode_clear restore"),
    "moto_frp":              ("FRP Remove",       "⚡", "Adaptive: ADB FRP remove when ADB is enabled, else the fastboot CVE-2016-10277 chain"),
    "frp_fake_login":        ("Easy Login · FlashPilot DPC", "🧩", "Own DPC (org.flashpilot.dpc) QR enrollment in the wizard: marks setup complete + enables ADB, then clears FRP"),
    "frp_fake_login_testdpc": ("Easy Login · TestDPC", "🧪", "TestDPC QR enrollment in the wizard, then FRP clear over ADB"),
    "frp_fake_login_adp":     ("Easy Login · Device Policy", "🏢", "Android Device Policy QR enrollment in the wizard, then FRP clear over ADB"),
    # Router act (not a flow): opens the QR window. TestDPC is the default
    # QR; Google Device Policy + FlashPilot are the two optional ones.
    "_qr_generator":         ("QR Provision", "📷", "MDM device-owner QR enrollment — TestDPC by default, with Google Device Policy / FlashPilot optional"),
    # ---- ADB hub (generic, non-brand flows; brand flows stay per-device)
    "adb_frp":               ("FRP Remove · ADB", "⚡", "Zero frp flag + provision + disable setup wizards over authorized ADB"),
    "frp_browser":           ("FRP Browser", "🌐", "On-device browser path to account removal"),
    "frp_emergency":         ("FRP Emergency Call", "📞", "Emergency-dialer path to Settings"),
    "frp_settings":          ("FRP Settings", "⚙", "Notification-shade path to Settings"),
    "frp_qr_provision":      ("FRP QR Provision", "📷", "TestDPC QR provisioning, then FRP clear"),
    "adb_info":              ("ADB Read Info", "ℹ", "Full getprop dump + fingerprint over ADB"),
    "repair_settings":       ("Repair Settings", "🛠", "Re-enable Settings/SystemUI when disabled"),
    "fix_adb_auth":          ("Fix ADB Auth", "🔑", "Re-seed ADB keys / authorization state"),
    "factory_reset":         ("Factory Reset", "🧹", "Wipe userdata via recovery (authorized ADB)"),
    "reboot_bootloader":     ("Reboot Bootloader", "🔃", "Reboot the phone to bootloader from ADB"),
    "reboot_edl":            ("Reboot EDL", "🔃", "Reboot the phone to EDL 9008 from ADB"),
    "reboot_normal":         ("Reboot System", "🔃", "Reboot the phone to Android from ADB"),
    "reboot_recovery":       ("Reboot Recovery", "🔃", "Reboot the phone to recovery from ADB"),
    "recovery":              ("Recovery", "🔃", "Boot to recovery"),
    "screen_lock_remove":    ("Screen Lock Remove", "🔓", "Remove screen lock over ADB"),
    "screen_lock_locksettings": ("Screen Lock · locksettings", "🔓", "locksettings clear (Android 8/9, no credential)"),
    "screen_lock_comprehensive": ("Screen Lock · Comprehensive", "🔓", "Multi-method screen-lock removal"),
    "screen_lock_recovery":  ("Screen Lock · Recovery", "🔓", "Screen-lock removal via recovery"),
    "mdm_qr":                ("MDM QR", "📷", "Device-owner provisioning QR generator"),
    "mdm_diagnostics":       ("MDM Diagnostics", "ℹ", "Read-only MDM/device-owner state"),
    "mdm_unlock":            ("MDM Unlock", "🔓", "Remove device owner / MDM"),
    "mdm_unlock_comprehensive": ("MDM Unlock · Full", "🔓", "Comprehensive MDM removal"),
    "enable_adb":            ("Enable ADB", "⚙", "ADB-enable helpers"),
    "emmc_raw":              ("eMMC Raw Read", "💾", "Raw eMMC reads (EXPERIMENTAL)"),
    "setup_wizard":          ("Setup Wizard", "🧙", "Force-complete the setup wizard over ADB"),
    "apple_icloud_remove": ("iCloud Remove",     "🧪", "EXPERIMENTAL — DFU/ramdisk iCloud remove (usbmuxd). Educational, own device only (at-apple-icloud-remove)."),
    "apple_icloud_add":    ("iCloud Add",        "🧪", "EXPERIMENTAL — Push activation plist via lockdownd (at-apple-icloud-add)."),
    "health":              ("Health Report",     "🧪", "EXPERIMENTAL — Device health JSON + HTML/PDF (health_report)."),
    "pac_extract":         ("PAC Extract",       "🧪", "EXPERIMENTAL — Extract SPD PAC container (pac_extract)."),
    "pac_pack":            ("PAC Pack",          "🧪", "EXPERIMENTAL — Pack folder to PAC (pac_pack)."),
    "ofp_extract":         ("OFP Extract",       "🧪", "EXPERIMENTAL — Oppo OFP detect + plain-extract, refuses encrypted (ofp_extract)."),
    "knox_check":          ("Knox Check",        "🧪", "EXPERIMENTAL — Knox warranty/KG read (knox_check)."),
    "knox_bypass":         ("Knox Bypass",       "🧪", "EXPERIMENTAL — Knox eFuse trip (irreversible, edu)."),
    "qcn_backup":          ("QCN Backup",        "🧪", "EXPERIMENTAL — modemst1/2 backup (qcn_backup)."),
    "qcn_imei_repair":     ("IMEI Repair",       "🧪", "EXPERIMENTAL — NV 682 IMEI restore-only (edu)."),
    "pixel_fastboot":      ("Pixel Fastboot",    "🧪", "EXPERIMENTAL — Pixel factory/unlock (fastboot)."),
    "emmc_health":         ("eMMC Health",       "🧪", "EXPERIMENTAL — eMMC/UFS health read."),
}


# Display-only engine hints for the small mode chip on a model-board action
# card. The board's group tuples carry no mode (their act keys are frozen, so
# a tuple may not grow a field), therefore the chip is derived from the
# per-brand sub-label the row already shows: the segment before the first
# " · " is matched against these keywords and handed to ``_mode_chip``, which
# owns the badge's wording + tokens. Purely cosmetic — routing, the act key
# and the click surface never read it.
_ROW_MODE_HINTS = (
    ("ADB", "ADB"),
    ("BROM", "BROM"),
    ("SPD", "SPD"),
    ("FASTBOOT", "FASTBOOT"),
    ("EDL", "EDL"),
    ("MTP", "MTP"),
    ("RECOVERY", "RECOVERY"),
)


def _row_mode_chip(sub_label):
    """The ``(label, bg, fg, border)`` engine chip for a row, or ``None``.

    Returns ``None`` (no chip) when the row's sub-label names no transport it
    maps cleanly onto — better an absent chip than a misleading one."""
    head = (sub_label or "").split(" · ")[0].upper()
    for needle, mode in _ROW_MODE_HINTS:
        if needle in head:
            from .common import _mode_chip

            return _mode_chip(mode)
    return None


def nav_entries():
    """(key_suffix, icon, label) triples for every brand — used by app shell."""
    return [(f"dev_{b['key']}", b.get("icon", "▣"), b["label"]) for b in BRANDS]


def _card(text, sub="", accent=None, clickable=True, **kwargs):
    C, _btn_ghost, _btn_primary, _btn_danger = _tok()
    from PyQt6.QtWidgets import QSizePolicy as _SP2
    card = QFrame()
    card.setCursor(Qt.CursorShape.PointingHandCursor if clickable else Qt.CursorShape.ArrowCursor)
    card.setSizePolicy(_SP2.Policy.Expanding, _SP2.Policy.Fixed)
    card.setMinimumHeight(86)
    card.setMinimumWidth(160)
    accent = accent or C["accent"]
    border = f"2px solid {accent}" if clickable else f"1px dashed {C['border']}"
    card.setStyleSheet(
        f"QFrame {{ background: qlineargradient(x1:0,y1:0,x2:0,y2:1,"
        f" stop:0 {C['card']}, stop:1 {C['inset']});"
        f" border: {border}; border-radius: 12px; }}"
        f"QFrame:hover {{ border-color: {accent}; background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #1a365d, stop:1 #0f172a); }}"
        f"QFrame:focus {{ border-color: {accent}; outline:none; }}"
    )
    lay = QVBoxLayout(card)
    lay.setContentsMargins(12, 9, 12, 9)
    lay.setSpacing(4)
    t = QLabel(text)
    t.setStyleSheet(f"color:{C['text']}; font-size:13px; font-weight:800;"
                    f" background:transparent; border:none;")
    t.setWordWrap(True)
    lay.addWidget(t)
    if sub:
        s = QLabel(sub)
        s.setStyleSheet(f"color:{C['dim']}; font-size:10px;"
                        f" background:transparent; border:none; font-family:'Consolas','Monaco',monospace;")
        s.setWordWrap(True)
        lay.addWidget(s)
    return card


def build_brand_page(win, key):
    """Level 2: split view — chip row on top, vertical
    supported-devices list LEFT, selected model's actions RIGHT."""
    from PyQt6.QtWidgets import QHBoxLayout as _HL, QVBoxLayout as _VL, \
        QScrollArea as _SA, QSizePolicy as _SP
    C, _btn_ghost, _btn_primary, _btn_danger = _tok()
    brand = BRAND_BY_KEY[key]
    models = brand.get("models", [])

    page = QWidget()
    page.setStyleSheet("background: transparent;")
    outer = _VL(page)
    outer.setContentsMargins(10, 8, 10, 8)
    outer.setSpacing(6)

    # Chip row: chips this brand's models actually use.
    # Supported chip -> clickable, navigates to its tool section; the
    # rest are grey + disabled with a reason tooltip — never dead popups.
    engines = set((m.get("engine") or "").lower() for m in models)
    chips_row = _HL()
    chips_row.setSpacing(6)
    for eng, clabel, glyph, section in _ENGINE_CHIPS:
        cb = QPushButton(f"{glyph}  {clabel}")
        cb.setCursor(Qt.CursorShape.PointingHandCursor)
        cb.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        cb.setMinimumHeight(30)
        if eng in engines and section:
            cb.setToolTip(f"{brand['label']} uses {clabel} — open the {clabel} tools")
            cb.setStyleSheet(
                "QPushButton { color:#04121a; background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
                " stop:0 #d4b78f, stop:1 #b89a6a); border:1px solid rgba(255,255,255,0.18);"
                " border-radius:14px; padding:4px 14px; font-weight:800; font-size:11px; }"
                " QPushButton:hover { background: #e2cfa5; }"
                " QPushButton:focus { outline:none; }"
            )
            cb.clicked.connect(lambda _=False, s=section: win._on_section(s))
        else:
            reason = ("no tool section yet" if eng in engines
                      else f"{brand['label']} doesn't use {clabel}")
            cb.setEnabled(False)
            cb.setToolTip(f"{glyph}  {clabel} — {reason}")
            cb.setStyleSheet(
                "QPushButton { color:#5b6b80; background:rgba(255,255,255,8);"
                " border:1px solid rgba(255,255,255,0.06); border-radius:14px;"
                " padding:4px 14px; font-weight:700; font-size:11px; }"
                " QPushButton:disabled { color:#5b6b80; background:rgba(255,255,255,8);"
                " border:1px solid rgba(255,255,255,0.06); }"
                " QPushButton:focus { outline:none; }"
            )
        chips_row.addWidget(cb)
    chips_row.addStretch(1)
    outer.addLayout(chips_row)

    # --- split view: vertical supported-devices list LEFT, selected
    # model's actions RIGHT. ---
    split = _HL()
    split.setSpacing(10)

    # LEFT: vertical model list, compact rows (fixed width, never stretch).
    list_col = QWidget()
    list_col.setStyleSheet("background: transparent;")
    # Expanding vertically so the column owns the split row's full height and
    # its inner lscroll takes the rest (many models later -> scroll, not grow).
    list_col.setSizePolicy(_SP.Policy.Preferred, _SP.Policy.Expanding)
    lv = QVBoxLayout(list_col)
    lv.setContentsMargins(0, 0, 0, 0)
    lv.setSpacing(6)
    lhead = QLabel("SUPPORTED DEVICES")
    lhead.setStyleSheet(f"color:{C['dim']}; font-size:11px; font-weight:800; letter-spacing:1px;")
    lv.addWidget(lhead)
    lscroll = QScrollArea()
    lscroll.setWidgetResizable(True)
    lscroll.setFrameShape(QFrame.Shape.NoFrame)
    lscroll.setFixedWidth(250)
    lscroll.setStyleSheet("QScrollArea { background: transparent; }")
    lhost = QWidget()
    lhost.setStyleSheet("background: transparent;")
    lv2 = QVBoxLayout(lhost)
    lv2.setContentsMargins(0, 0, 0, 0)
    lv2.setSpacing(6)
    model_buttons = []

    def _open_model(m, page_stack):
        # No fade-in here: the design system's Motion.fade is a deliberate
        # no-op on Linux (a QGraphicsOpacityEffect on a shadowed window both
        # broke the drop shadow and, on the model page, stuck at opacity 0.0
        # / rendered the board offset). Show the page immediately.
        page = _build_model_page(win, brand, m, back=None)
        if page_stack.indexOf(page) < 0:
            page_stack.addWidget(page)
        page_stack.setCurrentWidget(page)

    for i, m in enumerate(models):
        researched = m.get("status") == "researched"
        eng = (m.get("engine") or "?").upper()
        mb = QPushButton(("✓ " if researched else "… ") + m["model"])
        mb.setCursor(Qt.CursorShape.PointingHandCursor)
        mb.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        mb.setFixedHeight(34)
        mb.setToolTip(f"{m.get('chip','?')} · {eng}\n{m.get('notes') or ''}")
        mb.setStyleSheet(
            ("QPushButton { color:#e2e8f0; background:rgba(255,255,255,10);"
             " border:1px solid rgba(255,255,255,0.10); border-left:3px solid %s;"
             " border-radius:8px; padding:0 10px; text-align:left; font-size:11px; font-weight:700; }"
             "QPushButton:hover { background:rgba(255,255,255,18); border:1px solid rgba(255,255,255,0.22);"
             " border-left:3px solid %s; }"
             "QPushButton:focus { outline:none; }") %
            (C["ok"] if researched else C["mute"],
             C["accent_hi"] if researched else C["mute"])
        )
        mb.clicked.connect(lambda _=False, mm=m: _open_model(mm, right_stack))
        mb.setProperty("researched", researched)
        model_buttons.append(mb)
        lv2.addWidget(mb)
    lv2.addStretch(1)
    lscroll.setWidget(lhost)
    lv.addWidget(lscroll, 1)
    split.addWidget(list_col, 0)

    # RIGHT: lazily-built model action pages (stack; first model shown).
    right_stack = QStackedWidget()
    right_stack.setStyleSheet("background: transparent;")
    # Fill the split row's full height so the current model page's inner
    # _scroll gets the real height and scrolls its own (longer) content.
    right_stack.setSizePolicy(_SP.Policy.Preferred, _SP.Policy.Expanding)
    if models:
        _open_model(models[0], right_stack)
    split.addWidget(right_stack, 1)
    # Give the split row ALL the leftover height. The trailing addStretch(1)
    # that used to sit here competed with the split's stretch 1, so the two
    # panes were handed only ~half the page and a dead band was left below.
    outer.addLayout(split, 1)

    win._device_stacks[key] = page
    return page


def _build_model_page(win, brand, m, back):
    """Level 3: per-model action board, grouped by job (FRP / MDM / Screen Lock /
    Device Check / Enable ADB / Flash) — each with ADB and BROM sub-actions."""
    C, _btn_ghost, _btn_primary, _btn_danger = _tok()
    from PyQt6.QtWidgets import QVBoxLayout as _VL, QHBoxLayout as _HL, QLabel as _Lbl, QFrame as _Fr
    from .theme import SPACE as _SPC, RADIUS as _RAD
    page = QWidget()
    page.setStyleSheet("background: transparent;")
    _outer = _VL(page)
    _outer.setContentsMargins(0, 0, 0, 0)
    _outer.setSpacing(0)
    _scroll = QScrollArea()
    _scroll.setWidgetResizable(True)
    _scroll.setFrameShape(QFrame.Shape.NoFrame)
    _scroll.setStyleSheet("QScrollArea { background: transparent; }")
    _host = QWidget()
    _host.setStyleSheet("background: transparent;")
    v = _VL(_host)
    v.setContentsMargins(_SPC["md"], _SPC["sm"], _SPC["md"], _SPC["sm"])
    # 16px between group cards, 8px between the cards inside one group.
    v.setSpacing(_SPC["lg"])

    top = _HL()
    if back is not None:
        back_btn = QPushButton("← Back")
        back_btn.setStyleSheet(_btn_ghost())
        back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        back_btn.setFixedWidth(90)
        back_btn.clicked.connect(lambda: back())
        top.addWidget(back_btn)
    title = _Lbl(f"{brand['label']} · {m['model']}")
    title.setWordWrap(True)
    title.setStyleSheet(f"color:{C['text']}; font-size:15px; font-weight:800;")
    top.addWidget(title, 1)
    v.addLayout(top)
    brand_key = brand.get("key", "")
    badge_bg, badge_fg, left_border = "#d4b78f", "#04121a", "#d4b78f"
    if brand_key == "apple":
        badge_bg, badge_fg, left_border = "#e2e8f0", "#0f172a", "#94a3b8"
    elif brand_key == "samsung":
        badge_bg, badge_fg, left_border = "#3b82f6", "#ffffff", "#60a5fa"
    elif brand_key == "motorola":
        badge_bg, badge_fg, left_border = "#38bdf8", "#04121a", "#0ea5e9"
    elif brand_key == "tecno":
        badge_bg, badge_fg, left_border = "#f59e0b", "#04121a", "#f59e0b"

    # Chip badge on its own line: beside the title it stole width and
    # clipped both (the motorola G6 chip string is long).
    chip_lbl = _Lbl(f"{m.get('chip','')}   engine: {m.get('engine','—').upper()}")
    chip_lbl.setWordWrap(True)
    chip_lbl.setStyleSheet(
        f"color:{badge_fg}; background:{badge_bg}; border-radius:8px;"
        " padding:4px 12px; font-size:11px; font-weight:800; font-family:'Consolas', 'Monaco', monospace;"
    )
    v.addWidget(chip_lbl)

    notes = m.get("notes") or ""
    if notes:
        n = _Lbl(notes)
        n.setWordWrap(True)
        n.setStyleSheet(f"color:{C['dim']}; font-size:11px;"
                        f" background:{C['inset']}; border:1px solid {C['border']};"
                        " border-radius:8px; padding:8px;")
        v.addWidget(n)

    researched = m.get("status") == "researched"
    # Motorola and Apple flows are handled per brand/runtime
    if not researched and brand.get("key") not in ("motorola", "apple"):
        empty = _Lbl("No wired actions yet for this model — research in progress.")
        empty.setStyleSheet(f"color:{C['mute']}; font-size:12px;")
        v.addWidget(empty)
        v.addStretch(1)
        _scroll.setWidget(_host)
        _outer.addWidget(_scroll)
        return page

    # Job groups — per-brand (tecno keeps reverse-engineered flows, others use generic wired flows).
    if brand.get("key") == "tecno":
        groups = [
            ("FRP REMOVE", [
                ("tecno_frp_adb", "ADB · settings + GMS + accounts", "⚡"),
                ("tecno_frp_brom", "BROM · SPD userdata wipe", "🛠"),
            ]),
            ("MDM REMOVE", [
                ("_qr_generator", "QR Provision · TestDPC / Google / FlashPilot", "📷"),
                ("tecno_mdm_adb", "ADB · dpm + Transsion OEM sweep", "👤"),
                ("tecno_mdm_brom", "BROM · SPD userdata wipe", "🛠"),
            ]),
            ("SCREEN LOCK REMOVE", [
                ("tecno_screen_lock_adb", "ADB · locksettings clear", "🔓"),
                ("tecno_screen_lock_brom", "BROM · SPD userdata wipe", "🛠"),
            ]),
            ("DEVICE CHECK", [
                ("tecno_device_info", "ADB · getprop + OEM fingerprint", "ℹ"),
            ]),
            ("ENABLE ADB", [
                ("tecno_enable_adb", "On-device secret code + BROM fallback", "⚙"),
            ]),
        ]
    elif brand.get("key") == "apple":
        groups = [
            ("iCLOUD ACTIVATION LOCK", [
                ("apple_icloud_remove", "DFU / ramdisk iCloud remove (usbmuxd)", "🔓"),
                ("apple_icloud_add", "Push activation plist via lockdownd", "➕"),
            ]),
            ("DEVICE CHECK", [
                ("apple_info", "Lockdown / DFU device info (read-only)", "ℹ"),
            ]),
            ("PASSCODE / SCREEN TIME", [
                ("apple_passcode_guide", "Honest scope guide + backup-based checks", "ℹ"),
            ]),
        ]
    elif brand.get("key") == "motorola":
        groups = [
            ("FRP REMOVE", [
                ("moto_frp", "Adaptive: ADB remove · staged flash if firmware set · else CVE-2016-10277", "⚡"),
                ("moto_fb_frp", "Fastboot · signed flash + reboot cycles → ADB tap → wipe", "🛠"),
                ("moto_fb_factory_adb", "Factory-mode · fb_mode_set + reboot cycles → ADB tap → wipe", "🔁"),
                ("_qr_generator", "QR Provision · TestDPC / Google / FlashPilot (setup wizard)", "📷"),
            ]),
            ("SCREEN LOCK REMOVE", [
                ("screen_lock", "ADB locksettings / fastboot", "🔓"),
            ]),
            ("DEVICE CHECK", [
                ("info", "USB + ADB fingerprint", "ℹ"),
            ]),
            ("FLASH / BACKUP", [
                ("flash", "Workbench firmware flash", "⬆"),
                ("backup", "Dump partitions", "⬇"),
            ]),
            ("ENABLE ADB", [
                ("adb_enable", "MTP / secret-code path", "⚙"),
            ]),
        ]
    else:
        # Generic wired actions (nokia G20, samsung, etc.) — routed in qt_app.start_model_action.
        groups = [
            ("FRP REMOVE", [
                ("frp", "Browser / fastboot erase frp", "⚡"),
            ]),
            ("SCREEN LOCK REMOVE", [
                ("screen_lock", "ADB locksettings / fastboot", "🔓"),
            ]),
            ("DEVICE CHECK", [
                ("info", "USB + ADB fingerprint", "ℹ"),
            ]),
            ("FLASH / BACKUP", [
                ("flash", "Workbench firmware flash", "⬆"),
                ("backup", "Dump partitions", "⬇"),
                ("pac_extract", "Extract SPD PAC container", "🧪"),
                ("pac_pack", "Pack folder to PAC container", "🧪"),
                ("ofp_extract", "Extract Oppo OFP container", "🧪"),
            ]),
            ("ENABLE ADB", [
                ("adb_enable", "MTP / secret-code path", "⚙"),
            ]),
        ]

    def _row(act_key, sub_label, glyph, parent):
        # A full-width ActionRow card (icon tile + title + one-line elided
        # description + mode chip + chevron). It is a class, not a wrapping
        # QFrame with a monkeypatched mousePressEvent: the labels elide rather
        # than wrap, so a long flow label can never force the board wider than
        # its pane, and the row stays one tall, deliberate card down the page.
        meta_lbl, meta_glyph, meta_tip = _ACTION_META.get(
            act_key, (act_key, glyph, ""))
        title = meta_lbl
        if act_key in _EXPERIMENTAL_ACTS:
            title = f"🧪 {title} · EXPERIMENTAL"
        if act_key == "moto_frp":
            # Adaptive FRP Remove: the label names the current strategy,
            # the click re-checks and dispatches to the matching flow.
            title = _moto_frp_label()
        is_wipe = any(k in act_key for k in ("frp", "mdm", "screen_lock", "lock"))
        accent = C["err"] if is_wipe else C["accent_hi"]
        row = ActionRow(
            title=title,
            icon=meta_glyph or glyph,
            description=sub_label,
            accent=accent,
            tooltip=meta_tip or sub_label,
            chip=_row_mode_chip(sub_label),
            parent=parent,
        )
        # Device-first tag: apply_applicability fades QFrame tiles that need
        # an absent transport (see the tile branch there).
        row.setProperty("flow_act", act_key)
        row.setProperty("flow_tip", meta_tip or sub_label)

        def _go(r=row, a=act_key):
            if r.property("flow_dimmed"):
                return
            _dispatch(win, a, brand['label'], m)
        row.activated.connect(_go)
        return row

    for group_title, sub_actions in groups:
        # Section card — a container with the brand's left edge; its header
        # carries the job's action count (`FRP REMOVE · 4`), the same
        # name + count language the flow browser's job headers use.
        card = _Fr()
        card.setObjectName("modelgroup")
        card.setStyleSheet(
            f"QFrame#modelgroup {{ background: qlineargradient(x1:0,y1:0,x2:0,y2:1,"
            f" stop:0 {C['panel']}, stop:1 {C['inset']});"
            f" border: 1px solid {C['sel_border']};"
            f" border-left: 3px solid {left_border};"
            f" border-radius: {_RAD['lg']}px; }}"
        )
        cl = _VL(card)
        cl.setContentsMargins(_SPC["md"], _SPC["md"], _SPC["md"], _SPC["md"])
        cl.setSpacing(_SPC["sm"])
        head = _Lbl(
            f'<span style="color:{C["accent_hi"]};">{group_title}</span>'
            f'<span style="color:{C["dim"]};"> · {len(sub_actions)}</span>'
        )
        head.setTextFormat(Qt.TextFormat.RichText)
        head.setStyleSheet(
            f"font-size:11px; font-weight:800; letter-spacing:1px;"
        )
        cl.addWidget(head)
        for act_key, sub_label, glyph in sub_actions:
            cl.addWidget(_row(act_key, sub_label, glyph, card))
        v.addWidget(card)

    # Flash is special: only routes to the SPD/MTK tab for firmware work.
    # We DO NOT execute flash here; we just open the tab and instruct the user.
    flash_card = _Fr()
    flash_card.setObjectName("flashgroup")
    flash_card.setStyleSheet(
        f"QFrame#flashgroup {{ background: qlineargradient(x1:0,y1:0,x2:0,y2:1,"
        f" stop:0 {C['panel']}, stop:1 {C['inset']});"
        f" border: 1px solid {C['sel_border']};"
        f" border-left: 3px solid {C['experimental']};"
        f" border-radius: {_RAD['lg']}px; }}"
    )
    fl = _VL(flash_card)
    fl.setContentsMargins(_SPC["md"], _SPC["md"], _SPC["md"], _SPC["md"])
    fl.setSpacing(_SPC["sm"])
    fh = _Lbl("FLASH FIRMWARE")
    fh.setStyleSheet(
        f"color:{C['experimental_hi']}; font-size:11px; font-weight:800; letter-spacing:1px;"
    )
    fl.addWidget(fh)
    fb = QPushButton("  ⬆  Open Flash workbench (SPD/MTK tab)")
    fb.setCursor(Qt.CursorShape.PointingHandCursor)
    fb.setStyleSheet(
        "QPushButton { color:#fff; background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
        " stop:0 #d97706, stop:1 #f59e0b); border:none; border-radius:9px;"
        " padding:10px 14px; font-weight:800; font-size:12px; }"
        " QPushButton:hover { background: #f59e0b; }"
    )
    fb.setToolTip("Flash is destructive and firmware-specific. It opens the "
                  "SPD (or MTK) tab where you supply FDL1/FDL2 + a firmware "
                  "directory. Flash never runs inline from this page.")
    fb.clicked.connect(lambda: win._on_section(m.get("engine", "spd") if m.get("engine") in ("spd", "mtk") else "spd"))
    fl.addWidget(fb)
    v.addWidget(flash_card)

    v.addStretch(1)
    _scroll.setWidget(_host)
    _outer.addWidget(_scroll)
    return page


_EXPERIMENTAL_ACTS = {"apple_icloud_remove", "apple_icloud_add", "health", "pac_extract", "pac_pack", "ofp_extract", "knox_check", "knox_bypass", "qcn_backup", "qcn_imei_repair", "pixel_fastboot", "emmc_health"}


# ---------------- Phase-1 device-first: applicability --------------------
# Registry mode -> transports a connected phone must expose for the action
# to apply. Modes with unknown transports (Download mode, Samsung BROM)
# map to None = always enabled (never wrongly dimmed).
_MODE_TRANSPORTS = {
    "ADB": {"ADB"},
    "FASTBOOT": {"FASTBOOT"},
    "EDL": {"EDL"},
    "MTP": {"MTP"},
    "MTK": {"MTK", "MTK BROM"},
    "MTK BROM": {"MTK BROM"},
    "SPD": {"SPD"},
}

# Short-TTL cache over bridge.list_merged (a USB rescan each call).
# Guarded by a lock: concurrent scans must not let an older result
# overwrite a newer one.
import threading as _threading

_connected_cache = {"at": 0.0, "rows": []}
_connected_lock = _threading.Lock()
_CONNECTED_TTL = 5.0


def invalidate_connected_cache():
    """Force the next connected_rows() to rescan (manual refresh)."""
    _connected_cache["at"] = 0.0


def connected_rows():
    """Phone rows from the last detect-merged (cached 5s, [] on error).

    The lock is held through the scan: concurrent callers serialize and
    a stale result can never overwrite a newer one."""
    import time as _time
    with _connected_lock:
        now = _time.monotonic()
        if now - _connected_cache["at"] < _CONNECTED_TTL:
            return list(_connected_cache["rows"])
        rows = []
        try:
            from python.core import bridge as _bridge
            rows = _bridge.list_merged() or []
        except Exception:
            rows = []
        _connected_cache["at"] = _time.monotonic()
        _connected_cache["rows"] = rows
        return list(rows)


_BUCKET_KEYS = ("samsung", "mtk", "fastboot", "edl", "qcom", "spd",
                 "apple", "motorola", "other")


def buckets_from_rows(rows):
    """Group merged device rows into monitor buckets WITHOUT VID tables.

    Buckets derive purely from the Rust-assigned mode/transports — the
    single source of truth. Precedence mirrors the display order
    (fastboot first). ADB rows are passed through separately by callers.
    """
    buckets = {k: [] for k in _BUCKET_KEYS}
    for r in rows or []:
        if not isinstance(r, dict):
            continue
        mode = (r.get("mode") or "").lower()
        transports = set(str(t).upper() for t in (r.get("transports") or []))
        if "FASTBOOT" in transports:
            buckets["fastboot"].append(r)
        elif mode == "qualcomm-edl":
            buckets["edl"].append(r)
        elif mode.startswith("mediatek"):
            buckets["mtk"].append(r)
        elif mode in ("qualcomm", "qualcomm-diag"):
            buckets["qcom"].append(r)
        elif mode == "spd":
            buckets["spd"].append(r)
        elif mode == "apple":
            buckets["apple"].append(r)
        elif mode.startswith("motorola"):
            buckets["motorola"].append(r)
        elif mode.startswith("samsung"):
            buckets["samsung"].append(r)
        else:
            buckets["other"].append(r)
    return buckets


def connected_transports():
    """Union of transports across connected phone rows (may be empty)."""
    have = set()
    for row in connected_rows():
        for t in row.get("transports") or []:
            have.add(str(t).upper())
    return have


def usb_serial_ports(bus, addr):
    """Serial ports (ttyUSB*/ttyACM*) bound to the USB bus:addr device.

    Interface capture: a preloader/BROM/diag stage usually brings
    a VCOM port alongside the libusb device. Walks /sys (stdlib only),
    returns [] when nothing is bound or /sys is unavailable.
    """
    import os as _os
    found = []
    try:
        base = "/sys/bus/usb/devices"
        for entry in _os.listdir(base):
            ep = _os.path.join(base, entry)
            try:
                with open(_os.path.join(ep, "busnum")) as f:
                    eb = int(f.read().strip())
                with open(_os.path.join(ep, "devnum")) as f:
                    ea = int(f.read().strip())
            except (OSError, ValueError):
                continue
            if eb != bus or ea != addr:
                continue
            for root, dirs, _files in _os.walk(ep):
                for dd in dirs:
                    if dd.startswith("ttyUSB") or dd.startswith("ttyACM"):
                        if dd not in found:
                            found.append(dd)
                # Only the device node + its interface children matter.
                if root != ep and ":" not in _os.path.basename(root):
                    dirs[:] = []
    except OSError:
        return []
    return sorted(found)


# Actions the dimming pass must never dim: QR provisioning flows CREATE
# the ADB session (dimming them on a wizard MTP phone blocks the entry
# path), and the QR generator needs no device at all.
_QR_ENTRY_ACTS = {"frp_fake_login", "frp_fake_login_testdpc",
                  "frp_fake_login_adp",
                  "frp_qr_provision", "mdm_qr", "_qr_generator"}

# Router-level drill-down acts (not flow keys): transports they can use.
# None = adapts at click time (moto_frp) or guidance-level (the rest).
_ROUTER_ACTS = {
    "moto_frp": None,
    "info": None,
    "flash": None,
    "backup": None,
    "adb_enable": None,
    "kg_unlock": None,
    "frp": {"ADB", "FASTBOOT", "EDL", "MTP"},
    "screen_lock": {"ADB", "FASTBOOT", "EDL", "MTP"},
}


def required_transports(act):
    """Transports the act needs, from the Rust registry modes.

    Returns None when unknown (router/guidance acts, QR entry flows that
    create the session, unmapped modes like Download mode) — unknown means
    always enabled, never dimmed."""
    if act in _QR_ENTRY_ACTS:
        return None
    if act in _ROUTER_ACTS:
        return _ROUTER_ACTS[act]
    try:
        from python.core import core as _core
        reg = _core._load_registry()
    except Exception:
        return None
    if not reg:
        return None
    need = set()
    for row in reg:
        if row.get("key") == act:
            mapped = _MODE_TRANSPORTS.get(row.get("mode", ""))
            if mapped:
                need |= mapped
            else:
                # A mode we cannot map (e.g. Download mode): the requirement
                # is unknown, so the action stays enabled.
                return None
    return need or None


_DISABLED_SUFFIX = (
    " QPushButton:disabled { color:#5b6b80;"
    " background:rgba(255,255,255,8); border:1px solid rgba(255,255,255,0.06); }"
)


def apply_applicability(root):
    """Dim actions the connected phone can't use (buttons and hub tiles).

    An item dims only when exactly ONE phone is connected and its act
    positively requires an absent transport. Buttons disable + grey;
    tiles fade via opacity + ignore clicks. With no phone, several
    phones, or an unknown requirement, everything stays enabled.
    Purely additive: routing and labels are untouched."""
    if root is None:
        return
    from PyQt6.QtWidgets import QGraphicsOpacityEffect as _OPE
    rows = connected_rows()
    if len(rows) != 1:
        # Zero or several phones: restore everything enabled.
        for btn in root.findChildren(QPushButton):
            if not btn.property("flow_act"):
                continue
            if btn.property("flow_style") is not None:
                btn.setEnabled(True)
                btn.setStyleSheet(btn.property("flow_style") or "")
                btn.setToolTip(btn.property("flow_tip") or "")
        for tile in root.findChildren(QFrame):
            if not tile.property("flow_act"):
                continue
            tile.setGraphicsEffect(None)
            tile.setProperty("flow_dimmed", False)
            if tile.property("flow_tip") is not None:
                tile.setToolTip(tile.property("flow_tip") or "")
        return
    have = connected_transports()
    for btn in root.findChildren(QPushButton):
        act = btn.property("flow_act")
        if not act:
            continue
        if btn.property("flow_style") is None:
            btn.setProperty("flow_style", btn.styleSheet())
            btn.setProperty("flow_tip", btn.toolTip())
        base_style = btn.property("flow_style") or ""
        base_tip = btn.property("flow_tip") or ""
        need = required_transports(act)
        if have and need and not (need & have):
            btn.setEnabled(False)
            if _DISABLED_SUFFIX not in btn.styleSheet():
                btn.setStyleSheet(base_style + _DISABLED_SUFFIX)
            want = "/".join(sorted(need))
            got = "/".join(sorted(have)) if have else "none"
            btn.setToolTip(f"{base_tip}\nNeeds: {want} (connected: {got})")
        else:
            btn.setEnabled(True)
            if btn.styleSheet() != base_style:
                btn.setStyleSheet(base_style)
            if btn.toolTip() != base_tip:
                btn.setToolTip(base_tip)
    for tile in root.findChildren(QFrame):
        act = tile.property("flow_act")
        if not act:
            continue
        base_tip = tile.property("flow_tip") or tile.toolTip()
        need = required_transports(act)
        if have and need and not (need & have):
            eff = _OPE(tile)
            eff.setOpacity(0.4)
            tile.setGraphicsEffect(eff)
            tile.setProperty("flow_dimmed", True)
            want = "/".join(sorted(need))
            got = "/".join(sorted(have)) if have else "none"
            tile.setToolTip(f"{base_tip}\nNeeds: {want} (connected: {got})")
        else:
            tile.setGraphicsEffect(None)
            tile.setProperty("flow_dimmed", False)
            if tile.toolTip() != base_tip:
                tile.setToolTip(base_tip)


# Chip row: (engine, label, glyph, tool section). Section names
# match the window's _section_index (tools: mtk/qc/spd, samsung hub,
# dev_<brand> drill-down pages). None = no section exists yet.
_ENGINE_CHIPS = [
    ("mtk", "MTK", "▣", "mtk"),
    ("spd", "UNISOC", "✦", "spd"),
    ("qcom", "Qualcomm", "◈", "qc"),
    ("odin", "Samsung", "Ⓢ", "samsung"),
    ("apple", "Apple", "🍎", "dev_apple"),
    ("motorola", "Motorola", "📱", "dev_motorola"),
    ("kirin", "Kirin", "🐉", None),
]


def build_adb_hub_page(win):
    """ADB hub: three graphical tiles — ADB Remove FRP, ADB Remove MDM,
    ADB Info. Fixed-size cards in a left-aligned row (they never stretch
    to fill the area). Brand/chip-specific ADB flows stay on their device
    pages — each flow has exactly one home."""
    from PyQt6.QtWidgets import (QVBoxLayout as _VL, QHBoxLayout as _HL,
                                 QLabel as _Lbl, QWidget as _W,
                                 QFrame as _Fr,
                                 QGraphicsOpacityEffect as _OPE)
    C, _btn_ghost, _btn_primary, _btn_danger = _tok()
    page = _W()
    page.setStyleSheet("background: transparent;")
    v = _VL(page)
    v.setContentsMargins(10, 8, 10, 8)
    v.setSpacing(10)
    head = _Lbl("🔌  ADB Hub")
    head.setStyleSheet(f"color:{C['text']}; font-size:15px; font-weight:800;")
    v.addWidget(head)
    sub = _Lbl("Brand-specific ADB actions live on their device pages.")
    sub.setStyleSheet(f"color:{C['dim']}; font-size:11px;")
    sub.setWordWrap(True)
    v.addWidget(sub)

    row = _HL()
    row.setSpacing(12)
    for act_key, glyph, title, sub_label in (
        ("adb_frp", "⚡", "ADB Remove FRP", "Zero frp flag\n+ wizards"),
        ("mdm_unlock", "🔓", "ADB Remove MDM", "Remove device\nowner"),
        ("adb_info", "ℹ", "ADB Info", "getprop dump\n+ fingerprint"),
    ):
        meta_lbl, meta_glyph, meta_tip = _ACTION_META.get(act_key, (title, glyph, ""))
        tile = _Fr()
        tile.setFixedSize(170, 150)
        tile.setCursor(Qt.CursorShape.PointingHandCursor)
        tile.setStyleSheet(
            f"QFrame {{ background: qlineargradient(x1:0,y1:0,x2:0,y2:1,"
            f" stop:0 {C['card']}, stop:1 {C['inset']});"
            f" border:1px solid {C['border']}; border-left:3px solid {C['accent_hi']};"
            " border-radius:12px; }"
            f"QFrame:hover {{ border:1px solid {C['accent_hi']};"
            f" border-left:3px solid {C['accent_hi']}; background:{C['card_hover']}; }}"
        )
        tl = _VL(tile)
        tl.setContentsMargins(8, 10, 8, 10)
        tl.setSpacing(2)
        icon = _Lbl(meta_glyph or glyph)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        icon.setStyleSheet("font-size:44px; background:transparent; border:none;")
        tl.addWidget(icon)
        name = _Lbl(meta_lbl or title)
        name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name.setWordWrap(True)
        name.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        name.setStyleSheet(f"color:{C['text']}; font-size:12px; font-weight:800; background:transparent; border:none;")
        tl.addWidget(name)
        hint = _Lbl(sub_label)
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setWordWrap(True)
        hint.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        hint.setStyleSheet(f"color:{C['dim']}; font-size:10px; background:transparent; border:none;")
        tl.addWidget(hint)
        tile.setToolTip(meta_tip or sub_label)
        tile.setProperty("flow_act", act_key)
        tile.setProperty("flow_tip", meta_tip or sub_label)

        def _go(_e=None, a=act_key, t=tile):
            if t.property("flow_dimmed"):
                return
            _dispatch(win, a, "ADB", {})
        tile.mousePressEvent = _go
        row.addWidget(tile)
    row.addStretch(1)
    v.addLayout(row)

    # QR provisioning row: a single "QR Provision" entry that opens the QR
    # window (TestDPC by default; Google Device Policy + FlashPilot are the
    # two optional QRs in its dropdown). QR provisioning creates the ADB
    # session, so it is exempt from transport dimming (see _QR_ENTRY_ACTS).
    qr_head = _Lbl("QR PROVISIONING (setup wizard)")
    qr_head.setStyleSheet(f"color:{C['mute']}; font-size:11px; font-weight:800; letter-spacing:1px;")
    v.addWidget(qr_head)
    qr_row = _HL()
    qr_row.setSpacing(12)
    meta_lbl, meta_glyph, meta_tip = _ACTION_META.get(
        "_qr_generator", ("QR Provision", "📷", ""))
    tile = _Fr()
    tile.setFixedSize(210, 150)
    tile.setCursor(Qt.CursorShape.PointingHandCursor)
    tile.setStyleSheet(
        f"QFrame {{ background: qlineargradient(x1:0,y1:0,x2:0,y2:1,"
        f" stop:0 {C['card']}, stop:1 {C['inset']});"
        f" border:1px solid {C['border']}; border-left:3px solid {C['accent_hi']};"
        " border-radius:12px; }"
        f"QFrame:hover {{ border:1px solid {C['accent_hi']};"
        f" border-left:3px solid {C['accent_hi']}; background:{C['card_hover']}; }}"
    )
    tl = _VL(tile)
    tl.setContentsMargins(8, 10, 8, 10)
    tl.setSpacing(2)
    icon = _Lbl(meta_glyph)
    icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
    icon.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    icon.setStyleSheet("font-size:44px; background:transparent; border:none;")
    tl.addWidget(icon)
    name = _Lbl(meta_lbl)
    name.setAlignment(Qt.AlignmentFlag.AlignCenter)
    name.setWordWrap(True)
    name.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    name.setStyleSheet(f"color:{C['text']}; font-size:12px; font-weight:800; background:transparent; border:none;")
    tl.addWidget(name)
    hint = _Lbl("TestDPC (default)\n+ Google · FlashPilot")
    hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
    hint.setWordWrap(True)
    hint.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    hint.setStyleSheet(f"color:{C['dim']}; font-size:10px; background:transparent; border:none;")
    tl.addWidget(hint)
    tile.setToolTip(meta_tip or "Device-owner QR provisioning")
    tile.setProperty("flow_act", "_qr_generator")
    tile.setProperty("flow_tip", meta_tip or "Device-owner QR provisioning")

    def _go(_e=None, t=tile):
        if t.property("flow_dimmed"):
            return
        _dispatch(win, "_qr_generator", "ADB", {})
    tile.mousePressEvent = _go
    qr_row.addWidget(tile)
    qr_row.addStretch(1)
    v.addLayout(qr_row)
    v.addStretch(1)
    return page


def build_fastboot_hub_page(win):
    """Fastboot hub: BL Unlock / BL Relock / Reboot / Recovery / Info tiles.

    Mirrors the ADB hub (fixed-size cards in a left-aligned row). The
    unlock-code field feeds win._moto_unlock_code so the Unlock tile's
    flow gets its --code. Per-device fastboot flows (moto_frp_fastboot)
    stay on their device pages."""
    from PyQt6.QtWidgets import (QVBoxLayout as _VL, QHBoxLayout as _HL,
                                 QLabel as _Lbl, QWidget as _W,
                                 QFrame as _Fr, QLineEdit as _LE)
    C, _btn_ghost, _btn_primary, _btn_danger = _tok()
    page = _W()
    page.setStyleSheet("background: transparent;")
    v = _VL(page)
    v.setContentsMargins(10, 8, 10, 8)
    v.setSpacing(10)
    head = _Lbl("⚡  Fastboot Hub")
    head.setStyleSheet(f"color:{C['text']}; font-size:15px; font-weight:800;")
    v.addWidget(head)
    sub = _Lbl("Bootloader actions for any fastboot phone. Per-device fastboot flows stay on their device pages.")
    sub.setStyleSheet(f"color:{C['dim']}; font-size:11px;")
    sub.setWordWrap(True)
    v.addWidget(sub)

    code_row = _HL()
    code_row.setSpacing(8)
    code_lbl = _Lbl("Unlock code")
    code_lbl.setStyleSheet(f"color:{C['dim']}; font-size:11px; font-weight:700;")
    code_row.addWidget(code_lbl)
    code_edit = _LE()
    code_edit.setPlaceholderText("20-char code (BL Unlock only)")
    code_edit.setMinimumHeight(30)
    code_edit.setStyleSheet(
        f"QLineEdit {{ background: {C['inset']}; border: 1px solid {C['border']};"
        " border-radius: 6px; padding: 5px 10px; color: #e2e8f0;"
        " font-family:'Consolas', 'Monaco', monospace; font-size: 12px;"
        " letter-spacing: 1px; }"
    )
    code_row.addWidget(code_edit, 1)
    v.addLayout(code_row)
    try:
        win._moto_unlock_code = code_edit
    except Exception:
        pass

    from PyQt6.QtWidgets import QSizePolicy as _SP2
    lst = _VL()
    lst.setSpacing(12)
    for act_key, glyph, title, sub_label in (
        ("fastboot_unlock", "🔓", "BL Unlock", "oem unlock + code"),
        ("fastboot_lock", "🔒", "BL Relock", "flashing lock"),
        ("fastboot_reboot", "🔃", "Reboot", "reboot to system"),
        ("fastboot_recovery", "🔃", "Recovery", "reboot to recovery"),
        ("fastboot_getvar", "ℹ", "Fastboot Info", "getvar all"),
    ):
        meta_lbl, meta_glyph, meta_tip = _ACTION_META.get(act_key, (title, glyph, ""))
        tile = _Fr()
        tile.setMinimumHeight(64)
        tile.setFixedWidth(220)
        tile.setSizePolicy(_SP2.Policy.Fixed, _SP2.Policy.Fixed)
        tile.setCursor(Qt.CursorShape.PointingHandCursor)
        tile.setStyleSheet(
            f"QFrame {{ background: qlineargradient(x1:0,y1:0,x2:0,y2:1,"
            f" stop:0 {C['card']}, stop:1 {C['inset']});"
            f" border:1px solid {C['border']}; border-left:3px solid {C['accent_hi']};"
            " border-radius:12px; }"
            f"QFrame:hover {{ border:1px solid {C['accent_hi']};"
            f" border-left:3px solid {C['accent_hi']}; background:{C['card_hover']}; }}"
        )
        tl = _HL(tile)
        tl.setContentsMargins(12, 8, 12, 8)
        tl.setSpacing(12)
        icon = _Lbl(meta_glyph or glyph)
        icon.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        icon.setStyleSheet("font-size:32px; background:transparent; border:none;")
        tl.addWidget(icon)
        txt = _VL()
        txt.setContentsMargins(0, 0, 0, 0)
        txt.setSpacing(2)
        name = _Lbl(meta_lbl or title)
        name.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        name.setStyleSheet(f"color:{C['text']}; font-size:13px; font-weight:800; background:transparent; border:none;")
        txt.addWidget(name)
        hint = _Lbl(sub_label)
        hint.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        hint.setStyleSheet(f"color:{C['dim']}; font-size:11px; background:transparent; border:none;")
        txt.addWidget(hint)
        tl.addLayout(txt, 1)
        tile.setToolTip(meta_tip or sub_label)
        tile.setProperty("flow_act", act_key)
        tile.setProperty("flow_tip", meta_tip or sub_label)

        def _go(_e=None, a=act_key, t=tile):
            if t.property("flow_dimmed"):
                return
            _dispatch(win, a, "Fastboot", {})
        tile.mousePressEvent = _go
        lst.addWidget(tile)
    v.addLayout(lst)
    v.addStretch(1)
    return page


def build_easylogin_hub_page(win):
    """Easy Login hub: the three DPC provisioning choices + MDM QR, one
    tile each. Scanned in the setup wizard; enrollment ends the wizard
    before the FRP gate. Own page (Transports ▸ Easy Login) and linked
    from the MDM area."""
    from PyQt6.QtWidgets import QSizePolicy as _SP2
    C, _btn_ghost, _btn_primary, _btn_danger = _tok()
    page = QWidget()
    page.setStyleSheet("background: transparent;")
    v = QVBoxLayout(page)
    v.setContentsMargins(10, 8, 10, 8)
    v.setSpacing(10)
    head = QLabel("📷  Easy Login — QR provisioning")
    head.setStyleSheet(f"color:{C['text']}; font-size:15px; font-weight:800;")
    v.addWidget(head)
    sub = QLabel(
        "Scan in the setup wizard (tap the Welcome screen 6 times fast): the DPC\n"
        "enrolls as device owner, the wizard ends before the FRP gate, then FRP clears over ADB.")
    sub.setStyleSheet(f"color:{C['dim']}; font-size:11px;")
    sub.setWordWrap(True)
    v.addWidget(sub)

    def _tile(act_key, glyph, title, sub_label, tip):
        t = QFrame()
        t.setMinimumHeight(64)
        t.setSizePolicy(_SP2.Policy.Expanding, _SP2.Policy.Fixed)
        t.setCursor(Qt.CursorShape.PointingHandCursor)
        t.setStyleSheet(
            f"QFrame {{ background: qlineargradient(x1:0,y1:0,x2:0,y2:1,"
            f" stop:0 {C['card']}, stop:1 {C['inset']});"
            f" border:1px solid {C['border']}; border-left:3px solid {C['accent_hi']};"
            " border-radius:12px; }"
            f"QFrame:hover {{ border:1px solid {C['accent_hi']};"
            f" border-left:3px solid {C['accent_hi']}; background:{C['card_hover']}; }}"
        )
        tl = QHBoxLayout(t)
        tl.setContentsMargins(12, 8, 12, 8)
        tl.setSpacing(12)
        icon = QLabel(glyph)
        icon.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        icon.setStyleSheet("font-size:32px; background:transparent; border:none;")
        tl.addWidget(icon)
        txt = QVBoxLayout()
        txt.setContentsMargins(0, 0, 0, 0)
        txt.setSpacing(2)
        name = QLabel(title)
        name.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        name.setStyleSheet(f"color:{C['text']}; font-size:13px; font-weight:800; background:transparent; border:none;")
        txt.addWidget(name)
        hint = QLabel(sub_label)
        hint.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        hint.setStyleSheet(f"color:{C['dim']}; font-size:11px; background:transparent; border:none;")
        txt.addWidget(hint)
        tl.addLayout(txt, 1)
        meta = _ACTION_META.get(act_key)
        t.setToolTip((meta[2] if meta else "") or tip)
        t.setProperty("flow_act", act_key)
        t.setProperty("flow_tip", (meta[2] if meta else "") or tip)

        def _go(_e=None, a=act_key, tt=t):
            if tt.property("flow_dimmed"):
                return
            _dispatch(win, a, "Easy Login", {})
        t.mousePressEvent = _go
        return t

    lst = QVBoxLayout()
    lst.setSpacing(12)
    lst.addWidget(_tile(
        "frp_fake_login", "🧩", "Easy Login · FlashPilot DPC",
        "Our own app — completes setup + enables ADB by itself",
        "Needs the APK built (android/FlashPilotDPC/build.sh); warns honestly if missing."))
    lst.addWidget(_tile(
        "frp_fake_login_testdpc", "🧪", "Easy Login · TestDPC",
        "Google's sample DPC — local APK or Play Store",
        "Downloads from this PC when served, else the Play Store."))
    lst.addWidget(_tile(
        "frp_fake_login_adp", "🏢", "Easy Login · Device Policy",
        "Android Device Policy — Play Store download",
        "Google's production DPC (oobconfig); needs Play Store reachability."))
    lst.addWidget(_tile(
        "_qr_generator", "📷", "QR Provision",
        "Device-owner QR — TestDPC (default) + Google / FlashPilot",
        "Opens the QR window: TestDPC is shown; the dropdown offers the "
        "two optional DPCs (Google Device Policy, FlashPilot)."))
    v.addLayout(lst)
    v.addStretch(1)
    return page


def _moto_frp_adb_enabled():
    """True when a connected phone reports an ADB transport (the detected
    transports from the bridge's merged view). Cheap: reads the cached
    detect output the bridge refreshes on demand."""
    try:
        from python.core import bridge
        rows = bridge.list_merged() or []
        for row in rows:
            if "ADB" in (row.get("transports") or []):
                return True
    except Exception:
        pass
    return False


def _moto_fw_dir():
    """Staged-flash firmware dir (signed stock FW with flashfile.xml).

    Only MOTO_FW_DIR counts — the Rust flow reads the same env itself,
    so the GUI check and the flow can never disagree."""
    import os as _os
    d = _os.environ.get("MOTO_FW_DIR", "").strip()
    if d and _os.path.isdir(d) and _os.path.isfile(_os.path.join(d, "flashfile.xml")):
        return d
    return ""


def _moto_frp_choice():
    """(act, label, reason): ADB → moto_frp_adb; fastboot + staged
    firmware → moto_fb_frp; fastboot without firmware → CVE chain."""
    if _moto_frp_adb_enabled():
        return ("moto_frp_adb", "ADB FRP Remove", "")
    fw = _moto_fw_dir()
    if fw:
        return ("moto_fb_frp", "Fastboot Staged FRP",
                f"signed firmware found at {fw}")
    return ("moto_frp_fastboot", "FRP Fastboot Remove",
            "no staged firmware (MOTO_FW_DIR) — CVE-2016-10277 chain")


def _moto_frp_dispatch(win):
    """Adaptive FRP Remove: dispatch by live state (see _moto_frp_choice).
    The reason is toasted so the choice is never a mystery."""
    act, _label, reason = _moto_frp_choice()
    if reason and hasattr(win, "_toasts"):
        try:
            win._toasts.show_info("FRP strategy", reason)
        except Exception:
            pass
    _dispatch(win, act, "Motorola", {})


def _moto_frp_label():
    """Button label that names the strategy from the CURRENT device state."""
    _act, label, _reason = _moto_frp_choice()
    return label


def _dispatch(win, act, brand_label, m):
    """Route every action through the window's engine-aware router.
    Experimental acts are gated via the EXPERIMENTAL overlay (amber, ack, audit)
    — they stay under their native brand/model but flag as EXPERIMENTAL, tab-like."""
    if act == "moto_frp":
        _moto_frp_dispatch(win)
        return
    if act == "_qr_generator":
        win._open_qr_generator()
        return
    if act in _EXPERIMENTAL_ACTS:
        try:
            from python.core import experimental as _exp

            # Act key -> experimental feature id (single source; the flow
            # runners resolve the same map so tokens stay feature-bound).
            feat = _exp.FLOW_FEATURE_IDS.get(act, act)
            title, warn = _exp.get_warning(feat)

            def _go(_feat=feat):
                win.start_model_action(act, brand_label, m, feature=_feat)

            # Use the window's experimental overlay if available, else direct
            if hasattr(win, "_confirm_experimental_overlay"):
                win._confirm_experimental_overlay(feat, title, warn, act, confirm_label="I Accept — Run", on_confirm=_go, chip="wipe")
            else:
                _go()
            return
        except Exception:
            pass
    win.start_model_action(act, brand_label, m)
