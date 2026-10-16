"""
Custom UI Widgets for HP Control Center
"""

from PySide6.QtWidgets import (
    QFrame,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QSlider,
)
from PySide6.QtCore import Qt, Signal


class StatCard(QFrame):
    """Telemetry Card displaying a live metric."""

    def __init__(self, title: str, initial_value: str, unit: str = "", subtitle: str = ""):
        super().__init__()
        self.setProperty("class", "CardFrame")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(4)

        # Title
        self.title_lbl = QLabel(title.upper())
        self.title_lbl.setStyleSheet("color: #728096; font-size: 11px; font-weight: bold; letter-spacing: 1px;")
        layout.addWidget(self.title_lbl)

        # Value Row
        val_row = QHBoxLayout()
        val_row.setSpacing(4)
        self.val_lbl = QLabel(initial_value)
        self.val_lbl.setStyleSheet("font-size: 22px; font-weight: 800; color: #ffffff;")
        val_row.addWidget(self.val_lbl)

        if unit:
            self.unit_lbl = QLabel(unit)
            self.unit_lbl.setStyleSheet("font-size: 13px; color: #00e5ff; font-weight: 600; margin-bottom: 2px;")
            self.unit_lbl.setAlignment(Qt.AlignBottom)
            val_row.addWidget(self.unit_lbl)
        val_row.addStretch()
        layout.addLayout(val_row)

        # Subtitle / Status tag
        self.sub_lbl = QLabel(subtitle)
        self.sub_lbl.setStyleSheet("color: #94a3b8; font-size: 11px;")
        layout.addWidget(self.sub_lbl)

    def update_value(self, value_text: str, subtitle_text: str = None, color: str = None):
        self.val_lbl.setText(value_text)
        if subtitle_text is not None:
            self.sub_lbl.setText(subtitle_text)
        if color:
            self.val_lbl.setStyleSheet(f"font-size: 22px; font-weight: 800; color: {color};")


class SliderSetting(QFrame):
    """Horizontal setting with title, slider, and live numeric badge."""

    valueChanged = Signal(int)

    def __init__(self, label: str, min_val: int, max_val: int, default_val: int, unit: str = "W"):
        super().__init__()
        self.unit = unit

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 8)
        layout.setSpacing(6)

        # Label + Value Badge
        header_layout = QHBoxLayout()
        self.title_lbl = QLabel(label)
        self.title_lbl.setStyleSheet("font-weight: 600; color: #d0d7e2;")
        header_layout.addWidget(self.title_lbl)

        self.val_badge = QLabel(f"{default_val} {self.unit}")
        self.val_badge.setStyleSheet(
            "background-color: #1a2230; color: #00e5ff; font-weight: bold; "
            "padding: 2px 8px; border-radius: 4px; border: 1px solid #233147;"
        )
        header_layout.addWidget(self.val_badge)
        layout.addLayout(header_layout)

        # Slider
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(min_val, max_val)
        self.slider.setValue(default_val)
        self.slider.valueChanged.connect(self._on_slider_changed)
        layout.addWidget(self.slider)

    def _on_slider_changed(self, val: int):
        self.val_badge.setText(f"{val} {self.unit}")
        self.valueChanged.emit(val)

    def get_value(self) -> int:
        return self.slider.value()

    def set_value(self, val: int):
        self.slider.setValue(val)
        self.val_badge.setText(f"{val} {self.unit}")
