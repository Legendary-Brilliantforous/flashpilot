"""Theme tokens, QSS builders — unified professional theme.

Single source for the entire app. One dark, slate-professional palette —
no light variant, no 10-way rainbow. Accent is a muted sky, not neon.
All QSS and painted widgets import C, so recoloring is atomic.
"""

C = {
    # Eloquent Slate — ink-slate with champagne gold, high-contrast, atelier professional
    "bg": "#080c1a",            # ink window
    "panel": "#0f1e35",         # panel
    "card": "#122a4a",          # inner card
    "card_hover": "#1a365f",    # card hover
    "inset": "#0a1529",         # console / inputs
    "border": "#1c3052",
    "border_hi": "#2e4a7a",
    "glass": "rgba(18,38,66,0.80)",
    "glass_hi": "rgba(26,54,95,0.88)",
    "glass_border": "rgba(212,183,143,0.10)",
    "text": "#eef1f8",
    "text_hi": "#f5f7fb",
    "dim": "#8ea6c6",
    "mute": "#6e839e",
    # Eloquent accent — champagne gold, muted, not neon
    "accent": "#d4b78f",
    "accent_hi": "#f0d9b5",
    "accent_glow": "rgba(212,183,143,0.30)",
    "grad_a": "#b89a6a",
    "grad_b": "#d4b78f",
    # Semantic — refined jewel
    "ok": "#3dd9a0",
    "ok_dim": "#0a2e26",
    "warn": "#f0c24a",
    "warn_dim": "#2e2410",
    "err": "#ff7a86",
    "err_dim": "#2e1418",
    "chip_blue": "#201a14",
    "chip_text": "#f0d9b5",
    "accent_dim": "#2a2114",
    "sheen": "#ffffff",
    # Semantic UI tokens — NEVER accent-tinted, so switching to a red
    # accent theme (Crimson/Sunset) can't turn focus rings, selected-tab
    # borders or checkbox outlines red. Accent stays for fills/selection
    # backgrounds only.
    "focus_ring": "rgba(141,168,200,0.35)",
    "sel_border": "rgba(255,255,255,0.18)",
    "sel_border_hi": "rgba(255,255,255,0.28)",
}

# Professional accent gallery — 10 eloquent accents on the same ink-slate base.
# C stays eloquent slate; each entry only swaps accent/grad/acc_dim for the live switch.
ACCENT_THEMES = {
    "Slate Professional": {
        "accent": "#d4b78f", "accent_hi": "#f0d9b5",
        "grad_a": "#b89a6a", "grad_b": "#d4b78f", "accent_dim": "#2a2114",
    },
    "Neon Circuit": {
        "accent": "#22b8d6", "accent_hi": "#6ad8ea",
        "grad_a": "#1a8fb3", "grad_b": "#22b8d6", "accent_dim": "#0f2f3a",
    },
    "Cobalt Blue": {
        "accent": "#3b82f6", "accent_hi": "#6ea8ff",
        "grad_a": "#2563eb", "grad_b": "#3b82f6", "accent_dim": "#1d315c",
    },
    "Violet": {
        "accent": "#7c6bf0", "accent_hi": "#a594ff",
        "grad_a": "#6d4ee0", "grad_b": "#7c6bf0", "accent_dim": "#231e4a",
    },
    "Emerald": {
        "accent": "#10b981", "accent_hi": "#46d0a3",
        "grad_a": "#0a8a5f", "grad_b": "#10b981", "accent_dim": "#0f2e26",
    },
    "Amber": {
        "accent": "#e6a118", "accent_hi": "#f3c860",
        "grad_a": "#c47e0c", "grad_b": "#e6a118", "accent_dim": "#2e2410",
    },
    "Crimson": {
        "accent": "#e84557", "accent_hi": "#ff7e8d",
        "grad_a": "#c42e3e", "grad_b": "#e84557", "accent_dim": "#2e1418",
    },
    "Sunset": {
        "accent": "#f0672a", "accent_hi": "#ff9a6a",
        "grad_a": "#cf4a14", "grad_b": "#f0672a", "accent_dim": "#2e1e14",
    },
    "Arctic": {
        "accent": "#0eaec7", "accent_hi": "#5bd8eb",
        "grad_a": "#0b87a0", "grad_b": "#0eaec7", "accent_dim": "#0e2f3a",
    },
    "Midnight": {
        "accent": "#6366f1", "accent_hi": "#9ea3ff",
        "grad_a": "#4f46e5", "grad_b": "#6366f1", "accent_dim": "#1c1b4a",
    },
}

# Unified base QSS — single definition, no duplication
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
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 rgba(19,35,64,180), stop:1 rgba(10,20,38,200));
    border: 1px solid {C['glass_border']}; border-radius: 14px;
}}
QPushButton {{
    border-radius: 9px; padding: 7px 14px; font-size: 12px; font-weight: 600;
}}
QCheckBox {{ color: {C['text']}; spacing: 7px; }}
QCheckBox::indicator {{ width: 16px; height: 16px;
    border: 1px solid rgba(141,168,200,0.28); border-radius: 5px; background: {C['inset']}; }}
QCheckBox::indicator:hover {{ border-color: {C['accent']}; }}
QCheckBox::indicator:checked {{ background: {C['accent']}; border-color: {C['accent']}; }}
QScrollBar:vertical {{ background: transparent; width: 7px; margin: 2px; }}
QScrollBar::handle:vertical {{
    background: rgba(141,168,200,0.18); border-radius: 3px; min-height: 28px;
}}
QScrollBar::handle:vertical:hover {{ background: {C['accent']}; }}
QScrollBar:horizontal {{ background: transparent; height: 7px; margin: 2px; }}
QScrollBar::handle:horizontal {{
    background: rgba(141,168,200,0.18); border-radius: 3px; min-width: 28px;
}}
QScrollBar::handle:horizontal:hover {{ background: {C['accent']}; }}
"""



def _get_base_qss():
    """Regenerate base QSS with current C values — single source, no duplication."""
    return _BASE_QSS


def _btn_primary():
    return f"""
    QPushButton {{
        border: 1px solid {C['accent']};
        border-radius: 9px;
        padding: 8px 18px;
        font-size: 12px;
        font-weight: 700;
        letter-spacing: 0.2px;
        color: #f8fbff;
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                    stop:0 {C['grad_b']}, stop:1 {C['grad_a']});
    }}
    QPushButton:hover {{
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                    stop:0 {C['accent_hi']}, stop:1 {C['accent']});
        border-color: {C['accent_hi']};
    }}
    QPushButton:pressed {{ background: {C['grad_a']}; }}
    QPushButton:focus {{ border-color: {C['focus_ring']}; outline: none; }}
    QPushButton:disabled {{ background: rgba(255,255,255,12); color: {C['mute']};
                            border-color: {C['border']}; }}
    """


def _card_qss():
    """Glass surface — unified slate, subtle hi-line, professional lift."""
    return (
        f"QFrame#card {{ background: qlineargradient(x1:0,y1:0,x2:0,y2:1,"
        f" stop:0 rgba(19, 35, 64, 215), stop:1 rgba(10, 20, 38, 235));"
        f" border: 1px solid rgba(120,160,210,0.09);"
        f" border-left: 2px solid {C['accent']};"
        f" border-top: 1px solid rgba(200,220,240,0.06);"
        f" border-radius: 16px; }}"
        f"QFrame#card:hover {{ border-color: rgba(140,175,220,0.14);"
        f" border-left-color: {C['accent_hi']}; }}"
        f"QFrame#sbox {{ background: qlineargradient(x1:0,y1:0,x2:0,y2:1,"
        f" stop:0 rgba(18, 30, 54, 185), stop:1 rgba(9, 18, 34, 205));"
        f" border: 1px solid rgba(120,160,210,0.07);"
        f" border-top: 1px solid rgba(200,220,240,0.05);"
        f" border-radius: 16px; }}"
    )


def _btn_ghost():
    return f"""
    QPushButton {{
        border: 1px solid rgba(141,168,200,0.14);
        border-radius: 9px;
        padding: 7px 14px;
        font-size: 12px;
        font-weight: 600;
        letter-spacing: 0.2px;
        color: {C['text']};
        background: rgba(255,255,255,8);
    }}
    QPushButton:hover {{
        border: 1px solid {C['accent']};
        color: {C['accent_hi']};
        background: rgba(47,158,240,14);
    }}
    QPushButton:pressed {{ background: {C['accent_dim']}; color: #fff; }}
    QPushButton:focus {{ border-color: {C['focus_ring']}; outline: none; }}
    QPushButton:disabled {{ color: {C['mute']}; border-color: rgba(141,168,200,0.08);
                            background: transparent; }}
    """


def _btn_danger():
    return f"""
    QPushButton {{
        border: 1px solid rgba(255,107,122,0.45);
        border-radius: 9px;
        padding: 7px 14px;
        font-size: 12px;
        font-weight: 700;
        letter-spacing: 0.2px;
        color: #ffccd1;
        background: rgba(255,107,122,18);
    }}
    QPushButton:hover {{
        background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                                    stop:0 #ff6b7a, stop:1 #e23a4a);
        color: #ffffff; border-color: #ff8a96;
    }}
    QPushButton:pressed {{ background: #c41f2f; border-color: #c41f2f; }}
    QPushButton:focus {{ border-color: #ff8a96; }}
    QPushButton:disabled {{ color: {C['mute']};
                            border-color: rgba(141,168,200,0.08); background: transparent; }}
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
