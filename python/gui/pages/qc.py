"""Qualcomm (EDL / Firehose) tools page builder."""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ..common import _experimental_banner, _risk_banner
from ..theme import C, _btn_danger, _btn_ghost, _btn_primary, _card_qss
from ..widgets import CollapsibleSection, SectionTitle


class QcPageMixin:
    # ----------------------------- Qualcomm page --------------------------
    def _build_qc_page(self):
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

        lay.addWidget(SectionTitle("QUALCOMM EDL / SAHARA / FIREHOSE"))
        info = QLabel(
            "Qualcomm Emergency Download (EDL) tooling. Requires the device in EDL "
            "mode (VID 05c6) plus a firehose programmer and rawprogram XML."
        )
        info.setStyleSheet(f"color:{C['dim']}; font-size:11px;")
        info.setWordWrap(True)
        lay.addWidget(info)

        det_row = QHBoxLayout()
        self.qc_detect_btn = QPushButton("Detect Qualcomm")
        self.qc_detect_btn.setStyleSheet(_btn_primary())
        self.qc_detect_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.qc_detect_btn.clicked.connect(self._qc_detect)
        det_row.addWidget(self.qc_detect_btn)
        self.qc_status = QLabel("No Qualcomm EDL device detected")
        self.qc_status.setStyleSheet(f"color:{C['dim']}; font-size:12px;")
        det_row.addWidget(self.qc_status, 1)
        lay.addLayout(det_row)

        self.qc_files = {}
        for name, lbl, flt in (
            ("prog", "Programmer (.mbn)", "Programmer (*.mbn *.elf);;All files (*)"),
            ("xml", "Rawprogram XML", "XML (*.xml);;All files (*)"),
        ):
            row = QHBoxLayout()
            lab = QLabel(lbl)
            lab.setStyleSheet(f"color:{C['dim']}; font-weight:600; min-width:120px;")
            edit = QLineEdit()
            edit.setPlaceholderText(f"Select {lbl.lower()}...")
            edit.setStyleSheet(
                f"QLineEdit {{ background:{C['inset']}; border:1px solid {C['border']};"
                f" border-radius:8px; padding:6px 10px; color:{C['text']};"
                f" selection-background-color:{C['accent']}; }}"
                f" QLineEdit:hover {{ border:1px solid {C['border_hi']}; }}"
                f" QLineEdit:focus {{ border:1px solid {C['accent']}; }}"
            )
            btn = QPushButton("Browse...")
            btn.setStyleSheet(_btn_ghost())
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedWidth(90)
            btn.clicked.connect(
                lambda _=False, e=edit, n=name, f=flt: self._qc_browse(e, n, f)
            )
            row.addWidget(lab)
            row.addWidget(edit, 1)
            row.addWidget(btn)
            lay.addLayout(row)
            self.qc_files[name] = edit

        acts = QVBoxLayout()
        acts.setSpacing(8)
        acts_row1 = QHBoxLayout()
        acts_row1.setSpacing(10)
        for label, slot in (
            ("Flash via Firehose", self._qc_flash),
            ("Backup Partitions", self._qc_backup),
            ("Get Device Info", self._qc_info),
        ):
            b = QPushButton(label)
            b.setStyleSheet(_btn_ghost())
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(slot)
            self._gate_button(b, command={
                "Flash via Firehose": "qcom-flash",
                "Backup Partitions": "qcom-backup",
                "Get Device Info": "qcom-info",
            }.get(label))
            acts_row1.addWidget(b)
        acts_row1.addStretch(1)
        acts.addLayout(acts_row1)
        acts_row2 = QHBoxLayout()
        acts_row2.setSpacing(10)
        for label, slot in (
            ("FRP Reset", self._qc_frp_reset),
            ("Enable ADB", self._qc_adb),
        ):
            b = QPushButton(label)
            b.setStyleSheet(_btn_ghost())
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(slot)
            self._gate_button(b, command={
                "FRP Reset": "qcom-frp-reset",
                "Enable ADB": "adb_shell",
            }.get(label))
            acts_row2.addWidget(b)
        acts_row2.addStretch(1)
        self.qc_stop_btn = QPushButton("Stop")
        self.qc_stop_btn.setEnabled(False)
        self.qc_stop_btn.setStyleSheet(_btn_danger())
        self.qc_stop_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.qc_stop_btn.clicked.connect(self._qc_stop)
        self.qc_stop_btn.setToolTip("Cancel the running Qualcomm operation")
        acts_row2.addWidget(self.qc_stop_btn)
        self.qc_stop_btn.setVisible(False)
        acts.addLayout(acts_row2)
        lay.addLayout(acts)

        self.qc_fw_dir = QLineEdit()
        self.qc_fw_dir.setPlaceholderText("Firmware directory (partition images)...")
        self.qc_fw_dir.setStyleSheet(
            f"QLineEdit {{ background:{C['inset']}; border:1px solid {C['border']};"
            f" border-radius:8px; padding:6px 10px; color:{C['text']};"
            f" selection-background-color:{C['accent']}; }}"
            f" QLineEdit:hover {{ border:1px solid {C['border_hi']}; }}"
            f" QLineEdit:focus {{ border:1px solid {C['accent']}; }}"
        )
        fw_row = QHBoxLayout()
        fw_row.addWidget(QLabel("Firmware dir"), 0)
        fw_row.addWidget(self.qc_fw_dir, 1)
        fw_btn = QPushButton("Browse...")
        fw_btn.setStyleSheet(_btn_ghost())
        fw_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        fw_btn.clicked.connect(self._qc_browse_dir)
        fw_btn.setFixedWidth(90)
        fw_row.addWidget(fw_btn)
        lay.addLayout(fw_row)
        lay.addWidget(
            _risk_banner(
                "Qualcomm firehose flashing writes the whole device. The "
                "programmer must match your exact SoC - a mismatch can hard-brick."
            )
        )

        self.qc_progress = QProgressBar()
        self.qc_progress.setRange(0, 1000)
        self.qc_progress.setValue(0)
        self.qc_progress.setTextVisible(False)
        self.qc_progress.setFixedHeight(8)
        self.qc_progress.setStyleSheet(
            f"QProgressBar {{ background:{C['inset']}; border:none; border-radius:4px; }}"
            f" QProgressBar::chunk {{ background:qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            f" stop:0 {C['grad_a']}, stop:1 {C['grad_b']}); border-radius:4px; }}"
        )
        self.qc_progress.setVisible(False)

        # --- Fastboot partition tools (not covered by the job/flow maps) ---
        fb_body = QWidget()
        fb_body.setStyleSheet("background: transparent;")
        fb_lay = QVBoxLayout(fb_body)
        fb_lay.setContentsMargins(0, 0, 0, 0)
        fb_lay.setSpacing(8)

        fb_row = QHBoxLayout()
        fb_row.setSpacing(6)
        fb_part = QLineEdit()
        fb_part.setPlaceholderText("Partition (e.g. boot, system, super)")
        fb_part.setMinimumWidth(80)
        fb_part.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        fb_part.setStyleSheet(f"QLineEdit {{ background: {C['inset']}; border: 1px solid {C['border']}; border-radius: 6px; padding: 5px 8px; color: {C['text']}; selection-background-color: {C['accent']}; }} QLineEdit:hover {{ border: 1px solid {C['border_hi']}; }} QLineEdit:focus {{ border: 1px solid {C['accent']}; }}")
        fb_row.addWidget(fb_part, 1)
        fb_img = QLineEdit()
        fb_img.setPlaceholderText("Image file (.img / .tar)")
        fb_img.setMinimumWidth(80)
        fb_img.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        fb_img.setStyleSheet(f"QLineEdit {{ background: {C['inset']}; border: 1px solid {C['border']}; border-radius: 6px; padding: 5px 8px; color: {C['text']}; selection-background-color: {C['accent']}; }} QLineEdit:hover {{ border: 1px solid {C['border_hi']}; }} QLineEdit:focus {{ border: 1px solid {C['accent']}; }}")
        fb_row.addWidget(fb_img, 1)
        fb_browse = QPushButton("Browse...")
        fb_browse.setStyleSheet(_btn_ghost())
        fb_browse.setCursor(Qt.CursorShape.PointingHandCursor)
        fb_browse.setFixedWidth(80)
        fb_browse.clicked.connect(lambda: self._qc_browse(fb_img, "fastboot image", "Images (*.img *.img.gz *.tar);;All files (*)"))
        fb_row.addWidget(fb_browse)
        fb_lay.addLayout(fb_row)

        def _fb_run(method, label, tooltip):
            btn = QPushButton(label)
            btn.setStyleSheet(_btn_ghost())
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setToolTip(tooltip)
            btn.clicked.connect(
                lambda _=False, m=method, n=label: self._qc_fastboot_flow(
                    m, n, fb_part, fb_img
                )
            )
            return btn

        fb_btns = QHBoxLayout()
        fb_btns.setSpacing(6)
        fb_btns.addWidget(_fb_run("fastboot_flash", "Flash", "fastboot flash <partition> <image> (bootloader must be unlocked)"))
        fb_btns.addWidget(_fb_run("fastboot_format", "Format", "fastboot format <partition> (ext4/f2fs)"))
        fb_btns.addWidget(_fb_run("fastboot_lock", "Relock", "fastboot flashing lock / oem lock (re-lock the bootloader)"))
        fb_btns.addWidget(_fb_run("fastboot_set_active", "Set active", "fastboot set_active a/b - choose the boot slot"))
        fb_btns.addStretch(1)
        fb_lay.addLayout(fb_btns)

        fb_btns2 = QHBoxLayout()
        fb_btns2.setSpacing(6)
        fb_btns2.addWidget(_fb_run("fastboot_getvar", "Getvar", "fastboot getvar all - dump device variables"))
        fb_btns2.addWidget(_fb_run("fastboot_oem", "OEM", "fastboot oem <cmd> (set FASTBOOT_OEM, default device-info)"))
        fb_btns2.addStretch(1)
        fb_lay.addLayout(fb_btns2)

        fb_sec = CollapsibleSection(
            "FASTBOOT TOOLS", fb_body, accent=C["accent"], collapsed=True
        )
        lay.addWidget(fb_sec)

        qc_ops = self._build_chip_ops_section(
            "qc",
            {"EDL", "FASTBOOT", "ADB", "MTP"},
            self.qc_stop_btn, self.qc_progress, self._qc_reset_ui,
        )
        lay.addWidget(qc_ops, 1)

        # EXPERIMENTAL — Qualcomm QCN + IMEI (per-chip, amber, every-run ack)
        _qc_exp_host = QWidget()
        _qc_exp_host.setStyleSheet("background: transparent;")
        _qc_exp_lay = QVBoxLayout(_qc_exp_host)
        _qc_exp_lay.setContentsMargins(0, 0, 0, 0)
        _qc_exp_lay.setSpacing(8)
        _qc_exp_lay.addWidget(_experimental_banner(
            "EXPERIMENTAL — QCN/IMEI writes modem NV (NV 550/682, sec.dat). Foreign IMEI or non-owned device may be ILLEGAL (US 18 USC 1029 etc.) and can kill cellular. Educational, own device only. Every run requires the checkbox — IMEI Change additionally requires typing “I UNDERSTAND”."))
        self._add_job_flows(_qc_exp_lay, ["QCN / Modem", "IMEI Repair / Change"], modes={"EDL", "ADB"})
        _qc_exp_body = QWidget()
        _qc_exp_body.setStyleSheet("background: transparent;")
        _qc_exp_body_lay = QVBoxLayout(_qc_exp_body)
        _qc_exp_body_lay.setContentsMargins(16, 14, 16, 14)
        _qc_exp_body_lay.setSpacing(8)
        _qc_exp_body_lay.addWidget(_qc_exp_host)
        lay.addWidget(CollapsibleSection("QCN / IMEI — EXPERIMENTAL", _qc_exp_body, accent=C["warn"], collapsed=True))

        lay.addWidget(self.qc_progress)
        page_scroll.setWidget(host)
        panel_lay.addWidget(page_scroll)
        return panel
