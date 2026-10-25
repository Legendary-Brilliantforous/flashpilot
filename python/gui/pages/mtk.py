"""MediaTek (MTK) tools page builder."""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..common import _experimental_banner, _risk_banner
from ..theme import C, _btn_danger, _btn_ghost, _btn_primary, _card_qss
from ..widgets import CollapsibleSection, SectionTitle


class MtkPageMixin:
    # ----------------------------- MTK Tools page -------------------------
    def _build_mtk_page(self):
        panel = QFrame()
        panel.setObjectName("card")
        panel.setStyleSheet(
            _card_qss()
        )
        panel_lay = QVBoxLayout(panel)
        panel_lay.setContentsMargins(0, 0, 0, 0)
        panel_lay.setSpacing(0)
        page_scroll = self._ops_scroll_area()
        host = QWidget()
        host.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(host)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(9)

        lay.addWidget(SectionTitle("MEDIATEK LOW-LEVEL TOOLING"))
        info = QLabel(
            "MediaTek BROM / Preloader / DA tooling (VID 0e8d). Needs a matching "
            "DA + scatter file from the device's firmware."
        )
        info.setStyleSheet(f"color:{C['dim']}; font-size:11px;")
        info.setWordWrap(True)
        lay.addWidget(info)

        detect_row = QHBoxLayout()
        self.mtk_detect_btn = QPushButton("Detect MediaTek")
        self.mtk_detect_btn.setStyleSheet(_btn_primary())
        self.mtk_detect_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.mtk_detect_btn.clicked.connect(self._mtk_detect)
        detect_row.addWidget(self.mtk_detect_btn)
        self.mtk_status = QLabel("No MediaTek device detected")
        self.mtk_status.setStyleSheet(f"color:{C['dim']}; font-size:12px;")
        detect_row.addWidget(self.mtk_status, 1)
        lay.addLayout(detect_row)

        # --- Combination Flash section (Samsung-style: Scatter + DA + Firmware dir) ---
        combo_panel = QFrame()
        combo_panel.setObjectName("combo")
        combo_panel.setStyleSheet(
            f"QFrame#combo {{ background: qlineargradient(x1:0,y1:0,x2:0,y2:1,"
            f" stop:0 {C['card']}, stop:1 {C['inset']});"
            f" border: 1px solid {C['border']}; border-left: 2px solid {C['border_hi']};"
            f" border-top: 1px solid {C['border_hi']}; border-radius: 9px; }}"
        )
        combo_lay = QVBoxLayout(combo_panel)
        combo_lay.setContentsMargins(14, 10, 14, 14)
        combo_lay.setSpacing(8)

        combo_lay.addWidget(QLabel("COMBINATION FLASH (Scatter + DA + Firmware)"))
        combo_lay.addWidget(
            _risk_banner(
                "This flashes ALL partitions defined in the scatter file. "
                "Wrong DA/scatter/firmware for this model can hard-brick the device."
            )
        )

        # Scatter file row
        scatter_row = QHBoxLayout()
        scatter_lbl = QLabel("Scatter file")
        scatter_lbl.setStyleSheet(f"color:{C['accent_hi']}; font-weight:800; min-width:90px; font-size:11px;")
        scatter_row.addWidget(scatter_lbl)
        self.mtk_scatter_edit = QLineEdit()
        self.mtk_scatter_edit.setPlaceholderText("Select scatter file (.txt)...")
        self.mtk_scatter_edit.setStyleSheet(
            f"QLineEdit {{ background:{C['inset']}; border:1px solid {C['border']};"
            f" border-radius:8px; padding:6px 10px; color:{C['text']};"
            f" selection-background-color:{C['accent']}; }}"
            f" QLineEdit:hover {{ border:1px solid {C['border_hi']}; }}"
            f" QLineEdit:focus {{ border:1px solid {C['accent']}; }}"
        )
        scatter_row.addWidget(self.mtk_scatter_edit, 1)
        scatter_btn = QPushButton("Browse...")
        scatter_btn.setStyleSheet(_btn_ghost())
        scatter_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        scatter_btn.setFixedWidth(90)
        scatter_btn.clicked.connect(
            lambda: self._mtk_browse(self.mtk_scatter_edit, "scatter", "Scatter (*.txt);;All files (*)")
        )
        scatter_row.addWidget(scatter_btn)
        combo_lay.addLayout(scatter_row)

        # DA binary row
        da_row = QHBoxLayout()
        da_lbl = QLabel("DA binary")
        da_lbl.setStyleSheet(f"color:{C['accent_hi']}; font-weight:800; min-width:90px; font-size:11px;")
        da_row.addWidget(da_lbl)
        self.mtk_da_edit = QLineEdit()
        self.mtk_da_edit.setPlaceholderText("Select DA binary (.bin)...")
        self.mtk_da_edit.setStyleSheet(
            f"QLineEdit {{ background:{C['inset']}; border:1px solid {C['border']};"
            f" border-radius:8px; padding:6px 10px; color:{C['text']};"
            f" selection-background-color:{C['accent']}; }}"
            f" QLineEdit:hover {{ border:1px solid {C['border_hi']}; }}"
            f" QLineEdit:focus {{ border:1px solid {C['accent']}; }}"
        )
        da_row.addWidget(self.mtk_da_edit, 1)
        da_btn = QPushButton("Browse...")
        da_btn.setStyleSheet(_btn_ghost())
        da_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        da_btn.setFixedWidth(90)
        da_btn.clicked.connect(
            lambda: self._mtk_browse(self.mtk_da_edit, "da", "DA (*.bin);;All files (*)")
        )
        da_row.addWidget(da_btn)
        combo_lay.addLayout(da_row)

        # Firmware directory row
        fw_row = QHBoxLayout()
        fw_lbl = QLabel("Firmware dir")
        fw_lbl.setStyleSheet(f"color:{C['accent_hi']}; font-weight:800; min-width:90px; font-size:11px;")
        fw_row.addWidget(fw_lbl)
        self.mtk_fw_dir = QLineEdit()
        self.mtk_fw_dir.setPlaceholderText("Firmware directory (partition images)...")
        self.mtk_fw_dir.setStyleSheet(
            f"QLineEdit {{ background:{C['inset']}; border:1px solid {C['border']};"
            f" border-radius:8px; padding:6px 10px; color:{C['text']};"
            f" selection-background-color:{C['accent']}; }}"
            f" QLineEdit:hover {{ border:1px solid {C['border_hi']}; }}"
            f" QLineEdit:focus {{ border:1px solid {C['accent']}; }}"
        )
        fw_row.addWidget(self.mtk_fw_dir, 1)
        fw_btn = QPushButton("Browse...")
        fw_btn.setStyleSheet(_btn_ghost())
        fw_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        fw_btn.setFixedWidth(90)
        fw_btn.clicked.connect(self._mtk_browse_dir)
        fw_row.addWidget(fw_btn)
        combo_lay.addLayout(fw_row)

        # Auth bypass toggle
        auth_row = QHBoxLayout()
        self.mtk_auth_bypass_cb = QCheckBox("Auth bypass (da_auth_bypass mode)")
        self.mtk_auth_bypass_cb.setChecked(False)
        self.mtk_auth_bypass_cb.setToolTip(
            "When ON, uses 'da_auth_bypass' mode to skip preloader auth checks.\n"
            "Required for some secured devices where standard DA auth fails.\n"
            "WARNING: May not work on all chips; can brick if used incorrectly."
        )
        self.mtk_auth_bypass_cb.setStyleSheet(
            f"QCheckBox {{ color:{C['mute']}; font-size:10px; font-weight:600; }}"
            f" QCheckBox::indicator {{ width:14px; height:14px; }}"
        )
        auth_row.addWidget(self.mtk_auth_bypass_cb)
        auth_row.addStretch(1)
        combo_lay.addLayout(auth_row)

        # Flash button
        flash_row = QHBoxLayout()
        flash_row.setSpacing(10)
        self.mtk_flash_combo_btn = QPushButton("Flash Firmware (Combination)")
        self.mtk_flash_combo_btn.setStyleSheet(_btn_primary())
        self.mtk_flash_combo_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.mtk_flash_combo_btn.setToolTip(
            "Flash ALL partitions from the firmware directory using the scatter file"
        )
        self.mtk_flash_combo_btn.clicked.connect(self._mtk_flash)
        self._gate_button(self.mtk_flash_combo_btn, command="mtk-flash")
        flash_row.addWidget(self.mtk_flash_combo_btn)
        self.mtk_check_combo_btn = QPushButton("Check Scatter")
        self.mtk_check_combo_btn.setStyleSheet(_btn_ghost())
        self.mtk_check_combo_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.mtk_check_combo_btn.setToolTip(
            "Validate the scatter file and firmware directory without flashing"
        )
        self.mtk_check_combo_btn.clicked.connect(self._mtk_check_scatter)
        self._gate_button(self.mtk_check_combo_btn, command="mtk-check-scatter")
        flash_row.addWidget(self.mtk_check_combo_btn)
        flash_row.addStretch(1)
        combo_lay.addLayout(flash_row)

        lay.addWidget(combo_panel)

        # --- Advanced Tools section ---
        adv_panel = QFrame()
        adv_panel.setObjectName("adv")
        adv_panel.setStyleSheet(
            f"QFrame#adv {{ background: qlineargradient(x1:0,y1:0,x2:0,y2:1,"
            f" stop:0 {C['card']}, stop:1 {C['inset']});"
            f" border: 1px solid {C['border']}; border-left: 2px solid {C['ok']};"
            f" border-top: 1px solid {C['border_hi']}; border-radius: 9px; }}"
        )
        adv_lay = QVBoxLayout(adv_panel)
        adv_lay.setContentsMargins(14, 10, 14, 14)
        adv_lay.setSpacing(8)

        adv_lay.addWidget(QLabel("ADVANCED TOOLS"))
        adv_lay.addWidget(
            _risk_banner(
                "These write directly to partitions by NAME (no scatter). "
                "A wrong partition/image combo can soft-brick the device."
            )
        )

        # Generate scatter / Dump preloader row
        gen_row = QHBoxLayout()
        gen_btn = QPushButton("Generate Scatter (from device GPT)")
        gen_btn.setStyleSheet(_btn_ghost())
        gen_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        gen_btn.setToolTip(
            "Read the device's own GPT partition table and write an SP Flash\n"
            "Tool scatter file. Samsung firmware never includes a scatter file,\n"
            "so this rebuilds one from the phone. Large data partitions are\n"
            "marked non-downloadable. Needs the DA binary + BROM/preloader."
        )
        gen_btn.clicked.connect(self._mtk_gen_scatter)
        self._gate_button(gen_btn, command="mtk-gpt")
        gen_row.addWidget(gen_btn)
        dump_btn = QPushButton("Dump & Patch Preloader (build DA from phone)")
        dump_btn.setStyleSheet(_btn_ghost())
        dump_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        dump_btn.setToolTip(
            "Dump the phone's own preloader and patch its security checks -\n"
            "the result IS a working Download Agent for this device. This is\n"
            "how you get a DA without downloading one: the phone provides it.\n"
            "The patched file is saved to ~/Downloads/preloader_patched.bin\n"
            "and auto-selected as the DA binary. Needs the phone in BROM."
        )
        dump_btn.clicked.connect(self._mtk_dump_preloader)
        gen_row.addWidget(dump_btn)
        gen_row.addStretch(1)
        adv_lay.addLayout(gen_row)

        # Action buttons
        acts = QVBoxLayout()
        acts.setSpacing(8)
        acts_row1 = QHBoxLayout()
        acts_row1.setSpacing(10)
        for label, slot in (
            ("Backup Partitions", self._mtk_backup),
            ("Get Device Info", self._mtk_info),
            ("List Partitions", self._mtk_list_parts),
        ):
            b = QPushButton(label)
            b.setStyleSheet(_btn_ghost())
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(slot)
            acts_row1.addWidget(b)
        acts_row1.addStretch(1)
        acts.addLayout(acts_row1)
        acts_row2 = QHBoxLayout()
        acts_row2.setSpacing(10)
        for label, slot in (
            ("FRP Bypass", self._mtk_frp),
            ("Enable ADB", self._mtk_adb),
        ):
            b = QPushButton(label)
            b.setStyleSheet(_btn_ghost())
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(slot)
            acts_row2.addWidget(b)
        acts_row2.addStretch(1)
        self.mtk_stop_btn = QPushButton("Stop")
        self.mtk_stop_btn.setEnabled(False)
        self.mtk_stop_btn.setStyleSheet(_btn_danger())
        self.mtk_stop_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.mtk_stop_btn.clicked.connect(self._mtk_stop)
        self.mtk_stop_btn.setToolTip("Cancel the running MTK operation")
        acts_row2.addWidget(self.mtk_stop_btn)
        self.mtk_stop_btn.setVisible(False)
        acts.addLayout(acts_row2)
        acts_row3 = QHBoxLayout()
        acts_row3.setSpacing(10)
        self.mtk_flash_part_btn = QPushButton("Flash Partition (No Scatter)")
        self.mtk_flash_part_btn.setStyleSheet(_btn_ghost())
        self.mtk_flash_part_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.mtk_flash_part_btn.setToolTip(
            "Write one or more partitions by NAME, resolving addresses from "
            "the device GPT. No scatter file required."
        )
        self.mtk_flash_part_btn.clicked.connect(self._mtk_flash_part)
        self._gate_button(self.mtk_flash_part_btn, command="mtk-flash-part")
        acts_row3.addWidget(self.mtk_flash_part_btn)
        frp_gpt_btn = QPushButton("FRP Bypass (No Scatter)")
        frp_gpt_btn.setStyleSheet(_btn_ghost())
        frp_gpt_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        frp_gpt_btn.setToolTip(
            "Clear lock/FRP partitions by NAME from the device GPT. "
            "No scatter file required."
        )
        frp_gpt_btn.clicked.connect(self._mtk_frp_gpt)
        self._gate_button(frp_gpt_btn, command="mtk-frp-gpt")
        acts_row3.addWidget(frp_gpt_btn)
        acts_row3.addStretch(1)
        acts.addLayout(acts_row3)
        adv_lay.addLayout(acts)

        lay.addWidget(adv_panel)

        self.mtk_progress = QProgressBar()
        self.mtk_progress.setRange(0, 1000)
        self.mtk_progress.setValue(0)
        self.mtk_progress.setTextVisible(False)
        self.mtk_progress.setFixedHeight(8)
        self.mtk_progress.setStyleSheet(
            f"QProgressBar {{ background:{C['inset']}; border:none; border-radius:4px; }}"
            f" QProgressBar::chunk {{ background:qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            f" stop:0 {C['grad_a']}, stop:1 {C['grad_b']}); border-radius:4px; }}"
        )
        self.mtk_progress.setVisible(False)
        mtk_ops = self._build_chip_ops_section(
            "mtk",
            {"MTK", "MTK BROM", "ADB", "MTP", "FASTBOOT"},
            self.mtk_stop_btn, self.mtk_progress, self._mtk_reset_ui,
        )
        lay.addWidget(mtk_ops, 1)

        # EXPERIMENTAL — MediaTek IMEI (per-chip, amber, every-run ack)
        _mtk_exp_host = QWidget()
        _mtk_exp_host.setStyleSheet("background: transparent;")
        _mtk_exp_lay = QVBoxLayout(_mtk_exp_host)
        _mtk_exp_lay.setContentsMargins(0, 0, 0, 0)
        _mtk_exp_lay.setSpacing(8)
        _mtk_exp_lay.addWidget(_experimental_banner(
            "EXPERIMENTAL — MediaTek IMEI via NVRAM (nvdata MP0B001_*). Foreign IMEI on a non-owned device may be ILLEGAL. Educational, own device only. Every run requires the checkbox — Change additionally requires “I UNDERSTAND”."))
        self._add_job_flows(_mtk_exp_lay, ["IMEI Repair / Change"], modes={"MTK BROM", "ADB"})
        _mtk_exp_body = QWidget()
        _mtk_exp_body.setStyleSheet("background: transparent;")
        _mtk_exp_body_lay = QVBoxLayout(_mtk_exp_body)
        _mtk_exp_body_lay.setContentsMargins(16, 14, 16, 14)
        _mtk_exp_body_lay.setSpacing(8)
        _mtk_exp_body_lay.addWidget(_mtk_exp_host)
        lay.addWidget(CollapsibleSection("IMEI — EXPERIMENTAL", _mtk_exp_body, accent=C["warn"], collapsed=True))

        lay.addWidget(self.mtk_progress)
        page_scroll.setWidget(host)
        panel_lay.addWidget(page_scroll)
        return panel
