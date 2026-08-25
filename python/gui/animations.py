import math
import os

"""Animation & painted-widget layer — Motion helpers, glyph painters,
status orb, connection scene, accent strip, shimmer bar."""

from PyQt6.QtCore import (
    QRectF, QRect, Qt, QTimer, QObject, pyqtSignal, QPointF, QPoint,
    QPropertyAnimation, QEasingCurve, pyqtProperty,
)
from PyQt6.QtGui import (
    QColor, QFont, QPainter, QPainterPath, QPen, QPixmap, QPolygonF,
    QLinearGradient, QRadialGradient,
)
from PyQt6.QtWidgets import QWidget, QProgressBar, QFrame, QLabel

from .theme import C

class Motion:
    """Premium motion system - centralised easings and helpers."""
    @staticmethod
    def fade(widget, dur=220, start=0.0, end=1.0):
        from PyQt6.QtCore import QPropertyAnimation, QEasingCurve
        anim = QPropertyAnimation(widget, b"windowOpacity")
        anim.setDuration(dur)
        anim.setStartValue(start)
        anim.setEndValue(end)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.start()
        # keep reference
        if not hasattr(widget, "_anims"):
            widget._anims = []
        widget._anims.append(anim)
        return anim

    @staticmethod
    def scale_hover(widget):
        orig = widget.geometry()
        def enter(e):
            anim = QPropertyAnimation(widget, b"geometry") if hasattr(widget, "geometry") else None
            if anim:
                anim.setDuration(140)
                anim.setEasingCurve(QEasingCurve.Type.OutCubic)
                r = widget.geometry()
                r.adjust(-1, -1, 1, 1)
                anim.setEndValue(r)
                anim.start()
        widget.enterEvent = enter
        return widget

    @staticmethod
    def shimmer(bar: QProgressBar):
        bar.setStyleSheet(
            f"QProgressBar {{ background:{C['inset']}; border:1px solid {C['glass_border']}; border-radius:6px; height:8px; text-align:center; color:{C['text']}; }}"
            f"QProgressBar::chunk {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {C['grad_a']}, stop:0.5 {C['accent_hi']}, stop:1 {C['grad_b']}); border-radius:5px; }}"
        )


def _draw_computer(size, connected=False):
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    s = float(size)

    # ground shadow
    p.setBrush(QColor(0, 0, 0, 70))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(QRectF(s * 0.28, s * 0.945, s * 0.44, s * 0.05))

    # stand base
    base = QRectF(s * 0.27, s * 0.86, s * 0.46, s * 0.09)
    bgrad = QLinearGradient(0, base.top(), 0, base.bottom())
    bgrad.setColorAt(0, QColor(C["border_hi"]))
    bgrad.setColorAt(1, QColor(C["inset"]))
    p.setBrush(bgrad)
    p.setPen(QPen(QColor(C["border_hi"]), 1))
    p.drawRoundedRect(base, s * 0.05, s * 0.05)
    p.setPen(QPen(QColor(255, 255, 255, 42), 1))
    p.drawLine(QPointF(base.x() + s * 0.05, base.y() + 1.6),
               QPointF(base.x() + base.width() - s * 0.05, base.y() + 1.6))
    # neck
    ngrad = QLinearGradient(0, s * 0.70, 0, s * 0.90)
    ngrad.setColorAt(0, QColor(C["border_hi"]))
    ngrad.setColorAt(1, QColor(C["inset"]))
    p.setBrush(ngrad)
    p.setPen(QPen(QColor(C["border_hi"]), 1))
    p.drawRoundedRect(QRectF(s * 0.455, s * 0.72, s * 0.09, s * 0.16), s * 0.03, s * 0.03)

    # monitor bezel (dark metallic frame)
    bezel = QRectF(s * 0.06, s * 0.03, s * 0.88, s * 0.70)
    fr = QLinearGradient(bezel.left(), bezel.top(), bezel.right(), bezel.bottom())
    fr.setColorAt(0, QColor("#3a4450"))
    fr.setColorAt(0.5, QColor("#232b35"))
    fr.setColorAt(1, QColor("#10151d"))
    p.setBrush(fr)
    p.setPen(QPen(QColor("#4a5563"), 1.2))
    p.drawRoundedRect(bezel, s * 0.09, s * 0.09)
    p.setPen(QPen(QColor(255, 255, 255, 26), 1))
    p.drawLine(QPointF(bezel.x() + s * 0.02, bezel.y() + s * 0.02),
               QPointF(bezel.x() + bezel.width() - s * 0.02, bezel.y() + s * 0.02))

    # screen
    screen = QRectF(bezel.x() + s * 0.055, bezel.y() + s * 0.06,
                    bezel.width() - s * 0.11, bezel.height() - s * 0.12)
    if connected:
        sc = QLinearGradient(screen.left(), screen.top(), screen.right(), screen.bottom())
        sc.setColorAt(0, QColor(C["accent_hi"]))
        sc.setColorAt(0.55, QColor(C["grad_b"]))
        sc.setColorAt(1, QColor(C["grad_a"]))
    else:
        sc = QLinearGradient(screen.left(), screen.top(), screen.left(), screen.bottom())
        sc.setColorAt(0, QColor("#25314a"))
        sc.setColorAt(1, QColor(C["inset"]))
    p.setBrush(sc)
    p.setPen(QPen(QColor(0, 0, 0, 120), 1))
    p.drawRoundedRect(screen, s * 0.04, s * 0.04)

    if connected:
        # desktop: sun glow
        orb = QRadialGradient(screen.x() + screen.width() * 0.72,
                              screen.y() + screen.height() * 0.28, s * 0.22)
        orb.setColorAt(0, QColor(255, 255, 255, 90))
        orb.setColorAt(1, QColor(255, 255, 255, 0))
        p.setBrush(orb)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QRectF(screen.x() + screen.width() * 0.55,
                             screen.y() + screen.height() * 0.10,
                             s * 0.36, s * 0.36))
        # desktop window
        wx = screen.x() + screen.width() * 0.16
        wy = screen.y() + screen.height() * 0.15
        ww = screen.width() * 0.52
        wh = screen.height() * 0.5
        p.setBrush(QColor(13, 17, 26, 180))
        p.setPen(QPen(QColor(C["accent"]), 1))
        p.drawRoundedRect(QRectF(wx, wy, ww, wh), s * 0.02, s * 0.02)
        p.setPen(QPen(QColor(C["accent_hi"]), 1))
        p.drawLine(QPointF(wx + s * 0.02, wy + wh * 0.09),
                   QPointF(wx + ww - s * 0.02, wy + wh * 0.09))
        p.setBrush(QColor(C["accent_hi"]))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(QRectF(wx + s * 0.02, wy + wh * 0.14, ww * 0.45, s * 0.02),
                          s * 0.008, s * 0.008)
        # second window hint
        p.setBrush(QColor(13, 17, 26, 140))
        p.setPen(QPen(QColor(C["border_hi"]), 1))
        p.drawRoundedRect(QRectF(wx + ww * 0.30, wy + wh * 0.58, ww * 0.62, wh * 0.32),
                          s * 0.02, s * 0.02)
    else:
        # dark screen with faint reflection
        sh = QLinearGradient(screen.left(), screen.top(), screen.right(), screen.bottom())
        sh.setColorAt(0, QColor(255, 255, 255, 30))
        sh.setColorAt(1, QColor(255, 255, 255, 0))
        p.setBrush(sh)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(screen.adjusted(s * 0.02, s * 0.02, -s * 0.02, -s * 0.3),
                          s * 0.03, s * 0.03)

    # glass diagonal reflection
    p.setPen(QPen(QColor(255, 255, 255, 26), 1))
    p.drawLine(QPointF(screen.x(), screen.y() + screen.height() * 0.6),
               QPointF(screen.x() + screen.width() * 0.5, screen.y()))

    # webcam dot
    p.setBrush(QColor(C["border_hi"]))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(QRectF(bezel.x() + bezel.width() / 2 - s * 0.014,
                         bezel.y() + s * 0.006, s * 0.028, s * 0.028))
    p.setBrush(QColor(10, 14, 20))
    p.drawEllipse(QRectF(bezel.x() + bezel.width() / 2 - s * 0.008,
                         bezel.y() + s * 0.012, s * 0.016, s * 0.016))

    # status LED (bottom-right of bezel)
    led = QColor(C["ok"]) if connected else QColor(C["mute"])
    p.setBrush(led)
    p.drawEllipse(QRectF(bezel.x() + bezel.width() - s * 0.06,
                         bezel.y() + bezel.height() - s * 0.045,
                         s * 0.026, s * 0.026))
    p.end()
    return pix


def _draw_phone(size, connected):
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    s = float(size)

    # ground shadow
    p.setBrush(QColor(0, 0, 0, 70))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(QRectF(s * 0.36, s * 0.945, s * 0.28, s * 0.045))

    # ambient glow when connected
    if connected:
        glow = QRadialGradient(s * 0.5, s * 0.45, s * 0.58)
        glow.setColorAt(0, QColor(34, 197, 94, 80))
        glow.setColorAt(1, QColor(34, 197, 94, 0))
        p.setBrush(glow)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QRectF(0, 0, s, s))

    # body with metallic frame
    body = QRectF(s * 0.30, s * 0.02, s * 0.40, s * 0.94)
    frame = body.adjusted(-s * 0.006, -s * 0.006, s * 0.006, s * 0.006)
    fr = QLinearGradient(frame.left(), frame.top(), frame.right(), frame.bottom())
    fr.setColorAt(0, QColor("#b9c2cc"))
    fr.setColorAt(0.5, QColor("#7c8a99"))
    fr.setColorAt(1, QColor("#3d4754"))
    p.setBrush(fr)
    p.setPen(Qt.PenStyle.NoPen)
    p.drawRoundedRect(frame, s * 0.10, s * 0.10)

    if connected:
        bg = QLinearGradient(0, 0, 0, s)
        bg.setColorAt(0, QColor("#263544"))
        bg.setColorAt(1, QColor("#141b26"))
    else:
        bg = QLinearGradient(0, 0, 0, s)
        bg.setColorAt(0, QColor(C["card_hover"]))
        bg.setColorAt(1, QColor(C["inset"]))
    p.setBrush(bg)
    p.setPen(QPen(QColor("#0a0f15"), 1))
    p.drawRoundedRect(body, s * 0.09, s * 0.09)
    # left edge light reflection
    p.setPen(QPen(QColor(255, 255, 255, 26), 1))
    p.drawLine(QPointF(body.x() + s * 0.012, body.y() + s * 0.06),
               QPointF(body.x() + s * 0.012, body.y() + body.height() - s * 0.06))

    # side buttons
    p.setBrush(QColor("#9aa7b5"))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawRoundedRect(QRectF(frame.x() - s * 0.014, s * 0.22, s * 0.018, s * 0.09), 1, 1)
    p.drawRoundedRect(QRectF(frame.x() - s * 0.014, s * 0.34, s * 0.018, s * 0.06), 1, 1)
    p.drawRoundedRect(QRectF(frame.x() + frame.width(), s * 0.20, s * 0.018, s * 0.12), 1, 1)

    # screen
    screen = QRectF(body.x() + s * 0.022, body.y() + s * 0.05,
                    body.width() - s * 0.044, body.height() - s * 0.15)
    if connected:
        sg = QLinearGradient(screen.left(), screen.top(), screen.right(), screen.bottom())
        sg.setColorAt(0, QColor(C["grad_b"]))
        sg.setColorAt(1, QColor(C["grad_a"]))
    else:
        sg = QLinearGradient(screen.left(), screen.top(), screen.left(), screen.bottom())
        sg.setColorAt(0, QColor("#1d2939"))
        sg.setColorAt(1, QColor(C["inset"]))
    p.setBrush(sg)
    p.setPen(QPen(QColor(0, 0, 0, 110), 1))
    p.drawRoundedRect(screen, s * 0.035, s * 0.035)

    if connected:
        # wallpaper glow
        orb = QRadialGradient(screen.x() + screen.width() * 0.5,
                              screen.y() + screen.height() * 0.4, s * 0.28)
        orb.setColorAt(0, QColor(255, 255, 255, 70))
        orb.setColorAt(1, QColor(255, 255, 255, 0))
        p.setBrush(orb)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QRectF(screen.x() + screen.width() * 0.25,
                             screen.y() + screen.height() * 0.15,
                             screen.width() * 0.5, screen.width() * 0.5))
        # status bar
        p.setPen(QPen(QColor(255, 255, 255, 150), 1))
        p.drawLine(QPointF(screen.x() + s * 0.03, screen.y() + s * 0.035),
                   QPointF(screen.x() + screen.width() - s * 0.03,
                           screen.y() + s * 0.035))
        # clock
        p.setPen(QPen(QColor(255, 255, 255, 220), 1.4))
        fm = p.font()
        fm.setBold(True)
        p.setFont(fm)
        p.drawText(QRectF(screen.x(), screen.y() + s * 0.055, screen.width(), s * 0.06),
                   Qt.AlignmentFlag.AlignHCenter, "09:41")
        # app icon row
        p.setBrush(QColor(255, 255, 255, 190))
        p.setPen(Qt.PenStyle.NoPen)
        for i in range(4):
            ix = screen.x() + screen.width() * (0.12 + i * 0.24)
            iy = screen.y() + screen.height() * 0.70
            p.drawRoundedRect(QRectF(ix, iy, s * 0.048, s * 0.048), s * 0.012, s * 0.012)
        # status text
        p.setPen(QPen(QColor(255, 255, 255, 120), 1))
        p.drawText(QRectF(screen.x() + s * 0.03, screen.y() + s * 0.14,
                          screen.width() - s * 0.06, s * 0.03),
                   Qt.AlignmentFlag.AlignHCenter, "CONNECTED")
    else:
        # lock screen: faint sheen + label
        sh = QLinearGradient(screen.left(), screen.top(), screen.left(), screen.bottom())
        sh.setColorAt(0, QColor(255, 255, 255, 34))
        sh.setColorAt(1, QColor(255, 255, 255, 0))
        p.setBrush(sh)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(screen.adjusted(s * 0.02, s * 0.02, -s * 0.02, -s * 0.35),
                          s * 0.03, s * 0.03)
        p.setPen(QPen(QColor(255, 255, 255, 60), 1))
        p.drawText(QRectF(screen.x(), screen.y() + s * 0.16, screen.width(), s * 0.03),
                   Qt.AlignmentFlag.AlignHCenter, "OFFLINE")

    # glass diagonal reflection
    p.setPen(QPen(QColor(255, 255, 255, 26), 1))
    p.drawLine(QPointF(screen.x(), screen.y() + screen.height() * 0.5),
               QPointF(screen.x() + screen.width() * 0.55, screen.y()))

    # camera punch-hole with lens ring
    ring = QColor(C["ok"]) if connected else QColor(C["border_hi"])
    p.setPen(QPen(ring, 1))
    p.setBrush(QColor(8, 12, 18))
    p.drawEllipse(QRectF(s * 0.463, s * 0.062, s * 0.074, s * 0.074))
    p.setBrush(QColor(20, 28, 40))
    p.drawEllipse(QRectF(s * 0.473, s * 0.072, s * 0.054, s * 0.054))
    p.setBrush(QColor(4, 6, 10))
    p.drawEllipse(QRectF(s * 0.483, s * 0.082, s * 0.034, s * 0.034))
    if connected:
        p.setPen(QPen(QColor(C["ok"]), 0.8))
        p.drawArc(QRectF(s * 0.478, s * 0.077, s * 0.044, s * 0.044), 30 * 16, 200 * 16)

    # home indicator bar
    p.setBrush(QColor(255, 255, 255, 110))
    p.drawRoundedRect(
        QRectF(s * 0.42, screen.y() + screen.height() + s * 0.02,
               s * 0.16, s * 0.012), 1, 1
    )

    # USB-C port on the bottom edge (where the cable plugs in)
    port_w = s * 0.13
    port_h = s * 0.052
    port_x = body.x() + (body.width() - port_w) / 2
    port_y = body.y() + body.height() - port_h
    if connected:
        glow = QRadialGradient(port_x + port_w / 2, port_y + port_h / 2, s * 0.10)
        glow.setColorAt(0, QColor(34, 197, 94, 150))
        glow.setColorAt(1, QColor(34, 197, 94, 0))
        p.setBrush(glow)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QRectF(port_x - s * 0.03, port_y - s * 0.01,
                             port_w + s * 0.06, s * 0.10))
        p.setBrush(QColor(10, 14, 20))
        p.setPen(QPen(QColor("#9aa7b5"), 1))
        p.drawRoundedRect(QRectF(port_x, port_y, port_w, port_h), 2, 2)
        p.setBrush(QColor(C["ok"]))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(
            QRectF(port_x + port_w * 0.24, port_y + port_h * 0.3,
                   port_w * 0.52, port_h * 0.4), 1, 1
        )
    else:
        p.setBrush(QColor(8, 11, 16))
        p.setPen(QPen(QColor("#7c8a99"), 1))
        p.drawRoundedRect(QRectF(port_x, port_y, port_w, port_h), 2, 2)
        p.setBrush(QColor(20, 26, 36))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(
            QRectF(port_x + port_w * 0.24, port_y + port_h * 0.3,
                   port_w * 0.52, port_h * 0.4), 1, 1
        )
    p.end()
    return pix


def _draw_logo(size, version=None):
    """Draw the FlashPilot hex logo. When *version* is a beta (e.g. 1.2.1-beta)
    a 'BETA' pill + the display version is painted onto the pixmap so the
    launcher / window icon itself advertises the channel. Display version
    strips trailing .0 -> 1.2.0 shows as 1.2, 1.2.1 stays 1.2.1."""
    # Resolve version to show on the logo: explicit arg else current app version
    try:
        _ver = version if version is not None else APP_VERSION
    except Exception:
        _ver = version or ""
    _is_beta = _is_beta_version(_ver) if _ver else False
    _disp = _display_version(_ver) if _ver else ""
    # For stable the logo stays clean; for beta we reserve a bottom strip
    # so the pill doesn't overlap the hex art.
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    s = float(size)

    # Premium outer glow effect
    outer_glow = QRadialGradient(s * 0.5, s * 0.5, s * 0.5)
    outer_glow.setColorAt(0, QColor(99, 102, 241, 40))
    outer_glow.setColorAt(0.5, QColor(139, 92, 246, 20))
    outer_glow.setColorAt(1, QColor(139, 92, 246, 0))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(outer_glow)
    p.drawEllipse(QRectF(0, 0, s, s))

    # Outer hexagonal chip die with premium gradient
    hexpts = []
    for i in range(6):
        ang = math.pi / 180.0 * (60 * i - 30)
        hexpts.append(QPointF(s * 0.5 + s * 0.44 * math.cos(ang),
                              s * 0.5 + s * 0.44 * math.sin(ang)))
    hx = QPolygonF(hexpts)
    g = QLinearGradient(0, 0, s, s)
    g.setColorAt(0, QColor("#6366f1"))
    g.setColorAt(0.3, QColor("#8b5cf6"))
    g.setColorAt(0.7, QColor("#a855f7"))
    g.setColorAt(1, QColor("#22d3ee"))
    p.setPen(QPen(QColor("#c4b5fd"), s * 0.025))
    p.setBrush(g)
    p.drawPolygon(hx)

    # Inner hexagonal ring with metallic effect
    inner_ring = []
    for i in range(6):
        ang = math.pi / 180.0 * (60 * i - 30)
        inner_ring.append(QPointF(s * 0.5 + s * 0.36 * math.cos(ang),
                                 s * 0.5 + s * 0.36 * math.sin(ang)))
    ring_grad = QLinearGradient(0, 0, s, s)
    ring_grad.setColorAt(0, QColor("#1e1b4b"))
    ring_grad.setColorAt(0.5, QColor("#312e81"))
    ring_grad.setColorAt(1, QColor("#1e1b4b"))
    p.setPen(QPen(QColor("#818cf8"), s * 0.015))
    p.setBrush(ring_grad)
    p.drawPolygon(QPolygonF(inner_ring))

    # Inner core with premium dark gradient
    inner = []
    for i in range(6):
        ang = math.pi / 180.0 * (60 * i - 30)
        inner.append(QPointF(s * 0.5 + s * 0.26 * math.cos(ang),
                             s * 0.5 + s * 0.26 * math.sin(ang)))
    core_grad = QRadialGradient(s * 0.5, s * 0.5, s * 0.3)
    core_grad.setColorAt(0, QColor("#0f172a"))
    core_grad.setColorAt(0.5, QColor("#1e293b"))
    core_grad.setColorAt(1, QColor("#020617"))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(core_grad)
    p.drawPolygon(QPolygonF(inner))

    # Premium circuit traces with gradient
    for i in range(6):
        ang = math.pi / 180.0 * (60 * i - 30)
        x0 = s * 0.5 + s * 0.26 * math.cos(ang)
        y0 = s * 0.5 + s * 0.26 * math.sin(ang)
        x1 = s * 0.5 + s * 0.42 * math.cos(ang)
        y1 = s * 0.5 + s * 0.42 * math.sin(ang)
        
        trace_grad = QLinearGradient(x0, y0, x1, y1)
        trace_grad.setColorAt(0, QColor("#818cf8"))
        trace_grad.setColorAt(1, QColor("#22d3ee"))
        p.setPen(QPen(trace_grad, s * 0.028, Qt.PenStyle.SolidLine,
                      Qt.PenCapStyle.RoundCap))
        p.drawLine(QPointF(x0, y0), QPointF(x1, y1))

    # Secondary decorative traces
    for i in range(12):
        ang = math.pi / 180.0 * (30 * i - 15)
        x0 = s * 0.5 + s * 0.32 * math.cos(ang)
        y0 = s * 0.5 + s * 0.32 * math.sin(ang)
        x1 = s * 0.5 + s * 0.38 * math.cos(ang)
        y1 = s * 0.5 + s * 0.38 * math.sin(ang)
        
        p.setPen(QPen(QColor(129, 140, 248, 100), s * 0.015, Qt.PenStyle.SolidLine,
                      Qt.PenCapStyle.RoundCap))
        p.drawLine(QPointF(x0, y0), QPointF(x1, y1))

    # Premium centre node with multi-layer glow
    node_glow = QRadialGradient(s * 0.5, s * 0.5, s * 0.2)
    node_glow.setColorAt(0, QColor(99, 102, 241, 80))
    node_glow.setColorAt(0.5, QColor(139, 92, 246, 40))
    node_glow.setColorAt(1, QColor(139, 92, 246, 0))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(node_glow)
    p.drawEllipse(QRectF(s * 0.3, s * 0.3, s * 0.4, s * 0.4))

    # Centre node with premium gradient
    core = QRadialGradient(s * 0.5, s * 0.5, s * 0.16)
    core.setColorAt(0, QColor("#f8fafc"))
    core.setColorAt(0.3, QColor("#e2e8f0"))
    core.setColorAt(0.7, QColor("#cbd5e1"))
    core.setColorAt(1, QColor("#6366f1"))
    p.setBrush(core)
    p.setPen(QPen(QColor("#c4b5fd"), s * 0.02))
    p.drawEllipse(QRectF(s * 0.34, s * 0.34, s * 0.32, s * 0.32))

    # Inner bright core
    inner_core = QRadialGradient(s * 0.5, s * 0.5, s * 0.08)
    inner_core.setColorAt(0, QColor("#ffffff"))
    inner_core.setColorAt(0.5, QColor("#e0e7ff"))
    inner_core.setColorAt(1, QColor("#a5b4fc"))
    p.setBrush(inner_core)
    p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(QRectF(s * 0.42, s * 0.42, s * 0.16, s * 0.16))

    # ---- BETA badge + version (only when running a beta build) ----
    if _is_beta and s >= 28:
        # Use the display version without the redundant trailing .0
        # e.g. 1.2.0-beta -> 1.2-beta, displayed as "BETA  1.2"
        ver_text = _disp
        # For very small icons (title bar ~34px) keep the badge compact
        if s < 48:
            # Small corner pill: just "BETA"
            pill_w, pill_h = s * 0.52, s * 0.22
            pill_x, pill_y = s - pill_w - s * 0.04, s * 0.04
            grad = QLinearGradient(pill_x, pill_y, pill_x + pill_w, pill_y)
            grad.setColorAt(0, QColor("#f59e0b"))
            grad.setColorAt(1, QColor("#ea580c"))
            p.setBrush(grad)
            p.setPen(QPen(QColor("#fef3c7"), s * 0.008))
            p.drawRoundedRect(QRectF(pill_x, pill_y, pill_w, pill_h), pill_h / 2, pill_h / 2)
            p.setPen(QPen(QColor("#ffffff")))
            f = QFont("Inter", max(4, int(s * 0.09)), QFont.Weight.ExtraBold)
            p.setFont(f)
            p.drawText(QRectF(pill_x, pill_y, pill_w, pill_h),
                       Qt.AlignmentFlag.AlignCenter, "BETA")
        else:
            # Larger logo: pill at bottom with "BETA  •  v1.2" (or v1.2.1)
            vlabel = ver_text if ver_text else _ver
            # Ensure v prefix for version
            if vlabel and not vlabel.lower().startswith("v"):
                vlabel = f"v{vlabel}"
            label = f"BETA  {vlabel}" if vlabel else "BETA"
            # Measure to size pill
            f = QFont("Inter", max(5, int(s * 0.07)), QFont.Weight.ExtraBold)
            fm = QFontMetricsF(f)
            tw = fm.horizontalAdvance(label)
            pill_w = tw + s * 0.18
            pill_h = s * 0.15
            pill_x = (s - pill_w) / 2
            pill_y = s - pill_h - s * 0.06
            # Pill background
            grad = QLinearGradient(pill_x, pill_y, pill_x + pill_w, pill_y + pill_h)
            grad.setColorAt(0, QColor("#f59e0b"))
            grad.setColorAt(0.5, QColor("#ea580c"))
            grad.setColorAt(1, QColor("#dc2626"))
            p.setBrush(grad)
            p.setPen(QPen(QColor("#fef3c7"), s * 0.01))
            # shadow
            p.setOpacity(0.85)
            p.drawRoundedRect(QRectF(pill_x, pill_y, pill_w, pill_h), pill_h / 2, pill_h / 2)
            p.setOpacity(1.0)
            p.setPen(QPen(QColor("#ffffff")))
            p.setFont(f)
            p.drawText(QRectF(pill_x, pill_y, pill_w, pill_h),
                       Qt.AlignmentFlag.AlignCenter, label)

    p.end()
    return pix


class StatusOrb(QWidget):
    """Pulsing connection indicator."""

    def __init__(self):
        super().__init__()
        self._color = QColor(C["mute"])
        self._phase = 0.0
        self._connected = False
        self._anim = True
        self.setFixedSize(22, 22)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(35)

    def set_animations(self, on):
        self._anim = bool(on)
        if not on:
            self._phase = 0.0
            self.update()

    def set_connected(self, c):
        if c != self._connected:
            self._connected = c
            self._phase = 0.0
            if not c:
                self.update()

    def _tick(self):
        if self._connected and self._anim:
            self._phase = (self._phase + 0.05) % 1.0
            self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        cx = cy = 11.0
        if self._connected:
            r = 4.5 + 5.0 * (1.0 - self._phase)
            halo = QColor(C["ok"])
            halo.setAlpha(int(130 * (1.0 - self._phase)))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(halo)
            p.drawEllipse(QRectF(cx - r, cy - r, 2 * r, 2 * r))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(C["ok"]) if self._connected else QColor(C["mute"]))
        p.drawEllipse(QRectF(cx - 5, cy - 5, 10, 10))
        p.end()


class ConnectionScene(QWidget):
    """Computer -- cable -- phone, with the USB cable plugging into the
    BOTTOM of the phone (like a real phone port) instead of its side.

    Connected: the plug is seated in the phone's port, cable taut, data pulse
    running. Disconnected: the plug pulls out and dangles below the empty port
    on a slack cable.
    """

    def __init__(self):
        super().__init__()
        self.setMinimumHeight(176)
        self._connected = False
        self._plug_t = 0.0
        self._vendor = None
        self._vendor_color = None
        self._anim = True
        self._phase = 0.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(33)

    def set_animations(self, on):
        self._anim = bool(on)
        if not on:
            self._phase = 0.0
            self._plug_t = 1.0 if self._connected else 0.0
            self.update()

    def set_connected(self, c):
        if self._connected == c:
            return
        self._connected = c
        self.update()

    def set_vendor(self, label, color=None):
        self._vendor = label
        self._vendor_color = color or C["ok"]
        self.update()

    def _tick(self):
        self._phase = (self._phase + 0.02) % 1.0
        # ease the plug between dangling and seated so insertion/removal is smooth
        target = 1.0 if self._connected else 0.0
        if self._anim:
            step = 0.08
        else:
            step = 1.0
        if abs(self._plug_t - target) > 0.001:
            if self._plug_t < target:
                self._plug_t = min(target, self._plug_t + step)
            else:
                self._plug_t = max(target, self._plug_t - step)
        self.update()

    def _cable_path(self, c0, plug_pt, rail):
        path = QPainterPath()
        path.moveTo(c0)
        t = self._plug_t
        if t > 0.5:
            # mostly seated: tight, straight cable
            path.cubicTo(c0.x() + 16, c0.y(), c0.x() + 18, rail,
                         c0.x() + 30, rail)
            path.lineTo(plug_pt.x(), rail)
            path.cubicTo(plug_pt.x(), rail, plug_pt.x(),
                         plug_pt.y() - 5, plug_pt.x(), plug_pt.y())
        else:
            # dangling: deeper sag, then droops down to the loose plug
            sway = math.sin(self._phase * math.tau) * (2.2 if self._anim else 0.0)
            path.cubicTo(c0.x() + 22, c0.y() + 2, c0.x() + 26, rail,
                         c0.x() + 40 + sway, rail)
            path.lineTo(plug_pt.x(), rail)
            path.cubicTo(plug_pt.x(), rail + 2, plug_pt.x() + 3,
                         plug_pt.y() - 14, plug_pt.x(), plug_pt.y())
        return path

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = float(self.width())
        h = float(self.height())

        # premium glass panel backdrop
        p.setPen(QPen(QColor(255,255,255,18), 1))
        p.setBrush(QColor(13,22,34,160))
        p.drawRoundedRect(QRectF(1,1,w-2,h-2), 14, 14)
        # inner top highlight
        p.setPen(QPen(QColor(255,255,255,28), 1))
        p.drawLine(QPointF(14,1), QPointF(w-14,1))

        # circuit-grid backdrop: faint traces + nodes + a vertical scanline
        p.setClipRect(QRectF(4,4,w-8,h-8))
        grid = QColor(C["accent"])
        grid.setAlpha(18)
        p.setPen(QPen(grid, 1))
        step = 26.0
        gx = 0.0
        while gx < w:
            p.drawLine(QPointF(gx, 0), QPointF(gx, h))
            gx += step
        gy = 0.0
        while gy < h:
            p.drawLine(QPointF(0, gy), QPointF(w, gy))
            gy += step
        # junction nodes where traces cross
        node = QColor(C["accent_hi"])
        node.setAlpha(50)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(node)
        for gxx in range(1, int(w / step)):
            for gyy in range(1, int(h / step)):
                if (gxx + gyy) % 3 == 0:
                    p.drawEllipse(QRectF(gxx * step - 1.2, gyy * step - 1.2, 2.4, 2.4))
        # moving vertical scanline sweep
        scan_x = int((self._phase * (w + 80)) - 40)
        sc = QLinearGradient(scan_x - 20, 0, scan_x + 20, 0)
        sc.setColorAt(0, QColor(125, 211, 252, 0))
        sc.setColorAt(0.5, QColor(125, 211, 252, 22))
        sc.setColorAt(1, QColor(125, 211, 252, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(sc)
        p.drawRect(QRect(scan_x - 20, 0, 40, int(h)))
        p.setClipping(False)

        icon = 80.0
        pc_x = 10.0
        phone_x = w - 10.0 - icon
        top_y = (h - icon) * 0.24
        pc_y = top_y
        phone_y = top_y

        # devices
        p.drawPixmap(int(pc_x), int(pc_y),
                     _draw_computer(int(icon), self._connected))
        p.drawPixmap(int(phone_x), int(phone_y),
                     _draw_phone(int(icon), self._connected))

        # connected: soft radial glow behind the phone + vendor chip
        if self._connected:
            glow = QRadialGradient(phone_x + icon / 2, phone_y + icon / 2,
                                   icon * 0.9)
            vc = QColor(self._vendor_color or C["ok"])
            glow.setColorAt(0.0, QColor(vc.red(), vc.green(), vc.blue(), 70))
            glow.setColorAt(0.6, QColor(vc.red(), vc.green(), vc.blue(), 20))
            glow.setColorAt(1.0, QColor(vc.red(), vc.green(), vc.blue(), 0))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(glow)
            p.drawEllipse(QRectF(phone_x - 4, phone_y - 4,
                                 icon + 8, icon + 8))

            # premium PIT ring when in DOWNLOAD
            if self._vendor and "DOWNLOAD" in self._vendor.upper():
                p.setPen(QPen(QColor(vc.red(), vc.green(), vc.blue(), 90), 1.6, Qt.PenStyle.DotLine))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawEllipse(QRectF(phone_x - 6, phone_y - 6, icon + 12, icon + 12))
                # rotating segment
                p.setPen(QPen(QColor(vc.red(), vc.green(), vc.blue(), 180), 2.2))
                ang = int(self._phase * 360)
                p.drawArc(QRectF(phone_x - 6, phone_y - 6, icon + 12, icon + 12), ang*16, 70*16)

            if self._vendor:
                fm = p.fontMetrics()
                bw = fm.horizontalAdvance(self._vendor) + 20
                bh = 22
                bx = phone_x + icon / 2 - bw / 2
                by = max(0.0, phone_y - 28)
                p.setPen(QPen(QColor(255,255,255,18), 1))
                p.setBrush(QColor(14, 20, 30, 185))
                p.drawRoundedRect(QRectF(bx, by, bw, bh), 10, 10)
                p.setPen(QPen(QColor(255,255,255,32), 0.8))
                p.drawRoundedRect(QRectF(bx, by, bw, bh), 10, 10)
                p.setPen(QPen(vc))
                p.setFont(QFont("JetBrains Mono", 8, QFont.Weight.ExtraBold))
                p.drawText(QRectF(bx, by, bw, bh),
                           Qt.AlignmentFlag.AlignCenter, self._vendor)

        # --- plug geometry (interpolated for smooth insert/remove) ---
        t = self._plug_t
        plug_w = 20.0
        plug_h = 13.0
        px = phone_x + icon * 0.5
        port_bottom = phone_y + icon * 0.95

        # plug travels from dangling (t=0) up into the port (t=1)
        sway = math.sin(self._phase * math.tau) * (2.2 if self._anim else 0.0)
        plug_y = port_bottom - plug_h + 1 + (1.0 - t) * 18.0
        plug_x = px - plug_w / 2 + sway * (1.0 - t)
        plug = QRectF(plug_x, plug_y, plug_w, plug_h)
        plug_pt = QPointF(plug.center().x(), plug.top())
        c0 = QPointF(pc_x + icon * 0.92, pc_y + icon * 0.60)

        # --- cable ---
        rail = h - 24 if t > 0.5 else h - 9
        path = self._cable_path(c0, plug_pt, rail)

        # soft drop shadow under the whole cable
        p.setPen(QPen(QColor(0, 0, 0, 70), 8, Qt.PenStyle.SolidLine,
                      Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        p.drawPath(path.translated(0, 1.8))
        # braided body
        p.setPen(QPen(QColor("#2b3441"), 7.0, Qt.PenStyle.SolidLine,
                      Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        p.drawPath(path)
        p.setPen(QPen(QColor("#44515f"), 3.6, Qt.PenStyle.SolidLine,
                      Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        p.drawPath(path)
        p.setPen(QPen(QColor("#5c6c7c"), 1.1, Qt.PenStyle.DashLine,
                      Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        p.drawPath(path)
        if self._connected:
            p.setPen(QPen(QColor(C["ok"]), 1.8, Qt.PenStyle.SolidLine,
                          Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            p.drawPath(path)
            # data pulse dots along cable when connected
            if self._anim:
                for k in (0.25, 0.55, 0.85):
                    tpos = (self._phase + k) % 1.0
                    pt = path.pointAtPercent(tpos)
                    glow = QRadialGradient(pt.x(), pt.y(), 6)
                    vc2 = QColor(C["accent_hi"])
                    glow.setColorAt(0, QColor(vc2.red(), vc2.green(), vc2.blue(), 220))
                    glow.setColorAt(1, QColor(vc2.red(), vc2.green(), vc2.blue(), 0))
                    p.setBrush(glow)
                    p.setPen(Qt.PenStyle.NoPen)
                    p.drawEllipse(QRectF(pt.x()-5, pt.y()-5, 10, 10))
                    p.setBrush(QColor(255,255,255,230))
                    p.drawEllipse(QRectF(pt.x()-2, pt.y()-2, 4, 4))

        # --- computer socket ---
        sock = QRectF(c0.x() - 3, c0.y() - 6, 9, 12)
        p.setPen(QPen(QColor("#7c8a99"), 1))
        p.setBrush(QColor(12, 16, 22))
        p.drawRoundedRect(sock, 1.5, 1.5)
        if self._connected:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(C["ok"]))
            p.drawRoundedRect(QRectF(sock.x() + 2.5, sock.y() + 2.5, 4, 7), 1.5, 1.5)

        # --- plug (premium USB-C connector) ---
        # soft shadow under plug
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, 100))
        p.drawRoundedRect(plug.translated(0, 2.5), 4, 4)

        # animated connection glow (breathing) around the connector
        breathe = 0.5 + 0.5 * math.sin(self._phase * math.tau * 2)
        if self._connected:
            vc = QColor(self._vendor_color or C["ok"])
            halo = QRadialGradient(plug.center().x(), plug.center().y(),
                                   plug_w * 1.25)
            halo.setColorAt(0, QColor(vc.red(), vc.green(), vc.blue(),
                                      int(70 + 50 * breathe)))
            halo.setColorAt(0.55, QColor(vc.red(), vc.green(), vc.blue(),
                                         int(26 + 20 * breathe)))
            halo.setColorAt(1, QColor(vc.red(), vc.green(), vc.blue(), 0))
            p.setBrush(halo)
            p.drawRoundedRect(plug.adjusted(-6, -5, 6, 5), 7, 7)

        # connector collar (strain-relief where the sleeve meets the cable)
        collar = QRectF(plug.x() + 1.5, plug.y() - 1.2, plug.width() - 3, 3.5)
        cr = QLinearGradient(collar.left(), collar.top(), collar.right(), collar.bottom())
        cr.setColorAt(0, QColor("#4a525d"))
        cr.setColorAt(0.5, QColor("#6b7683"))
        cr.setColorAt(1, QColor("#39424e"))
        p.setPen(QPen(QColor("#2c343f"), 1))
        p.setBrush(cr)
        p.drawRoundedRect(collar, 1.5, 1.5)

        # metal plug body (brushed, with bevels)
        body_rect = plug
        pg = QLinearGradient(plug.left(), plug.top(), plug.right(), plug.bottom())
        pg.setColorAt(0.00, QColor("#f2f5f8"))
        pg.setColorAt(0.20, QColor("#c7cfd8"))
        pg.setColorAt(0.48, QColor("#9aa5b1"))
        pg.setColorAt(0.52, QColor("#7d8895"))
        pg.setColorAt(1.00, QColor("#58636f"))
        p.setPen(QPen(QColor("#39424e"), 1))
        p.setBrush(pg)
        p.drawRoundedRect(body_rect, 5, 5)

        # top sheen (moving highlight while powered)
        if self._anim and self._connected:
            sweep = self._phase
        else:
            sweep = 0.35
        shw = QRectF(plug.x() + 1.5, plug.y() + 1, plug.width() - 3, plug.height() * 0.36)
        sh = QLinearGradient(shw.left(), shw.top(), shw.right(), shw.top())
        sh.setColorAt(max(0.0, sweep - 0.5), QColor(255, 255, 255, 0))
        sh.setColorAt(sweep, QColor(255, 255, 255, 110))
        sh.setColorAt(min(1.0, sweep + 0.5), QColor(255, 255, 255, 0))
        p.setBrush(sh)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(shw, 2, 2)

        # grip ridges (machined lines)
        p.setPen(QPen(QColor(20, 26, 34, 80), 1))
        for i in range(3):
            gx = plug.x() + 3 + i * (plug.width() - 6) / 2
            p.drawLine(QPointF(gx, plug.y() + plug.height() * 0.40),
                       QPointF(gx, plug.bottom() - 1.2))

        # USB-C tip (recessed metal tongue with gold contacts)
        tip_w = 10.0
        tip_h = 7.0
        tip = QRectF(plug_pt.x() - tip_w / 2, plug.y() - tip_h + 1.2, tip_w, tip_h)
        tg = QLinearGradient(tip.left(), tip.top(), tip.left(), tip.bottom())
        tg.setColorAt(0, QColor("#e8edf2"))
        tg.setColorAt(0.5, QColor("#aeb9c4"))
        tg.setColorAt(1, QColor("#7c8895"))
        p.setPen(QPen(QColor("#3d4754"), 0.8))
        p.setBrush(tg)
        p.drawRoundedRect(tip, 1.5, 1.5)
        # gold pin contacts (2x3)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#f0c060"))
        for row in range(2):
            for k in range(3):
                cx = tip.x() + 1.6 + k * 2.3
                cy = tip.y() + 1.5 + row * 2.3
                p.drawRoundedRect(QRectF(cx, cy, 1.2, 0.8), 0.5, 0.5)
        # darker tongue core between the pins
        p.setPen(QPen(QColor("#2c343f"), 1))
        p.drawLine(QPointF(tip.center().x(), tip.y() + 0.6),
                   QPointF(tip.center().x(), tip.bottom() - 0.6))

        # activity LED on the plug: pulses with data while powered
        if self._connected:
            led_on = (math.sin(self._phase * math.tau * 6) > -0.4)
            led_rad = 2.6 + 0.4 * breathe
            led = QRadialGradient(plug.right() - 4.5, plug.y() + 4.5, 5)
            led_col = QColor(self._vendor_color or C["ok"])
            led.setColorAt(0, QColor(led_col.red(), led_col.green(), led_col.blue(), 220))
            led.setColorAt(1, QColor(led_col.red(), led_col.green(), led_col.blue(), 0))
            p.setBrush(led)
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QRectF(plug.right() - 7.5, plug.y() + 2.5, 7.5, 7.5))
            p.setBrush(led_col if led_on else QColor(led_col.red(), led_col.green(),
                                                     led_col.blue(), 120))
            p.drawEllipse(QRectF(plug.right() - 5.6, plug.y() + 4.2, 3.8, 3.8))

        # --- data pulses travelling along the cable (2 phases) ---
        if self._connected:
            for k in range(2):
                ph = (self._phase + k * 0.5) % 1.0
                pos = path.pointAtPercent(ph)
                glow = QRadialGradient(pos.x(), pos.y(), 9)
                vc = QColor(C["accent_hi"])
                glow.setColorAt(0, QColor(vc.red(), vc.green(), vc.blue(), 200))
                glow.setColorAt(1, QColor(vc.red(), vc.green(), vc.blue(), 0))
                p.setBrush(glow)
                p.setPen(Qt.PenStyle.NoPen)
                p.drawEllipse(QRectF(pos.x() - 9, pos.y() - 9, 18, 18))
                p.setPen(QPen(QColor(C["accent_hi"]), 5.0, Qt.PenStyle.SolidLine,
                              Qt.PenCapStyle.RoundCap))
                p.drawLine(pos, QPointF(pos.x() - 14, pos.y()))
                p.setPen(QPen(QColor(255, 255, 255, 130), 2.0, Qt.PenStyle.SolidLine,
                              Qt.PenCapStyle.RoundCap))
                p.drawLine(pos, QPointF(pos.x() - 14, pos.y()))
        p.end()


class AccentStrip(QWidget):
    """Ultra-thin animated gradient sheen pinned to the top of a panel."""

    def __init__(self):
        super().__init__()
        self.setFixedHeight(3)
        self._phase = 0.0
        self._active = False
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(30)

    def set_active(self, a):
        self._active = a
        if not a:
            self.update()

    def _tick(self):
        if self._active:
            self._phase = (self._phase + 0.012) % 1.0
            self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        grad = QLinearGradient(0, 0, w, 0)
        grad.setColorAt(0, QColor(C["grad_a"]))
        grad.setColorAt(0.5, QColor(C["grad_b"]))
        grad.setColorAt(1, QColor(C["grad_a"]))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(grad)
        p.drawRoundedRect(0, 0, w, h, h / 2, h / 2)
        if self._active:
            sweep = int(w * 0.34)
            x0 = int(self._phase * (w + sweep)) - sweep
            sheen = QLinearGradient(x0, 0, x0 + sweep, 0)
            sheen.setColorAt(0, QColor(255, 255, 255, 0))
            sheen.setColorAt(0.5, QColor(255, 255, 255, 200))
            sheen.setColorAt(1, QColor(255, 255, 255, 0))
            p.setBrush(sheen)
            p.drawRoundedRect(x0, 0, sweep, h, h / 2, h / 2)
        p.end()


class ShimmerBar(QWidget):
    """Animated gradient sweep used as the busy/progress indicator."""

    def __init__(self):
        super().__init__()
        self.setFixedHeight(8)
        self._active = False
        self._phase = 0.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(30)

    def set_active(self, a):
        self._active = a
        if not a:
            self.update()

    def _tick(self):
        if self._active:
            self._phase = (self._phase + 0.02) % 1.0
            self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(C["inset"]))
        p.drawRoundedRect(0, 0, w, h, h / 2, h / 2)
        if self._active:
            sweep = int(w * 0.42)
            x0 = int((self._phase * (w + sweep)) - sweep)
            grad = QLinearGradient(x0, 0, x0 + sweep, 0)
            grad.setColorAt(0, QColor(C["grad_a"]))
            grad.setColorAt(1, QColor(C["grad_b"]))
            p.setBrush(grad)
            p.drawRoundedRect(x0, 0, sweep, h, h / 2, h / 2)
        else:
            p.setBrush(QColor(C["border"]))
            p.drawRoundedRect(0, 0, w, h, h / 2, h / 2)
        p.end()


