"""FUS / Samsung firmware downloader page builder."""
import os

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..theme import C, _btn_ghost, _btn_primary, _card_qss
from ..widgets import SectionTitle


class FusPageMixin:
    # ----------------------------- Firmware Downloader page --------------
    def _build_fus_page(self):
        panel = QFrame()
        panel.setObjectName("card")
        panel.setStyleSheet(_card_qss())
        panel_lay = QVBoxLayout(panel)
        panel_lay.setContentsMargins(0, 0, 0, 0)
        panel_lay.setSpacing(0)
        page_scroll = self._ops_scroll_area()
        host = QWidget()
        host.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(host)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(12)

        lay.addWidget(SectionTitle("SAMSUNG OFFICIAL FIRMWARE DOWNLOADER (SAMFIRM / FUS)"))
        info = QLabel(
            "Direct FUS client to query Samsung servers, check latest firmware versions, "
            "download encrypted firmware packages in parallel, and auto-decrypt them into "
            "ready-to-flash .tar.md5 archives."
        )
        info.setStyleSheet(f"color:{C['dim']}; font-size:11px;")
        info.setWordWrap(True)
        lay.addWidget(info)

        form_card = QFrame()
        form_card.setStyleSheet(
            f"QFrame {{ background: {C['inset']}; border: 1px solid {C['border']}; border-radius: 10px; padding: 12px; }}"
        )
        form_lay = QVBoxLayout(form_card)
        form_lay.setSpacing(10)

        # Model row
        r1 = QHBoxLayout()
        lbl1 = QLabel("Device Model:")
        lbl1.setStyleSheet(f"color:{C['text']}; font-weight:600;")
        r1.addWidget(lbl1)
        self.fus_model_input = QLineEdit("SM-S918B")
        self.fus_model_input.setStyleSheet(f"background:{C['panel']}; color:{C['text']}; border:1px solid {C['border']}; border-radius:6px; padding:6px;")
        r1.addWidget(self.fus_model_input, 1)

        self.fus_detect_btn = QPushButton("🔍 Detect Connected Device")
        self.fus_detect_btn.setStyleSheet(_btn_ghost())
        self.fus_detect_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.fus_detect_btn.clicked.connect(self._fus_detect_device)
        self._gate_button(self.fus_detect_btn, command="adb_shell")
        r1.addWidget(self.fus_detect_btn)
        
        lbl_reg = QLabel("Region:")
        lbl_reg.setStyleSheet(f"color:{C['text']}; font-weight:600;")
        r1.addWidget(lbl_reg)
        self.fus_region_input = QLineEdit("EUX")
        self.fus_region_input.setStyleSheet(f"background:{C['panel']}; color:{C['text']}; border:1px solid {C['border']}; border-radius:6px; padding:6px;")
        self.fus_region_input.setMaximumWidth(100)
        r1.addWidget(self.fus_region_input)
        form_lay.addLayout(r1)

        # Version row
        r2 = QHBoxLayout()
        lbl2 = QLabel("Firmware Version:")
        lbl2.setStyleSheet(f"color:{C['text']}; font-weight:600;")
        r2.addWidget(lbl2)
        self.fus_version_input = QLineEdit()
        self.fus_version_input.setPlaceholderText("e.g. S918BXXU3BWCV/S918BOXM3BWCV/S918BXXU3BWCV (or click Check Version)")
        self.fus_version_input.setStyleSheet(f"background:{C['panel']}; color:{C['text']}; border:1px solid {C['border']}; border-radius:6px; padding:6px;")
        r2.addWidget(self.fus_version_input, 1)

        self.fus_check_btn = QPushButton("Check Version")
        self.fus_check_btn.setStyleSheet(_btn_primary())
        self.fus_check_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.fus_check_btn.clicked.connect(self._fus_check_version)
        r2.addWidget(self.fus_check_btn)

        self.fus_list_btn = QPushButton("List All Versions")
        self.fus_list_btn.setStyleSheet(_btn_ghost())
        self.fus_list_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.fus_list_btn.clicked.connect(self._fus_list_versions)
        r2.addWidget(self.fus_list_btn)
        form_lay.addLayout(r2)

        # Output dir row
        r3 = QHBoxLayout()
        lbl3 = QLabel("Output Directory:")
        lbl3.setStyleSheet(f"color:{C['text']}; font-weight:600;")
        r3.addWidget(lbl3)
        self.fus_out_input = QLineEdit(os.path.expanduser("~/brilliant/cache"))
        self.fus_out_input.setStyleSheet(f"background:{C['panel']}; color:{C['text']}; border:1px solid {C['border']}; border-radius:6px; padding:6px;")
        r3.addWidget(self.fus_out_input, 1)
        form_lay.addLayout(r3)

        lay.addWidget(form_card)

        # SamFW-style firmware details card: shows the exact firmware the
        # connected device needs. Auto-filled by Detect / Check Version.
        details_card = QFrame()
        details_card.setStyleSheet(
            f"QFrame {{ background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 {C['card']}, stop:1 {C['inset']});"
            f" border: 1px solid {C['border']}; border-left: 3px solid {C['accent']}; border-radius: 10px; }}"
        )
        details_lay = QVBoxLayout(details_card)
        details_lay.setContentsMargins(12, 10, 12, 10)
        details_lay.setSpacing(6)
        details_title = QLabel("📋 FIRMWARE FOR THIS DEVICE")
        details_title.setStyleSheet(f"color:{C['accent_hi']}; font-size:11px; font-weight:800; letter-spacing:1px;")
        details_lay.addWidget(details_title)
        details_grid = QGridLayout()
        details_grid.setContentsMargins(0, 0, 0, 0)
        details_grid.setHorizontalSpacing(12)
        details_grid.setVerticalSpacing(3)
        self.fus_detail_vals = {}
        for _row, (_dkey, _dlabel) in enumerate((
            ("model", "Model"), ("region", "Region / CSC"),
            ("pda", "PDA (AP)"), ("csc_ver", "CSC"), ("cp", "Modem (CP)"),
            ("size", "Size"), ("file", "File"),
        )):
            _k = QLabel(_dlabel + ":")
            _k.setStyleSheet(f"color:{C['dim']}; font-size:11px; font-weight:600;")
            _v = QLabel("—")
            _v.setStyleSheet(f"color:{C['text']}; font-size:11px; font-weight:700; font-family:'Consolas','Monaco',monospace;")
            _v.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            _v.setWordWrap(True)
            details_grid.addWidget(_k, _row, 0)
            details_grid.addWidget(_v, _row, 1)
            self.fus_detail_vals[_dkey] = _v
        details_grid.setColumnStretch(1, 1)
        details_lay.addLayout(details_grid)
        lay.addWidget(details_card)

        # Actions row
        act_row = QHBoxLayout()
        self.fus_download_btn = QPushButton("⬇ Download & Decrypt Firmware")
        self.fus_download_btn.setStyleSheet(_btn_primary())
        self.fus_download_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.fus_download_btn.setFixedHeight(38)
        self.fus_download_btn.clicked.connect(self._fus_download)
        act_row.addWidget(self.fus_download_btn)

        self.fus_load_ap_btn = QPushButton("📂 Load into AP Slot")
        self.fus_load_ap_btn.setStyleSheet(_btn_ghost())
        self.fus_load_ap_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.fus_load_ap_btn.setFixedHeight(38)
        self.fus_load_ap_btn.clicked.connect(self._fus_load_into_ap)
        act_row.addWidget(self.fus_load_ap_btn)
        lay.addLayout(act_row)

        # Progress bar
        self.fus_progress = QProgressBar()
        self.fus_progress.setRange(0, 100)
        self.fus_progress.setValue(0)
        self.fus_progress.setStyleSheet(f"QProgressBar {{ background:{C['inset']}; border:1px solid {C['border']}; border-radius:5px; text-align:center; color:{C['text']}; }} QProgressBar::chunk {{ background:{C['accent']}; border-radius:4px; }}")
        lay.addWidget(self.fus_progress)

        # Status label
        self.fus_status_lbl = QLabel("Ready.")
        self.fus_status_lbl.setStyleSheet(f"color:{C['dim']}; font-size:12px; font-weight:600;")
        lay.addWidget(self.fus_status_lbl)

        # Other brand resources card
        res_card = QFrame()
        res_card.setStyleSheet(
            f"QFrame {{ background: {C['inset']}; border: 1px solid {C['border']}; border-radius: 10px; padding: 12px; }}"
        )
        res_lay = QVBoxLayout(res_card)
        res_lay.setSpacing(6)
        
        res_title = QLabel("🌐 Other Brand Firmware & Loader Repositories (Reference)")
        res_title.setStyleSheet(f"color:{C['text']}; font-weight:700; font-size:12px;")
        res_lay.addWidget(res_title)

        res_info = QLabel(
            "• <b>MediaTek (MTK) Scatter / DA:</b> Check Hovatek & Needrom for scatter files and signed Download Agents.<br>"
            "• <b>Qualcomm EDL Firehose:</b> Use <i>bkerler/Firehose</i> on GitHub for open EDL programmer loaders.<br>"
            "• <b>UNISOC / Spreadtrum (SPD):</b> Stock PAC firmwares contain FDL1/FDL2 binaries required for BSL flashing."
        )
        res_info.setStyleSheet(f"color:{C['dim']}; font-size:11px;")
        res_info.setWordWrap(True)
        res_lay.addWidget(res_info)
        lay.addWidget(res_card)

        host.setLayout(lay)
        page_scroll.setWidget(host)
        panel_lay.addWidget(page_scroll)
        return panel
