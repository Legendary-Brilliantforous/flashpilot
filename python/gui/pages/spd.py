"""SPD / UNISOC (Spreadtrum BSL) tools page builder."""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
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
from ..widgets import CollapsibleSection, FlowLayout, SectionTitle


class SpdPageMixin:
    # ----------------------------- SPD / UNISOC page ----------------------
    def _build_spd_page(self):
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
        lay.setSpacing(9)

        lay.addWidget(SectionTitle("SPREADTRUM / UNISOC (SPD) DOWNLOAD"))
        info = QLabel(
            "Feature-phone & SoC BSL download tooling. Requires the device in "
            "download mode (1782:4d00) plus FDL1/FDL2 binaries + base addresses."
        )
        info.setStyleSheet(f"color:{C['dim']}; font-size:11px;")
        info.setWordWrap(True)
        lay.addWidget(info)

        det_row = QHBoxLayout()
        self.spd_detect_btn = QPushButton("Detect SPD")
        self.spd_detect_btn.setStyleSheet(_btn_primary())
        self.spd_detect_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.spd_detect_btn.clicked.connect(self._spd_detect)
        det_row.addWidget(self.spd_detect_btn)
        self.spd_brom_watch_btn = QPushButton("👁 Watch for BROM (3 min)")
        self.spd_brom_watch_btn.setStyleSheet(_btn_ghost())
        self.spd_brom_watch_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.spd_brom_watch_btn.setToolTip(
            "Unisoc BROM (1782:4d00) only appears for ~2s when a powered-off\n"
            "phone is plugged with the boot key held. This watcher polls every\n"
            "400ms and auto-fills the target when it catches the window.\n"
            "Steps: power off → hold VOL- → plug USB while watching."
        )
        self.spd_brom_watch_btn.clicked.connect(self._spd_brom_watch)
        det_row.addWidget(self.spd_brom_watch_btn)
        self.spd_status = QLabel("No SPD download device detected")
        self.spd_status.setStyleSheet(f"color:{C['dim']}; font-size:12px;")
        det_row.addWidget(self.spd_status, 1)
        lay.addLayout(det_row)

        # ——— Immediate BROM Factory Reset (FIRST) ———
        brom_box = QFrame()
        brom_box.setObjectName("brombox")
        brom_box.setStyleSheet(
            f"QFrame#brombox {{ background: qlineargradient(x1:0,y1:0,x2:0,y2:1,"
            f" stop:0 {C['card']}, stop:1 {C['inset']});"
            f" border: 1px solid {C['border']}; border-left: 3px solid #a78bfa;"
            f" border-radius: 10px; }}"
        )
        brom_lay = QVBoxLayout(brom_box)
        brom_lay.setContentsMargins(12, 10, 12, 10)
        brom_lay.setSpacing(6)
        brom_title = QLabel("⚡ BROM FACTORY RESET — IMMEDIATE (FIRST)")
        brom_title.setStyleSheet(f"color:#c4b5fd; font-weight:800; font-size:11px; letter-spacing:0.6px;")
        brom_lay.addWidget(brom_title)
        brom_info = QLabel(
            "One-click wipe for SPD BROM (1782:4d00). When caught, immediately erases "
            "userdata/cache/frp via BSL — no firmware flash. Works BROM-only without FDL; "
            "if FDL1/FDL2 are selected below they are used for full userdata wipe."
        )
        brom_info.setWordWrap(True)
        brom_info.setStyleSheet(f"color:{C['dim']}; font-size:11px;")
        brom_lay.addWidget(brom_info)
        brom_btn_row = QHBoxLayout()
        brom_btn_row.setSpacing(10)
        self.spd_brom_factory_btn = QPushButton("⚡ Factory Reset (BROM) — 1-Click")
        self.spd_brom_factory_btn.setStyleSheet(_btn_primary())
        self.spd_brom_factory_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.spd_brom_factory_btn.setToolTip(
            "Immediate factory reset from BROM. Auto-catches 1782:4d00 window (~2s),\n"
            "erases userdata/cache/frp via BROM-only (no FDL needed) or with FDL1/FDL2\n"
            "for full wipe. Do this FIRST before any flash. If FDLs are set they must match chipset."
        )
        self.spd_brom_factory_btn.clicked.connect(self._spd_brom_factory_reset)
        self._gate_button(self.spd_brom_factory_btn, command="spd-format")
        brom_btn_row.addWidget(self.spd_brom_factory_btn)
        self.spd_brom_auto_check = QCheckBox("Auto-run when BROM caught")
        self.spd_brom_auto_check.setChecked(False)
        self.spd_brom_auto_check.setStyleSheet(f"QCheckBox {{ color:{C['dim']}; font-size:11px; }}")
        self.spd_brom_auto_check.setToolTip("If checked, Format will fire automatically the instant BROM is caught — no extra click.")
        brom_btn_row.addWidget(self.spd_brom_auto_check)
        brom_btn_row.addStretch(1)
        brom_lay.addLayout(brom_btn_row)
        brom_lay.addWidget(_risk_banner(
            "BROM factory reset erases user data (password/PIN/FRP). No FDL needed for basic wipe; "
            "if FDLs are set, mismatch = hard-brick. This is intentionally the FIRST operation for SPD."
        ))
        lay.addWidget(brom_box)

        self.spd_files = {}
        for name, lbl, flt in (
            ("fdl1", "FDL1 binary", "FDL (*.bin);;All files (*)"),
            ("fdl2", "FDL2 binary", "FDL (*.bin);;All files (*)"),
        ):
            row = QHBoxLayout()
            lab = QLabel(lbl)
            lab.setStyleSheet(f"color:{C['dim']}; font-weight:600; min-width:90px;")
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
                lambda _=False, e=edit, n=name, f=flt: self._spd_browse(e, n, f)
            )
            row.addWidget(lab)
            row.addWidget(edit, 1)
            row.addWidget(btn)
            lay.addLayout(row)
            self.spd_files[name] = edit

        # FDL base addresses (hex)
        base_row = QHBoxLayout()
        self.spd_fdl1_addr = QLineEdit("0x40004000")
        self.spd_fdl1_addr.setToolTip("FDL1 base address for your chip")
        self.spd_fdl2_addr = QLineEdit("0x14000000")
        self.spd_fdl2_addr.setToolTip("FDL2 base address for your chip")
        for edit in (self.spd_fdl1_addr, self.spd_fdl2_addr):
            edit.setStyleSheet(
                f"QLineEdit {{ background:{C['inset']}; border:1px solid {C['border']};"
                f" border-radius:8px; padding:6px 10px; color:{C['text']};"
                f" selection-background-color:{C['accent']}; }}"
                f" QLineEdit:hover {{ border:1px solid {C['border_hi']}; }}"
            )
        base_row.addWidget(QLabel("FDL1 base"))
        base_row.addWidget(self.spd_fdl1_addr, 1)
        base_row.addWidget(QLabel("FDL2 base"))
        base_row.addWidget(self.spd_fdl2_addr, 1)
        lay.addLayout(base_row)

        acts = QVBoxLayout()
        acts.setSpacing(8)
        acts_row1 = QHBoxLayout()
        acts_row1.setSpacing(10)
        for label, slot in (
            ("Get Device Info", self._spd_info),
            ("Flash Firmware", self._spd_flash),
            ("Backup Partitions", self._spd_backup),
        ):
            b = QPushButton(label)
            b.setStyleSheet(_btn_ghost())
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(slot)
            self._gate_button(b, command={
                "Get Device Info": "spd-info",
                "Flash Firmware": "spd-flash",
                "Backup Partitions": "spd-backup",
            }.get(label))
            acts_row1.addWidget(b)
        acts_row1.addStretch(1)
        acts.addLayout(acts_row1)
        acts_row2 = QHBoxLayout()
        acts_row2.setSpacing(10)
        for label, slot in (
            ("Format / Unlock", self._spd_format),
            ("FRP Reset", self._spd_frp),
        ):
            b = QPushButton(label)
            b.setStyleSheet(_btn_ghost())
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(slot)
            self._gate_button(b, command={
                "Format / Unlock": "spd-format",
                "FRP Reset": "spd-frp",
            }.get(label))
            acts_row2.addWidget(b)
        acts_row2.addStretch(1)
        self.spd_stop_btn = QPushButton("Stop")
        self.spd_stop_btn.setEnabled(False)
        self.spd_stop_btn.setStyleSheet(_btn_danger())
        self.spd_stop_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.spd_stop_btn.clicked.connect(self._spd_stop)
        self.spd_stop_btn.setToolTip("Cancel the running SPD operation")
        acts_row2.addWidget(self.spd_stop_btn)
        self.spd_stop_btn.setVisible(False)
        acts.addLayout(acts_row2)

        # Reboot targets row (commercial-style: Recovery / Fastboot / Normal)
        acts_row3 = QHBoxLayout()
        acts_row3.setSpacing(10)
        for label, mode in (
            ("Reboot → Recovery", "recovery"),
            ("Reboot → Fastboot", "fastboot"),
            ("Reset (Normal)", "normal"),
        ):
            b = QPushButton(label)
            b.setStyleSheet(_btn_ghost())
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setToolTip(
                f"Reboot the download-mode Unisoc device into {mode}.\n"
                + ("Writes 'boot-recovery' to the misc BCB via FDL2, then resets.\n"
                   if mode != "normal" else
                   "Plain BSL NORMAL_RESET - works from bare BROM, no FDLs.\n")
                + ("Needs FDL1+FDL2." if mode != "normal" else "")
            )
            b.clicked.connect(lambda _=False, m=mode: self._spd_boot(m))
            self._gate_button(b, command="spd-boot")
            acts_row3.addWidget(b)
        acts_row3.addStretch(1)
        acts.addLayout(acts_row3)

        # --- Advanced: magic64 signature-preserving packer (fused SoCs) ---
        adv_box = QFrame()
        adv_box.setObjectName("spdadv")
        adv_box.setStyleSheet(
            f"QFrame#spdadv {{ background: qlineargradient(x1:0,y1:0,x2:0,y2:1,"
            f" stop:0 {C['card']}, stop:1 {C['inset']});"
            f" border: 1px solid {C['border']}; border-left: 2px solid {C['warn']};"
            f" border-radius: 9px; }}"
        )
        adv_lay = QVBoxLayout(adv_box)
        adv_lay.setContentsMargins(12, 8, 12, 10)
        adv_lay.setSpacing(6)

        _adv_title = QLabel("MAGIC64 — SIGNATURE-PRESERVING RUNTIME PATCH (FUSED SoC)")
        _adv_title.setStyleSheet(f"color:{C['accent_hi']}; font-weight:800; font-size:11px;")
        adv_lay.addWidget(_adv_title)

        # stock image row
        stock_row = QHBoxLayout()
        stock_lbl = QLabel("Stock image")
        stock_lbl.setStyleSheet(f"color:{C['dim']}; font-weight:600; min-width:90px;")
        stock_row.addWidget(stock_lbl)
        self.spd_magic_stock = QLineEdit()
        self.spd_magic_stock.setPlaceholderText("uboot.img read via Backup Partitions / spd-readback...")
        self.spd_magic_stock.setStyleSheet(
            f"QLineEdit {{ background:{C['inset']}; border:1px solid {C['border']};"
            f" border-radius:8px; padding:6px 10px; color:{C['text']};"
            f" selection-background-color:{C['accent']}; }}"
            f" QLineEdit:hover {{ border:1px solid {C['border_hi']}; }}"
            f" QLineEdit:focus {{ border:1px solid {C['accent']}; }}"
        )
        stock_row.addWidget(self.spd_magic_stock, 1)
        stock_btn = QPushButton("Browse...")
        stock_btn.setStyleSheet(_btn_ghost())
        stock_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        stock_btn.setFixedWidth(90)
        stock_btn.clicked.connect(lambda: self._spd_browse(
            self.spd_magic_stock, "stock image", "Images (*.img *.bin);;All files (*)"))
        stock_row.addWidget(stock_btn)
        adv_lay.addLayout(stock_row)

        # preset checkboxes (UMS9620 silencer pack)
        preset_row = FlowLayout(spacing=6)
        self.spd_magic_presets = {}
        for off, tip in (
            ("0xafe8=0xd503201f", "remove unlock warning + 10s pause"),
            ("0xb2a4=0xd503201f", "remove SKIP VERIFY (UART)"),
            ("0xb2ac=0xd503201f", "remove SKIP VERIFY (screen)"),
            ("0x604c0=0xd503201f", "force lock status = UNLOCKED"),
        ):
            cb = QCheckBox(off.split("=")[0])
            cb.setChecked(False)
            cb.setToolTip(f"{off}  —  {tip}\nWrong offsets corrupt memory at boot.")
            cb.setStyleSheet(f"QCheckBox {{ color:{C['dim']}; font-size:10px; }}")
            cb.toggled.connect(lambda _v, _off=off: self._spd_magic_sync_presets())
            preset_row.addWidget(cb)
            self.spd_magic_presets[off] = cb
        adv_lay.addLayout(preset_row)

        # patches row
        patch_row = QHBoxLayout()
        patch_lbl = QLabel("Patches")
        patch_lbl.setStyleSheet(f"color:{C['dim']}; font-weight:600; min-width:90px;")
        patch_row.addWidget(patch_lbl)
        self.spd_magic_patches = QLineEdit()
        self.spd_magic_patches.setPlaceholderText("off=word; off=word ... e.g. 0xafe8=0xd503201f; 0x604c0=0xd503201f")
        self.spd_magic_patches.setToolTip(
            "Runtime patches applied by the shellcode after the SPL's RSA check\n"
            "passes. Format: hexOffset=hexWord, semicolon-separated.\n"
            "Offsets are RELATIVE TO PAYLOAD START (file offset minus 0x200).\n"
            "Tick presets above or type custom entries here.\n"
            "Wrong offsets corrupt memory at boot - verify in Ghidra first."
        )
        self.spd_magic_patches.setStyleSheet(
            f"QLineEdit {{ background:{C['inset']}; border:1px solid {C['border']};"
            f" border-radius:8px; padding:6px 10px; color:{C['text']};"
            f" selection-background-color:{C['accent']}; }}"
            f" QLineEdit:hover {{ border:1px solid {C['border_hi']}; }}"
            f" QLineEdit:focus {{ border:1px solid {C['accent']}; }}"
        )
        patch_row.addWidget(self.spd_magic_patches, 1)
        adv_lay.addLayout(patch_row)

        # load base row
        lb_row = QHBoxLayout()
        lb_lbl = QLabel("Load base")
        lb_lbl.setStyleSheet(f"color:{C['dim']}; font-weight:600; min-width:90px;")
        lb_row.addWidget(lb_lbl)
        self.spd_magic_load_base = QLineEdit("0xB5000000")
        self.spd_magic_load_base.setToolTip(
            "Payload runtime address (text base). UMS9620 default 0xB5000000\n"
            "= PAC XML image base 0xB4FFFE00 + 0x200 header.\n"
            "Wrong load-base writes patches to random memory at boot."
        )
        self.spd_magic_load_base.setStyleSheet(
            f"QLineEdit {{ background:{C['inset']}; border:1px solid {C['border']};"
            f" border-radius:8px; padding:6px 10px; color:{C['text']}; }}"
        )
        self.spd_magic_load_base.setMaximumWidth(160)
        lb_row.addWidget(self.spd_magic_load_base)
        lb_row.addStretch(1)
        adv_lay.addLayout(lb_row)

        # actions row
        mpb_row = QHBoxLayout()
        self.spd_magic_pack_btn = QPushButton("🪄 Pack (no flash)")
        self.spd_magic_pack_btn.setStyleSheet(_btn_primary())
        self.spd_magic_pack_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.spd_magic_pack_btn.setToolTip(
            "Produce a magic64-packed copy next to the stock image.\n"
            "NEVER flashes anything - review the log then use Flash Firmware\n"
            "with the packed file to deliver it."
        )
        self.spd_magic_pack_btn.clicked.connect(self._spd_magic_pack)
        mpb_row.addWidget(self.spd_magic_pack_btn)

        self.spd_magic_flash_btn = QPushButton("Flash Packed Image")
        self.spd_magic_flash_btn.setStyleSheet(_btn_ghost())
        self.spd_magic_flash_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.spd_magic_flash_btn.setToolTip(
            "Two-step confirmation for the packed output. Refuses unless the\n"
            "packed file exists and ends with _magic.img (safety marker)."
        )
        self.spd_magic_flash_btn.clicked.connect(self._spd_magic_flash)
        self._gate_button(self.spd_magic_flash_btn, command="spd-flash")
        mpb_row.addWidget(self.spd_magic_flash_btn)
        mpb_row.addStretch(1)
        adv_lay.addLayout(mpb_row)

        adv_lay.addWidget(_risk_banner(
            "magic64 keeps the signed payload untouched so the SPL check still "
            "passes - but wrong load-base/offsets corrupt memory AT BOOT. "
            "Always keep the stock image."
        ))
        lay.addWidget(adv_box)

        # --- Enable ADB (boot patch) --------------------------------
        adb_box = QFrame()
        adb_box.setObjectName("spdadb")
        adb_box.setStyleSheet(
            f"QFrame#spdadb {{ background: qlineargradient(x1:0,y1:0,x2:0,y2:1,"
            f" stop:0 {C['card']}, stop:1 {C['inset']});"
            f" border: 1px solid {C['border']}; border-left: 2px solid {C['border_hi']};"
            f" border-radius: 9px; }}"
        )
        adb_lay = QVBoxLayout(adb_box)
        adb_lay.setContentsMargins(12, 8, 12, 10)
        adb_lay.setSpacing(6)
        adb_lay.addWidget(QLabel("ENABLE ADB — BOOT PATCH (NO ROOT NEEDED)"))
        adb_info = QLabel(
            "Reads boot_a via BROM/FDL, patches default.prop (ro.adb.secure=0, "
            "persist.sys.usb.config+=adb) cpio+gunzip round-trip, flashes it "
            "back and reboots. Stock boot saved to ~/flashpilot/backups/ first."
        )
        adb_info.setWordWrap(True)
        adb_info.setStyleSheet(f"color:{C['dim']}; font-size:11px;")
        adb_lay.addWidget(adb_info)
        adb_row = QHBoxLayout()
        self.spd_adb_part = QComboBox()
        self.spd_adb_part.addItems(["boot_a", "boot_b", "boot"])
        self.spd_adb_part.setCurrentText("boot_a")
        self.spd_adb_part.setMaximumWidth(110)
        self.spd_adb_part.setStyleSheet(
            f"QComboBox {{ background:{C['inset']}; border:1px solid {C['border']};"
            f" border-radius:8px; padding:6px; color:{C['text']}; }}"
        )
        adb_row.addWidget(QLabel("Part"))
        adb_row.addWidget(self.spd_adb_part)
        adb_row.addStretch(1)
        self.spd_adb_btn = QPushButton("🔓 Enable ADB (boot patch)")
        self.spd_adb_btn.setStyleSheet(_btn_primary())
        self.spd_adb_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.spd_adb_btn.clicked.connect(self._spd_enable_adb)
        self._gate_button(self.spd_adb_btn, command="spd-flash")
        adb_row.addWidget(self.spd_adb_btn)
        adb_lay.addLayout(adb_row)
        adb_lay.addWidget(_risk_banner(
            "Uses the same FDL pair as other SPD ops. Boot size must allow the "
            "patched ramdisk — larger props grow the cpio; always review the log."
        ))
        lay.addWidget(adb_box)
        lay.addLayout(acts)

        self.spd_fw_dir = QLineEdit()
        self.spd_fw_dir.setPlaceholderText("Firmware directory (partition images)...")
        self.spd_fw_dir.setStyleSheet(
            f"QLineEdit {{ background:{C['inset']}; border:1px solid {C['border']};"
            f" border-radius:8px; padding:6px 10px; color:{C['text']};"
            f" selection-background-color:{C['accent']}; }}"
            f" QLineEdit:hover {{ border:1px solid {C['border_hi']}; }}"
        )
        fw_row = QHBoxLayout()
        fw_row.addWidget(QLabel("Firmware dir"), 0)
        fw_row.addWidget(self.spd_fw_dir, 1)
        fw_btn = QPushButton("Browse...")
        fw_btn.setStyleSheet(_btn_ghost())
        fw_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        fw_btn.clicked.connect(self._spd_browse_dir)
        fw_btn.setFixedWidth(90)
        fw_row.addWidget(fw_btn)
        lay.addLayout(fw_row)
        lay.addWidget(
            _risk_banner(
                "SPD flashing and factory format write directly to the chip. "
                "The FDL binaries and base addresses must match your exact "
                "chipset - a wrong FDL can hard-brick the device."
            )
        )

        self.spd_progress = QProgressBar()
        self.spd_progress.setRange(0, 1000)
        self.spd_progress.setValue(0)
        self.spd_progress.setTextVisible(False)
        self.spd_progress.setFixedHeight(8)
        self.spd_progress.setStyleSheet(
            f"QProgressBar {{ background:{C['inset']}; border:none; border-radius:4px; }}"
            f" QProgressBar::chunk {{ background:qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            f" stop:0 {C['grad_a']}, stop:1 {C['grad_b']}); border-radius:4px; }}"
        )
        self.spd_progress.setVisible(False)
        spd_ops = self._build_chip_ops_section(
            "spd",
            {"ADB", "MTP", "FASTBOOT", "SPD"},
            self.spd_stop_btn, self.spd_progress, self._spd_reset_ui,
        )
        lay.addWidget(spd_ops, 1)

        # EXPERIMENTAL — SPD/UNISOC IMEI + PAC (per-chip, amber, every-run ack)
        _spd_exp_host = QWidget()
        _spd_exp_host.setStyleSheet("background: transparent;")
        _spd_exp_lay = QVBoxLayout(_spd_exp_host)
        _spd_exp_lay.setContentsMargins(0, 0, 0, 0)
        _spd_exp_lay.setSpacing(8)
        _spd_exp_lay.addWidget(_experimental_banner(
            "EXPERIMENTAL — SPD IMEI via BSL modem-NV. Foreign IMEI on a non-owned device may be ILLEGAL. Educational, own device only. Every run requires the checkbox — Change additionally requires “I UNDERSTAND”."))
        self._add_job_flows(_spd_exp_lay, ["IMEI Repair / Change"], modes={"ADB"})
        _spd_exp_body = QWidget()
        _spd_exp_body.setStyleSheet("background: transparent;")
        _spd_exp_body_lay = QVBoxLayout(_spd_exp_body)
        _spd_exp_body_lay.setContentsMargins(16, 14, 16, 14)
        _spd_exp_body_lay.setSpacing(8)
        _spd_exp_body_lay.addWidget(_spd_exp_host)
        lay.addWidget(CollapsibleSection("IMEI — EXPERIMENTAL", _spd_exp_body, accent=C["warn"], collapsed=True))

        lay.addWidget(self.spd_progress)
        page_scroll.setWidget(host)
        panel_lay.addWidget(page_scroll)
        return panel
