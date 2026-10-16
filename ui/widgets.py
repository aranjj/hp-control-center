"""
Custom UI Widgets for Performance Control Center
Includes:
- make_tinted_icon helper for symbolic Breeze icons
- StatCard with live 60-second rolling SparklineWidget using system accent & threshold status
- SliderSetting with unified two-column grid support (fixed label, equal slider, trailing reset)
- CollapsibleSection container
- SegmentedControl profile bar
- RevertCountdownDialog for safety revert
"""

import logging
import re
from collections import deque
from PySide6.QtWidgets import (
    QFrame,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QSlider,
    QSpinBox,
    QPushButton,
    QToolButton,
    QWidget,
    QDialog,
    QCheckBox,
    QDoubleSpinBox,
    QSizePolicy,
)
from PySide6.QtCore import Qt, Signal, QTimer, QObject, QByteArray, QSize, QRectF
from PySide6.QtGui import QPainter, QPainterPath, QColor, QPen, QLinearGradient, QIcon, QPixmap
from PySide6.QtSvg import QSvgRenderer

from ui.styles import STATUS_WARN, STATUS_CRITICAL

logger = logging.getLogger(__name__)

BUNDLED_SVGS = {
    "view-dashboard-symbolic": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><path fill="currentColor" d="M1.5 1.5h5v5h-5zm8 0h5v3h-5zm0 5h5v8h-5zm-8 2h5v6h-5z"/></svg>""",
    "video-card-symbolic": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><path fill="currentColor" d="M1 2h2v1H2v10h1v1H1V2zm3 1h11v8H4V3zm1 1v6h9V4H5zm5 1a2 2 0 1 0 0 4 2 2 0 0 0 0-4zm0 1a1 1 0 1 1 0 2 1 1 0 0 1 0-2zm-5 6h2v2H5v-2zm3 0h4v2H8v-2z"/></svg>""",
    "edit-undo-symbolic": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><path fill="currentColor" d="M6 2L1.5 6.5 6 11V8c3.866 0 7 2.239 7 5 0-4.418-3.134-7-7-7V2z"/></svg>""",
    "utilities-system-monitor-symbolic": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><path fill="currentColor" d="M1 2C.448 2 0 2.448 0 3v9c0 .552.448 1 1 1h5v1H4v1h8v-1h-2v-1h5c.552 0 1-.448 1-1V3c0-.552-.448-1-1-1H1zm0 1h14v8H1V3zm6 1l-2 3.5L3.5 5 2 6.5 2.7 7.2l.8-.8 1.5 2.5 2-3.5 1.5 2.5.7-.7-1.2-2z"/></svg>""",
    "speedometer-symbolic": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><path fill="currentColor" d="M8 1a7 7 0 0 0-7 7c0 2.485 1.303 4.673 3.25 5.906L5 12.5A5.5 5.5 0 0 1 2.5 8 5.5 5.5 0 0 1 8 2.5 5.5 5.5 0 0 1 13.5 8a5.5 5.5 0 0 1-2.5 4.5l.75 1.406A7 7 0 0 0 15 8a7 7 0 0 0-7-7zm0 6a1 1 0 0 0-1 1 1 1 0 0 0 .156.531l-2.656 2.657.708.707 2.656-2.656A1 1 0 0 0 8 9a1 1 0 0 0 1-1 1 1 0 0 0-1-1z"/></svg>""",
    "video-display-symbolic": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><path fill="currentColor" d="M1 2C.448 2 0 2.448 0 3v8c0 .552.448 1 1 1h5v2H4v1h8v-1h-2v-2h5c.552 0 1-.448 1-1V3c0-.552-.448-1-1-1H1zm0 1h14v7H1V3zm4 1.5v4l4-2-4-2z"/></svg>""",
    "preferences-desktop-display-symbolic": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><path fill="currentColor" d="M1 2.5C1 1.67 1.67 1 2.5 1h11c.83 0 1.5.67 1.5 1.5v7.5c0 .83-.67 1.5-1.5 1.5H9.5v2h2v1h-7v-1h2v-2H2.5C1.67 11.5 1 10.83 1 10v-7.5zm1.5-.5a.5.5 0 0 0-.5.5v7c0 .28.22.5.5.5h11a.5.5 0 0 0 .5-.5v-7a.5.5 0 0 0-.5-.5h-11z"/></svg>""",
    "temperature-cold-symbolic": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><path fill="currentColor" d="M8 1a2 2 0 0 0-2 2v6.172A3.5 3.5 0 0 0 5 12a3.5 3.5 0 0 0 6 0 3.5 3.5 0 0 0-1-2.828V3a2 2 0 0 0-2-2zm0 1a1 1 0 0 1 1 1v2H7V3a1 1 0 0 1 1-1zm1 4v2H7V6h2zm0 3v.688a2.5 2.5 0 0 1 1.5 2.312 2.5 2.5 0 0 1-5 0A2.5 2.5 0 0 1 7 9.688V9h2z"/></svg>""",
    "help-about-symbolic": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><path fill="currentColor" d="M8 1a7 7 0 1 0 0 14A7 7 0 0 0 8 1zm0 1a6 6 0 1 1 0 12A6 6 0 0 1 8 2zm-.5 2v2h1V4h-1zm0 3v5h1V7h-1z"/></svg>""",
    "preferences-system-symbolic": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><path fill="currentColor" d="M7 1v1.062a5 5 0 0 0-1.781.75L4.47 2.06 3.062 3.47l.75.75A5 5 0 0 0 3.062 6H2v2h1.062a5 5 0 0 0 .75 1.781l-.75.75 1.407 1.407.75-.75A5 5 0 0 0 7 11.938V13h2v-1.062a5 5 0 0 0 1.781-.75l.75.75 1.407-1.407-.75-.75A5 5 0 0 0 12.938 8H14V6h-1.062a5 5 0 0 0-.75-1.781l.75-.75L11.53 2.06l-.75.75A5 5 0 0 0 9 2.062V1H7zm1 4a2 2 0 1 1 0 4 2 2 0 0 1 0-4z"/></svg>""",
    "application-menu-symbolic": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><path fill="currentColor" d="M2 3v2h12V3H2zm0 4v2h12V7H2zm0 4v2h12v-2H2z"/></svg>""",
    "view-refresh-symbolic": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><path fill="currentColor" d="M8 2a6 6 0 0 0-5.656 4H1l2.5 3L6 6H3.39A5 5 0 1 1 8 13a4.99 4.99 0 0 1-3.535-1.465l-.707.707A6 6 0 1 0 8 2z"/></svg>""",
    "edit-copy-symbolic": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><path fill="currentColor" d="M4 1C3.448 1 3 1.448 3 2v9h1V2h8V1H4zm3 2C5.895 3 5 3.895 5 5v9c0 1.105.895 2 2 2h6c1.105 0 2-.895 2-2V5c0-1.105-.895-2-2-2H7zm0 1h6c.552 0 1 .448 1 1v9c0 .552-.448 1-1 1H7c-.552 0-1-.448-1-1V5c0-.552.448-1 1-1z"/></svg>""",
    "document-open-symbolic": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><path fill="currentColor" d="M1 2v12h14V5H7L5 2H1zm1 1h2.55l2 3H14v1H3l-1.5 6V3zm1.625 5h10.875l-1.5 5H2.125l1.5-5z"/></svg>""",
    "brightness-low-symbolic": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><circle cx="8" cy="8" r="3" fill="currentColor"/><path fill="currentColor" d="M7.5 1h1v2h-1zM7.5 13h1v2h-1zM1 7.5h2v1H1zM13 7.5h2v1h-2zM3.05 3.757l.707-.707 1.414 1.414-.707.707zM10.829 11.536l.707-.707 1.414 1.414-.707.707zM3.757 12.95l-.707-.707 1.414-1.414.707.707zM11.536 5.171l-.707-.707 1.414-1.414.707.707z"/></svg>""",
    "brightness-high-symbolic": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><circle cx="8" cy="8" r="4" fill="currentColor"/><path fill="currentColor" d="M7.5 0h1v3h-1zM7.5 13h1v3h-1zM0 7.5h3v1H0zM13 7.5h3v1h-3zM2.343 3.05l.707-.707 2.121 2.121-.707.707zM10.829 11.536l.707-.707 2.121 2.121-.707.707zM3.05 13.657l-.707-.707 2.121-2.121.707.707zM11.536 5.171l-.707-.707 2.121-2.121.707.707z"/></svg>""",
    "dialog-warning-symbolic": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><path fill="currentColor" d="M8 1L0 15h16L8 1zm0 3l5.5 10H2.5L8 4zm-.5 3v3h1V7h-1zm0 4v1.5h1V11h-1z"/></svg>""",
    "preferences-system-performance-symbolic": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><path fill="currentColor" d="M8 1a7 7 0 1 0 0 14A7 7 0 0 0 8 1zm0 2a5 5 0 0 1 5 5h-2a3 3 0 0 0-3-3V3zm-1 3v2.15A1.5 1.5 0 0 0 8 11a1.5 1.5 0 0 0 1.45-1.12l2.3-1.33A5 5 0 0 1 8 13 5 5 0 0 1 3 8a5 5 0 0 1 4-4.9V6z"/></svg>""",
    "battery-profile-performance-symbolic": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><path fill="currentColor" d="M4 2v1H2v11h11V3h-2V2H4zm-1 2h9v9H3V4zm5 1L5 9h3l-1 3 4-4H8l1-3z"/></svg>""",
    "application-exit-symbolic": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><path fill="currentColor" d="M7 2v2H3v8h4v2H1V2h6zm3.293 2.293l3.707 3.707-3.707 3.707-1.414-1.414L10.172 9H6V7h4.172L8.879 5.707l1.414-1.414z"/></svg>"""
}


def make_tinted_icon(theme_name: str, color: QColor, size: int = 16, prefer_bundled: bool = True) -> QIcon:
    """Renders a monochrome symbolic Breeze icon tinted with the specified QColor.
    Prioritizes bundled SVG symbolic icons for visual consistency and distinct silhouettes,
    falling back to system QIcon.fromTheme if not bundled."""
    if prefer_bundled and theme_name in BUNDLED_SVGS:
        svg_str = BUNDLED_SVGS[theme_name].replace("currentColor", color.name())
        renderer = QSvgRenderer(QByteArray(svg_str.encode("utf-8")))
        pix = QPixmap(size, size)
        pix.fill(Qt.transparent)
        p = QPainter(pix)
        renderer.render(p)
        p.end()
        return QIcon(pix)

    if QIcon.hasThemeIcon(theme_name):
        base_ic = QIcon.fromTheme(theme_name)
        pix = base_ic.pixmap(size, size)
        if not pix.isNull():
            tinted = QPixmap(pix.size())
            tinted.fill(Qt.transparent)
            p = QPainter(tinted)
            p.drawPixmap(0, 0, pix)
            p.setCompositionMode(QPainter.CompositionMode_SourceIn)
            p.fillRect(tinted.rect(), color)
            p.end()
            return QIcon(tinted)

    # Fallback to bundled SVG
    if theme_name in BUNDLED_SVGS:
        svg_str = BUNDLED_SVGS[theme_name].replace("currentColor", color.name())
        renderer = QSvgRenderer(QByteArray(svg_str.encode("utf-8")))
        pix = QPixmap(size, size)
        pix.fill(Qt.transparent)
        p = QPainter(pix)
        renderer.render(p)
        p.end()
        return QIcon(pix)

    return QIcon.fromTheme(theme_name)


class ToggleSwitch(QCheckBox):
    """Modern toggle switch widget adhering to KDE/Qt palette roles.
    Unchecked = muted track (Mid) and knob on the left (WindowText).
    Checked = accent-filled track (Highlight) and knob on the right (HighlightedText).
    """

    def __init__(self, text: str = "", parent: QWidget = None):
        super().__init__(text, parent)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(24)

    def sizeHint(self) -> QSize:
        fm = self.fontMetrics()
        w = 42 + (10 + fm.horizontalAdvance(self.text()) if self.text() else 0)
        h = max(24, fm.height())
        return QSize(w, h)

    def minimumSizeHint(self) -> QSize:
        return QSize(42, 24)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        pal = self.palette()
        is_chk = self.isChecked()
        is_en = self.isEnabled()

        track_w = 36.0
        track_h = 20.0
        track_y = (self.height() - track_h) / 2.0
        track_x = 0.0

        if is_chk:
            track_col = pal.highlight().color() if is_en else pal.mid().color()
            knob_col = pal.highlightedText().color() if is_en else pal.placeholderText().color()
            knob_x = track_x + track_w - 17.0
        else:
            track_col = pal.mid().color() if is_en else pal.dark().color()
            knob_col = pal.windowText().color() if is_en else pal.placeholderText().color()
            knob_x = track_x + 3.0

        knob_y = track_y + 3.0
        knob_d = 14.0

        # Track
        p.setPen(Qt.NoPen)
        p.setBrush(track_col)
        p.drawRoundedRect(QRectF(track_x, track_y, track_w, track_h), 10.0, 10.0)

        # Knob
        p.setBrush(knob_col)
        p.drawEllipse(QRectF(knob_x, knob_y, knob_d, knob_d))

        # Text
        if self.text():
            p.setPen(pal.windowText().color() if is_en else pal.placeholderText().color())
            text_x = int(track_x + track_w + 10.0)
            text_rect = self.rect().adjusted(text_x, 0, 0, 0)
        p.end()


class MutedCaptionLabel(QLabel):
    """Muted caption label that does not constrain the minimum width of its container."""
    def minimumSizeHint(self) -> QSize:
        return QSize(0, super().minimumSizeHint().height())


class MetricRingWidget(QWidget):
    """Small circular ring + inner dot indicator icon matching Intel Arc Control cards."""

    def __init__(self, color: QColor = None, parent=None):
        super().__init__(parent)
        self._color = color
        self.setFixedSize(14, 14)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)

    def set_color(self, color: QColor):
        self._color = color
        self.update()

    def get_color(self) -> QColor:
        if self._color:
            return self._color
        return self.palette().highlight().color()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        col = self.get_color()
        r = QRectF(1.5, 1.5, 11.0, 11.0)
        # Outer ring
        p.setPen(QPen(col, 1.8))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(r)
        # Center filled dot
        p.setBrush(col)
        p.setPen(Qt.NoPen)
        p.drawEllipse(QRectF(4.0, 4.0, 6.0, 6.0))
        p.end()


class SparklineWidget(QWidget):
    """60-second rolling stepped sparkline graph matching Intel Arc Control telemetry.
    - Recessed dark rectangular container with rounded corners (border-radius: 6px) and subtle border.
    - Sample-and-hold stepped line (step chart: horizontal to new time, vertical step to new value).
    - Continuous baseline across the full 60s width from x=0.
    - Soft vertical gradient glow fill under the stepped line.
    - Glowing dot on the newest sample.
    - Dynamic color: uses system accent / card color by default, switching to STATUS_WARN/STATUS_CRITICAL above thresholds.
    """

    def __init__(
        self,
        warn_threshold: float = None,
        crit_threshold: float = None,
        min_floor: float = 0.0,
        max_floor: float = 10.0,
        accent_color: QColor = None,
        maxlen: int = 60,
        parent=None,
    ):
        super().__init__(parent)
        self.warn_threshold = warn_threshold
        self.crit_threshold = crit_threshold
        self.min_floor = min_floor
        self.max_floor = max_floor
        self._custom_accent = accent_color
        self.data = deque(maxlen=maxlen)
        self.setFixedHeight(74)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)

    def set_custom_accent(self, color: QColor):
        self._custom_accent = color
        self.update()

    def changeEvent(self, event):
        if event.type() in (event.Type.PaletteChange, event.Type.ApplicationPaletteChange):
            self.update()
        super().changeEvent(event)

    def add_point(self, val: float):
        if val is not None:
            self.data.append(float(val))
            self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()
        pal = self.palette()

        # 1. Container box (recessed dark plot area with subtle border)
        box_rect = QRectF(0.5, 0.5, w - 1.0, h - 1.0)
        bg_col = pal.base().color()
        p.setBrush(bg_col)
        border_col = pal.mid().color()
        border_col.setAlpha(80)
        p.setPen(QPen(border_col, 1.0))
        p.drawRoundedRect(box_rect, 6.0, 6.0)

        # 2. Plot dimensions
        pad_x = 8.0
        pad_y = 8.0
        plot_w = w - (2.0 * pad_x)
        plot_h = h - (2.0 * pad_y)
        base_y = pad_y + plot_h

        # Compute range with floor
        if len(self.data) > 0:
            min_val = min(self.min_floor, min(self.data))
            max_val = max(self.max_floor, max(self.data))
        else:
            min_val = self.min_floor
            max_val = self.max_floor

        rng = max_val - min_val
        if rng < 0.001:
            rng = 1.0

        # Build full maxlen points list (pad left with baseline/min_val so graph is grounded from start)
        k = len(self.data)
        if k == 0:
            vals = [min_val] * self.data.maxlen
        elif k < self.data.maxlen:
            pad_val = self.data[0] if (self.data[0] <= min_val) else min_val
            vals = [pad_val] * (self.data.maxlen - k) + list(self.data)
        else:
            vals = list(self.data)

        step_x = plot_w / (self.data.maxlen - 1)
        points = []
        for i, val in enumerate(vals):
            x = pad_x + (i * step_x)
            norm = (val - min_val) / rng
            norm = max(0.0, min(1.0, norm))
            y = base_y - (norm * plot_h)
            points.append((x, y))

        # 3. Build stepped line path (sample-and-hold square wave telemetry)
        line_path = QPainterPath()
        line_path.moveTo(points[0][0], points[0][1])
        for i in range(1, len(points)):
            prev_x, prev_y = points[i - 1]
            cur_x, cur_y = points[i]
            # Horizontal to cur_x at prev_y, then vertical step to cur_y
            line_path.lineTo(cur_x, prev_y)
            line_path.lineTo(cur_x, cur_y)

        # 4. Fill path under stepped line
        fill_path = QPainterPath(line_path)
        fill_path.lineTo(points[-1][0], base_y)
        fill_path.lineTo(points[0][0], base_y)
        fill_path.closeSubpath()

        # Dynamic color check
        last_val = self.data[-1] if len(self.data) > 0 else min_val
        if self.crit_threshold is not None and last_val >= self.crit_threshold:
            line_color = QColor(STATUS_CRITICAL)
            is_accent = False
        elif self.warn_threshold is not None and last_val >= self.warn_threshold:
            line_color = QColor(STATUS_WARN)
            is_accent = False
        elif self._custom_accent is not None:
            line_color = self._custom_accent
            is_accent = True
        else:
            line_color = pal.highlight().color()
            is_accent = True

        # Subtle gradient fill below stepped line
        grad = QLinearGradient(0, pad_y, 0, base_y)
        grad.setColorAt(0.0, QColor(line_color.red(), line_color.green(), line_color.blue(), 45))
        grad.setColorAt(1.0, QColor(line_color.red(), line_color.green(), line_color.blue(), 0))
        p.fillPath(fill_path, grad)

        # 5. Draw crisp stepped stroke
        pen = QPen(line_color, 1.8)
        pen.setCapStyle(Qt.SquareCap)
        pen.setJoinStyle(Qt.MiterJoin)
        p.strokePath(line_path, pen)

        # 6. Glowing indicator dot on latest point
        last_x, last_y = points[-1]
        dot_fill = pal.highlightedText().color() if is_accent else QColor("#ffffff")
        p.setBrush(dot_fill)
        p.setPen(QPen(line_color, 1.5))
        p.drawEllipse(QRectF(last_x - 2.5, last_y - 2.5, 5.0, 5.0))

        p.end()


class StatCard(QFrame):
    """Telemetry Card displaying a live metric with status badges and an Intel Arc Control styled 60s stepped graph."""

    def __init__(
        self,
        title: str,
        initial_value: str,
        unit: str = "",
        subtitle: str = "",
        warn_threshold: float = None,
        crit_threshold: float = None,
        min_floor: float = 0.0,
        max_floor: float = 10.0,
        accent_color: str = None,
    ):
        super().__init__()
        self.setProperty("class", "CardFrame")
        self._accent_color = QColor(accent_color) if accent_color else None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(6)

        # Header Row: Indicator Ring + (Title & Subtitle stacked) + Badge
        top_row = QHBoxLayout()
        top_row.setSpacing(8)
        top_row.setContentsMargins(0, 0, 0, 0)

        self.ring = MetricRingWidget(color=self._accent_color)
        top_row.addWidget(self.ring, alignment=Qt.AlignTop)

        txt_col = QVBoxLayout()
        txt_col.setSpacing(1)
        txt_col.setContentsMargins(0, 0, 0, 0)

        self.title_lbl = QLabel(title)
        self.title_lbl.setStyleSheet("color: palette(window-text); font-size: 13px; font-weight: 700;")
        txt_col.addWidget(self.title_lbl)

        self.sub_lbl = QLabel(subtitle)
        self.sub_lbl.setStyleSheet("color: palette(placeholder-text); font-size: 11px;")
        txt_col.addWidget(self.sub_lbl)
        top_row.addLayout(txt_col)
        top_row.addStretch()

        self.badge_lbl = QLabel("")
        self.badge_lbl.setStyleSheet(
            "font-size: 10px; font-weight: bold; padding: 2px 6px; border-radius: 4px; "
            "background-color: palette(alternate-base); color: palette(window-text); border: 1px solid palette(mid);"
        )
        self.badge_lbl.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        self.badge_lbl.setVisible(False)
        top_row.addWidget(self.badge_lbl, alignment=Qt.AlignVCenter | Qt.AlignRight)
        layout.addLayout(top_row)

        # Value Row
        val_row = QHBoxLayout()
        val_row.setSpacing(6)
        val_row.setContentsMargins(0, 2, 0, 4)

        self.val_lbl = QLabel(initial_value)
        self.val_lbl.setStyleSheet("font-size: 28px; font-weight: 800; color: palette(window-text);")
        val_row.addWidget(self.val_lbl)

        if unit:
            self.unit_lbl = QLabel(unit)
            col_str = self._accent_color.name() if self._accent_color else "palette(highlight)"
            self.unit_lbl.setStyleSheet(f"font-size: 15px; font-weight: 700; color: {col_str}; margin-bottom: 4px;")
            self.unit_lbl.setAlignment(Qt.AlignBottom)
            val_row.addWidget(self.unit_lbl)
        val_row.addStretch()
        layout.addLayout(val_row)

        # 60-Second Stepped Graph
        self.sparkline = SparklineWidget(
            warn_threshold=warn_threshold,
            crit_threshold=crit_threshold,
            min_floor=min_floor,
            max_floor=max_floor,
            accent_color=self._accent_color,
            parent=self,
        )
        layout.addWidget(self.sparkline)

    def set_accent_color(self, color: str):
        col = QColor(color)
        self._accent_color = col
        self.ring.set_color(col)
        self.sparkline.set_custom_accent(col)
        if hasattr(self, "unit_lbl"):
            self.unit_lbl.setStyleSheet(f"font-size: 15px; font-weight: 700; color: {col.name()}; margin-bottom: 4px;")

    def update_value(
        self,
        value_text: str,
        subtitle_text: str = None,
        color: str = None,
        badge_text: str = None,
        badge_color: str = None,
        numeric_val: float = None,
    ):
        self.val_lbl.setText(value_text)
        if subtitle_text is not None:
            self.sub_lbl.setText(subtitle_text)

        # If explicit status color is passed (e.g. for temperature or throttle)
        if color:
            self.val_lbl.setStyleSheet(f"font-size: 28px; font-weight: 800; color: {color};")
            self.ring.set_color(QColor(color))
            if hasattr(self, "unit_lbl"):
                self.unit_lbl.setStyleSheet(f"font-size: 15px; font-weight: 700; color: {color}; margin-bottom: 4px;")
        else:
            self.val_lbl.setStyleSheet("font-size: 28px; font-weight: 800; color: palette(window-text);")
            col = self._accent_color or self.palette().highlight().color()
            self.ring.set_color(col)
            if hasattr(self, "unit_lbl"):
                self.unit_lbl.setStyleSheet(f"font-size: 15px; font-weight: 700; color: {col.name()}; margin-bottom: 4px;")

        if badge_text:
            self.badge_lbl.setText(badge_text)
            w = self.badge_lbl.fontMetrics().horizontalAdvance(badge_text) + 16
            self.badge_lbl.setFixedWidth(w)
            self.badge_lbl.setVisible(True)
            if badge_color:
                self.badge_lbl.setStyleSheet(
                    f"font-size: 10px; font-weight: bold; padding: 2px 6px; border-radius: 4px; "
                    f"background-color: {badge_color}; color: #ffffff;"
                )
            else:
                self.badge_lbl.setStyleSheet(
                    "font-size: 10px; font-weight: bold; padding: 2px 6px; border-radius: 4px; "
                    "background-color: palette(alternate-base); color: palette(window-text); border: 1px solid palette(mid);"
                )
        elif badge_text is not None:
            self.badge_lbl.setVisible(False)

        # Update sparkline
        if numeric_val is not None:
            self.sparkline.add_point(numeric_val)
        else:
            try:
                cleaned = value_text.replace(",", "").strip()
                self.sparkline.add_point(float(cleaned))
            except ValueError:
                pass


class SliderSetting(QObject):
    """
    Slider setting component with unified two-column grid support:
    - Col 0: Fixed-width label column
    - Col 1: Equal-width horizontal slider with min/max labels below
    - Col 2: Trailing spinbox & per-slider reset button right-aligned
    """

    valueChanged = Signal(int)

    def __init__(self, label: str, min_val: int, max_val: int, default_val: int, unit: str = "W", label_width: int = 240, parent=None):
        super().__init__(parent)
        self.min_val = min_val
        self.max_val = max_val
        self.default_val = default_val
        self.unit = unit
        self._block_signals = False

        # Col 0: Label
        self.title_lbl = QLabel(label)
        self.title_lbl.setProperty("class", "FormLabel")
        self.title_lbl.setWordWrap(True)
        self.title_lbl.setFixedWidth(label_width)

        # Col 1: Slider box
        self.slider_widget = QWidget()
        slider_box = QVBoxLayout(self.slider_widget)
        slider_box.setSpacing(2)
        slider_box.setContentsMargins(0, 0, 0, 0)

        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(min_val, max_val)
        self.slider.setValue(default_val)
        self.slider.valueChanged.connect(self._on_slider_changed)
        slider_box.addWidget(self.slider)

        range_row = QHBoxLayout()
        range_row.setContentsMargins(0, 0, 0, 0)
        self.min_lbl = QLabel(f"{min_val} {unit}")
        self.min_lbl.setProperty("class", "Footnote")
        range_row.addWidget(self.min_lbl)
        range_row.addStretch()
        self.max_lbl = QLabel(f"{max_val} {unit}")
        self.max_lbl.setProperty("class", "Footnote")
        range_row.addWidget(self.max_lbl)
        slider_box.addLayout(range_row)

        # Col 2: Trailing controls right-aligned (SpinBox + Reset)
        self.trailing_widget = QWidget()
        self.trailing_widget.setFixedWidth(130)
        trailing = QHBoxLayout(self.trailing_widget)
        trailing.setSpacing(6)
        trailing.setContentsMargins(0, 0, 0, 0)

        self.spin = QSpinBox()
        self.spin.setRange(min_val, max_val)
        self.spin.setValue(default_val)
        self.spin.setSuffix(f" {self.unit}")
        self.spin.setFixedWidth(96)
        self.spin.setAlignment(Qt.AlignCenter)
        self.spin.setProperty("class", "SettingSpin")
        self.spin.valueChanged.connect(self._on_spin_changed)
        trailing.addWidget(self.spin)

        self.btn_reset = QToolButton()
        self.btn_reset.setIcon(make_tinted_icon("edit-undo-symbolic", QColor("#ffffff"), 14))
        self.btn_reset.setToolTip(f"Reset to default ({default_val} {self.unit})")
        self.btn_reset.setProperty("class", "SettingReset")
        self.btn_reset.setCursor(Qt.PointingHandCursor)
        self.btn_reset.clicked.connect(self.reset_to_default)
        trailing.addWidget(self.btn_reset)

    def add_to_grid(self, grid: QGridLayout, row: int):
        grid.addWidget(self.title_lbl, row, 0, 1, 1, Qt.AlignVCenter)
        grid.addWidget(self.slider_widget, row, 1, 1, 1)
        grid.addWidget(self.trailing_widget, row, 2, 1, 1, Qt.AlignVCenter | Qt.AlignRight)

    def recolor_icon(self, color: QColor):
        self.btn_reset.setIcon(make_tinted_icon("edit-undo-symbolic", color, 14))

    def _on_slider_changed(self, val: int):
        if self._block_signals:
            return
        self._block_signals = True
        self.spin.setValue(val)
        self._block_signals = False
        self.valueChanged.emit(val)

    def _on_spin_changed(self, val: int):
        if self._block_signals:
            return
        self._block_signals = True
        self.slider.setValue(val)
        self._block_signals = False
        self.valueChanged.emit(val)

    def get_value(self) -> int:
        return self.slider.value()

    def set_value(self, val: int):
        self._block_signals = True
        clamped = max(self.min_val, min(self.max_val, val))
        self.slider.setValue(clamped)
        self.spin.setValue(clamped)
        self._block_signals = False

    def reset_to_default(self):
        self.set_value(self.default_val)
        self.valueChanged.emit(self.default_val)

    def set_range(self, min_val: int, max_val: int):
        self.min_val = min_val
        self.max_val = max_val
        self.slider.setRange(min_val, max_val)
        self.spin.setRange(min_val, max_val)
        self.min_lbl.setText(f"{min_val} {self.unit}")
        self.max_lbl.setText(f"{max_val} {self.unit}")


class FreqSliderSetting(QObject):
    """
    CPU Frequency Slider Setting component with unified two-column grid support:
    - Col 0: Fixed-width label column
    - Col 1: Equal-width horizontal slider with min/max labels and live requested vs actual readout
    - Col 2: Trailing editable value field (GHz, QDoubleSpinBox) and per-slider reset button right-aligned
    """

    valueChanged = Signal(int)  # Emits value in MHz

    def __init__(
        self,
        label: str,
        min_mhz: int,
        max_mhz: int,
        default_mhz: int,
        step_mhz: int = 100,
        label_width: int = 240,
        parent=None,
    ):
        super().__init__(parent)
        self.min_mhz = min_mhz
        self.max_mhz = max_mhz
        self.default_mhz = default_mhz
        self.step_mhz = step_mhz
        self._block_signals = False
        self._last_act_mhz = None

        # Col 0: Label
        self.title_lbl = QLabel(label)
        self.title_lbl.setProperty("class", "FormLabel")
        self.title_lbl.setWordWrap(True)
        self.title_lbl.setFixedWidth(label_width)

        # Col 1: Slider box
        self.slider_widget = QWidget()
        slider_box = QVBoxLayout(self.slider_widget)
        slider_box.setSpacing(2)
        slider_box.setContentsMargins(0, 0, 0, 0)

        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(min_mhz, max_mhz)
        self.slider.setSingleStep(step_mhz)
        self.slider.setPageStep(step_mhz * 2)
        self.slider.setValue(default_mhz)
        self.slider.valueChanged.connect(self._on_slider_changed)
        slider_box.addWidget(self.slider)

        range_row = QHBoxLayout()
        range_row.setContentsMargins(0, 0, 0, 0)
        self.min_lbl = QLabel(f"{min_mhz / 1000.0:.1f} GHz")
        self.min_lbl.setProperty("class", "Footnote")
        range_row.addWidget(self.min_lbl)
        range_row.addStretch()
        self.max_lbl = QLabel(f"{max_mhz / 1000.0:.1f} GHz")
        self.max_lbl.setProperty("class", "Footnote")
        range_row.addWidget(self.max_lbl)
        slider_box.addLayout(range_row)

        # Live requested vs actual readout on its own line below the track
        self.status_lbl = MutedCaptionLabel(f"Cap: {default_mhz / 1000.0:.2f} GHz • Avg: --")
        self.status_lbl.setProperty("class", "Footnote")
        self.status_lbl.setStyleSheet("color: palette(placeholder-text); font-size: 10px;")
        self.status_lbl.setAlignment(Qt.AlignCenter)
        slider_box.addWidget(self.status_lbl)

        # Col 2: Trailing controls right-aligned (DoubleSpinBox in GHz + Reset)
        self.trailing_widget = QWidget()
        self.trailing_widget.setFixedWidth(130)
        trailing = QHBoxLayout(self.trailing_widget)
        trailing.setSpacing(6)
        trailing.setContentsMargins(0, 0, 0, 0)

        self.spin = QDoubleSpinBox()
        self.spin.setRange(min_mhz / 1000.0, max_mhz / 1000.0)
        self.spin.setDecimals(2)
        self.spin.setSingleStep(step_mhz / 1000.0)
        self.spin.setValue(default_mhz / 1000.0)
        self.spin.setSuffix(" GHz")
        self.spin.setFixedWidth(96)
        self.spin.setAlignment(Qt.AlignCenter)
        self.spin.setProperty("class", "SettingSpin")
        self.spin.valueChanged.connect(self._on_spin_changed)
        trailing.addWidget(self.spin)

        self.btn_reset = QToolButton()
        self.btn_reset.setIcon(make_tinted_icon("edit-undo-symbolic", QColor("#ffffff"), 14))
        self.btn_reset.setToolTip(f"Reset to default ({default_mhz / 1000.0:.2f} GHz)")
        self.btn_reset.setProperty("class", "SettingReset")
        self.btn_reset.setCursor(Qt.PointingHandCursor)
        self.btn_reset.clicked.connect(self.reset_to_default)
        trailing.addWidget(self.btn_reset)

    def add_to_grid(self, grid: QGridLayout, row: int):
        grid.addWidget(self.title_lbl, row, 0, 1, 1, Qt.AlignVCenter)
        grid.addWidget(self.slider_widget, row, 1, 1, 1)
        grid.addWidget(self.trailing_widget, row, 2, 1, 1, Qt.AlignVCenter | Qt.AlignRight)

    def recolor_icon(self, color: QColor):
        self.btn_reset.setIcon(make_tinted_icon("edit-undo-symbolic", color, 14))

    def _on_slider_changed(self, val: int):
        if self._block_signals:
            return
        self._block_signals = True
        self.spin.setValue(val / 1000.0)
        self._update_status_lbl()
        self._block_signals = False
        self.valueChanged.emit(val)

    def _on_spin_changed(self, val: float):
        if self._block_signals:
            return
        self._block_signals = True
        mhz = int(round(val * 1000.0))
        self.slider.setValue(mhz)
        self._update_status_lbl()
        self._block_signals = False
        self.valueChanged.emit(mhz)

    def _update_status_lbl(self, act_mhz: int = None):
        if act_mhz is not None:
            self._last_act_mhz = act_mhz
        else:
            act_mhz = self._last_act_mhz

        cap_ghz = self.get_value() / 1000.0
        if act_mhz is not None and act_mhz > 0:
            act_ghz = act_mhz / 1000.0
            self.status_lbl.setText(f"Cap: {cap_ghz:.2f} • Avg: {act_ghz:.2f} GHz")
        else:
            self.status_lbl.setText(f"Cap: {cap_ghz:.2f} GHz • Idle")

    def update_actual_freq(self, act_mhz: int = None):
        self._update_status_lbl(act_mhz)

    def get_value(self) -> int:
        return self.slider.value()

    def set_value(self, mhz: int):
        self._block_signals = True
        clamped = max(self.min_mhz, min(self.max_mhz, mhz))
        self.slider.setValue(clamped)
        self.spin.setValue(clamped / 1000.0)
        self._update_status_lbl()
        self._block_signals = False

    def reset_to_default(self):
        self.set_value(self.default_mhz)
        self.valueChanged.emit(self.default_mhz)

    def set_enabled(self, enabled: bool, reason: str = ""):
        self.slider.setEnabled(enabled)
        self.spin.setEnabled(enabled)
        self.btn_reset.setEnabled(enabled)
        if not enabled and reason:
            self.title_lbl.setToolTip(reason)
            self.slider.setToolTip(reason)
            self.status_lbl.setText(reason)


class ThermalSliderSetting(QObject):
    """
    Thermal Target Slider Setting:
    - Range 69 to 100 (69 = Off, 70-100°C, default 90°C)
    - Live state label: ("Holding", "Reducing PL1", "Recovering", "Off")
    - Per-slider reset button (resets to 90°C)
    """

    valueChanged = Signal(int)  # 69 = Off, 70-100 = Target in °C

    def __init__(self, label: str = "Throttle at", default_val: int = 90, label_width: int = 240, parent=None):
        super().__init__(parent)
        self.default_val = default_val
        self._block_signals = False

        # Col 0: Label
        self.title_lbl = QLabel(label)
        self.title_lbl.setProperty("class", "FormLabel")
        self.title_lbl.setWordWrap(True)
        self.title_lbl.setFixedWidth(label_width)

        # Col 1: Slider box
        self.slider_widget = QWidget()
        slider_box = QVBoxLayout(self.slider_widget)
        slider_box.setSpacing(2)
        slider_box.setContentsMargins(0, 0, 0, 0)

        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(69, 100)
        self.slider.setValue(default_val)
        self.slider.valueChanged.connect(self._on_slider_changed)
        slider_box.addWidget(self.slider)

        range_row = QHBoxLayout()
        range_row.setContentsMargins(0, 0, 0, 0)
        self.min_lbl = QLabel("Off")
        self.min_lbl.setProperty("class", "Footnote")
        range_row.addWidget(self.min_lbl)
        range_row.addStretch()
        self.max_lbl = QLabel("100°C")
        self.max_lbl.setProperty("class", "Footnote")
        range_row.addWidget(self.max_lbl)
        slider_box.addLayout(range_row)

        # Live thermal state label on its own line below the track
        self.status_lbl = MutedCaptionLabel("Holding • Target: 90°C")
        self.status_lbl.setProperty("class", "Footnote")
        self.status_lbl.setStyleSheet("color: palette(placeholder-text); font-size: 10px;")
        self.status_lbl.setAlignment(Qt.AlignCenter)
        slider_box.addWidget(self.status_lbl)

        # Col 2: Trailing controls right-aligned (SpinBox + Reset)
        self.trailing_widget = QWidget()
        self.trailing_widget.setFixedWidth(130)
        trailing = QHBoxLayout(self.trailing_widget)
        trailing.setSpacing(6)
        trailing.setContentsMargins(0, 0, 0, 0)

        self.spin = QSpinBox()
        self.spin.setRange(69, 100)
        self.spin.setSpecialValueText("Off")
        self.spin.setValue(default_val)
        self.spin.setSuffix(" °C")
        self.spin.setFixedWidth(96)
        self.spin.setAlignment(Qt.AlignCenter)
        self.spin.setProperty("class", "SettingSpin")
        self.spin.valueChanged.connect(self._on_spin_changed)
        trailing.addWidget(self.spin)

        self.btn_reset = QToolButton()
        self.btn_reset.setIcon(make_tinted_icon("edit-undo-symbolic", QColor("#ffffff"), 14))
        self.btn_reset.setToolTip(f"Reset to default ({default_val}°C)")
        self.btn_reset.setProperty("class", "SettingReset")
        self.btn_reset.setCursor(Qt.PointingHandCursor)
        self.btn_reset.clicked.connect(self.reset_to_default)
        trailing.addWidget(self.btn_reset)

    def add_to_grid(self, grid: QGridLayout, row: int):
        grid.addWidget(self.title_lbl, row, 0, 1, 1, Qt.AlignVCenter)
        grid.addWidget(self.slider_widget, row, 1, 1, 1)
        grid.addWidget(self.trailing_widget, row, 2, 1, 1, Qt.AlignVCenter | Qt.AlignRight)

    def recolor_icon(self, color: QColor):
        self.btn_reset.setIcon(make_tinted_icon("edit-undo-symbolic", color, 14))

    def _on_slider_changed(self, val: int):
        if self._block_signals:
            return
        self._block_signals = True
        self.spin.setValue(val)
        self._update_status_lbl()
        self._block_signals = False
        self.valueChanged.emit(val)

    def _on_spin_changed(self, val: int):
        if self._block_signals:
            return
        self._block_signals = True
        self.slider.setValue(val)
        self._update_status_lbl()
        self._block_signals = False
        self.valueChanged.emit(val)

    def update_state(self, state: str, effective_pl1: float = None):
        self._last_state = state
        self._last_pl1 = effective_pl1
        self._update_status_lbl()

    def _update_status_lbl(self):
        val = self.get_value()
        state = getattr(self, "_last_state", "Holding")
        pl1 = getattr(self, "_last_pl1", None)
        if val <= 69:
            self.status_lbl.setText("Off (Disabled)")
        else:
            pl1_str = f" • PL1: {pl1:.0f}W" if pl1 else ""
            self.status_lbl.setText(f"{state} • Target: {val}°C{pl1_str}")

    def get_value(self) -> int:
        return self.slider.value()

    def set_value(self, val: int):
        self._block_signals = True
        clamped = max(69, min(100, val))
        self.slider.setValue(clamped)
        self.spin.setValue(clamped)
        self._update_status_lbl()
        self._block_signals = False

    def reset_to_default(self):
        self.set_value(self.default_val)
        self.valueChanged.emit(self.default_val)


class CollapsibleSection(QFrame):
    """Collapsible container with a toggle header."""

    def __init__(self, title: str, parent=None, is_expanded: bool = False):
        super().__init__(parent)
        self.setProperty("class", "CardFrame")

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(12, 10, 12, 10)
        self.main_layout.setSpacing(8)

        # Header button
        self.toggle_btn = QToolButton()
        self.toggle_btn.setProperty("class", "SectionToggle")
        self.toggle_btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.toggle_btn.setArrowType(Qt.DownArrow if is_expanded else Qt.RightArrow)
        self.toggle_btn.setText(f" {title}")
        self.toggle_btn.clicked.connect(self._toggle)
        self.main_layout.addWidget(self.toggle_btn)

        # Content area
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(4, 4, 4, 4)
        self.content_layout.setSpacing(10)
        self.content_widget.setVisible(is_expanded)
        self.main_layout.addWidget(self.content_widget)

    def _toggle(self):
        expanded = not self.content_widget.isVisible()
        self.content_widget.setVisible(expanded)
        self.toggle_btn.setArrowType(Qt.DownArrow if expanded else Qt.RightArrow)

    def add_widget(self, widget: QWidget):
        self.content_layout.addWidget(widget)

    def add_layout(self, layout):
        self.content_layout.addLayout(layout)

    @property
    def is_expanded(self) -> bool:
        return self.content_widget.isVisible()


class ThreadIndicatorWidget(QWidget):
    """
    Displays a row of thread indicator chips/dots for hybrid CPU architecture.
    Threads are colored distinctly by P-core / E-core, and dimmed when parked/offline.
    """

    def __init__(self, p_threads: list[int] = None, e_threads: list[int] = None, parent=None):
        super().__init__(parent)
        self.p_threads = p_threads if p_threads is not None else [0, 1, 2, 3]
        self.e_threads = e_threads if e_threads is not None else list(range(4, 12))
        self.all_threads = sorted(self.p_threads + self.e_threads)
        self.online_map = {cpu: True for cpu in self.all_threads}
        self.setFixedHeight(34)
        self.setMouseTracking(True)

    def set_online_map(self, online_map: dict[int, bool]):
        self.online_map.update(online_map)
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        pal = self.palette()
        p_online_col = pal.highlight().color()
        e_online_col = QColor("#00cec9")  # Distinct secondary color for E-cores
        offline_col = pal.mid().color()
        text_dim = pal.placeholderText().color()

        n = len(self.all_threads)
        if n == 0:
            p.end()
            return

        dot_w = 40.0
        dot_h = 24.0
        gap = 6.0
        start_x = 0.0
        y = (self.height() - dot_h) / 2.0

        font = self.font()
        font.setPointSize(9)
        font.setBold(True)
        p.setFont(font)

        for i, cpu in enumerate(self.all_threads):
            x = start_x + i * (dot_w + gap)
            rect = QRectF(x, y, dot_w, dot_h)
            is_p = cpu in self.p_threads
            is_online = self.online_map.get(cpu, True)

            if is_online:
                bg = p_online_col if is_p else e_online_col
                fg = pal.highlightedText().color() if is_p else QColor("#000000")
            else:
                bg = offline_col
                fg = text_dim

            p.setPen(Qt.NoPen)
            p.setBrush(bg)
            p.drawRoundedRect(rect, 6.0, 6.0)

            label = f"P{cpu}" if is_p else f"E{cpu}"
            p.setPen(fg)
            p.drawText(rect, Qt.AlignCenter, label)

        p.end()

    def mouseMoveEvent(self, event):
        dot_w = 40.0
        gap = 6.0
        pos = event.position().x()
        idx = int(pos // (dot_w + gap))
        if 0 <= idx < len(self.all_threads):
            cpu = self.all_threads[idx]
            is_p = cpu in self.p_threads
            is_on = self.online_map.get(cpu, True)
            core_type = "P-core" if is_p else "E-core"
            state = "Online" if is_on else "Offline (Parked)"
            self.setToolTip(f"CPU {cpu} ({core_type}): {state}")
        else:
            self.setToolTip("")
        super().mouseMoveEvent(event)


class SegmentedControl(QFrame):
    """Horizontal segmented button control for profiles with responsive label adaptation."""

    selectionChanged = Signal(str)

    def __init__(self, items: list[tuple]):
        super().__init__()
        self.setProperty("class", "SegmentedControlFrame")
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(2, 2, 2, 2)
        self.layout.setSpacing(4)

        self._items = []
        for item in items:
            if len(item) >= 4:
                self._items.append((item[0], item[1], item[2], item[3]))
            elif len(item) == 3:
                self._items.append((item[0], item[1], item[1], item[2]))
            else:
                self._items.append((item[0], item[1], item[1], ""))

        self._current_mode = -1
        self.buttons: dict[str, QPushButton] = {}
        for key, full_title, compact_title, sub in self._items:
            btn = QPushButton()
            btn.setCheckable(True)
            btn.setProperty("profileKey", key)
            btn.setProperty("class", "SegmentBtn")
            btn.setCursor(Qt.PointingHandCursor)
            btn.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
            btn.clicked.connect(lambda checked, k=key: self._on_btn_clicked(k))
            if sub:
                btn.setToolTip(f"{full_title} ({sub})")
            else:
                btn.setToolTip(full_title)
            self.buttons[key] = btn
            self.layout.addWidget(btn)

        self.set_compact_mode(0)

    def set_compact_mode(self, mode: int):
        if self._current_mode == mode:
            return
        self._current_mode = mode
        for key, full_title, compact_title, sub in self._items:
            btn = self.buttons.get(key)
            if not btn:
                continue
            if mode == 0:
                btn.setText(f"{full_title} ({sub})" if sub else full_title)
            elif mode == 1:
                btn.setText(f"{compact_title} ({sub})" if sub else compact_title)
            else:
                btn.setText(compact_title)

    def _on_btn_clicked(self, key: str):
        self.set_selected(key)
        self.selectionChanged.emit(key)

    def set_selected(self, key: str):
        for k, btn in self.buttons.items():
            btn.setChecked(k == key)
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        self.updateGeometry()


class RevertCountdownDialog(QDialog):
    """Safety countdown dialog: auto-reverts settings after 15s if unconfirmed."""

    def __init__(self, timeout_sec: int = 15, title: str = "Hardware Limits Applied", message: str = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setWindowFlags(Qt.Dialog | Qt.CustomizeWindowHint | Qt.WindowTitleHint)
        self.setFixedSize(420, 190)

        self.remaining = timeout_sec
        self.confirmed = False
        self._default_msg = message or (
            f"Keep these settings? To protect hardware stability, settings will "
            f"automatically revert in {self.remaining} seconds if not confirmed."
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 22, 22, 20)
        layout.setSpacing(16)

        title_lbl = QLabel(title)
        title_lbl.setProperty("class", "SectionTitle")
        layout.addWidget(title_lbl)

        self.msg_lbl = QLabel(self._default_msg)
        self.msg_lbl.setStyleSheet("font-size: 12px; color: palette(window-text); line-height: 1.4;")
        self.msg_lbl.setWordWrap(True)
        layout.addWidget(self.msg_lbl)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self.btn_keep = QPushButton("Keep Changes")
        self.btn_keep.setProperty("class", "ApplyButton")
        self.btn_keep.clicked.connect(self._on_keep)
        btn_row.addWidget(self.btn_keep)

        self.btn_revert = QPushButton(f"Revert Now ({self.remaining}s)")
        self.btn_revert.setProperty("class", "SecondaryButton")
        self.btn_revert.clicked.connect(self._on_revert)
        btn_row.addWidget(self.btn_revert)

        layout.addLayout(btn_row)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(1000)

    def _tick(self):
        self.remaining -= 1
        if "revert in" in self._default_msg:
            updated = re.sub(r"revert in \d+ seconds", f"revert in {self.remaining} seconds", self._default_msg)
            self.msg_lbl.setText(updated)
        self.btn_revert.setText(f"Revert Now ({self.remaining}s)")
        if self.remaining <= 0:
            self.timer.stop()
            self.reject()

    def _on_keep(self):
        self.confirmed = True
        self.timer.stop()
        self.accept()

    def _on_revert(self):
        self.confirmed = False
        self.timer.stop()
        self.reject()
