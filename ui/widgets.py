"""
Custom UI Widgets for HP Control Center
"""

from PySide6.QtWidgets import (
    QFrame,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QSlider,
    QSpinBox,
    QPushButton,
    QToolButton,
    QWidget,
)
from PySide6.QtCore import Qt, Signal


class StatCard(QFrame):
    """Telemetry Card displaying a live metric with status badges."""

    def __init__(self, title: str, initial_value: str, unit: str = "", subtitle: str = ""):
        super().__init__()
        self.setProperty("class", "CardFrame")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(6)

        # Header: Title + Badge
        top_row = QHBoxLayout()
        self.title_lbl = QLabel(title.upper())
        self.title_lbl.setStyleSheet("color: #728096; font-size: 11px; font-weight: bold; letter-spacing: 1px;")
        top_row.addWidget(self.title_lbl)

        self.badge_lbl = QLabel("")
        self.badge_lbl.setStyleSheet(
            "font-size: 10px; font-weight: bold; padding: 2px 6px; border-radius: 4px; "
            "background-color: #1a2230; color: #a0aec0;"
        )
        self.badge_lbl.setVisible(False)
        top_row.addWidget(self.badge_lbl, alignment=Qt.AlignRight)
        layout.addLayout(top_row)

        # Value Row
        val_row = QHBoxLayout()
        val_row.setSpacing(4)
        self.val_lbl = QLabel(initial_value)
        self.val_lbl.setStyleSheet("font-size: 26px; font-weight: 800; color: #ffffff;")
        val_row.addWidget(self.val_lbl)

        if unit:
            self.unit_lbl = QLabel(unit)
            self.unit_lbl.setStyleSheet("font-size: 13px; color: #00e5ff; font-weight: 600; margin-bottom: 4px;")
            self.unit_lbl.setAlignment(Qt.AlignBottom)
            val_row.addWidget(self.unit_lbl)
        val_row.addStretch()
        layout.addLayout(val_row)

        # Subtitle / Status tag
        self.sub_lbl = QLabel(subtitle)
        self.sub_lbl.setStyleSheet("color: #94a3b8; font-size: 11px;")
        layout.addWidget(self.sub_lbl)

    def update_value(self, value_text: str, subtitle_text: str = None, color: str = None, badge_text: str = None, badge_color: str = None):
        self.val_lbl.setText(value_text)
        if subtitle_text is not None:
            self.sub_lbl.setText(subtitle_text)
        if color:
            self.val_lbl.setStyleSheet(f"font-size: 26px; font-weight: 800; color: {color};")
        if badge_text:
            self.badge_lbl.setText(badge_text)
            self.badge_lbl.setVisible(True)
            bg = badge_color or "#1a2230"
            self.badge_lbl.setStyleSheet(
                f"font-size: 10px; font-weight: bold; padding: 2px 6px; border-radius: 4px; "
                f"background-color: {bg}; color: #ffffff;"
            )
        elif badge_text is not None:
            self.badge_lbl.setVisible(False)


class SliderSetting(QFrame):
    """
    Slider setting with:
    - Title
    - Small fixed-width editable spinbox next to label
    - Per-slider reset-to-default button
    - Full-width horizontal slider
    - Min and Max numeric labels at the ends
    """

    valueChanged = Signal(int)

    def __init__(self, label: str, min_val: int, max_val: int, default_val: int, unit: str = "W"):
        super().__init__()
        self.min_val = min_val
        self.max_val = max_val
        self.default_val = default_val
        self.unit = unit
        self._block_signals = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 8)
        layout.setSpacing(4)

        # Header Row: [Label] ... [SpinBox] [Reset Button]
        header = QHBoxLayout()
        header.setSpacing(8)

        self.title_lbl = QLabel(label)
        self.title_lbl.setStyleSheet("font-weight: 600; color: #d0d7e2; font-size: 13px;")
        header.addWidget(self.title_lbl)
        header.addStretch()

        # Fixed-width editable spinbox
        self.spin = QSpinBox()
        self.spin.setRange(min_val, max_val)
        self.spin.setValue(default_val)
        self.spin.setSuffix(f" {self.unit}")
        self.spin.setFixedWidth(84)
        self.spin.setAlignment(Qt.AlignCenter)
        self.spin.setStyleSheet(
            "QSpinBox { background-color: #161c26; color: #00e5ff; font-weight: bold; "
            "border: 1px solid #233147; border-radius: 4px; padding: 3px; font-size: 12px; }"
            "QSpinBox:focus { border: 1px solid #00e5ff; }"
        )
        self.spin.valueChanged.connect(self._on_spin_changed)
        header.addWidget(self.spin)

        # Per-slider reset button
        self.btn_reset = QToolButton()
        self.btn_reset.setText("↺")
        self.btn_reset.setToolTip(f"Reset to default ({default_val} {self.unit})")
        self.btn_reset.setStyleSheet(
            "QToolButton { background-color: #1a2230; color: #718096; border: 1px solid #233147; "
            "border-radius: 4px; font-weight: bold; padding: 3px 6px; }"
            "QToolButton:hover { color: #00e5ff; border: 1px solid #00e5ff; background-color: #202b3d; }"
        )
        self.btn_reset.clicked.connect(self.reset_to_default)
        header.addWidget(self.btn_reset)

        layout.addLayout(header)

        # Slider Row
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(min_val, max_val)
        self.slider.setValue(default_val)
        self.slider.valueChanged.connect(self._on_slider_changed)
        layout.addWidget(self.slider)

        # Min / Max labels at the ends
        range_row = QHBoxLayout()
        self.min_lbl = QLabel(f"{min_val} {unit}")
        self.min_lbl.setStyleSheet("color: #4a5568; font-size: 10px; font-weight: 500;")
        range_row.addWidget(self.min_lbl)
        range_row.addStretch()
        self.max_lbl = QLabel(f"{max_val} {unit}")
        self.max_lbl.setStyleSheet("color: #4a5568; font-size: 10px; font-weight: 500;")
        range_row.addWidget(self.max_lbl)
        layout.addLayout(range_row)

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
        self.toggle_btn.setStyleSheet(
            "QToolButton { border: none; font-weight: bold; font-size: 13px; color: #ffffff; "
            "text-align: left; background: transparent; padding: 2px 0px; }"
            "QToolButton:hover { color: #00e5ff; }"
        )
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


class SegmentedControl(QFrame):
    """Horizontal segmented button control for profiles."""

    selectionChanged = Signal(str)

    def __init__(self, items: list[tuple[str, str, str]]):
        """
        items: list of (key, title, subtitle)
        e.g., [("ultra_gaming", "Ultra Gaming", "25W"), ("balanced", "Daily Balanced", "24W"), ...]
        """
        super().__init__()
        self.setStyleSheet(
            "QFrame { background-color: #10141d; border: 1px solid #1a2230; border-radius: 8px; padding: 3px; }"
        )
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(2, 2, 2, 2)
        self.layout.setSpacing(4)

        self.buttons: dict[str, QPushButton] = {}
        for key, title, sub in items:
            btn = QPushButton(f"{title} ({sub})" if sub else title)
            btn.setCheckable(True)
            btn.setProperty("profileKey", key)
            btn.setStyleSheet(
                "QPushButton { background-color: transparent; border: none; border-radius: 6px; "
                "color: #8c9ba5; font-weight: 600; padding: 8px 14px; font-size: 12px; }"
                "QPushButton:hover { background-color: #171d2a; color: #ffffff; }"
                "QPushButton:checked { background-color: #1e2838; color: #00e5ff; font-weight: bold; border: 1px solid #00e5ff; }"
            )
            btn.clicked.connect(lambda checked, k=key: self._on_btn_clicked(k))
            self.buttons[key] = btn
            self.layout.addWidget(btn)

    def _on_btn_clicked(self, key: str):
        self.set_selected(key)
        self.selectionChanged.emit(key)

    def set_selected(self, key: str):
        for k, btn in self.buttons.items():
            btn.setChecked(k == key)
            if k == key:
                if k == "ultra_gaming":
                    btn.setStyleSheet(
                        "QPushButton { background-color: #27141d; color: #ff3366; font-weight: bold; border: 1px solid #ff3366; border-radius: 6px; padding: 8px 14px; }"
                    )
                elif k == "balanced":
                    btn.setStyleSheet(
                        "QPushButton { background-color: #10212e; color: #00e5ff; font-weight: bold; border: 1px solid #00e5ff; border-radius: 6px; padding: 8px 14px; }"
                    )
                elif k == "eco_quiet":
                    btn.setStyleSheet(
                        "QPushButton { background-color: #122419; color: #00e676; font-weight: bold; border: 1px solid #00e676; border-radius: 6px; padding: 8px 14px; }"
                    )
                else:
                    btn.setStyleSheet(
                        "QPushButton { background-color: #202736; color: #f6ad55; font-weight: bold; border: 1px solid #f6ad55; border-radius: 6px; padding: 8px 14px; }"
                    )
            else:
                btn.setStyleSheet(
                    "QPushButton { background-color: transparent; border: none; border-radius: 6px; "
                    "color: #8c9ba5; font-weight: 600; padding: 8px 14px; font-size: 12px; }"
                    "QPushButton:hover { background-color: #171d2a; color: #ffffff; }"
                )
