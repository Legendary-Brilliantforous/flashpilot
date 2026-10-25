"""Flow / ops-page rendering helpers shared by the vendor and hub mixins.

Extracted mechanically from :mod:`python.gui.qt_app`; method bodies are
unchanged and keep relying on ``self`` for cross-page resolution.
"""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QLabel,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ..common import _DESTRUCTIVE_CONFIRM, _EXPERIMENTAL_FLOW_MAP
from ..flow_meta import risk_for, route_for
from ..theme import C, _btn_ghost
from ..widgets import FlowBrowser, FlowRow, SamsungSubTabs
from ...core import core, experimental


class FlowRenderMixin:
    def _ops_scroll_area(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; }")
        return scroll

    def _add_qr_provisioning(self, parent_layout, run_cb=None):
        """MDM-via-QR entry: one "QR Provision" button. It opens the QR
        window, whose dropdown offers TestDPC (the default QR) plus the two
        optional DPCs (Google Device Policy, FlashPilot). Shown on every MDM
        surface (chip benches + Samsung) so the operator always finds it."""
        header = QLabel("QR PROVISIONING")
        header.setStyleSheet(
            f"color:{C['mute']}; font-size:11px; font-weight:800;"
            f" letter-spacing:1px; margin-top:4px;"
        )
        parent_layout.addWidget(header)
        b = QPushButton("📷  QR Provision")
        b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        b.setAutoDefault(False)
        b.setDefault(False)
        b.setStyleSheet(_btn_ghost())
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setToolTip("Device-owner QR enrollment — TestDPC by default, with "
                     "Google Device Policy / FlashPilot as the two optional QRs")
        b.setProperty("flow_act", "_qr_generator")
        b.clicked.connect(lambda _=False: self._open_qr_generator())
        parent_layout.addWidget(b, 0, Qt.AlignmentFlag.AlignLeft)

    def _flow_rows(self, jobs, modes=None, methods=None):
        """Resolve the render rows exactly as the old inline renderer did.

        Per job: dedupe flow keys across its modes (first mode wins), keep
        only keys registered in ``core.FLOWS``, honour the ``modes`` /
        ``methods`` filters, and drop jobs with no entries. Returns
        ``FlowRow(job, mode, key, label, risk)`` in render order.
        """
        rows = []
        for job in jobs:
            seen = set()
            try:
                _modes = core.modes_for(job)
            except KeyError:
                continue
            for mode in _modes:
                if modes is not None and mode not in modes:
                    continue
                try:
                    _methods = core.methods_for(job, mode)
                except KeyError:
                    continue
                for key in _methods:
                    if key in seen:
                        continue
                    if methods is not None and key not in methods:
                        continue
                    # Skip flows that haven't been registered
                    if key not in core.FLOWS:
                        continue
                    seen.add(key)
                    try:
                        _factory = core.FLOWS[key]
                        name = (_factory().name if callable(_factory)
                                else getattr(_factory, "name", key))
                    except Exception as e:
                        name = f"{key} ({e})"
                    rows.append(FlowRow(job, mode, key, name,
                                        risk_for(key, job)))
        return rows

    def _route_flow_activation(self, job, mode, key, label, run_cb=None):
        """Route a FlowBrowser click through :mod:`python.gui.flow_meta`.

        Reproduces EXACTLY the overlay calls (feature/title/body/chip and
        confirm labels) the old inline closures made — this is a
        safety-critical path, so the routed behaviour must not change.
        """
        if route_for(key) == "experimental":
            feature = _EXPERIMENTAL_FLOW_MAP.get(key)
            title, warn = experimental.get_warning(feature)
            self._confirm_experimental_overlay(
                feature, title, warn, key, confirm_label="I Accept — Run",
                on_confirm=lambda _=False, j=job, m=mode, k=key, n=label:
                    (run_cb(j, m, k, n) if run_cb
                     else self._run_ops_flow(j, m, k, n)),
                chip="wipe",
            )
            return
        confirm = _DESTRUCTIVE_CONFIRM.get(key)
        if confirm:
            title, text = confirm
            if run_cb is None:
                on_confirm = (lambda _=False, j=job, m=mode, k=key, n=label:
                              self._run_ops_flow(j, m, k, n))
            else:
                on_confirm = (lambda _=False, j=job, m=mode, k=key, n=label:
                              run_cb(j, m, k, n))
            self._confirm_overlay(
                title, text, confirm_label="Continue", on_confirm=on_confirm,
            )
            return
        if run_cb is None:
            self._run_ops_flow(job, mode, key, label)
        else:
            run_cb(job, mode, key, label)

    def _add_job_flows(self, parent_layout, jobs, modes=None, run_cb=None,
                       methods=None):
        """Add one wrapping FlowLayout of action buttons per job, no dropdowns.

        Rendering goes through the single :class:`FlowBrowser` view; clicks
        are routed by :meth:`_route_flow_activation`. ``modes``: optional
        iterable of frp modes to restrict which flows show. ``methods``:
        optional iterable of method keys to show (only those). ``run_cb``:
        optional callable(job, mode, key, name); defaults to the Samsung
        operations runner (_run_ops_flow).
        """
        if modes is not None:
            modes = set(modes)
        rows = self._flow_rows(jobs, modes=modes, methods=methods)
        browser = FlowBrowser(spacing=8)
        browser.set_legend(True)
        browser.set_rows(rows)
        # Register the rendered cards with the window's capability gate
        # (tooltip is final at this point, including the EXPERIMENTAL prefix).
        browser.register_gates(self._gate_button)
        browser.activated.connect(
            lambda job, mode, key, label: self._route_flow_activation(
                job, mode, key, label, run_cb=run_cb)
        )
        # Keep the view alive: it is never added to the page widget tree (the
        # rows are transplanted below), so the button click lambdas are what
        # hold it — an explicit ref makes that guarantee unambiguous.
        try:
            self._flow_browsers.append(browser)
        except AttributeError:
            self._flow_browsers = [browser]
        browser.transplant_into(parent_layout)

    def _build_ops_flow_page(self, jobs, modes=None, run_cb=None, qr=False):
        page = QWidget()
        page.setStyleSheet("background: transparent;")
        v = QVBoxLayout(page)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        scroll = self._ops_scroll_area()
        host = QWidget()
        host.setStyleSheet("background: transparent;")
        hv = QVBoxLayout(host)
        hv.setContentsMargins(0, 0, 0, 0)
        hv.setSpacing(10)
        self._add_job_flows(hv, jobs, modes=modes, run_cb=run_cb)
        if qr:
            # The three DPC choices travel with every MDM surface.
            self._add_qr_provisioning(hv, run_cb=run_cb)
        hv.addStretch(1)
        scroll.setWidget(host)
        v.addWidget(scroll)
        return page

    def _build_chip_ops_section(self, chip, modes, stop_btn, progress, reset_ui,
                                flash_jobs=None):
        """Samsung-style sub-tab operations section for the chip pages - the
        same FLASH / FRP / SCREEN LOCK / MDM / INFO & TOOLS tabs, but only the
        flows that apply to that chipset's modes, run through _run_job_flow so
        they use the chip page's own stop button / progress / reset.
        flash_jobs: job list for the FLASH tab; pass None to skip the FLASH tab
        (chip pages already flash through their native tools, not Odin)."""
        def run_cb(job, mode, method, label):
            self._run_job_flow(job, mode, method, label, stop_btn, progress, reset_ui)

        tab_specs = []
        if flash_jobs:
            tab_specs.append(("flash", "FLASH", flash_jobs))
        tab_specs += [
            ("frp", "FRP", ["Remove FRP"]),
            ("lock", "SCREEN LOCK", ["Remove Screen Lock"]),
            ("mdm", "MDM", ["Remove MDM"]),
            (
                "tools",
                "INFO & TOOLS",
                ["Read Device Info", "Detect Devices", "Reboot",
                 "Repair Settings"],
            ),
        ]
        modeset = set(modes)
        tabs = []
        pages = []
        for key, label, jobs in tab_specs:
            count = 0
            for job in jobs:
                for mode in core.modes_for(job):
                    if mode in modeset:
                        count += len(core.methods_for(job, mode))
            if not count:
                continue
            tabs.append((key, label))
            pages.append(
                (key, self._build_ops_flow_page(jobs, modes=modeset, run_cb=run_cb,
                                                qr=(key == "mdm")))
            )
        if not tabs:
            return None

        section = QWidget()
        section.setStyleSheet("background: transparent;")
        # Guarantee the sub-tab bar + a usable amount of action buttons room so
        # the chip pages never crush this section to ~0px (which made the tab
        # buttons overflow their bar and the flow buttons spill off-screen).
        section.setMinimumHeight(240)
        v = QVBoxLayout(section)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(8)
        subnav = SamsungSubTabs(tabs)
        v.addWidget(subnav)
        stack = QStackedWidget()
        stack.setStyleSheet("QStackedWidget { background: transparent; }")
        keys = [k for k, _ in pages]
        for _, page in pages:
            stack.addWidget(page)
        def _on_chip_tab(key):
            try:
                stack.setCurrentIndex(keys.index(key) if key in keys else 0)
                w = stack.currentWidget()
                if w:
                    for child in w.findChildren(QFrame):
                        lay = child.layout()
                        if lay and hasattr(lay, "invalidate"):
                            lay.invalidate()
                    w.updateGeometry()
            except Exception:
                pass
        subnav.tab_selected.connect(_on_chip_tab)
        v.addWidget(stack, 1)
        return section
