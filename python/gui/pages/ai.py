"""AI Advisor page + settings handlers.

The advisor is read-only: this module sends questions and renders answers.
It never calls a flow runner — the user still presses the buttons.

Everything the model sees is assembled in :mod:`python.core.ai.context`
(capability card, redacted device state, console tail, retrieved notes) and
the transcript is persisted by :mod:`python.core.ai.history`.
"""

from __future__ import annotations

import os
import threading
from html import escape

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QTextCursor
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSizeGrip,
    QSpinBox,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from ..theme import C, _btn_ghost, _btn_primary, _card_qss
from ..widgets import BeautifulToggle, FlowLayout, SectionTitle
from ...core import bridge
from ...core.ai import (
    assistant as ai_assistant,
    audit as ai_audit,
    classify as ai_classify,
    context as ai_context,
    guard as ai_guard,
    history as ai_history,
    keys as ai_keys,
    provider as ai_provider,
    retrieval as ai_retrieval,
    sessions as ai_sessions,
)

_ASSISTANT_COLOR = "#22d3ee"
_USER_COLOR = "#8fa4bd"
_BODY_COLOR = "#dbe6f2"


class _AiPanelHeader(QFrame):
    """Drag handle for the floating advisor.

    The panel is a plain child widget (not a top-level window), so it needs
    an explicit grab-and-move instead of the window manager doing it.
    """

    def __init__(self, panel):
        super().__init__(panel)
        self._panel = panel
        self._offset = None
        self.setCursor(Qt.CursorShape.SizeAllCursor)
        self.setStyleSheet("background: transparent;")
        self.setFixedHeight(20)

    def mousePressEvent(self, event):  # noqa: N802 - Qt API
        if event.button() == Qt.MouseButton.LeftButton:
            self._offset = (
                event.globalPosition().toPoint()
                - self._panel.frameGeometry().topLeft()
            )
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):  # noqa: N802 - Qt API
        if self._offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self._panel.move(event.globalPosition().toPoint() - self._offset)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):  # noqa: N802 - Qt API
        if self._offset is not None:
            self._offset = None
            callback = getattr(self._panel, "_on_moved", None)
            if callback is not None:
                callback()
            event.accept()
            return
        super().mouseReleaseEvent(event)


class AiPageMixin:
    """The Advisor page and every settings action it shares."""

    # ------------------------------------------------------------------
    # Chat state
    # ------------------------------------------------------------------
    def _ai_chat(self):
        """The active persisted transcript (named session)."""
        if not hasattr(self, "_ai_sessions"):
            active = self.settings.value("ai_active_session", None)
            self._ai_sessions = ai_sessions.SessionManager(active)
        return self._ai_sessions.active

    def _ai_session_manager(self):
        self._ai_chat()  # ensure initialised
        return self._ai_sessions

    def _ai_config(self):
        """Build a provider config from QSettings + the keyring."""
        preset_id = self.settings.value("ai_preset", "openai") or "openai"
        chosen = ai_provider.preset(str(preset_id))
        base_url = self.settings.value("ai_base_url", "") or chosen.base_url
        model = self.settings.value("ai_model", "") or chosen.model
        try:
            max_tokens = int(self.settings.value("ai_max_tokens", 1200))
        except (TypeError, ValueError):
            max_tokens = 1200
        try:
            timeout = float(self.settings.value("ai_timeout", 60))
        except (TypeError, ValueError):
            timeout = 60.0
        return ai_provider.ProviderConfig(
            preset_id=chosen.id,
            kind=chosen.kind,
            base_url=str(base_url),
            model=str(model),
            api_key=ai_keys.get_key(chosen.id) or "",
            max_tokens=max(64, max_tokens),
            timeout=max(5.0, timeout),
        )

    def _ai_ready(self):
        """``(ready, reason)`` — keyring first (when a key is needed), then config."""
        cfg = self._ai_config()
        if cfg.needs_key:
            usable, reason = ai_keys.available()
            if not usable:
                return False, reason
        problems = ai_provider.validate(cfg)
        if problems:
            return False, problems[0]
        return True, ""

    def _ai_status_text(self):
        ready, reason = self._ai_ready()
        cfg = self._ai_config()
        chosen = ai_provider.preset(cfg.preset_id)
        if not ready:
            return f"AI disabled (beta) — {reason}", False
        return f"Ready (beta) · {chosen.label} · {cfg.model}", True

    # ------------------------------------------------------------------
    # Page
    # ------------------------------------------------------------------
    def _build_ai_page(self):
        panel = QFrame()
        panel.setObjectName("card")
        panel.setStyleSheet(_card_qss())
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(10)

        head = QHBoxLayout()
        head.setSpacing(10)
        head.addWidget(SectionTitle(self.tr("ADVISOR (BETA)")), 1)
        self._ai_status = QLabel("")
        self._ai_status.setStyleSheet(f"color:{C['dim']}; font-size:11px;")
        self._ai_status.setWordWrap(True)
        head.addWidget(self._ai_status, 0)
        settings_btn = QPushButton(self.tr("AI Settings"))
        settings_btn.setStyleSheet(_btn_ghost())
        settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        settings_btn.clicked.connect(self._ai_open_settings)
        head.addWidget(settings_btn, 0)
        float_btn = QPushButton(self.tr("Float panel"))
        float_btn.setStyleSheet(_btn_ghost())
        float_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        float_btn.setToolTip(
            self.tr("Open the compact advisor over any page (Ctrl+Shift+A)")
        )
        float_btn.clicked.connect(self._ai_toggle_panel)
        head.addWidget(float_btn, 0)
        lay.addLayout(head)

        sess_row = FlowLayout(margin=2, spacing=8)
        sess_label = QLabel(self.tr("Session:"))
        sess_label.setStyleSheet(f"color:{C['dim']}; font-size:10px; font-weight:700;")
        sess_row.addWidget(sess_label)
        self._ai_session_combo = QComboBox()
        self._ai_session_combo.setMinimumWidth(160)
        sess_row.addWidget(self._ai_session_combo)
        for label, handler in (
            (self.tr("New"), self._ai_session_new),
            (self.tr("Rename"), self._ai_session_rename),
            (self.tr("Delete"), self._ai_session_delete),
            (self.tr("Export"), self._ai_session_export),
        ):
            btn = QPushButton(label)
            btn.setStyleSheet(_btn_ghost())
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(handler)
            sess_row.addWidget(btn)
        lay.addLayout(sess_row)

        self._ai_refresh_sessions()

        blurb = QLabel(
            self.tr(
                "Beta feature: ask why a flash, FRP or lock-removal step failed. "
                "The advisor reads the selected device, the console tail and "
                "FlashPilot's operation notes — and never runs anything itself. "
                "Answers are generated by your chosen provider; verify before acting."
            )
        )
        blurb.setWordWrap(True)
        blurb.setStyleSheet(f"color:{C['dim']}; font-size:11px;")
        lay.addWidget(blurb)

        self._ai_view = QTextBrowser()
        self._ai_view.setOpenExternalLinks(False)
        self._ai_view.setStyleSheet(
            f"QTextBrowser {{ background:{C['inset']}; color:{C['text']};"
            f" border:1px solid {C['border']}; border-radius:10px;"
            f" padding:8px; font-size:12px; }}"
        )
        lay.addWidget(self._ai_view, 1)

        suggest_row = FlowLayout()
        suggest_row.setSpacing(6)
        self._ai_suggest_label = QLabel(self.tr("Suggested flows:"))
        self._ai_suggest_label.setStyleSheet(
            f"color:{C['dim']}; font-size:10px; font-weight:700;"
        )
        suggest_row.addWidget(self._ai_suggest_label)
        self._ai_suggest_box = suggest_row
        self._ai_suggest_container = QWidget()
        self._ai_suggest_container.setLayout(suggest_row)
        lay.addWidget(self._ai_suggest_container)
        self._ai_suggestions: list = []
        self._ai_render_suggestions([])

        ctx_row = QHBoxLayout()
        ctx_row.setSpacing(14)
        self._ai_use_device = self._ai_toggle("ai_include_device", True)
        self._ai_use_log = self._ai_toggle("ai_include_log", True)
        self._ai_use_docs = self._ai_toggle("ai_include_docs", True)
        for toggle, label in (
            (self._ai_use_device, self.tr("Device")),
            (self._ai_use_log, self.tr("Console")),
            (self._ai_use_docs, self.tr("Notes")),
        ):
            box = QHBoxLayout()
            box.setSpacing(6)
            box.addWidget(toggle)
            tag = QLabel(label)
            tag.setStyleSheet(f"color:{C['dim']}; font-size:10px;")
            box.addWidget(tag)
            ctx_row.addLayout(box)
        ctx_row.addStretch(1)
        lay.addLayout(ctx_row)

        input_row = QHBoxLayout()
        input_row.setSpacing(8)
        self._ai_input = QPlainTextEdit()
        self._ai_input.setPlaceholderText(
            self.tr("Ask about a failure, a mode, or a lock-removal method…")
        )
        self._ai_input.setFixedHeight(64)
        self._ai_input.setStyleSheet(
            f"QPlainTextEdit {{ background:{C['inset']}; color:{C['text']};"
            f" border:1px solid {C['border']}; border-radius:8px;"
            f" padding:6px; font-size:12px; }}"
        )
        input_row.addWidget(self._ai_input, 1)

        buttons = QVBoxLayout()
        buttons.setSpacing(6)
        self._ai_send_btn = QPushButton(self.tr("Send"))
        self._ai_send_btn.setStyleSheet(_btn_primary())
        self._ai_send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._ai_send_btn.clicked.connect(self._ai_send)
        buttons.addWidget(self._ai_send_btn)

        self._ai_stop_btn = QPushButton(self.tr("Stop"))
        self._ai_stop_btn.setStyleSheet(_btn_ghost())
        self._ai_stop_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._ai_stop_btn.setEnabled(False)
        self._ai_stop_btn.clicked.connect(self._ai_stop)
        buttons.addWidget(self._ai_stop_btn)

        attach_btn = QPushButton(self.tr("Attach"))
        attach_btn.setStyleSheet(_btn_ghost())
        attach_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        attach_btn.setToolTip(
            self.tr("Attach a text file (log, crash report) to the question")
        )
        attach_btn.clicked.connect(self._ai_attach)
        buttons.addWidget(attach_btn)
        ask_btn = QPushButton(self.tr("Ask Assistant"))
        ask_btn.setStyleSheet(_btn_ghost())
        ask_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        ask_btn.setToolTip(
            self.tr("Answer from FlashPilot's knowledge base (local, text-based)")
        )
        ask_btn.clicked.connect(self._ai_ask_local)
        buttons.addWidget(ask_btn)
        input_row.addLayout(buttons)
        lay.addLayout(input_row)

        foot = QHBoxLayout()
        foot.setSpacing(8)
        diag = QPushButton(self.tr("Diagnose last failure"))
        diag.setStyleSheet(_btn_ghost())
        diag.setCursor(Qt.CursorShape.PointingHandCursor)
        diag.setToolTip(
            self.tr("Loads the console tail and the selected device into the question")
        )
        diag.clicked.connect(self._ai_diagnose)
        foot.addWidget(diag)

        clear = QPushButton(self.tr("Delete chat history"))
        clear.setStyleSheet(_btn_ghost())
        clear.setCursor(Qt.CursorShape.PointingHandCursor)
        clear.clicked.connect(self._ai_clear_history)
        foot.addWidget(clear)
        foot.addStretch(1)
        note = QLabel(self.tr("Read-only advisor — it cannot flash or unlock anything."))
        note.setWordWrap(True)
        note.setStyleSheet(f"color:{C['mute']}; font-size:10px;")
        foot.addWidget(note)
        lay.addLayout(foot)

        self._ai_busy = False
        self._ai_cancel = threading.Event()
        self._ai_refresh_sessions()
        self._ai_render_history()
        self._ai_refresh_status()
        return panel

    def _ai_toggle(self, key, default):
        toggle = BeautifulToggle()
        toggle.setChecked(self.settings.value(key, default, type=bool))
        toggle.toggled.connect(lambda on, k=key: self.settings.setValue(k, on))
        return toggle

    # ------------------------------------------------------------------
    # Floating panel (same transcript, compact surface)
    # ------------------------------------------------------------------
    def _ai_toggle_panel(self):
        """Show/hide the floating advisor; builds it on first use."""
        panel = getattr(self, "_ai_panel", None)
        if panel is None:
            panel = self._build_ai_panel()
        if panel.isVisible():
            self._ai_panel_save_geometry()
            panel.hide()
            self.settings.setValue("ai_panel_open", False)
            return
        self._ai_render_history(getattr(self, "_ai_panel_view", None))
        self._ai_refresh_status()
        self._ai_place_panel()
        panel.show()
        panel.raise_()
        self.settings.setValue("ai_panel_open", True)
        try:
            self._ai_panel_input.setFocus()
        except Exception:  # noqa: BLE001
            pass

    def _build_ai_panel(self):
        """Compact, draggable advisor that floats over the current page."""
        panel = QFrame(getattr(self, "_root", None) or self)
        panel.setObjectName("aifloat")
        panel.setStyleSheet(
            f"QFrame#aifloat {{ background: qlineargradient(x1:0,y1:0,x2:0,y2:1,"
            f" stop:0 {C['card']}, stop:1 {C['inset']});"
            f" border: 1px solid {C['border_hi']}; border-radius: 12px; }}"
        )
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(10, 8, 10, 10)
        lay.setSpacing(6)

        header = _AiPanelHeader(panel)
        head = QHBoxLayout(header)
        head.setContentsMargins(2, 0, 0, 0)
        head.setSpacing(6)
        title = QLabel(self.tr("ADVISOR (BETA)"))
        title.setStyleSheet(
            f"color:{C['text']}; font-size:11px; font-weight:800;"
            f" letter-spacing:0.6px;"
        )
        head.addWidget(title)
        head.addStretch(1)
        page_btn = QPushButton("⤢")
        page_btn.setToolTip(self.tr("Open the full advisor page"))
        page_btn.setFixedSize(20, 20)
        page_btn.setStyleSheet(
            f"QPushButton {{ background:transparent; border:none;"
            f" color:{C['dim']}; font-size:12px; }}"
            f"QPushButton:hover {{ color:{C['text']}; }}"
        )
        page_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        page_btn.clicked.connect(self._ai_panel_open_page)
        head.addWidget(page_btn)
        close_btn = QPushButton("✕")
        close_btn.setToolTip(self.tr("Close"))
        close_btn.setFixedSize(20, 20)
        close_btn.setStyleSheet(
            f"QPushButton {{ background:transparent; border:none;"
            f" color:{C['dim']}; font-size:11px; }}"
            f"QPushButton:hover {{ color:{C['err']}; }}"
        )
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self._ai_toggle_panel)
        head.addWidget(close_btn)
        lay.addWidget(header)

        self._ai_panel_status = QLabel("")
        self._ai_panel_status.setWordWrap(True)
        self._ai_panel_status.setStyleSheet(f"color:{C['dim']}; font-size:10px;")
        lay.addWidget(self._ai_panel_status)

        self._ai_panel_view = QTextBrowser()
        self._ai_panel_view.setOpenExternalLinks(False)
        self._ai_panel_view.setStyleSheet(
            f"QTextBrowser {{ background:{C['inset']}; color:{C['text']};"
            f" border:1px solid {C['border']}; border-radius:8px;"
            f" padding:6px; font-size:11px; }}"
        )
        lay.addWidget(self._ai_panel_view, 1)

        self._ai_panel_input = QPlainTextEdit()
        self._ai_panel_input.setPlaceholderText(
            self.tr("Ask about a failure or a lock-removal method…")
        )
        self._ai_panel_input.setFixedHeight(44)
        self._ai_panel_input.setStyleSheet(
            f"QPlainTextEdit {{ background:{C['inset']}; color:{C['text']};"
            f" border:1px solid {C['border']}; border-radius:7px;"
            f" padding:4px; font-size:11px; }}"
        )
        lay.addWidget(self._ai_panel_input)

        row = QHBoxLayout()
        row.setSpacing(6)
        self._ai_panel_send_btn = QPushButton(self.tr("Send"))
        self._ai_panel_send_btn.setStyleSheet(_btn_primary())
        self._ai_panel_send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._ai_panel_send_btn.clicked.connect(self._ai_panel_send)
        row.addWidget(self._ai_panel_send_btn)
        self._ai_panel_stop_btn = QPushButton(self.tr("Stop"))
        self._ai_panel_stop_btn.setStyleSheet(_btn_ghost())
        self._ai_panel_stop_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._ai_panel_stop_btn.setEnabled(False)
        self._ai_panel_stop_btn.clicked.connect(self._ai_stop)
        row.addWidget(self._ai_panel_stop_btn)
        row.addStretch(1)
        grip = QSizeGrip(panel)
        grip.setFixedSize(14, 14)
        row.addWidget(grip, 0, Qt.AlignmentFlag.AlignBottom)
        lay.addLayout(row)

        panel.setMinimumSize(320, 300)
        panel.resize(400, 460)
        panel._on_moved = self._ai_panel_moved
        self._ai_panel = panel
        self._ai_panel_header = header
        self._ai_panel_grip = grip
        self._ai_render_history(self._ai_panel_view)
        self._ai_refresh_status()
        return panel

    def _ai_panel_open_page(self):
        self._ai_toggle_panel()
        self._on_section("ai")

    def _ai_place_panel(self):
        """Keep the floating panel inside the window, honouring a saved spot."""
        panel = getattr(self, "_ai_panel", None)
        root = getattr(self, "_root", None)
        if panel is None or root is None:
            return
        margin = 18
        saved = str(self.settings.value("ai_panel_geometry", "") or "")
        if saved and not getattr(self, "_ai_panel_user_moved", False):
            try:
                x, y, w, h = (int(v) for v in saved.split(","))
                if w >= panel.minimumWidth() and h >= panel.minimumHeight():
                    panel.resize(w, h)
                panel.move(
                    min(max(0, x), max(0, root.width() - panel.width())),
                    min(max(0, y), max(0, root.height() - panel.height())),
                )
                return
            except (TypeError, ValueError):
                pass
        if getattr(self, "_ai_panel_user_moved", False):
            panel.move(
                min(max(0, panel.x()), max(0, root.width() - panel.width())),
                min(max(0, panel.y()), max(0, root.height() - panel.height())),
            )
            return
        panel.move(
            max(margin, root.width() - panel.width() - margin),
            max(margin, root.height() - panel.height() - margin),
        )

    def _ai_panel_keep_on_screen(self):
        """Called from resizeEvent so the panel never ends up off-window."""
        panel = getattr(self, "_ai_panel", None)
        root = getattr(self, "_root", None)
        if panel is None or root is None or not panel.isVisible():
            return
        panel.move(
            min(max(0, panel.x()), max(0, root.width() - panel.width())),
            min(max(0, panel.y()), max(0, root.height() - panel.height())),
        )

    def _ai_panel_moved(self):
        panel = getattr(self, "_ai_panel", None)
        if panel is None:
            return
        self._ai_panel_user_moved = True
        self._ai_panel_save_geometry()

    def _ai_panel_save_geometry(self):
        panel = getattr(self, "_ai_panel", None)
        if panel is None:
            return
        self.settings.setValue(
            "ai_panel_geometry",
            f"{panel.x()},{panel.y()},{panel.width()},{panel.height()}",
        )

    # ------------------------------------------------------------------
    # Rendering — the page and the floating panel share every helper
    # ------------------------------------------------------------------
    def _ai_views(self):
        """Every transcript surface that currently exists."""
        out = []
        for name in ("_ai_view", "_ai_panel_view"):
            view = getattr(self, name, None)
            if view is not None:
                out.append(view)
        return out

    def _ai_render_history(self, view=None):
        targets = [view] if view is not None else self._ai_views()
        md = self._ai_build_markdown(self._ai_chat().messages)
        for target in targets:
            if target is None:
                continue
            target.setMarkdown(md)
            self._ai_scroll_bottom(target)

    def _ai_build_markdown(self, messages, streaming=""):
        parts: list[str] = []
        for message in messages:
            content = (message.get("content") or "").strip()
            if not content:
                continue
            if message.get("role") == "user":
                parts.append(f"**You**\n\n{content}")
            else:
                parts.append(f"**Advisor**\n\n{content}")
        if streaming and streaming.strip():
            parts.append(f"**Advisor**\n\n{streaming}")
        return "\n\n---\n\n".join(parts)

    def _ai_streaming_text(self):
        if not hasattr(self, "_ai_streaming"):
            self._ai_streaming = ""
        return self._ai_streaming

    def _ai_render_user(self, text, view=None):
        return

    def _ai_render_assistant(self, text, view=None):
        return

    def _ai_begin_reply(self, view=None):
        self._ai_streaming = ""
        targets = [view] if view is not None else self._ai_views()
        for target in targets:
            if target is None:
                continue
            target.setMarkdown(
                self._ai_build_markdown(self._ai_chat().messages, streaming="")
            )
            self._ai_scroll_bottom(target)

    def _ai_append_chunk(self, chunk, view=None):
        if not chunk:
            return
        self._ai_streaming = getattr(self, "_ai_streaming", "") + chunk
        targets = [view] if view is not None else self._ai_views()
        for target in targets:
            if target is None:
                continue
            target.setMarkdown(
                self._ai_build_markdown(
                    self._ai_chat().messages, streaming=self._ai_streaming
                )
            )
            self._ai_scroll_bottom(target)

    def _ai_scroll_bottom(self, view):
        bar = view.verticalScrollBar()
        bar.setValue(bar.maximum())

    def _ai_refresh_status(self):
        text, ready = self._ai_status_text()
        status = getattr(self, "_ai_status", None)
        if status is not None:
            status.setText(text)
            status.setStyleSheet(
                f"color:{C['ok'] if ready else C['warn']}; font-size:11px;"
            )
        panel_status = getattr(self, "_ai_panel_status", None)
        if panel_status is not None:
            panel_status.setText(text)
            panel_status.setStyleSheet(
                f"color:{C['ok'] if ready else C['warn']}; font-size:10px;"
            )
        if not getattr(self, "_ai_busy", False):
            for btn in (getattr(self, "_ai_send_btn", None),
                        getattr(self, "_ai_panel_send_btn", None)):
                if btn is not None:
                    btn.setEnabled(ready)

    # ------------------------------------------------------------------
    # Context from the live window
    # ------------------------------------------------------------------
    def ai_device_state(self):
        """The selected device as a redaction-ready dict for the advisor."""
        def tile(name):
            card = getattr(self, "info", {}).get(name)
            try:
                text = card.value.text().strip()
            except Exception:  # noqa: BLE001
                return None
            return None if text in ("", "--") else text

        return {
            "model": tile("Device Model") or getattr(self, "_cached_model", None),
            "device_type": getattr(self, "_cached_device_type", None),
            "transport": tile("Interface"),
            "mode": tile("USB Mode"),
            "adb": tile("ADB Status") or getattr(self, "_cached_adb_status", None),
            "build": tile("Build Number") or getattr(self, "_cached_build", None),
            "android": tile("Android Ver") or getattr(self, "_cached_android", None),
            "serial": getattr(self, "_cached_serial", None),
        }

    def ai_log_tail(self, lines=120):
        """The last *lines* console lines, ANSI-free."""
        buffer = getattr(self, "_log_buffer", []) or []
        tail = buffer[-max(1, int(lines)):]
        return "\n".join(plain for _level, plain in tail)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def _ai_open_settings(self):
        self._on_section("settings")
        try:
            self._switch_settings("ai")
        except Exception:  # noqa: BLE001
            pass

    def _ai_ask_local(self):
        """Answer a question from the FlashPilot Assistant's text knowledge base.

        Grounds the answer in the live console tail, the selected device (ADB
        status and friends) and the flow registry — and corrects wrong flow-key
        commands. Still read-only: nothing here executes a flow.
        """
        question = self._ai_input.toPlainText().strip()
        if not question:
            return
        try:
            flows = bridge.flow_list() or []
        except Exception:  # noqa: BLE001
            flows = []
        assistant = ai_assistant.FlashPilotAssistant.from_default(flows=flows)
        device = self.ai_device_state()
        log_tail = self.ai_log_tail(60)
        result = assistant.ask(question, log_tail=log_tail, device=device, flows=flows)
        if not result.complete:
            self.show_toast(
                self.tr("Assistant has no answer"),
                self.tr("No matching FlashPilot knowledge yet."),
                "warning",
            )
            return
        text = result.answer
        if result.corrections:
            text = "\n\n".join(result.corrections) + "\n\n" + text
        if result.sources:
            text = (
                text
                + "\n\n"
                + self.tr("Sources: {sources}").format(
                    sources=", ".join(result.sources)
                )
            )
        self._ai_chat().append("assistant", text)
        self._ai_render_history()

    def _ai_diagnose(self):
        prompt = self.tr(
            "Explain exactly why the last operation failed, using the console "
            "tail and the selected device."
        )
        self._ai_input.setPlainText(prompt)
        self._ai_input.setFocus()
        self._ai_refresh_status()

    def _ai_attach(self):
        from PyQt6.QtWidgets import QFileDialog

        path, _ = QFileDialog.getOpenFileName(
            self,
            self.tr("Attach a file"),
            "",
            self.tr("Text files (*.txt *.log *.md *.json);;All files (*)"),
        )
        if not path:
            return
        try:
            with open(path, encoding="utf-8", errors="replace") as fh:
                content = fh.read(8000)
        except OSError as exc:
            self.show_toast(self.tr("Attach failed"), str(exc), "error")
            return
        content = ai_guard.redact(content)
        name = os.path.basename(path)
        existing = self._ai_input.toPlainText()
        suffix = f"\n\n--- attached: {name} ---\n{content}\n--- end ---\n"
        self._ai_input.setPlainText((existing + suffix).strip())
        self._ai_input.setFocus()

    def _ai_stop(self):
        self._ai_cancel.set()
        for btn in (getattr(self, "_ai_stop_btn", None),
                    getattr(self, "_ai_panel_stop_btn", None)):
            if btn is not None:
                btn.setEnabled(False)

    def _ai_refresh_sessions(self):
        combo = getattr(self, "_ai_session_combo", None)
        if combo is None:
            return
        manager = self._ai_session_manager()
        combo.blockSignals(True)
        combo.clear()
        for name in manager.list_names():
            combo.addItem(name)
        idx = combo.findText(manager.active_name)
        if idx >= 0:
            combo.setCurrentIndex(idx)
        combo.blockSignals(False)
        try:
            combo.currentTextChanged.disconnect(self._ai_session_switched)
        except TypeError:
            pass
        combo.currentTextChanged.connect(self._ai_session_switched)

    def _ai_session_switched(self, name):
        if not name:
            return
        manager = self._ai_session_manager()
        if name == manager.active_name:
            return
        manager.switch(name)
        self.settings.setValue("ai_active_session", manager.active_name)
        self._ai_render_history()
        self._ai_render_suggestions([])

    def _ai_session_new(self):
        manager = self._ai_session_manager()
        name = manager.create(self.tr("New chat"))
        self.settings.setValue("ai_active_session", name)
        self._ai_refresh_sessions()
        self._ai_render_history()
        self._ai_render_suggestions([])

    def _ai_session_rename(self):
        from PyQt6.QtWidgets import QInputDialog

        manager = self._ai_session_manager()
        new_name, ok = QInputDialog.getText(
            self, self.tr("Rename session"), self.tr("New name:"),
            text=manager.active_name,
        )
        if not ok or not new_name.strip():
            return
        manager.rename(manager.active_name, new_name.strip())
        self.settings.setValue("ai_active_session", manager.active_name)
        self._ai_refresh_sessions()

    def _ai_session_delete(self):
        manager = self._ai_session_manager()
        manager.delete(manager.active_name)
        self.settings.setValue("ai_active_session", manager.active_name)
        self._ai_refresh_sessions()
        self._ai_render_history()
        self._ai_render_suggestions([])

    def _ai_session_export(self):
        from PyQt6.QtWidgets import QFileDialog

        manager = self._ai_session_manager()
        path, _ = QFileDialog.getSaveFileName(
            self, self.tr("Export session"), f"{manager.active_name}.md",
            self.tr("Markdown (*.md)"),
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(manager.export_markdown())
        except OSError as exc:
            self.show_toast(self.tr("Export failed"), str(exc), "error")
            return
        self.show_toast(
            self.tr("Session exported"), path, "success"
        )

    def _ai_clear_history(self):
        self._ai_chat().clear()
        self._ai_render_history()
        self._ai_render_suggestions([])
        self._ai_refresh_history_note()
        self.show_toast(
            self.tr("Chat history deleted"),
            self.tr("The advisor transcript was removed from this machine."),
            "success",
        )

    def _ai_render_suggestions(self, suggestions=None):
        box = getattr(self, "_ai_suggest_box", None)
        if box is None:
            return
        if suggestions is not None:
            self._ai_suggestions = list(suggestions or [])
        suggestions = self._ai_suggestions
        # Remove everything except the label (index 0).
        while box.count() > 1:
            item = box.takeAt(1)
            if item.widget() is not None:
                item.widget().deleteLater()
        if not suggestions:
            self._ai_suggest_label.setText(self.tr("Suggested flows: (none)"))
            self._ai_suggest_label.setStyleSheet(
                f"color:{C['mute']}; font-size:10px;"
            )
            return
        self._ai_suggest_label.setText(self.tr("Suggested flows:"))
        self._ai_suggest_label.setStyleSheet(
            f"color:{C['dim']}; font-size:10px; font-weight:700;"
        )
        for suggestion in suggestions[:6]:
            btn = QPushButton(suggestion.label)
            btn.setStyleSheet(_btn_ghost())
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setToolTip(
                f"{suggestion.reason}\n\n"
                f"Flow: {suggestion.key}  ·  {suggestion.mode}\n"
                f"Read-only: opens the page, does not run anything."
            )
            btn.clicked.connect(
                lambda _checked=False, s=suggestion: self._ai_open_suggestion(s)
            )
            box.addWidget(btn)

    def _ai_open_suggestion(self, suggestion):
        section = getattr(suggestion, "section", "") or "general"
        if section not in getattr(self, "_section_index", {}):
            section = "general"
        self._on_section(section)
        self.show_toast(
            self.tr("Suggested flow"),
            self.tr("Look for '{label}' ({key}) on this page.").format(
                label=suggestion.label, key=suggestion.key
            ),
            "info",
        )
        self._ai_chat().clear()
        self._ai_render_history()
        self._ai_render_suggestions([])
        self._ai_refresh_history_note()
        self.show_toast(
            self.tr("Chat history deleted"),
            self.tr("The advisor transcript was removed from this machine."),
            "success",
        )

    def _ai_send(self):
        self._ai_submit(
            self._ai_input,
            getattr(self, "_ai_view", None),
            getattr(self, "_ai_send_btn", None),
            getattr(self, "_ai_stop_btn", None),
        )

    def _ai_panel_send(self):
        self._ai_submit(
            getattr(self, "_ai_panel_input", None),
            getattr(self, "_ai_panel_view", None),
            getattr(self, "_ai_panel_send_btn", None),
            getattr(self, "_ai_panel_stop_btn", None),
        )

    def _ai_submit(self, input_widget, view, send_btn, stop_btn):
        """Send whatever is in *input_widget*, streaming into *view*.

        Shared by the page and the floating panel so both surfaces use one
        transcript, one provider config and one cancel event.
        """
        if getattr(self, "_ai_busy", False) or input_widget is None:
            return
        question = input_widget.toPlainText().strip()
        if not question:
            return
        ready, reason = self._ai_ready()
        if not ready:
            self.show_toast(self.tr("Advisor unavailable"), reason, "warning")
            self._ai_open_settings()
            return

        cfg = self._ai_config()
        include_device = self.settings.value("ai_include_device", True, type=bool)
        include_log = self.settings.value("ai_include_log", True, type=bool)
        include_docs = self.settings.value("ai_include_docs", True, type=bool)
        try:
            log_lines = int(self.settings.value("ai_log_lines", 120))
        except (TypeError, ValueError):
            log_lines = 120
        device = self.ai_device_state() if include_device else None
        log_tail = self.ai_log_tail(log_lines) if include_log else ""
        history = self._ai_chat().messages

        self._ai_render_user(question, view)
        self._ai_chat().append("user", question)
        input_widget.clear()
        self._ai_begin_reply(view)

        self._ai_busy = True
        self._ai_cancel = threading.Event()
        if send_btn is not None:
            send_btn.setEnabled(False)
        if stop_btn is not None:
            stop_btn.setEnabled(True)
        if getattr(self, "_ai_status", None) is not None:
            self._ai_status.setText(self.tr("Thinking…"))
        if getattr(self, "_ai_panel_status", None) is not None:
            self._ai_panel_status.setText(self.tr("Thinking…"))

        def work():
            pieces: list[str] = []
            usage: dict = {}
            try:
                flows = bridge.flow_list() or []
                index = ai_retrieval.default_index() if include_docs else None
                built = ai_context.build_messages(
                    question,
                    flows=flows,
                    device=device,
                    log_tail=log_tail,
                    history=history,
                    index=index,
                    include_docs=include_docs,
                    log_lines=log_lines,
                )
                suggestions = ai_classify.classify(
                    log_tail, flows if isinstance(flows, list) else [], question
                )
                ai_audit.log_event(
                    "request",
                    question=question,
                    provider=cfg.preset_id,
                    model=cfg.model,
                    input_tokens=built.input_tokens,
                    docs=built.used_docs,
                    causes=built.matched_causes,
                )
                for chunk in ai_provider.stream_chat(
                    cfg, built.messages, cancel=self._ai_cancel.is_set,
                    usage_out=usage,
                ):
                    pieces.append(chunk)
                    self._ui.ui.emit(
                        lambda c=chunk: self._ai_append_chunk(c, view)
                    )
                text = "".join(pieces).strip()
                self._ui.ui.emit(
                    lambda: self._ai_finish(text, usage, None, question, view, suggestions)
                )
            except Exception as exc:  # noqa: BLE001
                message = str(exc)
                self._ui.ui.emit(
                    lambda: self._ai_finish(
                        "".join(pieces).strip(), usage, message, question, view, suggestions
                    )
                )

        threading.Thread(target=work, daemon=True).start()

    def _ai_finish(self, text, usage, error, question, view=None, suggestions=None):
        self._ai_busy = False
        self._ai_streaming = ""
        for btn in (getattr(self, "_ai_stop_btn", None),
                    getattr(self, "_ai_panel_stop_btn", None)):
            if btn is not None:
                btn.setEnabled(False)
        if text:
            self._ai_chat().append("assistant", text)
        if error:
            ai_audit.log_event(
                "error", question=question, provider=self._ai_config().preset_id,
                detail=error,
            )
            self.show_toast(self.tr("Advisor error"), error, "error")
        else:
            ai_audit.log_event(
                "reply", question=question,
                provider=self._ai_config().preset_id,
                tokens_in=usage.get("in"),
                tokens_out=usage.get("out"),
                chars=len(text),
            )
        md = self._ai_build_markdown(self._ai_chat().messages)
        if error:
            md = (md + "\n\n---\n\n**Advisor**\n\n_Error: "
                  + error.replace("\n", " ") + "_") if md else (
                "**Advisor**\n\n_Error: " + error.replace("\n", " ") + "_"
            )
        for target in self._ai_views():
            target.setMarkdown(md)
            self._ai_scroll_bottom(target)
        self._ai_render_suggestions(suggestions)
        self._ai_refresh_status()

    # ------------------------------------------------------------------
    # Settings handlers (AI section)
    # ------------------------------------------------------------------
    def _ai_on_preset_changed(self, preset_id):
        self.settings.setValue("ai_preset", preset_id)
        chosen = ai_provider.preset(preset_id)
        if hasattr(self, "_ai_base_url"):
            self._ai_base_url.setText(chosen.base_url)
        if hasattr(self, "_ai_model"):
            self._ai_model.setText(chosen.model)
        self.settings.setValue("ai_base_url", chosen.base_url)
        self.settings.setValue("ai_model", chosen.model)
        self._ai_refresh_key_state()
        self._ai_refresh_status()

    def _ai_save_key(self):
        preset_id = self.settings.value("ai_preset", "openai") or "openai"
        key = self._ai_key.text().strip()
        if not key:
            return
        try:
            ai_keys.set_key(str(preset_id), key)
        except RuntimeError as exc:
            self.show_toast(self.tr("Key not saved"), str(exc), "error")
            return
        self._ai_key.clear()
        self._ai_refresh_key_state()
        self._ai_refresh_status()
        self.show_toast(
            self.tr("API key saved"),
            self.tr("Stored in the system keyring — never in a config file."),
            "success",
        )

    def _ai_clear_key(self):
        preset_id = self.settings.value("ai_preset", "openai") or "openai"
        ai_keys.delete_key(str(preset_id))
        self._ai_refresh_key_state()
        self._ai_refresh_status()
        self.show_toast(self.tr("API key removed"), "", "success")

    def _ai_refresh_key_state(self):
        label = getattr(self, "_ai_key_state", None)
        if label is None:
            return
        preset_id = str(self.settings.value("ai_preset", "openai") or "openai")
        usable, reason = ai_keys.available()
        if not usable:
            label.setText(f"✕ {reason}")
            label.setStyleSheet(f"color:{C['err']}; font-size:11px;")
            return
        key = ai_keys.get_key(preset_id)
        if key:
            label.setText(self.tr("Stored: {masked}").format(masked=ai_keys.mask_key(key)))
            label.setStyleSheet(f"color:{C['ok']}; font-size:11px;")
        else:
            label.setText(self.tr("No key stored for this provider."))
            label.setStyleSheet(f"color:{C['warn']}; font-size:11px;")

    def _ai_test_connection(self):
        ready, reason = self._ai_ready()
        if not ready:
            self.show_toast(self.tr("Advisor unavailable"), reason, "warning")
            return
        cfg = self._ai_config()
        self.show_toast(
            self.tr("Testing connection"),
            self.tr("Sending a short request to {provider}…").format(
                provider=ai_provider.preset(cfg.preset_id).label
            ),
            "info",
        )

        def work():
            try:
                reply = ai_provider.complete(
                    cfg, [{"role": "user", "content": "Reply with OK."}]
                )
                text = reply.strip()[:120] or "OK"
                self._ui.ui.emit(
                    lambda: self.show_toast(
                        self.tr("Connection OK"), text, "success"
                    )
                )
                ai_audit.log_event(
                    "test", provider=cfg.preset_id, model=cfg.model, chars=len(reply)
                )
            except Exception as exc:  # noqa: BLE001
                message = str(exc)
                self._ui.ui.emit(
                    lambda: self.show_toast(
                        self.tr("Connection failed"), message, "error"
                    )
                )
                ai_audit.log_event(
                    "test_error", provider=cfg.preset_id, detail=message
                )

        threading.Thread(target=work, daemon=True).start()
