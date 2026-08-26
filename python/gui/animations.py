import math
import os

"""Animation & painted-widget layer — Motion helpers, glyph painters,
status orb, connection scene, accent strip, shimmer bar."""

from PyQt6.QtCore import (
    QRectF, QRect, Qt, QTimer, QObject, pyqtSignal, QPointF, QPoint,
    QPropertyAnimation, QEasingCurve, pyqtProperty,
)
from PyQt6.QtGui import (
    QFontMetricsF,
    QColor, QFont, QPainter, QPainterPath, QPen, QPixmap, QPolygonF,
    QLinearGradient, QRadialGradient,
)
from PyQt6.QtWidgets import QWidget, QProgressBar, QFrame, QLabel

from .theme import C, _display_version, _is_beta_version
from ..core import APP_VERSION

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


def _draw_computer(s, connected=False):
    """Premium desktop workstation: slim-bezel monitor, live screen UI,
    stand + base, power LED and desk reflection."""
    pix = QPixmap(s, s)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    ss = float(s)

    mon = QRectF(ss * 0.03, ss * 0.08, ss * 0.94, ss * 0.60)

    # drop shadow under the panel
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(0, 0, 0, 90))
    p.drawRoundedRect(mon.translated(0, ss * 0.018), ss * 0.035, ss * 0.035)

    # bezel with metallic edge
    frame = QLinearGradient(mon.left(), mon.top(), mon.left(), mon.bottom())
    frame.setColorAt(0, QColor("#454f5c"))
    frame.setColorAt(0.5, QColor("#2b333d"))
    frame.setColorAt(1, QColor("#1c232b"))
    p.setPen(QPen(QColor("#11161c"), ss * 0.008))
    p.setBrush(frame)
    p.drawRoundedRect(mon, ss * 0.035, ss * 0.035)

    # screen
    bz = ss * 0.035
    screen = mon.adjusted(bz, bz, -bz, -bz * 1.5)
    scr = QLinearGradient(screen.left(), screen.top(),
                          screen.right(), screen.bottom())
    if connected:
        scr.setColorAt(0, QColor("#0e3a46"))
        scr.setColorAt(0.55, QColor("#0b2b35"))
        scr.setColorAt(1, QColor("#071b22"))
    else:
        scr.setColorAt(0, QColor("#131a22"))
        scr.setColorAt(1, QColor("#0a0f15"))
    p.setPen(QPen(QColor("#05080c"), ss * 0.006))
    p.setBrush(scr)
    p.drawRoundedRect(screen, ss * 0.012, ss * 0.012)

    # screen glass sheen (diagonal)
    sheen = QLinearGradient(screen.left(), screen.top(),
                            screen.right(), screen.bottom())
    sheen.setColorAt(0.0, QColor(255, 255, 255, 26))
    sheen.setColorAt(0.35, QColor(255, 255, 255, 4))
    sheen.setColorAt(0.55, QColor(255, 255, 255, 0))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(sheen)
    p.drawRoundedRect(screen, ss * 0.012, ss * 0.012)

    # live screen UI
    p.setPen(Qt.PenStyle.NoPen)
    if connected:
        acc = QColor(C["accent_hi"])
        bars = [0.30, 0.48, 0.38, 0.62]
        bw = screen.width() * 0.11
        for i, frac in enumerate(bars):
            bh = screen.height() * 0.16 * (0.5 + frac)
            bx = screen.left() + screen.width() * 0.10 + i * (bw + bw * 0.28)
            by = screen.bottom() - ss * 0.05 - bh
            g = QLinearGradient(bx, by, bx, by + bh)
            g.setColorAt(0, QColor(acc.red(), acc.green(), acc.blue(), 210))
            g.setColorAt(1, QColor(acc.red(), acc.green(), acc.blue(), 60))
            p.setBrush(g)
            p.drawRoundedRect(QRectF(bx, by, bw, bh), ss * 0.008, ss * 0.008)
        # SYNC pill top-right of screen
        pill = QRectF(screen.right() - screen.width() * 0.30,
                      screen.top() + screen.height() * 0.08,
                      screen.width() * 0.20, screen.height() * 0.13)
        p.setBrush(QColor(6, 20, 24, 200))
        p.setPen(QPen(QColor(C["ok"]), ss * 0.006))
        p.drawRoundedRect(pill, pill.height() / 2, pill.height() / 2)
        p.setBrush(QColor(C["ok"]))
        p.drawEllipse(QRectF(pill.left() + pill.width() * 0.10,
                             pill.center().y() - ss * 0.011,
                             ss * 0.022, ss * 0.022))
        p.setPen(QPen(QColor(C["ok"])))
        f = QFont("Inter", max(5, int(ss * 0.055)), QFont.Weight.Bold)
        p.setFont(f)
        p.drawText(pill.adjusted(pill.width() * 0.22, 0, 0, 0),
                   Qt.AlignmentFlag.AlignVCenter, "SYNC")
    else:
        p.setBrush(QColor(255, 255, 255, 26))
        for i in range(3):
            ln = QRectF(screen.left() + screen.width() * 0.12,
                        screen.top() + screen.height() * (0.30 + i * 0.16),
                        screen.width() * (0.52 - i * 0.10), ss * 0.018)
            p.drawRoundedRect(ln, ss * 0.009, ss * 0.009)

    # chin brand dot + power LED on bezel
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(255, 255, 255, 40))
    p.drawEllipse(QRectF(mon.center().x() - ss * 0.008,
                         mon.bottom() - bz * 0.9,
                         ss * 0.016, ss * 0.016))
    led_c = QColor(C["ok"]) if connected else QColor("#5b6875")
    p.setBrush(led_c)
    led_r = ss * 0.012
    lx = mon.right() - bz * 1.6 - led_r
    ly = mon.bottom() - bz * 0.85 - led_r
    if connected:
        gl = QRadialGradient(lx + led_r, ly + led_r, led_r * 3)
        gl.setColorAt(0, QColor(led_c.red(), led_c.green(), led_c.blue(), 170))
        gl.setColorAt(1, QColor(led_c.red(), led_c.green(), led_c.blue(), 0))
        p.setBrush(gl)
        p.drawEllipse(QRectF(lx - led_r * 2, ly - led_r * 2,
                             led_r * 6, led_r * 6))
    p.setBrush(led_c)
    p.drawEllipse(QRectF(lx, ly, led_r * 2, led_r * 2))

    # stand neck + base
    neck = QRectF(mon.center().x() - ss * 0.05, mon.bottom() - ss * 0.002,
                  ss * 0.10, ss * 0.12)
    ng = QLinearGradient(neck.left(), 0, neck.right(), 0)
    ng.setColorAt(0, QColor("#2a323c"))
    ng.setColorAt(0.5, QColor("#49525e"))
    ng.setColorAt(1, QColor("#232a33"))
    p.setPen(QPen(QColor("#141a21"), ss * 0.005))
    p.setBrush(ng)
    p.drawRoundedRect(neck, ss * 0.01, ss * 0.01)
    base = QRectF(mon.center().x() - ss * 0.19, neck.bottom() - ss * 0.004,
                  ss * 0.38, ss * 0.035)
    bg2 = QLinearGradient(base.left(), 0, base.right(), 0)
    bg2.setColorAt(0, QColor("#39434f"))
    bg2.setColorAt(0.5, QColor("#59636f"))
    bg2.setColorAt(1, QColor("#2c343f"))
    p.setBrush(bg2)
    p.setPen(QPen(QColor("#141a21"), ss * 0.005))
    p.drawRoundedRect(base, ss * 0.017, ss * 0.017)
    # desk reflection
    refl = QLinearGradient(0, base.bottom(), 0, base.bottom() + ss * 0.06)
    refl.setColorAt(0, QColor(120, 140, 160, 50))
    refl.setColorAt(1, QColor(120, 140, 160, 0))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(refl)
    p.drawRoundedRect(QRectF(base.left() + ss * 0.02, base.bottom(),
                             base.width() - ss * 0.04, ss * 0.05),
                      ss * 0.02, ss * 0.02)

    p.end()
    return pix


def _draw_phone(s, connected=False):
    """Modern flagship phone: metal frame, punch-hole camera, status icons,
    side buttons, USB-C port + speaker/mic detail, charging state."""
    pix = QPixmap(s, s)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    ss = float(s)

    body = QRectF(ss * 0.27, ss * 0.04, ss * 0.46, ss * 0.92)
    rad = ss * 0.075

    # side buttons (right edge): power + volume — drawn under the frame edge
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor("#39424e"))
    p.drawRoundedRect(QRectF(body.right() - ss * 0.004, body.top() + body.height() * 0.16,
                             ss * 0.016, body.height() * 0.09), ss * 0.006, ss * 0.006)
    p.drawRoundedRect(QRectF(body.right() - ss * 0.004, body.top() + body.height() * 0.28,
                             ss * 0.016, body.height() * 0.05), ss * 0.006, ss * 0.006)

    # drop shadow
    p.setBrush(QColor(0, 0, 0, 95))
    p.drawRoundedRect(body.translated(ss * 0.012, ss * 0.014), rad, rad)

    # metal frame
    fg = QLinearGradient(body.left(), body.top(), body.right(), body.top())
    fg.setColorAt(0, QColor("#525c68"))
    fg.setColorAt(0.5, QColor("#8b97a3"))
    fg.setColorAt(1, QColor("#3a434e"))
    p.setPen(QPen(QColor("#10151b"), ss * 0.007))
    p.setBrush(fg)
    p.drawRoundedRect(body, rad, rad)

    # screen
    bz = ss * 0.014
    screen = body.adjusted(bz, bz, -bz, -bz)
    sr = rad - bz * 0.6
    wall = QLinearGradient(screen.left(), screen.top(),
                           screen.left(), screen.bottom())
    if connected:
        wall.setColorAt(0, QColor("#0f4652"))
        wall.setColorAt(0.5, QColor("#0b333d"))
        wall.setColorAt(1, QColor("#06181e"))
    else:
        wall.setColorAt(0, QColor("#161d26"))
        wall.setColorAt(1, QColor("#0b0f15"))
    p.setPen(QPen(QColor("#05080c"), ss * 0.004))
    p.setBrush(wall)
    p.drawRoundedRect(screen, sr, sr)

    # punch-hole camera
    ch = QPointF(screen.center().x(), screen.top() + ss * 0.030)
    p.setBrush(QColor("#04070a"))
    p.setPen(QPen(QColor("#2c3a47"), ss * 0.004))
    p.drawEllipse(QRectF(ch.x() - ss * 0.016, ch.y() - ss * 0.016,
                         ss * 0.032, ss * 0.032))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(140, 190, 230, 130))
    p.drawEllipse(QRectF(ch.x() - ss * 0.006, ch.y() - ss * 0.008,
                         ss * 0.010, ss * 0.010))

    # status cluster: signal bars + battery
    top_y = screen.top() + ss * 0.030
    sig_c = QColor(C["ok"]) if connected else QColor("#5b6875")
    for i in range(4):
        bh = ss * (0.014 + i * 0.007)
        bx = screen.left() + ss * 0.030 + i * ss * 0.014
        p.setBrush(sig_c if (connected or i < 2) else QColor("#3a4653"))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(QRectF(bx, top_y + ss * 0.028 - bh,
                                 ss * 0.009, bh), ss * 0.002, ss * 0.002)
    bat_w, bat_h = ss * 0.052, ss * 0.020
    bat = QRectF(screen.right() - ss * 0.034 - bat_w, top_y, bat_w, bat_h)
    p.setPen(QPen(QColor("#7c8a99"), ss * 0.004))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawRoundedRect(bat, ss * 0.004, ss * 0.004)
    fill_frac = 0.82 if connected else 0.38
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(C["ok"]) if connected else QColor("#8fa4bd"))
    fw = (bat.width() - ss * 0.006) * fill_frac
    p.drawRoundedRect(QRectF(bat.left() + ss * 0.003, bat.top() + ss * 0.003,
                             fw, bat.height() - ss * 0.006),
                      ss * 0.002, ss * 0.002)
    p.setBrush(QColor("#7c8a99"))
    p.drawRoundedRect(QRectF(bat.right() + ss * 0.002, bat.center().y() - ss * 0.004,
                             ss * 0.005, ss * 0.008), ss * 0.001, ss * 0.001)

    # charging bolt when connected
    if connected:
        cxp = screen.center().x()
        cyp = screen.center().y() + screen.height() * 0.06
        sc = ss * 0.05
        bolt = QPolygonF([
            QPointF(cxp + sc * 0.25, cyp - sc * 0.9),
            QPointF(cxp - sc * 0.45, cyp + sc * 0.15),
            QPointF(cxp - sc * 0.02, cyp + sc * 0.15),
            QPointF(cxp - sc * 0.25, cyp + sc * 0.9),
            QPointF(cxp + sc * 0.45, cyp - sc * 0.20),
            QPointF(cxp + sc * 0.02, cyp - sc * 0.20),
        ])
        gl = QRadialGradient(cxp, cyp, sc * 1.6)
        gl.setColorAt(0, QColor(250, 204, 21, 120))
        gl.setColorAt(1, QColor(250, 204, 21, 0))
        p.setBrush(gl)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QRectF(cxp - sc * 1.6, cyp - sc * 1.6, sc * 3.2, sc * 3.2))
        bg3 = QLinearGradient(0, cyp - sc, 0, cyp + sc)
        bg3.setColorAt(0, QColor("#fde047"))
        bg3.setColorAt(1, QColor("#f59e0b"))
        p.setBrush(bg3)
        p.setPen(QPen(QColor("#78350f"), ss * 0.004))
        p.drawPolygon(bolt)

    # bottom bezel details: speaker grill + USB-C + mic
    by_ = body.bottom() - bz * 0.9
    port_w, port_h = ss * 0.085, ss * 0.016
    port = QRectF(body.center().x() - port_w / 2, by_ - port_h / 2, port_w, port_h)
    p.setPen(QPen(QColor("#0a0f14"), ss * 0.004))
    pg2 = QLinearGradient(port.left(), 0, port.right(), 0)
    pg2.setColorAt(0, QColor("#0c1218"))
    pg2.setColorAt(0.5, QColor("#1d2630"))
    pg2.setColorAt(1, QColor("#0c1218"))
    p.setBrush(pg2)
    p.drawRoundedRect(port, port_h / 2, port_h / 2)
    if connected:
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(C["ok"]))
        p.drawRoundedRect(port.adjusted(port_w * 0.18, port_h * 0.22,
                                        -port_w * 0.18, -port_h * 0.22),
                          port_h * 0.28, port_h * 0.28)
    p.setBrush(QColor("#202a34"))
    p.setPen(Qt.PenStyle.NoPen)
    for k in range(4):
        dx = port.left() - ss * 0.030 + (k % 2) * ss * 0.012
        dy = by_ - ss * 0.004 + (k // 2) * ss * 0.010
        p.drawEllipse(QRectF(dx, dy, ss * 0.006, ss * 0.006))
        dx2 = port.right() + ss * 0.018 + (k % 2) * ss * 0.012
        p.drawEllipse(QRectF(dx2, dy, ss * 0.006, ss * 0.006))
    p.drawEllipse(QRectF(body.center().x() - ss * 0.004,
                         by_ + ss * 0.014, ss * 0.008, ss * 0.008))

    # screen glass reflection sweep
    sh = QLinearGradient(screen.left(), screen.top(),
                         screen.right(), screen.bottom())
    sh.setColorAt(0.0, QColor(255, 255, 255, 20))
    sh.setColorAt(0.4, QColor(255, 255, 255, 0))
    p.setBrush(sh)
    p.setPen(Qt.PenStyle.NoPen)
    p.drawRoundedRect(screen, sr, sr)

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
        self.setMinimumHeight(96)
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

        icon = max(52.0, min(78.0, h * 0.60))
        pc_x = 8.0
        phone_x = w - 8.0 - icon
        top_y = max(4.0, (h - icon) * 0.22)
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

        # --- cable (sag rail adapts: always below ports, never clipped) ---
        rail_seated = min(h - 10.0, max(port_bottom + 9.0, c0.y() + 24.0))
        rail = rail_seated if t > 0.5 else min(h - 4.0, rail_seated + 8.0)
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

        # --- data packets travelling ALONG the cable (never leave the wire):
        # each packet is a comet whose tail is sampled from the cable path
        # itself, so it bends with every curve of the braid. ---
        if self._connected and self._anim:
            vc = QColor(C["accent_hi"])
            tails = (0.050, 0.038, 0.027, 0.018, 0.010, 0.004, 0.0)
            for k in range(3):
                ph = (self._phase * 0.9 + k / 3.0) % 1.0
                pts = [path.pointAtPercent(max(0.0, ph - d)) for d in tails]
                # tail segments fade out behind the head, hugging the curve
                n = len(pts) - 1
                for i in range(n):
                    a = int(210 * (i + 1) / n)
                    p.setPen(QPen(QColor(vc.red(), vc.green(), vc.blue(), a),
                                  3.6 - 1.6 * i / n, Qt.PenStyle.SolidLine,
                                  Qt.PenCapStyle.RoundCap))
                    p.drawLine(pts[i], pts[i + 1])
                head = pts[-1]
                glow = QRadialGradient(head.x(), head.y(), 8)
                glow.setColorAt(0, QColor(vc.red(), vc.green(), vc.blue(), 230))
                glow.setColorAt(1, QColor(vc.red(), vc.green(), vc.blue(), 0))
                p.setBrush(glow)
                p.setPen(Qt.PenStyle.NoPen)
                p.drawEllipse(QRectF(head.x() - 8, head.y() - 8, 16, 16))
                p.setBrush(QColor(255, 255, 255, 235))
                p.drawEllipse(QRectF(head.x() - 2.2, head.y() - 2.2, 4.4, 4.4))
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


