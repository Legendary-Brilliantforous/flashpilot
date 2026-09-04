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
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)


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
    "apple_icloud_remove": ("iCloud Remove",     "🧪", "EXPERIMENTAL — DFU/ramdisk iCloud remove (usbmuxd). Educational, own device only (at-apple-icloud-remove)."),
    "apple_icloud_add":    ("iCloud Add",        "🧪", "EXPERIMENTAL — Push activation plist via lockdownd (at-apple-icloud-add)."),
    "health":              ("Health Report",     "🧪", "EXPERIMENTAL — Device health JSON + HTML/PDF (health_report)."),
    "pac_extract":         ("PAC Extract",       "🧪", "EXPERIMENTAL — Extract SPD PAC container (pac_extract)."),
    "pac_pack":            ("PAC Pack",          "🧪", "EXPERIMENTAL — Pack folder to PAC (pac_pack)."),
    "knox_check":          ("Knox Check",        "🧪", "EXPERIMENTAL — Knox warranty/KG read (knox_check)."),
    "knox_bypass":         ("Knox Bypass",       "🧪", "EXPERIMENTAL — Knox eFuse trip (irreversible, edu)."),
    "qcn_backup":          ("QCN Backup",        "🧪", "EXPERIMENTAL — modemst1/2 backup (qcn_backup)."),
    "qcn_imei_repair":     ("IMEI Repair",       "🧪", "EXPERIMENTAL — NV 682 IMEI restore-only (edu)."),
    "pixel_fastboot":      ("Pixel Fastboot",    "🧪", "EXPERIMENTAL — Pixel factory/unlock (fastboot)."),
    "emmc_health":         ("eMMC Health",       "🧪", "EXPERIMENTAL — eMMC/UFS health read."),
}


def nav_entries():
    """(key_suffix, icon, label) triples for every brand — used by app shell."""
    return [(f"dev_{b['key']}", b.get("icon", "▣"), b["label"]) for b in BRANDS]


def _card(text, sub="", accent=None, clickable=True):
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
        f"QFrame:hover {{ border-color: {accent}; }}"
        f"QFrame:focus {{ border-color: {accent}; outline:none; }}"
    )
    lay = QVBoxLayout(card)
    lay.setContentsMargins(10, 7, 10, 7)
    lay.setSpacing(4)
    t = QLabel(text)
    t.setStyleSheet(f"color:{C['text']}; font-size:13px; font-weight:800;"
                    f" background:transparent; border:none;")
    t.setWordWrap(True)
    lay.addWidget(t)
    if sub:
        s = QLabel(sub)
        s.setStyleSheet(f"color:{C['dim']}; font-size:10px;"
                        f" background:transparent; border:none;")
        s.setWordWrap(True)
        lay.addWidget(s)
    return card


def build_brand_page(win, key):
    """Level 2: model cards grid + nested stack to Level 3."""
    C, _btn_ghost, _btn_primary, _btn_danger = _tok()
    brand = BRAND_BY_KEY[key]
    models = brand.get("models", [])

    stack = QStackedWidget()
    stack.setStyleSheet("background: transparent;")

    # --- grid page ---
    grid_page = QWidget()
    grid_page.setStyleSheet("background: transparent;")
    outer = QVBoxLayout(grid_page)
    outer.setContentsMargins(10, 8, 10, 8)
    outer.setSpacing(6)

    head = QLabel(f"{brand.get('icon','')}  {brand['label']} — pick a model")
    head.setStyleSheet(f"color:{C['text']}; font-size:15px; font-weight:800;")
    outer.addWidget(head)

    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setStyleSheet("QScrollArea { background: transparent; }")
    host = QWidget()
    host.setStyleSheet("background: transparent;")
    grid = QGridLayout(host)
    grid.setContentsMargins(0, 0, 0, 0)
    grid.setSpacing(8)

    for i, m in enumerate(models):
        researched = m.get("status") == "researched"
        chip_badge = f"{m.get('chip','?')}  ·  {m.get('engine','?').upper()}"
        status_txt = "✓ researched — instant actions" if researched else "… planned — help us research"
        sub = f"{chip_badge}\n{status_txt}"
        card = _card(m["model"], sub,
                     accent=C["ok"] if researched else C["mute"],
                     clickable=True)
        card.setToolTip(m.get("notes") or "")
        r, c = divmod(i, 3)
        grid.addWidget(card, r, c)

    grid.setColumnStretch(0, 1)
    grid.setColumnStretch(1, 1)
    grid.setColumnStretch(2, 1)
    grid.setRowStretch(len(models) // 3 + 1, 1)
    scroll.setWidget(host)
    outer.addWidget(scroll, 1)
    stack.addWidget(grid_page)

    # keep one model-page instance per model, created lazily on first click
    def open_model(m):
        page = _build_model_page(win, brand, m, back=lambda: stack.setCurrentIndex(0))
        stack.addWidget(page)
        stack.setCurrentWidget(page)

    # bind cards to the lazy builder
    for i in range(grid.count()):
        card = grid.itemAt(i).widget()
        m = models[i]
        card.mousePressEvent = lambda e, mm=m, op=open_model: op(mm)

    win._device_stacks[key] = stack
    return stack


def _build_model_page(win, brand, m, back):
    """Level 3: per-model action board, grouped by job (FRP / MDM / Screen Lock /
    Device Check / Enable ADB / Flash) — each with ADB and BROM sub-actions."""
    C, _btn_ghost, _btn_primary, _btn_danger = _tok()
    from PyQt6.QtWidgets import QVBoxLayout as _VL, QHBoxLayout as _HL, QLabel as _Lbl, QFrame as _Fr, QGridLayout as _GL, QSizePolicy as _SP
    page = QWidget()
    page.setStyleSheet("background: transparent;")
    v = _VL(page)
    v.setContentsMargins(10, 8, 10, 8)
    v.setSpacing(8)

    top = _HL()
    back_btn = QPushButton("← Back")
    back_btn.setStyleSheet(_btn_ghost())
    back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    back_btn.setFixedWidth(90)
    back_btn.clicked.connect(lambda: back())
    top.addWidget(back_btn)
    title = _Lbl(f"{brand['label']} · {m['model']}")
    title.setStyleSheet(f"color:{C['text']}; font-size:15px; font-weight:800;")
    top.addWidget(title, 1)
    chip_lbl = _Lbl(f"{m.get('chip','')}   engine: {m.get('engine','—').upper()}")
    chip_lbl.setStyleSheet(
        "color:#04121a; background:#d4b78f; border-radius:8px;"
        " padding:3px 10px; font-size:11px; font-weight:800;"
    )
    top.addWidget(chip_lbl)
    v.addLayout(top)

    notes = m.get("notes") or ""
    if notes:
        n = _Lbl(notes)
        n.setWordWrap(True)
        n.setStyleSheet(f"color:{C['dim']}; font-size:11px;"
                        f" background:{C['inset']}; border:1px solid {C['border']};"
                        " border-radius:8px; padding:8px;")
        v.addWidget(n)

    researched = m.get("status") == "researched"
    if not researched:
        empty = _Lbl("No wired actions yet for this model — research in progress.")
        empty.setStyleSheet(f"color:{C['mute']}; font-size:12px;")
        v.addWidget(empty)
        v.addStretch(1)
        return page

    # Job groups — per-brand (tecno keeps reverse-engineered flows, others use generic wired flows).
    if brand.get("key") == "tecno":
        groups = [
            ("FRP REMOVE", [
                ("tecno_frp_adb", "ADB · settings + GMS + accounts", "⚡"),
                ("tecno_frp_brom", "BROM · SPD userdata wipe", "🛠"),
            ]),
            ("MDM REMOVE", [
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
    else:
        # Generic wired actions (motorola G6, nokia G20, samsung, etc.) — routed in qt_app.start_model_action.
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
            ]),
            ("ENABLE ADB", [
                ("adb_enable", "MTP / secret-code path", "⚙"),
            ]),
        ]

    def _row(act_key, sub_label, glyph, parent):
        btn = QPushButton()
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn.setMinimumHeight(44)
        btn.setMinimumWidth(180)
        btn.setSizePolicy(_SP.Policy.Expanding, _SP.Policy.Fixed)
        # Compose label: glyph + meta label + sub label (2 lines)
        meta_lbl, meta_glyph, meta_tip = _ACTION_META.get(
            act_key, (act_key, glyph, ""))
        is_experimental = act_key in _EXPERIMENTAL_ACTS
        title = meta_lbl
        if is_experimental:
            title = f"🧪 {title} · EXPERIMENTAL"
        if any(k in act_key for k in ("frp", "mdm", "screen_lock", "lock")):
            # wipe-class buttons: red gradient - no red border on press/focus/checked, smaller for visibility
            btn.setStyleSheet(
                "QPushButton { color:#fff; background:"
                " qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #dc2626, stop:1 #ef4444);"
                " border:none; border-radius:8px; padding:6px 12px; font-weight:700; font-size:10px; }"
                " QPushButton:hover { background: #ef4444; border:none; }"
                " QPushButton:pressed { background: #b91c1c; border:none; }"
                " QPushButton:focus { outline:none; border:none; }"
                " QPushButton:checked { background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #dc2626, stop:1 #ef4444); border:none; }"
            )
        else:
            s = _btn_primary()
            s = s.replace("font-size: 12px;", "font-size: 10px;").replace("padding: 8px 18px;", "padding: 6px 12px;").replace("border-radius: 9px;", "border-radius: 8px;")
            s += " QPushButton:focus { outline:none; border:1px solid rgba(255,255,255,0.08); } QPushButton:pressed { border:1px solid rgba(255,255,255,0.08); } QPushButton:checked { border:1px solid rgba(255,255,255,0.08); } QPushButton:checked:focus { border:1px solid rgba(255,255,255,0.08); }"
            btn.setStyleSheet(s)
        # Custom 2-line text
        btn.setText(f"  {meta_glyph}  {title}\n         {sub_label}")
        btn.setToolTip(meta_tip)
        btn.clicked.connect(
            lambda _=False, a=act_key, bl=brand['label'], mm=m: _dispatch(win, a, bl, mm)
        )
        return btn

    # --- Horizontal layout: FRP REMOVE horizontal + rest as tabs (all researched, Spark 10C was pilot) ---
    is_horizontal = m.get("status") == "researched"
    if is_horizontal:
        from PyQt6.QtWidgets import QStackedWidget as _Stk
        tab_bar = _HL()
        tab_bar.setSpacing(6)
        tab_bar.setContentsMargins(0, 6, 0, 6)
        stack = _Stk()
        stack.setStyleSheet("background: transparent;")
        tab_btns = []
        # Spark 10C: smaller text + no focus border (user reported too large + red border on click)
        def _row_small(act_key, sub_label, glyph, parent):
            b = QPushButton()
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            b.setMinimumHeight(44)
            b.setMinimumWidth(220)
            b.setSizePolicy(_SP.Policy.Expanding, _SP.Policy.Fixed)
            meta_lbl, meta_glyph, meta_tip = _ACTION_META.get(act_key, (act_key, glyph, ""))
            title = meta_lbl
            if any(k in act_key for k in ("frp", "mdm", "screen_lock", "lock")):
                b.setStyleSheet(
                    "QPushButton { color:#fff; background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #dc2626, stop:1 #ef4444);"
                    " border:none; border-radius:8px; padding:6px 12px; font-weight:700; font-size:10px; }"
                    " QPushButton:hover { background: #ef4444; border:none; }"
                    " QPushButton:pressed { background: #b91c1c; border:none; }"
                    " QPushButton:focus { outline:none; border:none; }"
                )
            else:
                # use primary but smaller
                s = _btn_primary()
                s = s.replace("font-size: 12px;", "font-size: 10px;").replace("padding: 8px 18px;", "padding: 6px 12px;").replace("border-radius: 9px;", "border-radius: 8px;")
                s += " QPushButton:focus { outline:none; }"
                b.setStyleSheet(s)
                b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            b.setText(f"  {meta_glyph}  {title}\n         {sub_label}")
            b.setToolTip(meta_tip)
            b.clicked.connect(lambda _=False, a=act_key, bl=brand['label'], mm=m: _dispatch(win, a, bl, mm))
            return b

        for idx, (group_title, sub_actions) in enumerate(groups):
            btn = QPushButton(group_title)
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn.setFixedHeight(28)
            btn.setSizePolicy(_SP.Policy.Expanding, _SP.Policy.Fixed)
            f = btn.font(); f.setPixelSize(10); f.setBold(True); btn.setFont(f)
            btn.setStyleSheet(
                "QPushButton { color:#8fa4bd; background:rgba(255,255,255,9); border:1px solid rgba(255,255,255,0.08); border-radius:14px; padding:0 14px; font-size:10px; }"
                "QPushButton:hover { color:#e2e8f0; border-color:rgba(255,255,255,0.22); background:rgba(255,255,255,20); }"
                "QPushButton:checked { color:#04121a; background:qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #d4b78f, stop:1 #b89a6a); border: 1px solid rgba(255,255,255,0.18); }"
                "QPushButton:focus { outline:none; border:1px solid rgba(255,255,255,0.08); }"
                "QPushButton:checked:focus { border: 1px solid rgba(255,255,255,0.18); outline:none; }"
                "QPushButton:pressed { background:rgba(255,255,255,20); border:1px solid rgba(255,255,255,0.08); }"
            )
            if idx == 0:
                btn.setChecked(True)
            tab_bar.addWidget(btn)
            tab_btns.append(btn)
            page_card = _Fr()
            page_card.setStyleSheet(
                f"QFrame {{ background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 {C['card']}, stop:1 {C['inset']});"
                " border:1px solid #1c3052; border-left:3px solid #d4b78f; border-radius:10px; }"
            )
            cl = _VL(page_card)
            cl.setContentsMargins(12, 12, 12, 12)
            cl.setSpacing(8)
            for act_key, sub_label, glyph in sub_actions:
                cl.addWidget(_row_small(act_key, sub_label, glyph, page_card))
            wrap = QWidget()
            wrap.setStyleSheet("background: transparent;")
            wl = _VL(wrap)
            wl.setContentsMargins(0,0,0,0)
            wl.addWidget(page_card)
            wl.addStretch(1)
            stack.addWidget(wrap)
        def _on_tab(idx):
            for i, b in enumerate(tab_btns):
                b.setChecked(i == idx)
            stack.setCurrentIndex(idx)
            try:
                w = stack.currentWidget()
                if w:
                    for child in w.findChildren(QFrame):
                        lay = child.layout()
                        if lay and hasattr(lay, "invalidate"):
                            lay.invalidate()
                    w.updateGeometry()
            except Exception:
                pass
        for i, b in enumerate(tab_btns):
            b.clicked.connect(lambda _=False, ix=i: _on_tab(ix))
        tab_bar.addStretch(1)
        badge_txt = f"{m.get('chip','')[:22]} · {m.get('model','').upper()}"
        badge = _Lbl(badge_txt)
        badge.setStyleSheet("color:#04121a; background:#d4b78f; border-radius:8px; padding:4px 10px; font-size:10px; font-weight:800; letter-spacing:0.6px;")
        badge.setToolTip(m.get("notes","")[:120])
        tab_bar.addWidget(badge)
        v.addLayout(tab_bar)
        v.addWidget(stack, 1)
        flash_card = _Fr()
        flash_card.setObjectName("flashgroup")
        flash_card.setStyleSheet(
            f"QFrame#flashgroup {{ background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 {C['card']}, stop:1 {C['inset']});"
            f" border:1px solid {C['border']}; border-left:3px solid #f59e0b; border-radius:10px; }}"
        )
        fl = _VL(flash_card)
        fl.setContentsMargins(12, 10, 12, 10)
        fl.setSpacing(6)
        fh = _Lbl("FLASH FIRMWARE")
        fh.setStyleSheet(f"color:#fbbf24; font-size:11px; font-weight:800; letter-spacing:1px;")
        fl.addWidget(fh)
        fb = QPushButton("  ⬆  Open Flash workbench (SPD tab)")
        fb.setCursor(Qt.CursorShape.PointingHandCursor)
        fb.setStyleSheet(
            "QPushButton { color:#fff; background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #d97706, stop:1 #f59e0b); border:none; border-radius:9px; padding:10px 14px; font-weight:800; font-size:12px; }"
            " QPushButton:hover { background: #f59e0b; }"
        )
        fb.clicked.connect(lambda: win._on_section(m.get("engine", "spd") if m.get("engine") in ("spd", "mtk") else "spd"))
        fl.addWidget(fb)
        v.addWidget(flash_card)
        v.addStretch(1)
        return page

    for group_title, sub_actions in groups:
        # Section card
        card = _Fr()
        card.setObjectName("modelgroup")
        card.setStyleSheet(
            "QFrame#modelgroup { background: qlineargradient(x1:0,y1:0,x2:0,y2:1,"
            " stop:0 #122a4a, stop:1 #0a1529);"
            " border: 1px solid #1c3052; border-left: 3px solid #d4b78f;"
            " border-radius: 10px; }"
        )
        cl = _VL(card)
        cl.setContentsMargins(12, 10, 12, 10)
        cl.setSpacing(6)
        head = _Lbl(group_title)
        head.setStyleSheet(
            f"color:{C['accent_hi']}; font-size:11px; font-weight:800; letter-spacing:1px;"
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
        f" stop:0 {C['card']}, stop:1 {C['inset']});"
        f" border: 1px solid {C['border']}; border-left: 3px solid #f59e0b;"
        f" border-radius: 10px; }}"
    )
    fl = _VL(flash_card)
    fl.setContentsMargins(12, 10, 12, 10)
    fl.setSpacing(6)
    fh = _Lbl("FLASH FIRMWARE")
    fh.setStyleSheet(
        f"color:#fbbf24; font-size:11px; font-weight:800; letter-spacing:1px;"
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
    return page


_EXPERIMENTAL_ACTS = {"apple_icloud_remove", "apple_icloud_add", "health", "pac_extract", "pac_pack", "knox_check", "knox_bypass", "qcn_backup", "qcn_imei_repair", "pixel_fastboot", "emmc_health"}


def _dispatch(win, act, brand_label, m):
    """Route every action through the window's engine-aware router.
    Experimental acts are gated via the EXPERIMENTAL overlay (amber, ack, audit)
    — they stay under their native brand/model but flag as EXPERIMENTAL, tab-like."""
    if act in _EXPERIMENTAL_ACTS:
        try:
            from python.core import experimental as _exp

            # Map act key to experimental feature id for ack store
            _map = {
                "apple_icloud_remove": "apple_icloud_remove",
                "apple_icloud_add": "apple_icloud_add",
                "knox_check": "knox_warranty",
                "knox_bypass": "knox_bypass",
                "qcn_backup": "qcn_backup",
                "qcn_imei_repair": "qcn_imei_repair",
                "emmc_health": "emmc_ufs_raw",
                "health": "qcn_backup",  # health uses generic health gate still EXPERIMENTAL-ish
                "pac_extract": "pac_flash",
                "pac_pack": "pac_flash",
                "pixel_fastboot": "fastboot_pixel",
            }
            feat = _map.get(act, act)
            title, warn = _exp.get_warning(feat)

            def _go():
                win.start_model_action(act, brand_label, m)

            # Use the window's experimental overlay if available, else direct
            if hasattr(win, "_confirm_experimental_overlay"):
                win._confirm_experimental_overlay(feat, title, warn, confirm_label="I Accept — Run", on_confirm=_go, chip="wipe")
            else:
                _go()
            return
        except Exception:
            pass
    win.start_model_action(act, brand_label, m)
