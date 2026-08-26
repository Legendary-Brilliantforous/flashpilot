"""Theme tokens, accent packs and QSS builders — canonical home.

Extracted from qt_app.py (step 3). C is a shared mutable dict so live theme
switching keeps working across every importer.
"""

C = {
    "bg": "#04070c",            # window background (deep carbon)
    "panel": "#0a111a",         # card panel
    "card": "#0d1622",          # inner card
    "card_hover": "#152032",    # card hover state
    "inset": "#070d15",         # console / inputs
    "border": "#16233a",
    "border_hi": "#2c405e",
    "glass": "rgba(13,22,34,0.78)",  # glassmorphism base
    "glass_hi": "rgba(21,32,50,0.88)",
    "glass_border": "rgba(255,255,255,0.08)",
    "text": "#e7eef8",
    "text_hi": "#f1f5f9",
    "dim": "#a8bdd6",
    "mute": "#6b7d94",
    "accent": "#22d3ee",        # circuit-cyan signature
    "accent_hi": "#7dd3fc",
    "accent_glow": "rgba(34,211,238,0.28)",
    "grad_a": "#0ea5e9",
    "grad_b": "#22d3ee",
    "ok": "#2dd4bf",
    "ok_dim": "#0c332f",
    "warn": "#fbbf24",
    "warn_dim": "#3a3010",
    "err": "#fb7185",
    "err_dim": "#3d1721",
    "chip_blue": "#0f2a41",
    "chip_text": "#7dd3fc",
    "accent_dim": "#0e3350",     # soft accent fill (dropdown selection, tiles)
    "sheen": "#ffffff",          # highlight on painted glyphs
}

# Accent themes selectable in Settings -> Appearance. Each swaps the accent /
# gradient tokens, mirroring how premium commercial tools ship colour packs.
ACCENT_THEMES = {
    "Neon Circuit": {
        "accent": "#22d3ee", "accent_hi": "#7dd3fc",
        "grad_a": "#0ea5e9", "grad_b": "#22d3ee", "accent_dim": "#0e3350",
    },
    "Cobalt Blue": {
        "accent": "#3b82f6", "accent_hi": "#6ea8ff",
        "grad_a": "#2563eb", "grad_b": "#06b6d4", "accent_dim": "#1d3a66",
    },
    "Violet": {
        "accent": "#8b5cf6", "accent_hi": "#a78bfa",
        "grad_a": "#7c3aed", "grad_b": "#06b6d4", "accent_dim": "#2b2350",
    },
    "Emerald": {
        "accent": "#10b981", "accent_hi": "#34d399",
        "grad_a": "#059669", "grad_b": "#2dd4bf", "accent_dim": "#0f3d31",
    },
    "Amber": {
        "accent": "#f59e0b", "accent_hi": "#fbbf24",
        "grad_a": "#d97706", "grad_b": "#f59e0b", "accent_dim": "#3d3413",
    },
    "Crimson": {
        "accent": "#ef4444", "accent_hi": "#f87171",
        "grad_a": "#dc2626", "grad_b": "#f97316", "accent_dim": "#3d1b1e",
    },
    "Sunset": {
        "accent": "#f97316", "accent_hi": "#fdba74",
        "grad_a": "#ea580c", "grad_b": "#ec4899", "accent_dim": "#3d2314",
    },
    "Arctic": {
        "accent": "#06b6d4", "accent_hi": "#67e8f9",
        "grad_a": "#0891b2", "grad_b": "#22d3ee", "accent_dim": "#0e2f3d",
    },
    "Midnight": {
        "accent": "#6366f1", "accent_hi": "#a5b4fc",
        "grad_a": "#4f46e5", "grad_b": "#8b5cf6", "accent_dim": "#1e1b4b",
    },
    "Graphite": {
        "accent": "#94a3b8", "accent_hi": "#cbd5e1",
        "grad_a": "#475569", "grad_b": "#94a3b8", "accent_dim": "#1e293b",
    },
}

_BASE_QSS = f"""
* {{
    font-family: "Inter", "Segoe UI", "Roboto", "Helvetica Neue", Arial, sans-serif;
    font-size: 13px;
}}
QToolTip {{
    background-color: {C['panel']}; color: {C['text_hi']};
    border: 1px solid {C['border_hi']}; border-radius: 8px; padding: 8px 10px;
    font-size: 12px;
}}
QLineEdit {{
    background: {C['inset']};
    border: 1px solid {C['border']};
    border-radius: 10px;
    padding: 8px 12px;
    color: {C['text_hi']};
    selection-background-color: {C['accent']};
    selection-color: #ffffff;
}}
QLineEdit:hover {{ border: 1px solid {C['border_hi']}; background: {C['card']}; }}
QLineEdit:focus {{ border: 1px solid {C['accent']}; background: {C['card_hover']}; }}
QComboBox {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                stop:0 {C['card_hover']}, stop:1 {C['card']});
    border: 1px solid {C['glass_border']};
    border-radius: 10px;
    padding: 8px 34px 8px 12px;
    color: {C['text_hi']};
    min-height: 22px;
    selection-background-color: {C['accent_dim']};
    selection-color: {C['accent_hi']};
}}
QComboBox:hover {{ border: 1px solid {C['accent']}; background: {C['card_hover']}; }}
QComboBox:focus {{ border: 1px solid {C['accent']}; }}
QComboBox:disabled {{ color: {C['mute']}; }}
QComboBox:on {{ border: 1px solid {C['accent']}; }}
QComboBox::drop-down {{
    border: none; width: 30px;
    subcontrol-origin: padding; subcontrol-position: center right;
    background: transparent;
}}
QComboBox::down-arrow {{
    image: none; width: 0; height: 0;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid {C['dim']};
}}
QComboBox::down-arrow:on {{ border-top: 6px solid {C['accent']}; }}
QComboBox QAbstractItemView {{
    background-color: {C['panel']};
    border: 1px solid {C['border_hi']};
    border-radius: 12px;
    color: {C['text']};
    selection-background-color: {C['accent_dim']};
    selection-color: {C['accent_hi']};
    outline: 0;
    padding: 6px;
}}
QScrollBar:vertical {{
    background: transparent; width: 8px; border-radius: 4px; margin: 2px;
}}
QScrollBar::handle:vertical {{ background: {C['border_hi']}; border-radius: 4px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {C['accent']}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}
QScrollBar:horizontal {{ height: 0; }}
QFrame#sbox {{
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 rgba(18,28,44,180), stop:1 rgba(9,15,27,200));
    border: 1px solid {C['glass_border']}; border-radius: 14px;
}}
"""


def _get_base_qss():
    """Regenerate base QSS with current C values — so theme changes affect
    the whole app, not just the accent line."""
    return f"""
* {{
    font-family: "Inter", "Segoe UI", "Roboto", "Helvetica Neue", Arial, sans-serif;
    font-size: 13px;
}}
QToolTip {{
    background-color: {C['panel']}; color: {C['text_hi']};
    border: 1px solid {C['border_hi']}; border-radius: 8px; padding: 8px 10px;
    font-size: 12px;
}}
QLineEdit {{
    background: {C['inset']};
    border: 1px solid {C['border']};
    border-radius: 10px;
    padding: 8px 12px;
    color: {C['text_hi']};
    selection-background-color: {C['accent']};
    selection-color: #ffffff;
}}
QLineEdit:hover {{ border: 1px solid {C['border_hi']}; background: {C['card']}; }}
QLineEdit:focus {{ border: 1px solid {C['accent']}; background: {C['card_hover']}; }}
QComboBox {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                stop:0 {C['card_hover']}, stop:1 {C['card']});
    border: 1px solid {C['glass_border']};
    border-radius: 10px;
    padding: 8px 34px 8px 12px;
    color: {C['text_hi']};
    min-height: 22px;
    selection-background-color: {C['accent_dim']};
    selection-color: {C['accent_hi']};
}}
QComboBox:hover {{ border: 1px solid {C['accent']}; background: {C['card_hover']}; }}
QComboBox:focus {{ border: 1px solid {C['accent']}; }}
QComboBox:disabled {{ color: {C['mute']}; }}
QComboBox:on {{ border: 1px solid {C['accent']}; }}
QComboBox::drop-down {{
    border: none; width: 30px;
    subcontrol-origin: padding; subcontrol-position: center right;
    background: transparent;
}}
QComboBox::down-arrow {{
    image: none; width: 0; height: 0;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid {C['dim']};
}}
QComboBox::down-arrow:on {{ border-top: 6px solid {C['accent']}; }}
QComboBox QAbstractItemView {{
    background-color: {C['panel']};
    border: 1px solid {C['border_hi']};
    border-radius: 12px;
    color: {C['text']};
    selection-background-color: {C['accent_dim']};
    selection-color: {C['accent_hi']};
    outline: 0;
    padding: 6px;
}}
QScrollBar:vertical {{
    background: transparent; width: 8px; border-radius: 4px; margin: 2px;
}}
QScrollBar::handle:vertical {{ background: {C['border_hi']}; border-radius: 4px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {C['accent']}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}
QScrollBar:horizontal {{ height: 0; }}
QFrame#sbox {{
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 rgba(18,28,44,180), stop:1 rgba(9,15,27,200));
    border: 1px solid {C['glass_border']}; border-radius: 14px;
}}
"""


def _btn_primary():
    return f"""
    QPushButton {{
        border: 1px solid {C['accent']};
        border-radius: 8px;
        padding: 7px 16px;
        font-size: 12px;
        font-weight: 700;
        letter-spacing: 0.3px;
        color: #04121a;
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                    stop:0 {C['grad_a']}, stop:1 {C['grad_b']});
    }}
    QPushButton:hover {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                    stop:0 {C['accent']}, stop:1 #67e8f9);
                         border: 1px solid {C['accent_hi']}; }}
    QPushButton:pressed {{ background: {C['grad_a']};
                          border: 1px solid {C['accent_hi']}; }}
    QPushButton:disabled {{ background: {C['border']}; color: {C['mute']};
                           border: 1px solid {C['border']}; }}
    """


def _card_qss():
    """Premium glassmorphism card: translucent frosted glass with soft blur,
    14px radius, inner highlight and accent left edge."""
    return (
        f"QFrame#card {{ background: qlineargradient(x1:0,y1:0,x2:0,y2:1,"
        f" stop:0 rgba(18, 28, 44, 210), stop:1 rgba(9, 15, 27, 230));"
        f" border: 1px solid {C['glass_border']}; border-left: 2.5px solid {C['accent']};"
        f" border-top: 1px solid rgba(255,255,255,0.10);"
        f" border-radius: 14px; }}"
        f"QFrame#sbox {{ background: qlineargradient(x1:0,y1:0,x2:0,y2:1,"
        f" stop:0 rgba(18, 28, 44, 180), stop:1 rgba(9, 15, 27, 200));"
        f" border: 1px solid {C['glass_border']}; border-top: 1px solid rgba(255,255,255,0.08);"
        f" border-radius: 14px; }}"
    )


def _btn_ghost():
    return f"""
    QPushButton {{
        border: 1px solid {C['border']};
        border-radius: 8px;
        padding: 6px 12px;
        font-size: 12px;
        font-weight: 600;
        color: {C['text']};
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                    stop:0 {C['card']}, stop:1 {C['inset']});
    }}
    QPushButton:hover {{ border: 1px solid {C['accent']}; color: {C['accent_hi']};
                        background: {C['card_hover']}; }}
    QPushButton:pressed {{ background: {C['accent_dim']}; color: #fff; }}
    QPushButton:disabled {{ color: {C['mute']}; border: 1px solid {C['border']}; background: {C['card']}; }}
    """


def _btn_danger():
    return f"""
    QPushButton {{
        border: 1px solid {C['err']};
        border-radius: 6px;
        padding: 6px 12px;
        font-size: 12px;
        font-weight: 700;
        color: #ffa3b2;
        background: {C['card']};
    }}
    QPushButton:hover {{ background: {C['err']}; color: #ffffff; }}
    QPushButton:pressed {{ background: #b91c1c; border-color: #b91c1c; }}
    QPushButton:disabled {{ color: {C['mute']}; border: 1px solid {C['border']}; }}
    """


def _console_qss():
    return f"""
    QPlainTextEdit {{
        background-color: {C['inset']};
        border: 1px solid {C['glass_border']};
        border-radius: 12px;
        color: {C['text_hi']};
        font-family: "JetBrains Mono", "Consolas", "Menlo", monospace;
        font-size: 12px;
        padding: 14px;
        selection-background-color: {C['accent_dim']};
        selection-color: {C['accent_hi']};
    }}
    QPlainTextEdit:focus {{ border: 1px solid {C['accent']}; }}
    """




# ---- version helpers (pure strings, no Qt) ----
def _parse_version(tag):
    """Simple version parser: strips leading 'v', extracts numeric + alpha segments."""
    if not tag:
        return (0, 0, 0), ""
    t = tag.lstrip("v")
    parts = t.split("-", 1)
    num_parts = []
    for p in parts[0].split("."):
        try:
            num_parts.append(int(p))
        except ValueError:
            num_parts.append(0)
    while len(num_parts) < 3:
        num_parts.append(0)
    alpha = parts[1] if len(parts) > 1 else ""
    return tuple(num_parts), alpha


def _display_version(tag):
    """Display version: strips trailing '.0' patches.
    1.2.0 -> 1.2, 1.2.1 -> 1.2.1, 1.2.0-beta -> 1.2-beta, 2.0.0 -> 2.0.
    Preserves prerelease suffix (-beta, -rc1, etc.) exactly."""
    if not tag:
        return ""
    t = tag.lstrip("v")
    parts = t.split("-", 1)
    numeric = parts[0]
    suffix = f"-{parts[1]}" if len(parts) > 1 else ""
    # Split numeric, strip trailing zeros but keep at least major.minor
    nums = numeric.split(".")
    # Remove trailing "0" segments while we have >2 parts
    while len(nums) > 2 and nums[-1] == "0":
        nums.pop()
    # Special case: 1.0.0 -> 1.0, 2.0 stays 2.0 etc.
    clean = ".".join(nums)
    return f"{clean}{suffix}"


def _is_beta_version(tag):
    """True if version string denotes a beta/prerelease."""
    if not tag:
        return False
    _, alpha = _parse_version(tag)
    if not alpha:
        return False
    low = alpha.lower()
    return any(k in low for k in ("beta", "alpha", "rc", "pre"))
