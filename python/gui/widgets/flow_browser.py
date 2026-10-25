"""FlowBrowser — the single flow-rendering view (Phase 7).

Renders an optional risk legend (``set_legend(True)``), then per job a
``{"JOB"} · count`` group header followed by, for each run of rows that share a
mode, a small mode sub-heading and a wrapping
:class:`~python.gui.widgets.flow_layout.FlowLayout` of
:class:`~python.gui.widgets.method_card.MethodCard` buttons.

It is a **pure view**: it never imports the top-level application module and
never runs flows. Clicks are surfaced as :attr:`activated` and the host mixin
decides how to route them (via :mod:`python.gui.flow_meta`); the confirm
overlays are window-owned modals parented to the window root and therefore
cannot live in this leaf widget.

Builder use in this slice
-------------------------
The hard requirement for this slice is that the UI inventory stays
byte-identical, so the browser must not add a container widget to the page.
The host renders its rows into the browser and then calls
:meth:`transplant_into` to move the built widgets into the page's own layout.
The next (visual) slice will instead insert the browser itself — that is the
change that deliberately regenerates the inventory golden.
"""
from dataclasses import dataclass

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QFrame, QLabel, QVBoxLayout

from ...core import experimental
from ..common import _EXPERIMENTAL_FLOW_MAP
from ..theme import C, FONT_SIZE
from .flow_layout import FlowLayout
from .method_card import MethodCard


@dataclass(frozen=True)
class FlowRow:
    """One rendered method button: ``(job, mode, key, label, risk)``."""

    job: str
    mode: str
    key: str
    label: str
    risk: str


class FlowBrowser(QFrame):
    """Renders flow rows; click/run behaviour is owned by the host."""

    # job, mode, key, label
    activated = pyqtSignal(str, str, str, str)

    def __init__(self, parent=None, spacing=8):
        super().__init__(parent)
        self._spacing = spacing
        self._show_legend = False
        self._cards = []  # [(card, job, mode)] in render order
        self._lay = QVBoxLayout(self)
        self._lay.setContentsMargins(0, 0, 0, 0)
        self._lay.setSpacing(0)

    # -- configuration -----------------------------------------------------
    def set_legend(self, on=True):
        """Show the read-only / medium / high / experimental legend."""
        self._show_legend = bool(on)

    # -- rendering ---------------------------------------------------------
    def _legend_label(self):
        legend = QLabel(
            f'<span style="color:{C["ok"]};">●</span> read-only&nbsp;&nbsp;'
            f'<span style="color:{C["warn"]};">●</span> medium&nbsp;&nbsp;'
            f'<span style="color:{C["err"]};">●</span> high&nbsp;&nbsp;'
            f'<span style="color:{C["experimental"]};">●</span> experimental'
        )
        legend.setObjectName("risk_legend")
        legend.setTextFormat(Qt.TextFormat.RichText)
        legend.setStyleSheet(
            f"font-size:10px; color:{C['mute']}; margin-bottom:2px;"
        )
        return legend

    def _job_header(self, job, count):
        """Group header: the job name plus how many methods it offers.

        Token-styled and rich-text so the name keeps the existing
        11px / 800 / 1px treatment while the trailing count reads dimmer
        (``mute`` name, dimmer ``border_hi`` count) inside the same label.
        """
        header = QLabel(
            f'<span style="color:{C["mute"]};">{job.upper()}</span>'
            f'<span style="color:{C["border_hi"]};"> · {count}</span>'
        )
        header.setTextFormat(Qt.TextFormat.RichText)
        header.setStyleSheet(
            f"font-size:{FONT_SIZE['small']}px; font-weight:800;"
            f" letter-spacing:1px; margin-top:4px;"
        )
        return header

    def _mode_heading(self, mode):
        """Small sub-heading naming the transport mode of the cards below it."""
        label = QLabel(f"— {mode.upper()}")
        label.setStyleSheet(
            f"color:{C['dim']}; font-size:{FONT_SIZE['caption']}px;"
            f" font-weight:700; letter-spacing:1.4px; margin-top:2px;"
        )
        return label

    def set_rows(self, rows):
        """Render ``rows`` (an iterable of :class:`FlowRow`) as Job → Mode.

        Rows arrive job-major then mode-major (see ``_flow_rows``), so within a
        job any consecutive equal-mode run is one mode section. Each job gets
        one count-bearing header; each mode run gets a sub-heading and its own
        wrapping layout, with the cards in render order. The rendered row set,
        card text/tooltips, dedupe and click routing are unchanged.
        """
        self._cards = []
        rows = list(rows)
        if self._show_legend:
            self._lay.addWidget(self._legend_label())
        group_job = None
        group_mode = None
        flow = None
        for i, row in enumerate(rows):
            if row.job != group_job:
                count = sum(1 for r in rows[i:] if r.job == row.job)
                self._lay.addWidget(self._job_header(row.job, count))
                group_job = row.job
                group_mode = None  # force a mode sub-heading at each job start
            if row.mode != group_mode:
                self._lay.addWidget(self._mode_heading(row.mode))
                flow = FlowLayout(spacing=self._spacing)
                self._lay.addLayout(flow)
                group_mode = row.mode
            card = MethodCard(row.label, self)
            card.setToolTip(f"{row.job} / {row.mode} / {row.key}")
            if row.risk == "experimental":
                # EXPERIMENTAL: the warning title leads the tooltip. The amber
                # dashed border comes from set_risk (risk == experimental),
                # before the tooltip is captured by the gate registry.
                feature = _EXPERIMENTAL_FLOW_MAP.get(row.key)
                title, _warn = experimental.get_warning(feature)
                card.setToolTip(
                    f"[EXPERIMENTAL] {title}\n{row.job} / {row.mode} / {row.key}"
                )
            card.set_risk(row.risk)
            card.clicked.connect(
                lambda _=False, r=row: self.activated.emit(
                    r.job, r.mode, r.key, r.label)
            )
            flow.addWidget(card)
            self._cards.append((card, row.job, row.mode))
        return self

    # -- hooks -------------------------------------------------------------
    def register_gates(self, cb):
        """Register every rendered card with the host's gate callback."""
        for card, job, mode in self._cards:
            cb(card, job=job, mode=mode)

    def transplant_into(self, parent_layout):
        """Move the built rows into ``parent_layout`` (no container widget).

        Keeps the page's widget tree identical to the pre-browser renderer;
        the browser itself is never added to the tree.
        """
        lay = self._lay
        while lay.count():
            item = lay.takeAt(0)
            widget = item.widget()
            sub = item.layout()
            if widget is not None:
                parent_layout.addWidget(widget)
            elif sub is not None:
                parent_layout.addLayout(sub)
