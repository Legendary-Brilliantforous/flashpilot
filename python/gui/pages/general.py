"""General hub page builders: QUICK / BATTERY / NETWORK sub-tabs."""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ..theme import C, _btn_ghost, _btn_primary, _card_qss
from ..widgets import CollapsibleSection, MetricCard, SamsungSubTabs, SectionTitle


class GeneralPageMixin:
    # ----------------------------- Battery page --------------------------
    def _build_battery_page(self):
        panel = QFrame()
        panel.setObjectName("card")
        panel.setStyleSheet(_card_qss())
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(12)

        lay.addWidget(SectionTitle("BATTERY REPAIR (ADB)"))
        info = QLabel(
            "Diagnose and repair any connected Android device over ADB - no "
            "vendor-specific hardware needed.\n"
            "Works on Samsung, MediaTek (Tecno/Infinix/itel/Redmi...), Qualcomm "
            "and any other phone with USB debugging enabled."
        )
        info.setStyleSheet(f"color:{C['dim']}; font-size:11px;")
        info.setWordWrap(True)
        lay.addWidget(info)

        status_row = QHBoxLayout()
        self.batt_status = QLabel("No device probed yet")
        self.batt_status.setStyleSheet(f"color:{C['dim']}; font-size:12px;")
        status_row.addWidget(self.batt_status, 1)
        lay.addLayout(status_row)

        # three big action cards
        cards = QHBoxLayout()
        cards.setSpacing(12)

        def action_card(title, desc, btn_label, slot, primary=False):
            c = QFrame()
            c.setStyleSheet(
                f"background: {C['inset']}; border: 1px solid {C['border']};"
                f" border-radius: 12px;"
            )
            cv = QVBoxLayout(c)
            cv.setContentsMargins(14, 14, 14, 14)
            cv.setSpacing(10)
            t = QLabel(title)
            t.setStyleSheet(f"color:{C['text']}; font-size:13px; font-weight:800;")
            t.setWordWrap(True)
            cv.addWidget(t)
            d = QLabel(desc)
            d.setStyleSheet(f"color:{C['dim']}; font-size:11px;")
            d.setWordWrap(True)
            cv.addWidget(d)
            cv.addStretch(1)
            b = QPushButton(btn_label)
            b.setStyleSheet(_btn_primary() if primary else _btn_ghost())
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(slot)
            # ADB-mechanism cards gate on adb_shell availability.
            self._gate_button(b, command={
                "_battery_report": "adb_shell",
                "_battery_repair": "adb_shell",
                "_battery_load_test": "adb_shell",
                "_network_report": "adb_shell",
                "_network_repair": "adb_shell",
                "_network_modem_reset": "adb_shell",
            }.get(getattr(slot, "__name__", "")))
            cv.addWidget(b)
            return c

        cards.addWidget(
            action_card(
                "Battery Report",
                "Accurate health % from the fuel gauge, level, temperature, "
                "voltage, current draw and top consumers.",
                "Run Report",
                self._battery_report,
            ),
            1,
        )
        cards.addWidget(
            action_card(
                "Battery Repair",
                "The fixes commercial tools apply: reset battery stats, "
                "Battery Saver, disable scanning, kill background apps, trim "
                "caches, tune screen/animation power.",
                "Repair Battery",
                self._battery_repair,
                primary=True,
            ),
            1,
        )
        cards.addWidget(
            action_card(
                "Load Test",
                "Stress the battery under heavy load and measure voltage sag / "
                "internal resistance to confirm a weak cell.",
                "Start Load Test",
                self._battery_load_test,
            ),
            1,
        )
        lay.addLayout(cards, 1)

        tip = QLabel(
            "Tip: for accurate battery health the device must expose the "
            "fuel-gauge sysfs (charge_full / charge_full_design). Connect the "
            "phone, authorize USB debugging, then run any tool - they work on "
            "any connected device."
        )
        tip.setStyleSheet(f"color:{C['dim']}; font-size:11px;")
        tip.setWordWrap(True)
        lay.addWidget(tip)

        return panel

    # ----------------------------- Network page --------------------------
    def _build_network_page(self):
        panel = QFrame()
        panel.setObjectName("card")
        panel.setStyleSheet(_card_qss())
        root_lay = QVBoxLayout(panel)
        root_lay.setContentsMargins(0, 0, 0, 0)
        root_lay.setSpacing(0)

        # Scroll wrapper: the page holds a live readout + two action groups, so
        # it must be scrollable rather than crushed into the fixed viewport.
        page_scroll = self._ops_scroll_area()
        host = QWidget()
        host.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(host)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(14)

        lay.addWidget(SectionTitle("NETWORK REPAIR (ADB)"))
        info = QLabel(
            "Diagnose and repair Wi-Fi / mobile data / modem issues on any "
            "connected Android device over ADB.\n"
            "Useful for: no internet, weak signal, stuck on 3G, DNS failures, "
            "SIM not detected after a flash, airplane-mode glitches."
        )
        info.setStyleSheet(f"color:{C['dim']}; font-size:11px;")
        info.setWordWrap(True)
        lay.addWidget(info)

        # --- Live diagnostics readout (updates every 3s while an ADB device
        #     is connected - no need to click anything) ---
        self.net_cards = {}
        net_grid = QGridLayout()
        net_grid.setContentsMargins(0, 0, 0, 0)
        net_grid.setHorizontalSpacing(14)
        net_grid.setVerticalSpacing(12)
        for i, (key, cap) in enumerate(
            (
                ("sim", "SIM STATE"),
                ("net", "NETWORK TYPE"),
                ("mode", "PREFERRED MODE"),
                ("signal", "SIGNAL"),
                ("data", "MOBILE DATA"),
                ("wifi", "WI-FI"),
                ("dns", "PRIVATE DNS"),
                ("airplane", "AIRPLANE MODE"),
            )
        ):
            mc = MetricCard(cap, "--", accent=C["accent"])
            net_grid.addWidget(mc, i // 4, i % 4)
            self.net_cards[key] = mc
        net_grid.setColumnStretch(0, 1)
        net_grid.setColumnStretch(1, 1)
        net_grid.setColumnStretch(2, 1)
        net_grid.setColumnStretch(3, 1)
        lay.addLayout(net_grid)

        status_row = QHBoxLayout()
        self.net_status = QLabel("Live diagnostics update while a device is connected")
        self.net_status.setStyleSheet(f"color:{C['dim']}; font-size:11px;")
        status_row.addWidget(self.net_status, 1)
        lay.addLayout(status_row)

        def action_card(title, desc, btn_label, slot, primary=False):
            c = QFrame()
            c.setStyleSheet(
                f"background: {C['inset']}; border: 1px solid {C['border']};"
                f" border-radius: 12px;"
            )
            cv = QVBoxLayout(c)
            cv.setContentsMargins(16, 16, 16, 16)
            cv.setSpacing(10)
            t = QLabel(title)
            t.setStyleSheet(f"color:{C['text']}; font-size:13px; font-weight:800;")
            t.setWordWrap(True)
            cv.addWidget(t)
            d = QLabel(desc)
            d.setStyleSheet(f"color:{C['dim']}; font-size:11px;")
            d.setWordWrap(True)
            cv.addWidget(d)
            cv.addStretch(1)
            b = QPushButton(btn_label)
            b.setStyleSheet(_btn_primary() if primary else _btn_ghost())
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(slot)
            # ADB-mechanism cards gate on adb_shell availability.
            self._gate_button(b, command={
                "_battery_report": "adb_shell",
                "_battery_repair": "adb_shell",
                "_battery_load_test": "adb_shell",
                "_network_report": "adb_shell",
                "_network_repair": "adb_shell",
                "_network_modem_reset": "adb_shell",
            }.get(getattr(slot, "__name__", "")))
            cv.addWidget(b)
            return c

        lay.addWidget(SectionTitle("ACTIONS"))
        cards = QHBoxLayout()
        cards.setSpacing(14)
        cards.addWidget(
            action_card(
                "Network Report",
                "Full report: SIM state, network type, preferred mode, "
                "data/Wi-Fi flags, DNS, IP and radio version - printed to the "
                "console.",
                "Run Report",
                self._network_report,
            ),
            1,
        )
        cards.addWidget(
            action_card(
                "Network Repair",
                "The fixes commercial tools use: reset radios (airplane cycle), "
                "re-enable Wi-Fi/data, restore network mode, clear DNS, flush "
                "phone/telephony caches.",
                "Repair Network",
                self._network_repair,
                primary=True,
            ),
            1,
        )
        cards.addWidget(
            action_card(
                "Mobile Data Reset",
                "Force the modem to re-register: airplane cycle + preferred "
                "network mode + data re-enable. Good for stuck 'No service'.",
                "Reset Modem",
                self._network_modem_reset,
            ),
            1,
        )
        lay.addLayout(cards)

        # --- SIM / carrier lock lives in a collapsible section so the main
        #     view stays open and breathable ---
        lock_body = QWidget()
        lock_body.setStyleSheet("background: transparent;")
        lock_lay = QVBoxLayout(lock_body)
        lock_lay.setContentsMargins(0, 0, 0, 0)
        lock_lay.setSpacing(12)

        lock_info = QLabel(
            "Check the SIM / network lock state on any device (read-only), and "
            "read / back up the modem lock record on MediaTek A05/A06 (BROM).\n"
            "The MTK unlock step never writes without a validated device recipe."
        )
        lock_info.setStyleSheet(f"color:{C['dim']}; font-size:11px;")
        lock_info.setWordWrap(True)
        lock_lay.addWidget(lock_info)

        lock_cards = QHBoxLayout()
        lock_cards.setSpacing(14)
        lock_cards.addWidget(
            action_card(
                "Carrier Lock Status",
                "Read the SIM / network lock state over ADB on ANY phone "
                "(Samsung, MTK, Qualcomm, UNISOC). Pure read - nothing is "
                "written.",
                "Check Status",
                self._carrier_lock_status,
                primary=True,
            ),
            1,
        )
        lock_cards.addWidget(
            action_card(
                "MTK NVRAM SimLock",
                "A05/A06 (Helio G85): dump the modem NVRAM lock record over the "
                "DA, keep a backup and locate the SimLock record. Recipe-gated "
                "patch.",
                "Read / Backup",
                self._carrier_lock_mtk,
            ),
            1,
        )
        lock_lay.addLayout(lock_cards)

        lay.addWidget(CollapsibleSection(
            "CARRIER / SIM LOCK", lock_body, accent=C["warn"], collapsed=True
        ))

        tip = QLabel(
            "All fixes work over ADB on any connected device (Samsung / MTK / "
            "Qualcomm / any Android). Reversible from the phone's network "
            "settings."
        )
        tip.setStyleSheet(f"color:{C['dim']}; font-size:11px;")
        tip.setWordWrap(True)
        lay.addWidget(tip)
        lay.addStretch(1)

        page_scroll.setWidget(host)
        root_lay.addWidget(page_scroll)
        return panel

    def _build_general_page(self):
        # General = Quick + Battery + Network behind sub-tabs.
        gen = QWidget()
        gen.setStyleSheet("background: transparent;")
        gv = QVBoxLayout(gen)
        gv.setContentsMargins(0, 0, 0, 0)
        gv.setSpacing(8)
        gen_tabs = SamsungSubTabs(
            [("quick", "QUICK"), ("battery", "BATTERY"), ("network", "NETWORK")]
        )
        gv.addWidget(gen_tabs)
        gen_stack = QStackedWidget()
        gen_stack.setStyleSheet("QStackedWidget { background: transparent; }")
        for b in (self._build_quick_page, self._build_battery_page,
                  self._build_network_page):
            gen_stack.addWidget(b())
        gen_keys = ["quick", "battery", "network"]
        gen_tabs.tab_selected.connect(
            lambda k: gen_stack.setCurrentIndex(gen_keys.index(k) if k in gen_keys else 0)
        )
        gv.addWidget(gen_stack, 1)
        self._gen_stack = gen_stack
        return gen
