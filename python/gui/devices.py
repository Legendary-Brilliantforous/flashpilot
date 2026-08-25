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
    from .qt_app import C, _btn_ghost, _btn_primary, _btn_danger
    return C, _btn_ghost, _btn_primary, _btn_danger

_ACTION_META = {
    "frp":        ("FRP Bypass",      "⚡", "Instant FRP using known PIT/offset (bridge: spd-frp / mtk-frp-gpt / odin)"),
    "info":       ("Device Check",    "ℹ", "Read model/chip info (wired: refresh_device)"),
    "backup":     ("Backup",          "⬇", "Dump critical partitions before any write (spd-readback / mtk-backup / odin efs)"),
    "flash":      ("Flash Firmware",  "⬆", "Write stock firmware for this model (odin-flash-multi / spd-flash)"),
    "adb_enable": ("ADB Enable",      "⚙", "Enable USB debugging without Settings (magic64 / *#*#49#*#*)"),
    "kg_unlock":  ("KG Unlock",       "◈", "KnoxGuard state reset via AT chain (at-kg-unlock)"),
}


def nav_entries():
    """(key_suffix, icon, label) triples for every brand — used by app shell."""
    return [(f"dev_{b['key']}", b.get("icon", "▣"), b["label"]) for b in BRANDS]


def _card(text, sub="", accent=None, clickable=True):
    C, _btn_ghost, _btn_primary, _btn_danger = _tok()
    card = QFrame()
    card.setCursor(Qt.CursorShape.PointingHandCursor if clickable else Qt.CursorShape.ArrowCursor)
    accent = accent or C["accent"]
    border = f"2px solid {accent}" if clickable else f"1px dashed {C['border']}"
    card.setStyleSheet(
        f"QFrame {{ background: qlineargradient(x1:0,y1:0,x2:0,y2:1,"
        f" stop:0 {C['card']}, stop:1 {C['inset']});"
        f" border: {border}; border-radius: 12px; }}"
        f"QFrame:hover {{ border-color: {accent}; }}"
    )
    lay = QVBoxLayout(card)
    lay.setContentsMargins(14, 10, 14, 10)
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
    outer.setContentsMargins(16, 14, 16, 14)
    outer.setSpacing(10)

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
    grid.setSpacing(12)

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
    """Level 3: per-model action board."""
    C, _btn_ghost, _btn_primary, _btn_danger = _tok()
    page = QWidget()
    page.setStyleSheet("background: transparent;")
    v = QVBoxLayout(page)
    v.setContentsMargins(16, 14, 16, 14)
    v.setSpacing(12)

    top = QHBoxLayout()
    back_btn = QPushButton("← Back")
    back_btn.setStyleSheet(_btn_ghost())
    back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    back_btn.setFixedWidth(90)
    back_btn.clicked.connect(lambda: back())
    top.addWidget(back_btn)
    title = QLabel(f"{brand['label']} · {m['model']}")
    title.setStyleSheet(f"color:{C['text']}; font-size:15px; font-weight:800;")
    top.addWidget(title, 1)
    chip_lbl = QLabel(f"{m.get('chip','')}   engine: {m.get('engine','—').upper()}")
    chip_lbl.setStyleSheet(
        f"color:#04121a; background:{C['accent']}; border-radius:8px;"
        " padding:3px 10px; font-size:11px; font-weight:800;"
    )
    top.addWidget(chip_lbl)
    v.addLayout(top)

    notes = m.get("notes") or ""
    if notes:
        n = QLabel(notes)
        n.setWordWrap(True)
        n.setStyleSheet(f"color:{C['dim']}; font-size:11px;"
                        f" background:{C['inset']}; border:1px solid {C['border']};"
                        " border-radius:8px; padding:8px;")
        v.addWidget(n)

    researched = m.get("status") == "researched"

    acts_title = QLabel("ACTIONS FOR THIS MODEL")
    acts_title.setStyleSheet(f"color:{C['mute']}; font-size:11px; font-weight:800; letter-spacing:1px;")
    v.addWidget(acts_title)

    grid = QGridLayout()
    grid.setSpacing(12)
    actions = m.get("actions", []) or []
    if not actions:
        empty = QLabel("No wired actions yet for this model — research in progress.")
        empty.setStyleSheet(f"color:{C['mute']}; font-size:12px;")
        v.addWidget(empty)

    for i, act in enumerate(actions):
        label, glyph, tip = _ACTION_META.get(act, (act, "•", ""))
        enabled = researched
        btn = QPushButton(f"  {glyph}  {label}" if not enabled else f"⚡ {label}  —  instant")
        if act in ("frp", "kg_unlock"):
            btn.setStyleSheet(_btn_danger() if not enabled else
                              btn.styleSheet())  # danger tint when live later
            if enabled:
                btn.setStyleSheet(
                    "QPushButton { color:#fff; background:"
                    " qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #dc2626, stop:1 #ef4444);"
                    " border:none; border-radius:9px; padding:12px 18px;"
                    " font-weight:900; font-size:13px; }"
                )
                btn.setFixedHeight(52)
        else:
            btn.setStyleSheet(_btn_primary() if enabled else _btn_ghost())
            btn.setFixedHeight(48)
        btn.setEnabled(act == "info")  # Device Check wired now; rest next steps
        btn.setToolTip(tip if enabled else
                       f"{tip}\n(GUI preview — wiring lands in a following step)")
        btn.clicked.connect(lambda _=False, a=act, mm=m: _dispatch(win, a, mm))
        r, c = divmod(i, 3)
        grid.addWidget(btn, r, c)

    grid.setColumnStretch(0, 1)
    grid.setColumnStretch(1, 1)
    grid.setColumnStretch(2, 1)
    v.addLayout(grid)

    if not researched:
        help_lbl = QLabel("Want this model faster? Capture `detect-all` output + a PIT "
                          "dump and open an issue — it lights up here.")
        help_lbl.setWordWrap(True)
        help_lbl.setStyleSheet(f"color:{C['mute']}; font-size:10px;")
        v.addWidget(help_lbl)

    v.addStretch(1)
    return page


def _dispatch(win, act, m):
    """Only safe, already-wired action runs today."""
    if act == "info":
        win.refresh_device()
    # frp/backup/flash/adb_enable/kg_unlock land in wiring steps — no-op now
