"""Reusable GUI widgets extracted from :mod:`python.gui.qt_app`.

Mechanically moved (verbatim) — no behaviour change.
"""

from PyQt6.QtCore import QPoint, QRect, QSize, Qt
from PyQt6.QtWidgets import QFrame, QLayout


class FlowLayout(QLayout):
    """Wrapping layout: children flow left-to-right and wrap to the next
    row when they exceed the available width (used for the operations
    button grid so 60+ action buttons never clip vertically)."""

    def __init__(self, parent=None, margin=0, spacing=8):
        super().__init__(parent)
        self._items = []
        self._margin = margin
        self._spacing = spacing
        self.setContentsMargins(margin, margin, margin, margin)

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, index):
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._do_layout(QRect(0, 0, width, 0), True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do_layout(rect, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        m = self.contentsMargins()
        size += QSize(m.left() + m.right(), m.top() + m.bottom())
        return size

    def _do_layout(self, rect, test_only):
        x = rect.x()
        y = rect.y()
        line_height = 0
        spacing = self._spacing
        m = self.contentsMargins()
        max_x = rect.right() - m.right()
        for item in self._items:
            hint = item.sizeHint()
            if x + hint.width() > max_x and line_height > 0:
                x = rect.x() + m.left()
                y += line_height + spacing
                line_height = 0
            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), hint))
            x += hint.width() + spacing
            line_height = max(line_height, hint.height())
        return y + line_height - rect.y()

class FlowHost(QFrame):
    """Container that correctly delegates heightForWidth to its FlowLayout — so wrapping preview/theme grids stay visible and clickable on small screens."""
    def hasHeightForWidth(self):
        lay = self.layout()
        return lay.hasHeightForWidth() if lay else super().hasHeightForWidth()

    def heightForWidth(self, w):
        lay = self.layout()
        if lay and lay.hasHeightForWidth():
            m = self.contentsMargins()
            return lay.heightForWidth(w - m.left() - m.right()) + m.top() + m.bottom()
        return super().heightForWidth(w)

    def sizeHint(self):
        # For QScrollArea with widgetResizable, sizeHint based on current width so wrapping is accounted
        lay = self.layout()
        if lay and lay.hasHeightForWidth() and self.width() > 0:
            return QSize(self.width(), self.heightForWidth(self.width()))
        if lay:
            return lay.sizeHint()
        return super().sizeHint()

    def minimumSizeHint(self):
        lay = self.layout()
        if lay:
            # Minimum is one row height
            return lay.minimumSize()
        return super().minimumSizeHint()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Trigger height recalculation when width changes (wrap)
        self.updateGeometry()
