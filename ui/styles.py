"""
Control Center - Dynamic System Palette Theming
Follows active KDE Plasma / Qt system palette in real-time.
Uses Qt palette roles (Highlight, Window, Button, Base, Mid, etc.) for full dark/light and custom accent support.
"""

# Semantic Status Colors (Fixed across themes for hardware safety & state clarity)
# These never use the palette accent so that OK, Warning, and Critical states remain unambiguous.
STATUS_OK = "#27ae60"        # Green: Daemon online, AC connected, thermal safe, normal state
STATUS_WARN = "#e67e22"      # Amber: Thermal throttle, battery power, unsaved modifications, >80°C
STATUS_CRITICAL = "#d63031"  # Red: >90°C emergency, BD PROCHOT warning, daemon offline/error


def get_native_stylesheet(accent_tint: str = "rgba(61, 174, 233, 0.15)") -> str:
    return f"""
QMainWindow {{
    background-color: palette(window);
    color: palette(window-text);
}}

QWidget {{
    color: palette(window-text);
}}

QDialog {{
    background-color: palette(window);
    color: palette(window-text);
}}

/* Sidebar */
QFrame#SidebarFrame {{
    background-color: palette(window);
    border-right: 1px solid palette(mid);
}}

QPushButton.MenuCollapseBtn {{
    background: transparent;
    border: none;
    font-weight: 800;
    color: palette(window-text);
    text-align: left;
    padding: 8px 12px;
    font-size: 13px;
}}
QPushButton.MenuCollapseBtn:hover {{
    color: palette(highlight);
}}

QPushButton.NavBtn {{
    background-color: transparent;
    border: none;
    border-left: 3px solid transparent;
    border-radius: 6px;
    padding: 10px 14px;
    font-weight: 600;
    font-size: 13px;
    color: palette(window-text);
    text-align: left;
}}
QPushButton.NavBtn:hover {{
    background-color: palette(alternate-base);
    color: palette(window-text);
}}

QPushButton.NavBtnActive {{
    background-color: {accent_tint};
    border-left: 3px solid palette(highlight);
    border-radius: 6px;
    padding: 10px 14px;
    font-weight: bold;
    font-size: 13px;
    color: palette(window-text);
    text-align: left;
}}

/* Scroll area */
QScrollArea {{
    background-color: transparent;
    border: none;
}}
QScrollBar:vertical {{
    background: palette(window);
    width: 8px;
    margin: 0px;
    border-radius: 4px;
}}
QScrollBar::handle:vertical {{
    background: palette(mid);
    min-height: 20px;
    border-radius: 4px;
}}
QScrollBar::handle:vertical:hover {{
    background: palette(highlight);
}}

/* Card Containers - Slightly lighter than window background with subtle 1px border */
QFrame.CardFrame {{
    background-color: palette(button);
    border: 1px solid palette(mid);
    border-radius: 12px;
    padding: 12px;
}}
QFrame.CardFrame:hover {{
    border: 1px solid palette(dark);
}}

/* Segmented Profile Bar */
QFrame.SegmentedControlFrame {{
    background-color: palette(base);
    border: 1px solid palette(mid);
    border-radius: 8px;
    padding: 3px;
}}

QPushButton.SegmentBtn {{
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 6px;
    color: palette(window-text);
    font-weight: 600;
    padding: 7px 18px;
    font-size: 12px;
    min-width: 130px;
}}
QPushButton.SegmentBtn:hover {{
    background-color: palette(alternate-base);
    color: palette(window-text);
}}
QPushButton.SegmentBtn:checked {{
    background-color: palette(highlight);
    color: palette(highlighted-text);
    font-weight: 600;
    border: 1px solid palette(highlight);
}}

/* Sliders */
QSlider::groove:horizontal {{
    height: 6px;
    background: palette(midlight);
    border-radius: 3px;
}}
QSlider::sub-page:horizontal {{
    background: palette(highlight);
    border-radius: 3px;
}}
QSlider::add-page:horizontal {{
    background: palette(midlight);
    border-radius: 3px;
}}
QSlider::handle:horizontal {{
    background: #ffffff;
    border: 3px solid palette(highlight);
    width: 16px;
    height: 16px;
    margin: -5px 0;
    border-radius: 8px;
}}
QSlider::handle:horizontal:hover {{
    background: #ffffff;
    border: 3px solid palette(highlight);
    width: 18px;
    height: 18px;
    margin: -6px 0;
    border-radius: 9px;
}}
QSlider::handle:horizontal:pressed {{
    background: palette(highlight);
    border: 3px solid #ffffff;
}}

/* SpinBox */
QSpinBox {{
    background-color: palette(base);
    color: palette(text);
    font-weight: bold;
    border: 1px solid palette(mid);
    border-radius: 4px;
    padding: 3px;
    font-size: 12px;
}}
QSpinBox:focus {{
    border: 1px solid palette(highlight);
}}

/* ToolButtons */
QToolButton.SettingReset {{
    background-color: palette(base);
    color: palette(button-text);
    border: 1px solid palette(mid);
    border-radius: 4px;
    font-weight: bold;
    padding: 4px 6px;
}}
QToolButton.SettingReset:hover {{
    color: palette(highlight);
    border: 1px solid palette(highlight);
}}

QToolButton.SectionToggle {{
    border: none;
    font-weight: bold;
    font-size: 14px;
    color: palette(window-text);
    text-align: left;
    background: transparent;
    padding: 2px 0px;
}}
QToolButton.SectionToggle:hover {{
    color: palette(highlight);
}}

/* Checkboxes & Toggle Switches */
QCheckBox {{
    spacing: 8px;
    font-weight: 500;
}}
QCheckBox::indicator {{
    width: 18px;
    height: 18px;
    border-radius: 4px;
    border: 1px solid palette(mid);
    background-color: palette(base);
}}
QCheckBox::indicator:checked {{
    background-color: palette(highlight);
    border: 1px solid palette(highlight);
}}

ToggleSwitch {{
    background: transparent;
    border: none;
    font-weight: 500;
}}
ToggleSwitch::indicator {{
    width: 0px;
    height: 0px;
}}

/* Combo Box */
QComboBox {{
    background-color: palette(base);
    border: 1px solid palette(mid);
    border-radius: 6px;
    padding: 6px 12px;
    color: palette(text);
    font-weight: 500;
}}
QComboBox:hover {{
    border: 1px solid palette(highlight);
}}
QComboBox:disabled {{
    background-color: palette(window);
    color: palette(placeholder-text);
    border: 1px solid palette(mid);
}}
QComboBox QAbstractItemView {{
    background-color: palette(base);
    border: 1px solid palette(mid);
    selection-background-color: palette(highlight);
    selection-color: palette(highlighted-text);
}}

/* Line Edit */
QLineEdit {{
    background-color: palette(base);
    border: 1px solid palette(mid);
    border-radius: 6px;
    padding: 6px 10px;
    color: palette(text);
}}
QLineEdit:focus {{
    border: 1px solid palette(highlight);
}}

/* Action Buttons */
QPushButton.ApplyButton {{
    background-color: palette(highlight);
    color: palette(highlighted-text);
    font-weight: bold;
    font-size: 13px;
    border: 1px solid palette(highlight);
    border-radius: 6px;
    padding: 8px 20px;
}}
QPushButton.ApplyButton:hover {{
    opacity: 0.9;
}}
QPushButton.ApplyButton:disabled {{
    background-color: palette(mid);
    color: palette(placeholder-text);
    border-color: palette(mid);
}}

QPushButton.SecondaryButton {{
    background-color: palette(base);
    border: 1px solid palette(mid);
    border-radius: 6px;
    padding: 8px 16px;
    color: palette(button-text);
    font-weight: 600;
}}
QPushButton.SecondaryButton:hover {{
    border-color: palette(highlight);
    color: palette(highlight);
}}

/* Typography */
QLabel.SectionTitle {{
    font-size: 15px;
    font-weight: 700;
    color: palette(window-text);
}}
QLabel.FormLabel {{
    font-size: 12px;
    font-weight: 600;
    color: palette(placeholder-text);
}}
QLabel.Value {{
    font-size: 12px;
    font-weight: 700;
    color: palette(window-text);
}}
QLabel.Footnote {{
    font-size: 12px;
    color: palette(placeholder-text);
    line-height: 1.4;
}}
QLabel.CardUnitAccent {{
    font-size: 13px;
    color: palette(highlight);
    font-weight: bold;
    margin-bottom: 4px;
}}
QLabel.CoolingFanAccent {{
    color: palette(highlight);
    font-weight: bold;
}}

/* Text Edit / Logs */
QTextEdit {{
    background-color: palette(base);
    color: palette(text);
    font-family: monospace;
    font-size: 11px;
    border: 1px solid palette(mid);
    border-radius: 6px;
}}

/* Code Block */
QLabel.CodeBlock {{
    background-color: palette(alternate-base);
    color: palette(text);
    padding: 10px;
    border-radius: 6px;
    font-family: monospace;
    font-size: 11px;
    border: 1px solid palette(mid);
}}

/* Status Bar Frame with 1px top separator */
QFrame#StatusBarFrame {{
    border-top: 1px solid palette(mid);
    padding-top: 8px;
    margin-top: 4px;
}}

/* Warning alert box */
QFrame.WarningBox {{
    background-color: rgba(214, 48, 49, 0.15);
    border: 1px solid #d63031;
    border-radius: 8px;
    padding: 10px;
}}
"""

NATIVE_PALETTE_THEME = get_native_stylesheet()
CYBER_DARK_THEME = NATIVE_PALETTE_THEME
THEMES = {
    "Follow System (KDE / Qt Palette)": NATIVE_PALETTE_THEME,
}
