"""Settings page builders (category rail + General / Updates / Appearance /
Tools / About sub-pages).

Split out mechanically from :mod:`python.gui.qt_app`; method bodies are
unchanged. The small ``_settings_box`` / ``_settings_row`` /
``_settings_switch`` helpers stay in the shell, as do the ``_apply_*`` value
handlers these builders connect to.
"""
import os

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ..animations import Motion, _draw_logo
from ..theme import (
    ACCENT_THEMES,
    C,
    _btn_danger,
    _btn_ghost,
    _card_qss,
    _display_version,
    _is_beta_version,
)
from ..widgets import FlowHost, FlowLayout, _SettingsCatButton
from ...core import APP_VERSION, bridge


class SettingsPageMixin:
    # ----------------------------- Settings page --------------------------
    def _build_settings_page(self):
        panel = QFrame()
        panel.setObjectName("card")
        panel.setStyleSheet(
            _card_qss()
        )
        root_lay = QHBoxLayout(panel)
        root_lay.setContentsMargins(0, 0, 0, 0)
        root_lay.setSpacing(0)

        # Left category rail - premium Windows 11 style settings sidebar
        cat = QFrame()
        cat.setStyleSheet(
            f"QFrame {{ background: qlineargradient(x1:0,y1:0,x2:0,y2:1,"
            f" stop:0 rgba(15, 23, 42, 245), stop:1 rgba(2, 6, 23, 245));"
            f" border-right: 1px solid {C['border_hi']}; border-top-left-radius: 14px;"
            f" border-bottom-left-radius: 14px; }}"
        )
        cat.setFixedWidth(180)
        cat_lay = QVBoxLayout(cat)
        cat_lay.setContentsMargins(12, 20, 12, 16)
        cat_lay.setSpacing(6)

        self._settings_pages = QStackedWidget()
        self._settings_pages.setStyleSheet(
            "QStackedWidget { background: transparent; }"
        )
        self._settings_cats = {}

        categories = [
            ("general", "◈", "General",
             self._build_settings_general),
            ("updates", "↻", "Updates",
             self._build_settings_updates),
            ("appearance", "✦", "Appearance",
             self._build_settings_appearance),
            ("tools", "▤", "Tools",
             self._build_settings_tools),
            ("about", "ℹ", "About",
             self._build_settings_about),
        ]
        for key, glyph, label, builder in categories:
            page = builder()
            self._settings_pages.addWidget(page)
            btn = _SettingsCatButton(glyph, label)
            btn.clicked.connect(lambda _=False, k=key: self._switch_settings(k))
            cat_lay.addWidget(btn)
            self._settings_cats[key] = btn

        cat_lay.addStretch(1)
        root_lay.addWidget(cat)
        root_lay.addWidget(self._settings_pages, 1)
        self._switch_settings("general")
        return panel

    def _switch_settings(self, key):
        order = {"general": 0, "updates": 1, "appearance": 2, "tools": 3, "about": 4}
        idx = order.get(key, 0)
        self._settings_pages.setCurrentIndex(idx)
        for k, btn in self._settings_cats.items():
            btn.set_active(k == key)

    # --- General -----------------------------------------------------------
    def _build_settings_general(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(18, 18, 18, 18)
        lay.setSpacing(12)

        bl = self._settings_box("SCAN & BEHAVIOUR", lay)
        self._s_interval = QSpinBox()
        self._s_interval.setRange(1, 30)
        self._s_interval.setSuffix(" s")
        self._s_interval.setValue(int(self.settings.value("scan_interval", 3)))
        self._s_interval.valueChanged.connect(self._apply_scan_interval)
        self._settings_row(
            bl, "USB / ADB auto-scan interval",
            "How often the app re-checks the USB bus for connected devices.",
            self._s_interval,
        )
        self._s_autoscan = self._settings_switch()
        self._s_autoscan.setChecked(
            self.settings.value("autoscan", "true", type=bool)
        )
        self._s_autoscan.toggled.connect(self._apply_autoscan)
        self._settings_row(
            bl, "Auto-scan on startup",
            "Begin monitoring devices immediately when the app opens.",
            self._s_autoscan,
        )
        self._s_toast = self._settings_switch()
        self._s_toast.setChecked(self.settings.value("toasts", "true", type=bool))
        self._s_toast.toggled.connect(self._apply_toasts)
        self._settings_row(
            bl, "Desktop notifications",
            "Show a toast when a device connects or disconnects.",
            self._s_toast,
        )

        bl = self._settings_box("DEFAULT PATHS", lay)
        self._s_dir_row = QHBoxLayout()
        self._s_dir = QLineEdit(
            self.settings.value("default_dir", os.path.expanduser("~/Downloads"))
        )
        self._s_dir.setStyleSheet(
            f"QLineEdit {{ background:{C['inset']}; border:1px solid {C['border']};"
            f" border-radius:8px; padding:6px 10px; color:{C['text']}; }}"
        )
        dir_btn = QPushButton("Browse...")
        dir_btn.setStyleSheet(_btn_ghost())
        dir_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        dir_btn.clicked.connect(self._pick_default_dir)
        self._s_dir_row.addWidget(self._s_dir, 1)
        self._s_dir_row.addWidget(dir_btn)
        bl.addLayout(self._s_dir_row)
        self._s_dir.editingFinished.connect(self._apply_default_dir)

        bl = self._settings_box("FLASHING", lay)
        self._s_clear = self._settings_switch()
        self._s_clear.setChecked(
            self.settings.value("clear_on_run", "false", type=bool)
        )
        self._s_clear.toggled.connect(self._apply_clear_on_run)
        self._settings_row(
            bl, "Clear console before each run",
            "Automatically empty the log when you start an operation.",
            self._s_clear,
        )

        lay.addStretch(1)
        return page

    def _build_settings_updates(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(18, 18, 18, 18)
        lay.setSpacing(12)

        bl = self._settings_box("UPDATES & RELEASES", lay)
        self._auto_update_cb = self._settings_switch()
        self._auto_update_cb.setChecked(
            self.settings.value("auto_update_check", False, type=bool)
        )
        self._auto_update_cb.toggled.connect(lambda on: self.settings.setValue("auto_update_check", on))
        self._settings_row(
            bl, "Auto-check for updates",
            "Automatically check for new versions when FlashPilot starts.",
            self._auto_update_cb,
        )

        self._auto_download_cb = self._settings_switch()
        self._auto_download_cb.setChecked(
            self.settings.value("auto_download_update", False, type=bool)
        )
        self._auto_download_cb.toggled.connect(lambda on: self.settings.setValue("auto_download_update", on))
        self._settings_row(
            bl, "Automatically download updates",
            "Download new updates in the background when available.",
            self._auto_download_cb,
        )

        # Manual check button
        self._check_updates_btn = QPushButton("Check for Updates Now")
        self._check_updates_btn.setStyleSheet(
            f"QPushButton {{ background:{C['accent']}; color:{C['panel']}; padding:8px 16px; border-radius:6px; font-size:12px; font-weight:700; }}"
            f" QPushButton:hover {{ background:{C['card_hover']}; }}"
            f" QPushButton:disabled {{ background:{C['border']}; color:{C['mute']}; }}"
        )
        self._check_updates_btn.setFixedWidth(200)
        self._check_updates_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._check_updates_btn.clicked.connect(self._manual_check_update)
        self._settings_row(
            bl, "Manual version check",
            "Query GitHub releases immediately for updates.",
            self._check_updates_btn,
        )

        # Two-tier light patch (python-only) button
        self._apply_patch_btn = QPushButton("Apply Python Patch…")
        self._apply_patch_btn.setStyleSheet(
            f"QPushButton {{ background:{C['inset']}; color:{C['text']}; padding:8px 16px;"
            f" border:1px solid {C['border']}; border-radius:6px; font-size:12px; font-weight:600; }}"
            f" QPushButton:hover {{ border-color:{C['accent']}; }}"
            f" QPushButton:disabled {{ color:{C['mute']}; }}"
        )
        self._apply_patch_btn.setFixedWidth(200)
        self._apply_patch_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._apply_patch_btn.setToolTip(
            "Tier-1 update: pulls only the python/ tree from GitHub main when\n"
            "no bridge/packaging changes are involved (~200 KB, no full .deb).\n"
            "Requires a restart afterwards."
        )
        self._apply_patch_btn.clicked.connect(self._apply_python_patch_clicked)
        self._settings_row(
            bl, "Light patch (python only)",
            "Fast tier-1 update when only python code changed upstream.",
            self._apply_patch_btn,
        )

        # Beta warning frequency — first_install (default) vs every_boot
        self._beta_every_boot = self._settings_switch()
        self._beta_every_boot.setChecked(
            self.settings.value("beta_warning_mode", "first_install") == "every_boot"
        )
        self._beta_every_boot.toggled.connect(self._apply_beta_warning_mode)
        self._settings_row(
            bl, "Beta warning on every boot",
            "ON shows the beta risk dialog every launch; OFF (default) shows only on first install of each beta version.",
            self._beta_every_boot,
        )
        prev_btn = QPushButton("Preview beta warning")
        prev_btn.setStyleSheet(
            f"QPushButton {{ background:{C['inset']}; color:{C['text']}; padding:8px 16px;"
            f" border:1px solid {C['border']}; border-radius:6px; font-size:12px; font-weight:600; }}"
            f" QPushButton:hover {{ border-color:{C['accent']}; }}"
        )
        prev_btn.setFixedWidth(200)
        prev_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        prev_btn.clicked.connect(lambda: self._show_beta_risk_dialog(
            APP_VERSION, "", force=True))
        self._settings_row(
            bl, "Preview beta warning",
            "Show the full-screen beta risk dialog now (ignores 'accepted' state).",
            prev_btn,
        )

        lay.addStretch(1)
        return page

    # --- Appearance --------------------------------------------------------
    def _build_settings_appearance(self):
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; }")
        host = QWidget()
        host.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(host)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(18)

        # THEME — 10 cards only (no dropdown) — progressively advanced, fit-well
        bl = self._settings_box("THEME — 10 professional accents (click a card)", lay)
        # Hidden combo for back-compat (cards drive it)
        self._s_theme = QComboBox()
        self._s_theme.addItems(list(ACCENT_THEMES))
        self._s_theme.setCurrentText(self.settings.value("theme", "Slate Professional"))
        self._s_theme.currentTextChanged.connect(self._apply_theme)
        self._s_theme.setVisible(False)
        intro = QLabel("Whole-app live — buttons, cards, console, shimmer, cable/ORB recolor instantly. Each next theme is a touch more advanced.")
        intro.setStyleSheet(f"color:{C['dim']}; font-size:11px;")
        intro.setWordWrap(True)
        bl.addWidget(intro)
        # Fit-well wrapping grid: FlowHost delegates heightForWidth so wrap is visible/clickable on small screens
        grid_host = FlowHost()
        grid_host.setStyleSheet("background: transparent;")
        grid = FlowLayout(grid_host, spacing=10)
        grid.setContentsMargins(0, 0, 0, 0)
        for idx, (th, tok) in enumerate(ACCENT_THEMES.items()):
            card = QFrame()
            card.setCursor(Qt.CursorShape.PointingHandCursor)
            # Fixed width for wrapping — 158 allows 3 per row on 520px, 2 on 340px, always visible via wrap
            card.setFixedWidth(158)
            h = 64 + (idx // 3) * 4 + (1 if idx >= 7 else 0) * 4
            card.setFixedHeight(h)
            card.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            is_sel = self.settings.value("theme", "Slate Professional") == th
            # Progressively advanced border/glow
            prog = idx / 9.0  # 0..1
            # Level 0-2: flat, 3-5: soft glow, 6-8: double border, 9: premium halo
            if idx < 3:
                bd = tok["accent_hi"] if is_sel else "rgba(255,255,255,14)"
                bw = "2px" if is_sel else "1px"
                shadow = ""
            elif idx < 6:
                bd = tok["accent_hi"] if is_sel else "rgba(255,255,255,20)"
                bw = "2px" if is_sel else "1px"
                shadow = f" QFrame {{ border-bottom: 1px solid {tok['accent_hi']}20; }}"
            elif idx < 9:
                bd = tok["accent_hi"] if is_sel else tok["accent"] + "55"
                bw = "2px" if is_sel else "1.5px"
                shadow = ""
            else:
                bd = tok["accent_hi"]
                bw = "2px"
                shadow = f" QFrame {{ border-top: 1px solid rgba(255,255,255,18); }}"
            # Gradient gets more stops as we advance
            if idx < 2:
                bg = f"qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {tok['grad_a']}, stop:1 {tok['grad_b']})"
            elif idx < 5:
                mid = tok["accent"]
                bg = f"qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {tok['grad_a']}, stop:0.55 {mid}, stop:1 {tok['grad_b']})"
            elif idx < 8:
                bg = f"qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {tok['grad_a']}, stop:0.35 {tok['accent']}, stop:0.75 {tok['grad_b']}, stop:1 {tok['accent_hi']})"
            else:
                bg = f"qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {tok['grad_a']}, stop:0.5 {tok['accent_hi']}, stop:1 {tok['grad_b']})"
            card.setStyleSheet(
                f"QFrame {{ background: {bg}; border: {bw} solid {bd}; border-radius: 11px; }}"
                + shadow
            )
            card.setToolTip(f"{th}\n{tok['accent']} → {tok['grad_b']} (click to apply)")
            # Subtle drop shadow for most advanced tiers
            if idx >= 6:
                sd = QGraphicsDropShadowEffect(card)
                sd.setBlurRadius(12 + idx * 2)
                sd.setOffset(0, 2)
                sd.setColor(QColor(0, 0, 0, 90 if idx < 8 else 120))
                card.setGraphicsEffect(sd)
            cl = QVBoxLayout(card)
            cl.setContentsMargins(12, 10, 12, 10)
            cl.setSpacing(2)
            # Advancement badge for later cards
            hdr = QHBoxLayout()
            hdr.setSpacing(6)
            name = QLabel(th)
            name.setStyleSheet("color: #ffffff; font-size: 11px; font-weight: 800; background: transparent; border: none;")
            hdr.addWidget(name, 1)
            if idx >= 3:
                lvl = QLabel(f"Lv{idx+1}")
                lvl.setFixedHeight(16)
                lvl.setStyleSheet(f"color: {tok['accent_hi']}; background: rgba(0,0,0,22); border: 1px solid {tok['accent_hi']}55; border-radius: 8px; padding: 0 5px; font-size: 8px; font-weight: 800;")
                hdr.addWidget(lvl, 0)
            cl.addLayout(hdr)
            hexlbl = QLabel(f"{tok['accent']} → {tok['grad_b']}")
            hexlbl.setStyleSheet("color: rgba(255,255,255,195); font-size: 9px; background: transparent; border: none;")
            cl.addWidget(hexlbl)
            # tiny progress bar hint for most advanced
            if idx >= 5:
                bar = QFrame()
                bar.setFixedHeight(2)
                bar.setStyleSheet(f"QFrame {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {tok['grad_a']}, stop:1 {tok['accent_hi']}); border-radius: 1px; }}")
                cl.addWidget(bar)
            card.mousePressEvent = lambda e, t=th: self._s_theme.setCurrentText(t)
            grid.addWidget(card)
        bl.addWidget(grid_host)
        hint = QLabel("Tip: cards only — no dropdown. Each next theme adds a stop/glow, fitted in a 3-column grid that never overflows.")
        hint.setStyleSheet(f"color:{C['dim']}; font-size:11px;")
        hint.setWordWrap(True)
        bl.addWidget(hint)

        # ANIMATIONS — granular, not single switch
        bl2 = self._settings_box("ANIMATIONS — granular", lay)
        self._s_anim = self._settings_switch()
        self._s_anim.setChecked(self.settings.value("animations", "true", type=bool))
        self._s_anim.toggled.connect(self._apply_animations)
        self._settings_row(
            bl2, "Master animations",
            "Global toggle — disables all motion when off.",
            self._s_anim,
        )
        # Granular toggles — every toggle demos immediately when turned ON, stops when OFF
        def _make_anim_toggle(key, label, detail):
            sw = self._settings_switch()
            sw.setChecked(self.settings.value(key, "true", type=bool))
            def _on_toggled(on, k=key, s=sw):
                self.settings.setValue(k, bool(on))
                if on and self.settings.value("animations", "true", type=bool):
                    try:
                        do_s = self.settings.value("anim_shake", "true", type=bool)
                        do_r = self.settings.value("anim_rubber", "true", type=bool)
                        if do_s and do_r:
                            Motion.shake(s, amplitude=4)
                            from PyQt6.QtCore import QTimer
                            QTimer.singleShot(420, lambda w=s: Motion.rubber(w, scale=1.10, dur=320))
                        elif do_s:
                            Motion.shake(s, amplitude=4)
                        elif do_r:
                            Motion.rubber(s, scale=1.10, dur=320)
                    except Exception:
                        pass
                try:
                    if k == "anim_cable":
                        if hasattr(self, "scene"):
                            self.scene.update()
                    elif k == "anim_orb":
                        self.orb.set_animations(bool(on) and self._s_anim.isChecked())
                    elif k == "anim_window":
                        if on:
                            Motion.window_open(self, dur=220)
                    elif k == "anim_shake":
                        if on:
                            Motion.shake(s, amplitude=6)
                    elif k == "anim_rubber":
                        if on:
                            Motion.rubber(s, scale=1.08, dur=340)
                    elif k == "anim_bubble":
                        if on and hasattr(self, "scene"):
                            Motion.bubble_splash(self.scene, count=6)
                    elif k == "anim_shimmer":
                        if hasattr(self, "shimmer"):
                            self.shimmer.setVisible(bool(on) and self._s_anim.isChecked())
                            self.shimmer.update()
                except Exception:
                    pass
            sw.toggled.connect(_on_toggled)
            self._settings_row(bl2, label, detail, sw)
            return sw

        self._s_anim_cable = _make_anim_toggle("anim_cable", "Cable pulse", "Animated data flow in the connection banner.")
        self._s_anim_orb = _make_anim_toggle("anim_orb", "Status orb", "Pulsing LED orb next to connection state.")
        self._s_anim_shimmer = _make_anim_toggle("anim_shimmer", "Shimmer bar", "Progress shimmer during flash.")
        self._s_anim_toast = _make_anim_toggle("anim_toast", "Toast slide", "Slide-in animation for notifications.")
        self._s_anim_window = _make_anim_toggle("anim_window", "Window pop", "Rubber window open/close pop.")
        self._s_anim_shake = _make_anim_toggle("anim_shake", "Button shake", "Every button tap shakes (when enabled).")
        self._s_anim_rubber = _make_anim_toggle("anim_rubber", "Rubber band", "Elastic pop on buttons/windows (when enabled).")
        self._s_anim_bubble = _make_anim_toggle("anim_bubble", "Bubble splash", "Bubbles rising from USB-C on phone connect (when enabled).")

        # No preview row — toggle itself demos immediately when turned ON (see _make_anim_toggle)

        self._s_blur = self._settings_switch()
        self._s_blur.setChecked(self.settings.value("blur", "true", type=bool))
        self._s_blur.toggled.connect(self._apply_blur)
        self._settings_row(
            bl2, "Window glow / shadow",
            "Drop shadow and halo around the main window.",
            self._s_blur,
        )

        # SHORTCUTS — table with all shortcuts, editable hint
        bl3 = self._settings_box("SHORTCUTS", lay)
        shortcuts = [
            ("F5 / Ctrl+R", "Re-scan USB / ADB"),
            ("Ctrl+Enter", "Run selected operation"),
            ("Ctrl+L", "Clear console"),
            ("Ctrl+S", "Save console log"),
            ("Ctrl+F", "Find in console"),
            ("Ctrl+Shift+C", "Copy console"),
            ("Ctrl+Esc", "Stop any operation (global)"),
        ]
        for k, d in shortcuts:
            row = QHBoxLayout()
            chip = QLabel(k)
            chip.setStyleSheet(
                f"color:{C['dim']}; font-weight:700; font-size:10px;"
                f" background:{C['card_hover']}; border:1px solid {C['border']};"
                f" border-radius:6px; padding:3px 8px;"
            )
            chip.setFixedWidth(130)
            desc = QLabel(d)
            desc.setStyleSheet(f"color:{C['dim']}; font-size:11px;")
            row.addWidget(chip)
            row.addWidget(desc, 1)
            bl3.addLayout(row)
        sc_hint = QLabel("Shortcuts are fixed in this build — custom key mapping is planned. Use Settings → Tools → Reset to restore defaults.")
        sc_hint.setStyleSheet(f"color:{C['dim']}; font-size:10px;")
        sc_hint.setWordWrap(True)
        bl3.addWidget(sc_hint)

        # UI DENSITY / FONT — more UI improvements
        bl4 = self._settings_box("UI DENSITY", lay)
        self._s_density = QComboBox()
        self._s_density.addItems(["Comfortable", "Compact", "Spacious"])
        self._s_density.setCurrentText(self.settings.value("density", "Comfortable"))
        self._style_combo(self._s_density)
        self._s_density.currentTextChanged.connect(lambda v: self.settings.setValue("density", v))
        self._settings_row(bl4, "Layout density", "Compact saves vertical space, Spacious adds padding.", self._s_density)
        self._s_font = QSpinBox()
        self._s_font.setRange(8, 16)
        self._s_font.setValue(int(self.settings.value("font_size", 13)))
        self._s_font.setSuffix(" px")
        self._s_font.valueChanged.connect(lambda v: self.settings.setValue("font_size", int(v)))
        self._settings_row(bl4, "Base font size", "Applies to console and cards (restart to fully apply).", self._s_font)

        lay.addStretch(1)
        scroll.setWidget(host)
        outer.addWidget(scroll)
        return page

    # --- Tools --------------------------------------------------------------
    def _build_settings_tools(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(18, 18, 18, 18)
        lay.setSpacing(12)

        bl = self._settings_box("ENGINE", lay)
        rows = [
            ("Engine", "Rust core (flashpilot-bridge) + PyQt6 shell"),
            ("Bridge binary", str(bridge.BRIDGE)),
            ("Bridge built", "yes" if bridge.BRIDGE.exists()
             else "no (run `cargo build --release`)"),
            ("ADB available", "yes (native)" if bridge.has_adb() else "no (bridge not built)"),
        ]
        for label, value in rows:
            row = QHBoxLayout()
            lab = QLabel(label)
            lab.setStyleSheet(f"color:{C['dim']}; font-weight:600; min-width:110px;")
            val = QLabel(value)
            val.setStyleSheet(f"color:{C['text']}; font-size:12px;")
            val.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            row.addWidget(lab)
            row.addWidget(val, 1)
            bl.addLayout(row)

        bl = self._settings_box("ACTIONS", lay)
        act = QHBoxLayout()
        act.setSpacing(10)
        b1 = QPushButton("Rebuild bridge (cargo)")
        b1.setStyleSheet(_btn_ghost())
        b1.setCursor(Qt.CursorShape.PointingHandCursor)
        b1.clicked.connect(self._rebuild_bridge)
        act.addWidget(b1)
        b2 = QPushButton("Open log folder")
        b2.setStyleSheet(_btn_ghost())
        b2.setCursor(Qt.CursorShape.PointingHandCursor)
        b2.clicked.connect(self._open_log_dir)
        act.addWidget(b2)
        b3 = QPushButton("Reset all settings")
        b3.setStyleSheet(_btn_danger())
        b3.setCursor(Qt.CursorShape.PointingHandCursor)
        b3.clicked.connect(self._reset_settings)
        act.addWidget(b3)
        act.addStretch(1)
        bl.addLayout(act)

        lay.addStretch(1)
        return page

    # --- About --------------------------------------------------------------
    def _build_settings_about(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(18, 18, 18, 18)
        lay.setSpacing(12)

        card = QFrame()
        card.setObjectName("aboutcard")
        card.setStyleSheet(
            f"QFrame#aboutcard {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:1,"
            f" stop:0 rgba(37, 99, 235, 26), stop:1 rgba(6, 182, 212, 18));"
            f" border: 1px solid {C['border']}; border-top: 1px solid {C['border_hi']};"
            f" border-radius: 14px; }}"
        )
        cl = QVBoxLayout(card)
        cl.setContentsMargins(20, 22, 20, 22)
        cl.setSpacing(6)
        logo = QLabel()
        logo.setPixmap(_draw_logo(56))
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cl.addWidget(logo)
        name = QLabel("Legendary-Brilliantforous")
        name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name.setStyleSheet(
            f"color:{C['text']}; font-size:17px; font-weight:800; letter-spacing:1px;"
        )
        cl.addWidget(name)
        _disp = _display_version(APP_VERSION)
        _beta = _is_beta_version(APP_VERSION)
        ver_text = f"Version {_disp}  ·  Rust core + PyQt6"
        if _beta:
            ver_text += "  ·  BETA"
            # Beta pill badge
            badge = QLabel("  BETA  ")
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            badge.setStyleSheet(
                "color: #ffffff; background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
                " stop:0 #f59e0b, stop:1 #dc2626);"
                " border-radius: 6px; padding: 2px 8px; font-size: 9px; font-weight: 800; letter-spacing: 1px;"
            )
            # container for badge
            badge_wrap = QHBoxLayout()
            badge_wrap.setAlignment(Qt.AlignmentFlag.AlignCenter)
            badge_wrap.addStretch()
            badge_wrap.addWidget(badge)
            badge_wrap.addStretch()
            bw = QWidget()
            bw.setLayout(badge_wrap)
            bw.setStyleSheet("background: transparent;")
            cl.addWidget(bw)
        ver = QLabel(ver_text)
        ver.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ver.setStyleSheet(
            f"color:{C['dim']}; font-size:11px;"
            + (" color: #fbbf24;" if _beta else "")
        )
        cl.addWidget(ver)
        tag = QLabel(
            "Samsung · MediaTek · Qualcomm low-level flashing & repair\n"
            "FRP bypass · screen-lock removal · download-mode tooling"
        )
        tag.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tag.setStyleSheet(f"color:{C['mute']}; font-size:10px;")
        cl.addWidget(tag)

        lay.addWidget(card)

        bl = self._settings_box("SHORTCUTS", lay)
        for k, d in (
            ("F5", "Re-scan USB / ADB"),
            ("Ctrl+Enter", "Run the selected operation"),
            ("Ctrl+L", "Clear console"),
            ("Ctrl+S", "Save console log"),
            ("Ctrl+F", "Find in console"),
        ):
            row = QHBoxLayout()
            chip = QLabel(k)
            chip.setStyleSheet(
                f"color:{C['dim']}; font-weight:700; font-size:10px;"
                f" background:{C['card_hover']}; border:1px solid {C['border']};"
                f" border-radius:6px; padding:3px 8px;"
            )
            chip.setFixedWidth(90)
            desc = QLabel(d)
            desc.setStyleSheet(f"color:{C['dim']}; font-size:11px;")
            row.addWidget(chip)
            row.addWidget(desc, 1)
            bl.addLayout(row)

        lay.addStretch(1)
        return page
