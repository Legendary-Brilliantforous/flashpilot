"""QUICK page builder (one-tap ADB / Fastboot / reset actions)."""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..theme import C, _btn_ghost, _btn_primary, _card_qss
from ..widgets import SectionTitle
from ...core import core


class QuickPageMixin:
    def _build_quick_page(self):
        """QUICK page: one-tap Factory reset / Reboot / ADB / Fastboot
        actions without hunting through mode dropdowns."""
        panel = QFrame()
        panel.setObjectName("card")
        panel.setStyleSheet(
            _card_qss()
        )
        panel_lay = QVBoxLayout(panel)
        panel_lay.setContentsMargins(0, 0, 0, 0)
        panel_lay.setSpacing(0)
        scroll = self._ops_scroll_area()
        host = QWidget()
        host.setStyleSheet("background: transparent;")
        hv = QVBoxLayout(host)
        hv.setContentsMargins(16, 14, 16, 14)
        hv.setSpacing(12)

        hv.addWidget(SectionTitle("QUICK ACTIONS"))
        info = QLabel(
            "One-tap ADB & Fastboot actions - reboot destinations and factory "
            "reset without hunting through the mode dropdowns."
        )
        info.setWordWrap(True)
        info.setStyleSheet(f"color:{C['mute']}; font-size:11px;")
        hv.addWidget(info)

        # --- XOS/Transsion unlock (secret codes) --------------------------
        hv.addWidget(SectionTitle("XOS / INFINIX-TECNO-ITEL UNLOCK (SECRET CODES)"))
        xos_info = QLabel(
            "Enable ADB on a factory-reset (FRP) Transsion phone:\n"
            "① Welcome → select language & country → connect WiFi → Next\n"
            "② On the Agreement page tap the 'Personalized Recommendations'\n"
            "    privacy-policy link → Chrome opens\n"
            "③ In Chrome type 'frpbypass' → on that site find the DIALER link\n"
            "    and open it → the real phone Dialer appears despite OOBE lock\n"
            "④ Dial *#*#49#*#* → ADB enables persistently. Plug USB, authorize."
        )
        xos_info.setWordWrap(True)
        xos_info.setStyleSheet(f"color:{C['mute']}; font-size:11px;")
        hv.addWidget(xos_info)

        xos_row = QHBoxLayout()
        codes_btn = QPushButton("📋 Secret Codes Reference")
        codes_btn.setStyleSheet(_btn_ghost())
        codes_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        codes_btn.setToolTip("Full code table for Transsion/XOS devices")
        codes_btn.clicked.connect(self._show_secret_codes)
        xos_row.addWidget(codes_btn)
        triage_btn = QPushButton("🔎 ADB Triage")
        triage_btn.setStyleSheet(_btn_primary())
        triage_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        triage_btn.setToolTip(
            "Probe the connected device over ADB: lock enforcement state, root, "
            "partition access, FRP markers - tells you which flow to use next."
        )
        triage_btn.clicked.connect(self._adb_triage)
        self._gate_button(triage_btn, command="adb_shell")
        xos_row.addWidget(triage_btn)
        xos_row.addStretch(1)
        hv.addLayout(xos_row)

        # --- PIT safety contract (auto-fetch + forensic validation) -------
        hv.addWidget(SectionTitle("PIT SAFETY CONTRACT"))
        pit_info = QLabel(
            "Fetches the partition table straight from the phone (the device "
            "is always the source of truth), validates it with the odin4 "
            "checklist plus FlashPilot chain analysis, and caches it by "
            "content hash. Runs automatically before every flash."
        )
        pit_info.setWordWrap(True)
        pit_info.setStyleSheet(f"color:{C['mute']}; font-size:11px;")
        hv.addWidget(pit_info)

        pit_btn_row = QHBoxLayout()
        self._pit_fetch_btn = QPushButton("Fetch & Verify PIT")
        self._pit_fetch_btn.setStyleSheet(_btn_primary())
        self._pit_fetch_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._pit_fetch_btn.setToolTip(
            "Auto-fetch PIT from the phone in download mode, validate it and "
            "show the storage map"
        )
        self._pit_fetch_btn.clicked.connect(self._pit_fetch_clicked)
        self._gate_button(self._pit_fetch_btn, command="pit-fetch")
        pit_btn_row.addWidget(self._pit_fetch_btn)
        self._pit_cache_lbl = QLabel("")
        self._pit_cache_lbl.setStyleSheet(f"color:{C['mute']}; font-size:10px;")
        pit_btn_row.addWidget(self._pit_cache_lbl, 1)
        hv.addLayout(pit_btn_row)

        self._pit_view = QPlainTextEdit()
        self._pit_view.setReadOnly(True)
        self._pit_view.setMaximumHeight(190)
        self._pit_view.setPlaceholderText(
            "PIT health, findings and storage map will appear here..."
        )
        self._pit_view.setStyleSheet(
            f"QPlainTextEdit {{ background:{C['inset']}; border:1px solid {C['border']};"
            f" border-radius:8px; color:{C['text']}; font-size:10px;"
            f" font-family:'JetBrains Mono','Consolas',monospace; }}"
        )
        hv.addWidget(self._pit_view)
        self._refresh_pit_cache_label()

        # --- Native one-session archive flash -----------------------------
        hv.addWidget(SectionTitle("NATIVE FLASH (ONE SESSION)"))
        nf_info = QLabel(
            "Flash an Odin .tar archive with FlashPilot's own writer - "
            "extract, decompress, PIT-map and write every partition in a "
            "single session. No replugging, no odin4 (which cannot talk to "
            "A14-class devices anyway)."
        )
        nf_info.setWordWrap(True)
        nf_info.setStyleSheet(f"color:{C['mute']}; font-size:11px;")
        hv.addWidget(nf_info)

        nf_row = QHBoxLayout()
        self._nf_tar_edit = QLineEdit()
        self._nf_tar_edit.setPlaceholderText("Bootloader/AP archive (.tar)...")
        self._nf_tar_edit.setStyleSheet(
            f"QLineEdit {{ background:{C['inset']}; border:1px solid {C['border']};"
            f" border-radius:8px; padding:6px 10px; color:{C['text']}; }}"
        )
        nf_row.addWidget(self._nf_tar_edit, 1)
        nf_browse = QPushButton("Browse...")
        nf_browse.setStyleSheet(_btn_ghost())
        nf_browse.setCursor(Qt.CursorShape.PointingHandCursor)
        nf_browse.setFixedWidth(90)
        nf_browse.clicked.connect(self._nf_pick_tar)
        nf_row.addWidget(nf_browse)
        hv.addLayout(nf_row)

        self._nf_patch_cb = QCheckBox("Patch vbmeta - disable AVB verification")
        self._nf_patch_cb.setChecked(True)
        self._nf_patch_cb.setToolTip(
            "Rewrites the archive's vbmeta flags to 0x03 so mixed-version\n"
            "bootloaders pass Android Verified Boot. Required when flashing\n"
            "a BL from a different build than the installed system."
        )
        self._nf_patch_cb.setStyleSheet(
            f"QCheckBox {{ color:{C['text']}; font-size:11px; }}"
            f" QCheckBox::indicator {{ width:16px; height:16px; }}"
        )
        hv.addWidget(self._nf_patch_cb)

        nf_btn_row = QHBoxLayout()
        self._nf_flash_btn = QPushButton("⚡ Flash Archive Now")
        self._nf_flash_btn.setStyleSheet(_btn_primary())
        self._nf_flash_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._nf_flash_btn.clicked.connect(self._native_flash_clicked)
        self._gate_button(self._nf_flash_btn, job="Flash Firmware", mode="Download mode")
        nf_btn_row.addWidget(self._nf_flash_btn)
        nf_btn_row.addStretch(1)
        hv.addLayout(nf_btn_row)

        # --- Factory reset (ADB + recovery fallback) ---
        hv.addWidget(SectionTitle("FACTORY RESET"))
        fr_row = QHBoxLayout()
        fr_row.setSpacing(8)
        fr_btn = QPushButton("Factory reset")
        fr_btn.setStyleSheet(_btn_primary())
        fr_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        fr_btn.setToolTip("ADB wipe /data when authorized, else guided recovery reset")
        fr_btn.clicked.connect(
            lambda: self._confirm_overlay(
                "Factory Reset",
                "This WIPES ALL DATA on the connected device:\n\n"
                "  - Apps, accounts, photos, messages, files\n"
                "  - Phone / modem settings are kept\n\n"
                "It tries an ADB /data wipe first, and falls back to a guided "
                "recovery-mode reset if the device is not authorized.\n\n"
                "There is NO undo. Continue?",
                confirm_label="Wipe Device",
                on_confirm=lambda: self._run_ops_flow(
                    "Remove FRP", "ADB", "factory_reset",
                    core.FLOWS["factory_reset"]().name,
                ),
            )
        )
        fr_row.addWidget(fr_btn)
        fr_row.addStretch(1)
        hv.addLayout(fr_row)

        # --- ADB: one-tap reboot destinations ---
        hv.addWidget(SectionTitle("ADB / USB DEBUGGING"))
        self._add_job_flows(hv, ["Reboot"], modes=["ADB"])
        sw_row = QHBoxLayout()
        sw_row.setSpacing(8)
        sw_btn = QPushButton("Setup wizard bypass")
        sw_btn.setStyleSheet(_btn_ghost())
        sw_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        sw_btn.setToolTip(
            "Classic ADB bypass for older Android (7-8) stuck on the setup wizard"
        )
        sw_btn.clicked.connect(
            lambda: self._run_ops_flow(
                "Remove FRP", "ADB", "setup_wizard",
                core.FLOWS["setup_wizard"]().name,
            )
        )
        sw_row.addWidget(sw_btn)
        sw_row.addStretch(1)
        hv.addLayout(sw_row)

        # --- Fastboot: reboot out of / within bootloader mode ---
        hv.addWidget(SectionTitle("FASTBOOT"))
        self._add_job_flows(hv, ["Reboot"], modes=["FASTBOOT"])

        hv.addStretch(1)
        scroll.setWidget(host)
        panel_lay.addWidget(scroll)
        return panel
