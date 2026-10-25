"""Samsung hub page builders (ODIN FLASH / UNLOCK / ADVANCED / TOOLS)."""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ..animations import ShimmerBar
from ..common import _experimental_banner, _risk_banner
from ..theme import C, _btn_danger, _btn_ghost, _btn_primary, _card_qss
from ..widgets import CollapsibleSection, FlowLayout, SamsungSubTabs, SectionTitle


class SamsungPageMixin:
    def _build_right(self):
        panel = QFrame()
        panel.setObjectName("card")
        panel.setStyleSheet(
            _card_qss()
        )
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(12)

        lay.addWidget(SectionTitle("OPERATIONS"))

        top_row = QHBoxLayout()
        top_row.setSpacing(10)
        self.info_btn = QPushButton("Get Device Info")
        self.info_btn.setStyleSheet(_btn_ghost())
        self.info_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.info_btn.clicked.connect(self.refresh_device)
        self.info_btn.setToolTip("Scan the bus and print full device info to the console")
        top_row.addWidget(self.info_btn)
        top_row.addStretch(1)
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setEnabled(False)
        self.stop_btn.setStyleSheet(_btn_danger())
        self.stop_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.stop_btn.clicked.connect(self.on_stop)
        self.stop_btn.setToolTip("Cancel the running operation")
        top_row.addWidget(self.stop_btn)
        # Legacy per-chip Stop hidden — global STOP in titlebar is the single entry point
        self.stop_btn.setVisible(False)
        lay.addLayout(top_row)

        # Samsung hub: SUPPORTED | ODIN FLASH | UNLOCK | ADVANCED FLASH | TOOLS.
        # Unlock opens its own inner tab row (FRP / MDM / CARRIER / SCREEN LOCK).
        self.samsung_tabs = SamsungSubTabs(
            [
                ("supported", "SUPPORTED DEVICES"),
                ("flash", "ODIN FLASH"),
                ("unlock", "UNLOCK"),
                ("adv", "ADVANCED FLASH"),
                ("tools", "INFO & TOOLS"),
            ]
        )
        self.samsung_tabs.tab_selected.connect(self._on_samsung_tab)
        lay.addWidget(self.samsung_tabs)

        self.samsung_stack = QStackedWidget()
        self.samsung_stack.setStyleSheet("QStackedWidget { background: transparent; }")

        self._build_flash_inputs()
        flash_page = QWidget()
        flash_page.setStyleSheet("background: transparent;")
        fp_lay = QVBoxLayout(flash_page)
        fp_lay.setContentsMargins(0, 0, 0, 0)
        fp_lay.setSpacing(0)
        flash_scroll = self._ops_scroll_area()
        flash_host = QWidget()
        flash_host.setStyleSheet("background: transparent;")
        fh_lay = QVBoxLayout(flash_host)
        fh_lay.setContentsMargins(0, 0, 0, 0)
        fh_lay.setSpacing(8)
        self._firmware_sec = CollapsibleSection(
            "FIRMWARE SLOTS", self.firmware_panel, accent=C["accent"],
            collapsed=False
        )
        self._options_sec = CollapsibleSection(
            "FLASH OPTIONS", self.options_panel, accent=C["warn"],
            collapsed=True
        )
        fh_lay.addWidget(self._firmware_sec)
        fh_lay.addWidget(self._options_sec)

        # Odin utilities moved from INFO & TOOLS → here (under ODIN FLASH, not INFO)
        _odin_utils_body = QWidget()
        _odin_utils_body.setStyleSheet("background: transparent;")
        _odin_ulay = QVBoxLayout(_odin_utils_body)
        _odin_ulay.setContentsMargins(0, 0, 0, 0)
        _odin_ulay.setSpacing(0)
        self._add_job_flows(
            _odin_ulay, ["Flash Firmware"],
            modes=["Download mode", "ADB"],
            methods=[
                "odin_preflight", "odin_efs_backup", "odin_efs_restore",
                "odin_pit_tools", "odin_list_devices", "odin_vbmeta",
                "reboot_normal",
            ],
        )
        fh_lay.addWidget(CollapsibleSection("ODIN UTILITIES", _odin_utils_body, accent=C["mute"], collapsed=True))
        fh_lay.addStretch(1)
        flash_scroll.setWidget(flash_host)
        fp_lay.addWidget(flash_scroll)
        self.samsung_stack.addWidget(flash_page)

        # SUPPORTED DEVICES — reuse the devices drill-down (level2/3) here
        from . import devices as _dp
        self._device_stacks.setdefault("samsung", None)
        if self._device_stacks.get("samsung") is None:
            self._device_stacks["samsung"] = _dp.build_brand_page(self, "samsung")
        self.samsung_stack.addWidget(self._device_stacks["samsung"])

        # UNLOCK — nested tabs: FRP / MDM / CARRIER / SCREEN LOCK
        unlock_wrap = QWidget()
        unlock_wrap.setStyleSheet("background: transparent;")
        uv = QVBoxLayout(unlock_wrap)
        uv.setContentsMargins(0, 0, 0, 0)
        uv.setSpacing(8)
        unlock_tabs = SamsungSubTabs(
            [("frp", "FRP"), ("mdm", "MDM"),
             ("carrier", "CARRIER LOCK"), ("lock", "SCREEN LOCK")]
        )
        uv.addWidget(unlock_tabs)
        unlock_stack = QStackedWidget()
        unlock_stack.setStyleSheet("QStackedWidget { background: transparent; }")
        u_keys = ["frp", "mdm", "carrier", "lock"]
        u_pages = {
            "frp": self._build_ops_flow_page(["Remove FRP"]),
            "mdm": self._build_ops_flow_page(["Remove MDM"], qr=True),
            "carrier": self._build_ops_flow_page(["Unlock Carrier"]),
            "lock": self._build_ops_flow_page(["Remove Screen Lock"]),
        }
        for k in u_keys:
            unlock_stack.addWidget(u_pages[k])
        unlock_tabs.tab_selected.connect(
            lambda k: unlock_stack.setCurrentIndex(
                u_keys.index(k) if k in u_keys else 0)
        )
        uv.addWidget(unlock_stack, 1)
        self._unlock_stack = unlock_stack
        self.samsung_stack.addWidget(unlock_wrap)

        # ADVANCED FLASH — dedicated tab (was collapsed section on FLASH)
        adv_page = QWidget()
        adv_page.setStyleSheet("background: transparent;")
        av = QVBoxLayout(adv_page)
        av.setContentsMargins(0, 0, 0, 0)
        av.setSpacing(8)
        adv_scroll = self._ops_scroll_area()
        adv_host = QWidget()
        adv_host.setStyleSheet("background: transparent;")
        ah = QVBoxLayout(adv_host)
        ah.setContentsMargins(0, 0, 0, 0)
        ah.setSpacing(8)
        self._adv_sec = CollapsibleSection(
            "ADVANCED FLASH", self.adv_panel, accent=C["ok"], collapsed=False
        )
        ah.addWidget(self._adv_sec)
        ah.addStretch(1)
        adv_scroll.setWidget(adv_host)
        av.addWidget(adv_scroll)
        self.samsung_stack.addWidget(adv_page)

        tools_combo = QWidget()
        tools_combo.setStyleSheet("background: transparent;")
        tc_lay = QVBoxLayout(tools_combo)
        tc_lay.setContentsMargins(0, 0, 0, 0)
        tc_lay.setSpacing(0)
        scroll = self._ops_scroll_area()
        host = QWidget()
        host.setStyleSheet("background: transparent;")
        hv = QVBoxLayout(host)
        hv.setContentsMargins(0, 0, 0, 0)
        hv.setSpacing(10)
        self._add_job_flows(hv, ["Read Device Info", "Detect Devices", "Reboot",
                                 "Repair Settings"])
        hv.addStretch(1)
        scroll.setWidget(host)
        tc_lay.addWidget(scroll)
        self.samsung_stack.addWidget(tools_combo)

        # EXPERIMENTAL — Samsung Knox (per-chip, amber, every-run ack)
        knox_exp_host = QWidget()
        knox_exp_host.setStyleSheet("background: transparent;")
        knox_exp_lay = QVBoxLayout(knox_exp_host)
        knox_exp_lay.setContentsMargins(0, 0, 0, 0)
        knox_exp_lay.setSpacing(8)
        knox_exp_lay.addWidget(_experimental_banner(
            "EXPERIMENTAL — Knox bypass permanently trips eFuse (0x1, irreversible). Educational, own device only. Audit logged. Every run requires the checkbox."))
        self._add_job_flows(knox_exp_lay, ["Knox / Warranty"])
        knox_exp_body = QWidget()
        knox_exp_body.setStyleSheet("background: transparent;")
        _knox_body_lay = QVBoxLayout(knox_exp_body)
        _knox_body_lay.setContentsMargins(16, 14, 16, 14)
        _knox_body_lay.setSpacing(8)
        _knox_body_lay.addWidget(knox_exp_host)
        lay.addWidget(CollapsibleSection("KNOX — EXPERIMENTAL", knox_exp_body, accent=C["warn"], collapsed=True))

        lay.addWidget(self.samsung_stack, 1)

        # Fix: default stack is 0 (ODIN FLASH) but tabs default to SUPPORTED → mismatch
        # User sees FLASH while selector says SUPPORTED. Sync to FLASH.
        try:
            self.samsung_tabs.set_active("flash")
            self.samsung_stack.setCurrentIndex(0)
        except Exception:
            pass

        self.shimmer = ShimmerBar()
        self.shimmer.setVisible(False)
        lay.addWidget(self.shimmer)

        self.status = QLabel("Ready")
        self.status.setStyleSheet(f"color:{C['dim']}; font-size:12px;")
        lay.addWidget(self.status)

        return panel

    def _on_samsung_tab(self, key):
        index = {"supported": 1, "flash": 0, "unlock": 2,
                 "adv": 3, "tools": 4}.get(key, 0)
        self.samsung_stack.setCurrentIndex(index)
        # Fix shrink: Samsung sub-stack hides FlowHost; invalidate so heightForWidth recomputes.
        try:
            w = self.samsung_stack.currentWidget()
            if w:
                for child in w.findChildren(QFrame):
                    lay = child.layout()
                    if lay and hasattr(lay, "invalidate"):
                        lay.invalidate()
                w.updateGeometry()
                self.samsung_stack.updateGeometry()
        except Exception:
            pass

    def _build_flash_inputs(self):
        # --- Zone 1: Firmware slots (circuit-deck panel) ---
        self.firmware_panel = QFrame()
        self.firmware_panel.setObjectName("firmware")
        self.firmware_panel.setStyleSheet(
            f"QFrame#firmware {{ background: qlineargradient(x1:0,y1:0,x2:0,y2:1,"
            f" stop:0 {C['card']}, stop:1 {C['inset']});"
            f" border: 1px solid {C['border']}; border-left: 2px solid {C['border_hi']};"
            f" border-top: 1px solid {C['border_hi']}; border-radius: 9px; }}"
        )
        f_lay = QVBoxLayout(self.firmware_panel)
        f_lay.setContentsMargins(14, 10, 14, 14)
        f_lay.setSpacing(8)

        self.slot_inputs = {}
        slots_grid = QGridLayout()
        slots_grid.setContentsMargins(0, 0, 0, 0)
        slots_grid.setHorizontalSpacing(10)
        slots_grid.setVerticalSpacing(8)

        slot_row = {"AP": 0, "BL": 0, "CP": 1, "CSC": 1, "USERDATA": 2}
        slot_col = {"AP": 0, "BL": 1, "CP": 0, "CSC": 1, "USERDATA": 0}

        def _slot_row(label, row, col, span):
            cell = QWidget()
            cell.setStyleSheet("background: transparent;")
            c_lay = QVBoxLayout(cell)
            c_lay.setContentsMargins(0, 0, 0, 0)
            c_lay.setSpacing(4)
            hl = QHBoxLayout()
            hl.setSpacing(6)
            lbl = QLabel(label)
            lbl.setStyleSheet(f"color: {C['accent_hi']}; font-weight: 800; font-size: 10px; min-width: 58px;")
            hl.addWidget(lbl)
            edit = QLineEdit()
            edit.setPlaceholderText(f"Select {label} (.tar)")
            edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            edit.setStyleSheet(f"QLineEdit {{ background: {C['inset']}; border: 1px solid {C['border']}; border-radius: 6px; padding: 4px 8px; color: {C['text']}; selection-background-color: {C['accent']}; }} QLineEdit:hover {{ border: 1px solid {C['border_hi']}; }} QLineEdit:focus {{ border: 1px solid {C['accent']}; }}")
            hl.addWidget(edit, 1)
            btn = QPushButton("Browse")
            btn.setStyleSheet(_btn_ghost())
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedWidth(66)
            btn.clicked.connect(
                (lambda e=edit, n=label: lambda: self._browse_slot(e, n))()
            )
            hl.addWidget(btn)
            c_lay.addLayout(hl)
            slots_grid.addWidget(cell, row, col, 1, span)
            self.slot_inputs[label] = edit

        _slot_row("AP", 0, 0, 1)
        _slot_row("BL", 0, 1, 1)
        _slot_row("CP", 1, 0, 1)
        _slot_row("CSC", 1, 1, 1)
        _slot_row("USERDATA", 2, 0, 2)
        slots_grid.setColumnStretch(0, 1)
        slots_grid.setColumnStretch(1, 1)
        f_lay.addLayout(slots_grid)

        run_row = QHBoxLayout()
        run_row.setSpacing(8)
        self.flash_btn = QPushButton("Flash Firmware")
        self.flash_btn.setStyleSheet(_btn_primary())
        self.flash_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.flash_btn.setToolTip(
            "Flash the selected AP/BL/CP/CSC/USERDATA firmware (odin4)"
        )
        self.flash_btn.clicked.connect(self._on_flash_slots)
        self._gate_button(self.flash_btn, job="Flash Firmware", mode="Download mode")
        run_row.addWidget(self.flash_btn)
        self.check_tar_btn = QPushButton("Check archive")
        self.check_tar_btn.setStyleSheet(_btn_ghost())
        self.check_tar_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.check_tar_btn.setToolTip(
            "Validate the firmware archive / PIT with odin4 --check-only (no write)"
        )
        self.check_tar_btn.clicked.connect(
            lambda: self._run_ops_flow(
                "Flash Firmware", "Download mode",
                "odin_check_tar", "Check firmware archive (odin4)"
            )
        )
        run_row.addWidget(self.check_tar_btn)
        run_row.addStretch(1)
        f_lay.addLayout(run_row)
        f_lay.addWidget(
            _risk_banner(
                "Flashing overwrites your device's firmware. Wrong files or a "
                "power cut can brick it - keep it plugged in and charged."
            )
        )

        # --- Zone 2: Flash options (safety switches) ---
        self.options_panel = QFrame()
        self.options_panel.setObjectName("flashopts")
        self.options_panel.setStyleSheet(
            f"QFrame#flashopts {{ background: qlineargradient(x1:0,y1:0,x2:0,y2:1,"
            f" stop:0 {C['card']}, stop:1 {C['inset']});"
            f" border: 1px solid {C['border']}; border-left: 2px solid {C['warn']};"
            f" border-top: 1px solid {C['border_hi']}; border-radius: 9px; }}"
        )
        opt_lay = QVBoxLayout(self.options_panel)
        opt_lay.setContentsMargins(14, 10, 14, 14)
        opt_lay.setSpacing(6)

        opt_row = FlowLayout(spacing=8)
        self.allow_unknown_cb = QCheckBox("Allow unknown partitions (bypass PIT check, --allow-unknown)")
        self.allow_unknown_cb.setChecked(False)
        self.allow_unknown_cb.setToolTip(
            "OFF by default (safety). Lets odin4 skip archive entries that have no match\n"
            "in the device's PIT. Needed for unofficial/custom firmware or region variants\n"
            "whose partition table differs from the device ('check failure pit' / PIT mismatch).\n"
            "Only enable for firmware you are certain is correct for this device."
        )
        self.allow_unknown_cb.setStyleSheet(
            f"QCheckBox {{ color:{C['mute']}; font-size:10px; font-weight:600; }}"
            f" QCheckBox::indicator {{ width:14px; height:14px; }}"
        )
        opt_row.addWidget(self.allow_unknown_cb)
        self.auto_reboot_cb = QCheckBox("Auto-reboot after flash (--reboot)")
        self.auto_reboot_cb.setChecked(False)
        self.auto_reboot_cb.setToolTip(
            "OFF by default (safety). Lets odin4 reboot the phone as soon as the flash\n"
            "finishes. Leave OFF so you can verify the flash completed before rebooting -\n"
            "a failed write otherwise hides behind a phone that no longer answers."
        )
        self.auto_reboot_cb.setStyleSheet(
            f"QCheckBox {{ color:{C['mute']}; font-size:10px; font-weight:600; }}"
            f" QCheckBox::indicator {{ width:14px; height:14px; }}"
        )
        opt_row.addWidget(self.auto_reboot_cb)
        opt_lay.addLayout(opt_row)

        # Advanced options row 2 - always-work repair steps
        opt_row2 = FlowLayout(spacing=8)
        self.erase_nv_cb = QCheckBox("Erase NVRAM/NVDATA (zero-fill nv* partitions)")
        self.erase_nv_cb.setChecked(False)
        self.erase_nv_cb.setToolTip(
            "OFF by default (safety - wipes network calibration). After the flash,\n"
            "zero-fills every NVRAM/NVDATA partition from the device's own PIT using\n"
            "the native Odin flash path. Standard fix for IMEI/network issues and a\n"
            "common FRP-adjacent step. Works on Odin-protocol (Exynos/Qualcomm)\n"
            "download mode; MTK download-agent devices use the MediaTek workbench."
        )
        self.erase_nv_cb.setStyleSheet(
            f"QCheckBox {{ color:{C['mute']}; font-size:10px; font-weight:600; }}"
            f" QCheckBox::indicator {{ width:14px; height:14px; }}"
        )
        opt_row2.addWidget(self.erase_nv_cb)
        self.check_only_cb = QCheckBox("Validate archives first (--check-only)")
        self.check_only_cb.setChecked(False)
        self.check_only_cb.setToolTip(
            "Run odin4 --check-only over every selected archive BEFORE flashing.\n"
            "Aborts on corrupt/renamed .tar.md5 or PIT mismatches so a bad archive\n"
            "is never written to the phone."
        )
        self.check_only_cb.setStyleSheet(
            f"QCheckBox {{ color:{C['mute']}; font-size:10px; font-weight:600; }}"
            f" QCheckBox::indicator {{ width:14px; height:14px; }}"
        )
        opt_row2.addWidget(self.check_only_cb)
        self.redownload_cb = QCheckBox("Re-download after flash (--redownload)")
        self.redownload_cb.setChecked(False)
        self.redownload_cb.setToolTip(
            "After flashing, odin4 sends the Redownload command so the phone re-enters\n"
            "download mode instead of rebooting - the reliable way to chain a second\n"
            "step (like Erase NVRAM) without power-cycling. Mutually exclusive with\n"
            "auto-reboot."
        )
        self.redownload_cb.setStyleSheet(
            f"QCheckBox {{ color:{C['mute']}; font-size:10px; font-weight:600; }}"
            f" QCheckBox::indicator {{ width:14px; height:14px; }}"
        )
        opt_row2.addWidget(self.redownload_cb)
        self.verbose_cb = QCheckBox("Verbose logging (--verbose)")
        self.verbose_cb.setChecked(False)
        self.verbose_cb.setToolTip(
            "Pass --verbose to odin4 so the console shows detailed per-partition\n"
            "progress - useful for diagnosing stuck flashes."
        )
        self.verbose_cb.setStyleSheet(
            f"QCheckBox {{ color:{C['mute']}; font-size:10px; font-weight:600; }}"
            f" QCheckBox::indicator {{ width:14px; height:14px; }}"
        )
        opt_row2.addWidget(self.verbose_cb)
        opt_lay.addLayout(opt_row2)

        # Auto-reboot and re-download are mutually exclusive.
        self.auto_reboot_cb.toggled.connect(
            lambda on: self.redownload_cb.setChecked(False) if on else None
        )
        self.redownload_cb.toggled.connect(
            lambda on: self.auto_reboot_cb.setChecked(False) if on else None
        )

        # BL downgrade override row (native multi-partition flash gate)
        opt_row3 = FlowLayout(spacing=8)
        self.skip_efs_cb = QCheckBox("Skip EFS backup requirement (ODIN4_SKIP_BACKUP=1)")
        self.skip_efs_cb.setChecked(False)
        self.skip_efs_cb.setToolTip(
            "OFF by default (safety). The flash refuses to run without a recent\n"
            "EFS backup (<30 days) or an authorized-ADB auto-backup. Tick this\n"
            "ONLY if you already have backups elsewhere - EFS holds IMEI/radio\n"
            "calibration; losing it without a backup is unrecoverable."
        )
        self.skip_efs_cb.setStyleSheet(
            f"QCheckBox {{ color:{C['mute']}; font-size:10px; font-weight:600; }}"
            f" QCheckBox::indicator {{ width:14px; height:14px; }}"
        )
        opt_row3.addWidget(self.skip_efs_cb)
        self.engine_native_cb = QCheckBox("Use native engine (recommended)")
        self.engine_native_cb.setChecked(True)
        self.engine_native_cb.setToolTip(
            "ON  = FlashPilot's own single-session Rust writer.\n"
            "     Preserves Loke's one-session-per-plug rule; best for\n"
            "     MTK-Samsung units like A14/A15 Helio variants.\n"
            "OFF = Samsung's proprietary odin4 binary (Exynos fallback)."
        )
        self.engine_native_cb.setStyleSheet(
            f"QCheckBox {{ color:{C['mute']}; font-size:10px; font-weight:600; }}"
            f" QCheckBox::indicator {{ width:14px; height:14px; }}"
        )
        opt_row3.addWidget(self.engine_native_cb)
        self.force_bl_cb = QCheckBox("Allow BL revision downgrade (ODIN4_FORCE_BL=1)")
        self.force_bl_cb.setChecked(False)
        self.force_bl_cb.setToolTip(
            "OFF by default (safety). Lets the native multi-partition flash write a\n"
            "bootloader whose revision is LOWER than the device's current one.\n"
            "Flashing a lower BL revision on a newer device can hard-brick it - only\n"
            "enable when you are certain the older firmware is correct for this device."
        )
        self.force_bl_cb.setStyleSheet(
            f"QCheckBox {{ color:{C['mute']}; font-size:10px; font-weight:600; }}"
            f" QCheckBox::indicator {{ width:14px; height:14px; }}"
        )
        opt_row3.addWidget(self.force_bl_cb)
        opt_lay.addLayout(opt_row3)

        # vbmeta auto-patch toggle
        opt_row4 = FlowLayout(spacing=8)
        self.vbmeta_patch_cb = QCheckBox("Auto-patch vbmeta (disable AVB verification)")
        self.vbmeta_patch_cb.setChecked(True)
        self.vbmeta_patch_cb.setToolTip(
            "When ON, extracts vbmeta from AP firmware, patches it to disable\n"
            "AVB verification (flags 0x03), and flashes the patched vbmeta.\n"
            "Required for booting custom kernels / unofficial firmware."
        )
        self.vbmeta_patch_cb.setStyleSheet(
            f"QCheckBox {{ color:{C['mute']}; font-size:10px; font-weight:600; }}"
            f" QCheckBox::indicator {{ width:14px; height:14px; }}"
        )
        opt_row4.addWidget(self.vbmeta_patch_cb)
        opt_lay.addLayout(opt_row4)

        # --- Zone 3: Advanced single-partition + native flash (circuit-deck) ---
        self.adv_panel = QFrame()
        self.adv_panel.setObjectName("adv")
        self.adv_panel.setStyleSheet(
            f"QFrame#adv {{ background: qlineargradient(x1:0,y1:0,x2:0,y2:1,"
            f" stop:0 {C['card']}, stop:1 {C['inset']});"
            f" border: 1px solid {C['border']}; border-left: 2px solid {C['ok']};"
            f" border-top: 1px solid {C['border_hi']}; border-radius: 9px; }}"
        )
        a_lay = QVBoxLayout(self.adv_panel)
        a_lay.setContentsMargins(14, 10, 14, 14)
        a_lay.setSpacing(8)
        a_lay.addWidget(
            _risk_banner(
                "Advanced: these write directly to partitions. A wrong "
                "partition/image combo can soft-brick the device."
            )
        )

        self.partition_edit = QLineEdit()
        self.partition_edit.setPlaceholderText("e.g. vbmeta, boot, super, system ...")
        self.partition_edit.setMinimumWidth(80)
        self.partition_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.partition_edit.setStyleSheet(f"QLineEdit {{ background: {C['inset']}; border: 1px solid {C['border']}; border-radius: 8px; padding: 6px 10px; color: {C['text']}; selection-background-color: {C['accent']}; }} QLineEdit:hover {{ border: 1px solid {C['border_hi']}; }} QLineEdit:focus {{ border: 1px solid {C['accent']}; }}")

        self.image_edit = QLineEdit()
        self.image_edit.setPlaceholderText("Image file (.img / .lz4 / .tar)")
        self.image_edit.setMinimumWidth(80)
        self.image_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.image_edit.setStyleSheet(f"QLineEdit {{ background: {C['inset']}; border: 1px solid {C['border']}; border-radius: 8px; padding: 6px 10px; color: {C['text']}; selection-background-color: {C['accent']}; }} QLineEdit:hover {{ border: 1px solid {C['border_hi']}; }} QLineEdit:focus {{ border: 1px solid {C['accent']}; }}")

        self.sales_code_edit = QLineEdit()
        self.sales_code_edit.setPlaceholderText("e.g. XSG")
        self.sales_code_edit.setMinimumWidth(80)
        self.sales_code_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.sales_code_edit.setStyleSheet(f"QLineEdit {{ background: {C['inset']}; border: 1px solid {C['border']}; border-radius: 8px; padding: 6px 10px; color: {C['text']}; selection-background-color: {C['accent']}; }} QLineEdit:hover {{ border: 1px solid {C['border_hi']}; }} QLineEdit:focus {{ border: 1px solid {C['accent']}; }}")

        self.flash_specs_edit = QLineEdit()
        self.flash_specs_edit.setPlaceholderText("partition=image;partition=image")
        self.flash_specs_edit.setMinimumWidth(80)
        self.flash_specs_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.flash_specs_edit.setStyleSheet(f"QLineEdit {{ background: {C['inset']}; border: 1px solid {C['border']}; border-radius: 8px; padding: 6px 10px; color: {C['text']}; selection-background-color: {C['accent']}; }} QLineEdit:hover {{ border: 1px solid {C['border_hi']}; }} QLineEdit:focus {{ border: 1px solid {C['accent']}; }}")

        self.pit_file_edit = QLineEdit()
        self.pit_file_edit.setPlaceholderText("Path to .pit")
        self.pit_file_edit.setMinimumWidth(80)
        self.pit_file_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.pit_file_edit.setStyleSheet(f"QLineEdit {{ background: {C['inset']}; border: 1px solid {C['border']}; border-radius: 8px; padding: 6px 10px; color: {C['text']}; selection-background-color: {C['accent']}; }} QLineEdit:hover {{ border: 1px solid {C['border_hi']}; }} QLineEdit:focus {{ border: 1px solid {C['accent']}; }}")

        def _adv_run(method, label, tooltip):
            btn = QPushButton(label)
            btn.setStyleSheet(_btn_ghost())
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setToolTip(tooltip)
            btn.clicked.connect(
                lambda _=False, m=method, n=label: self._confirm_flash_action(
                    n, m,
                    "This writes data to your device. DO NOT unplug it until "
                    "the operation finishes.",
                )
            )
            return btn

        # single partition + image -> one row
        p_row = QHBoxLayout()
        p_label = QLabel("Single")
        p_label.setStyleSheet(f"color: {C['accent_hi']}; font-weight: 800; min-width: 52px; font-size: 11px;")
        p_row.addWidget(p_label)
        p_row.addWidget(self.partition_edit, 1)
        p_row.addWidget(self.image_edit, 1)
        img_btn = QPushButton("Browse...")
        img_btn.setStyleSheet(_btn_ghost())
        img_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        img_btn.setFixedWidth(80)
        img_btn.clicked.connect(lambda: self._browse_slot(self.image_edit, "partition image"))
        p_row.addWidget(img_btn)
        p_run = _adv_run(
            "odin_flash_partition", "Flash",
            "Flash one partition (raw) with the partition name + image above"
        )
        p_run.setFixedWidth(64)
        p_row.addWidget(p_run)
        a_lay.addLayout(p_row)

        # sales code -> one row
        sc_row = QHBoxLayout()
        sc_label = QLabel("Sales Code")
        sc_label.setStyleSheet(f"color: {C['accent_hi']}; font-weight: 800; min-width: 70px; font-size: 11px;")
        sc_row.addWidget(sc_label)
        sc_row.addWidget(self.sales_code_edit, 1)
        sc_run = _adv_run(
            "odin_sales_code", "Apply",
            "Change the CSC / sales code on the device (needs a matching CSC archive)"
        )
        sc_run.setFixedWidth(64)
        sc_row.addWidget(sc_run)
        a_lay.addLayout(sc_row)

        # multi-partition specs -> one row
        ms_row = QHBoxLayout()
        ms_label = QLabel("Flash specs")
        ms_label.setStyleSheet(f"color: {C['accent_hi']}; font-weight: 800; min-width: 70px; font-size: 11px;")
        ms_row.addWidget(ms_label)
        ms_row.addWidget(self.flash_specs_edit, 1)
        ms_run = _adv_run(
            "odin_flash_multi", "Flash",
            "Flash multiple partitions from partition=image;partition=image specs"
        )
        ms_run.setFixedWidth(64)
        ms_row.addWidget(ms_run)
        a_lay.addLayout(ms_row)

# pit -> one row
        pit_row = QHBoxLayout()
        pit_label = QLabel("PIT file")
        pit_label.setStyleSheet(f"color: {C['accent_hi']}; font-weight: 800; min-width: 70px; font-size: 11px;")
        pit_row.addWidget(pit_label)
        pit_row.addWidget(self.pit_file_edit, 1)
        pit_btn = QPushButton("Browse...")
        pit_btn.setStyleSheet(_btn_ghost())
        pit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        pit_btn.setFixedWidth(80)
        pit_btn.clicked.connect(lambda: self._browse_slot(self.pit_file_edit, "pit"))
        pit_run = _adv_run(
            "odin_send_pit", "Send",
            "Send the PIT to the device (repartition)"
        )
        pit_run.setFixedWidth(64)
        pit_row.addWidget(pit_run)
        a_lay.addLayout(pit_row)

        # vbmeta -> one row
        vb_row = QHBoxLayout()
        vb_label = QLabel("vbmeta")
        vb_label.setStyleSheet(f"color: {C['accent_hi']}; font-weight: 800; min-width: 70px; font-size: 11px;")
        vb_row.addWidget(vb_label)
        self.vbmeta_edit = QLineEdit()
        self.vbmeta_edit.setPlaceholderText("vbmeta image (.img / .img.lz4)")
        self.vbmeta_edit.setMinimumWidth(80)
        self.vbmeta_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.vbmeta_edit.setStyleSheet(f"QLineEdit {{ background: {C['inset']}; border: 1px solid {C['border']}; border-radius: 8px; padding: 6px 10px; color: {C['text']}; selection-background-color: {C['accent']}; }} QLineEdit:hover {{ border: 1px solid {C['border_hi']}; }} QLineEdit:focus {{ border: 1px solid {C['accent']}; }}")
        vb_row.addWidget(self.vbmeta_edit, 1)
        vb_img_btn = QPushButton("Browse...")
        vb_img_btn.setStyleSheet(_btn_ghost())
        vb_img_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        vb_img_btn.setFixedWidth(80)
        vb_img_btn.clicked.connect(lambda: self._browse_slot(self.vbmeta_edit, "vbmeta image"))
        vb_row.addWidget(vb_img_btn)
        vb_run = _adv_run(
            "odin_flash_partition", "Flash vbmeta",
            "Flash vbmeta partition (use pre-modified image to disable verification)"
        )
        vb_run.setFixedWidth(64)
        vb_row.addWidget(vb_run)
        a_lay.addLayout(vb_row)
