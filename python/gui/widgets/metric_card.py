"""Reusable GUI widgets extracted from :mod:`python.gui.qt_app`.

Mechanically moved (verbatim) — no behaviour change.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout

from ..theme import C


class MetricCard(QFrame):
    def __init__(self, caption, value="--", accent=C["accent"]):
        super().__init__()
        self.setObjectName("metric")
        self._accent_hex = accent
        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 5, 8, 6)
        lay.setSpacing(7)
        bar = QLabel()
        bar.setFixedSize(3, 18)
        bar.setStyleSheet(f"background:{accent}; border-radius:1.5px;")
        lay.addWidget(bar, 0, Qt.AlignmentFlag.AlignVCenter)
        col = QVBoxLayout()
        col.setSpacing(0)
        cap = QLabel(caption.upper())
        cap.setStyleSheet(
            f"color:{C['mute']}; font-size:8px; font-weight:700; letter-spacing:1px;"
        )
        col.addWidget(cap)
        self.value = QLabel(value)
        self.value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.value.setWordWrap(True)
        self.value.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        try:
            from PyQt6.QtWidgets import QSizePolicy
            self.value.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.MinimumExpanding)
            self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.MinimumExpanding)
        except Exception:
            pass
        self.value.setToolTip(value)
        self.value.setStyleSheet(
            f"color:{C['text']}; font-size:11px; font-weight:600; background:transparent;"
        )
        col.addWidget(self.value)
        lay.addLayout(col, 1)
        self.setStyleSheet(
            f"QFrame#metric {{ background: qlineargradient(x1:0,y1:0,x2:0,y2:1,"
            f" stop:0 rgba(21,32,50,0.9), stop:1 rgba(13,22,34,0.9));"
            f" border: 1px solid {C['glass_border']}; border-left: 2.5px solid {self._accent_hex};"
            f" border-top: 1px solid rgba(255,255,255,0.08);"
            f" border-radius: 12px; }}"
            f" QFrame#metric:hover {{ border: 1px solid {self._accent_hex};"
            f" background: {C['glass_hi']}; }}"
        )

    def set(self, text):
        if self.value.text() != text:
            self.value.setText(text)
            try:
                self.value.setToolTip(text)
            except Exception:
                pass
