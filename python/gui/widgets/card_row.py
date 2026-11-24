"""CardRow — a row of action cards that wraps instead of widening its page.

The BATTERY and NETWORK pages put three action cards side by side in a plain
``QHBoxLayout``. A horizontal layout's minimum width is the **sum** of its
children's minimum widths, and each card's minimum is set by its button label
("Repair Battery", "Start Load Test"): three cards need ~500px before the page
is even padded. That fit on the machine the layout was measured on, but text
metrics are a property of the installed typeface, not of the app — with the UI
font falling back to a wider face (or with a longer translation) the same row
demanded 534px inside a 500px page, so the page scrolled sideways and its
right-hand card sat under the console edge.

``CardRow`` gives every card a comfortable preferred width and lays them out in
equal columns; when the page gets narrower the cards drop to the next line
instead of forcing the page wider. Rows share the same height so the cards stay
aligned, and the preferred width is only a *layout* hint — the page minimum
stays at one card, so a narrow window never clips or scrolls.
"""
from PyQt6.QtCore import QSize
from PyQt6.QtWidgets import QSizePolicy, QWidget


class CardRow(QWidget):
    """Equal-width action cards that wrap when the page is narrow.

    ``preferred`` is the width a card wants (two cards + spacing fit a 420px
    page, three fit ~640px); ``minimum`` is the floor that keeps a button label
    readable and is what the widget reports as its own minimum width.
    """

    def __init__(self, parent=None, spacing=12, preferred=196, minimum=150):
        super().__init__(parent)
        self._cards = []
        self._spacing = spacing
        self._preferred = preferred
        self._minimum = minimum
        self.setStyleSheet("background: transparent;")
        self.setSizePolicy(QSizePolicy.Policy.Preferred,
                           QSizePolicy.Policy.Minimum)

    # ---- content ------------------------------------------------------
    def addWidget(self, card):
        """Append a card (already parented to this row or not)."""
        card.setParent(self)
        self._cards.append(card)
        card.show()
        self.updateGeometry()
        self._relayout()
        return card

    def count(self):
        return len(self._cards)

    # ---- geometry -----------------------------------------------------
    def _columns(self, width):
        if not self._cards:
            return 1
        columns = max(1, int((max(0, width) + self._spacing)
                             // (self._preferred + self._spacing)))
        return min(columns, len(self._cards))

    @staticmethod
    def _card_height(card, width):
        """Preferred height of ``card`` once laid out at ``width``."""
        height = card.heightForWidth(width)
        if height < 0:
            height = card.sizeHint().height()
        return max(0, height)

    def _layout(self, width, apply):
        """Lay the cards out for ``width`` px; return the total height.

        ``apply`` is False while Qt is only *asking* for a height (layout
        negotiation), True when the geometries may actually move.
        """
        total = 0
        if not self._cards or width <= 0:
            return total
        columns = self._columns(width)
        card_w = max(
            self._minimum,
            (width - self._spacing * (columns - 1)) // columns,
        )
        y = 0
        for start in range(0, len(self._cards), columns):
            row = self._cards[start:start + columns]
            row_h = max(self._card_height(c, card_w) for c in row)
            if apply:
                for i, card in enumerate(row):
                    card.setGeometry(
                        i * (card_w + self._spacing), y, card_w, row_h)
            y += row_h + self._spacing
        return max(0, y - self._spacing)

    def _relayout(self):
        self._layout(self.width(), True)

    # ---- QWidget contract --------------------------------------------
    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._layout(width, False)

    def sizeHint(self):
        if not self._cards:
            return QSize(0, 0)
        width = self.width()
        if width <= 0:
            width = self._preferred * len(self._cards) + \
                self._spacing * (len(self._cards) - 1)
        return QSize(width, self._layout(width, False))

    def minimumSizeHint(self):
        if not self._cards:
            return QSize(0, 0)
        return QSize(self._minimum, self._layout(self._minimum, False))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._relayout()

    def showEvent(self, event):
        super().showEvent(event)
        self._relayout()
