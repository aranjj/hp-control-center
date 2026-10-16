"""
Theme Stylesheets for HP Control Center
Themes:
1. Cyberpunk Dark (Default) - Electric cyan & deep navy
2. Obsidian Neon - OLED pitch black with neon violet / magenta
3. Breeze Dark Native - KDE Plasma Breeze Dark palette with Breeze blue
"""

# ==============================================================================
# 1. CYBERPUNK DARK (DEFAULT)
# ==============================================================================
CYBER_DARK_THEME = """
QMainWindow {
    background-color: #0b0d11;
    color: #e0e6ed;
}

QWidget {
    font-family: "Inter", "Segoe UI", "Cantarell", "Ubuntu", sans-serif;
    color: #cfd7e3;
    font-size: 13px;
}

QDialog {
    background-color: #0f1218;
    color: #cfd7e3;
}

/* Sidebar */
QFrame#SidebarFrame {
    background-color: #0d1017;
    border-right: 1px solid #1a2230;
}

QPushButton.MenuCollapseBtn {
    background: transparent;
    border: none;
    font-weight: 800;
    color: #a0aec0;
    text-align: left;
    padding: 8px 12px;
    font-size: 13px;
}
QPushButton.MenuCollapseBtn:hover {
    color: #00e5ff;
}

QPushButton.NavBtn {
    background-color: transparent;
    border: none;
    border-radius: 8px;
    padding: 10px 14px;
    font-weight: 600;
    font-size: 13px;
    color: #7d8b9f;
    text-align: left;
}
QPushButton.NavBtn:hover {
    background-color: #151a24;
    color: #ffffff;
}

QPushButton.NavBtnActive {
    background-color: #172130;
    border-left: 3px solid #00e5ff;
    border-radius: 6px;
    padding: 10px 14px;
    font-weight: bold;
    font-size: 13px;
    color: #00e5ff;
    text-align: left;
}

/* Scroll area */
QScrollArea {
    background-color: transparent;
    border: none;
}
QScrollBar:vertical {
    background: #0f1218;
    width: 6px;
    margin: 0px;
    border-radius: 3px;
}
QScrollBar::handle:vertical {
    background: #252d3d;
    min-height: 20px;
    border-radius: 3px;
}
QScrollBar::handle:vertical:hover {
    background: #00e5ff;
}

/* Card Containers */
QFrame.CardFrame {
    background-color: #121620;
    border: 1px solid #1c2331;
    border-radius: 10px;
    padding: 14px;
}
QFrame.CardFrame:hover {
    border: 1px solid #283344;
}

/* Segmented Profile Bar */
QFrame.SegmentedControlFrame {
    background-color: #10141d;
    border: 1px solid #1a2230;
    border-radius: 8px;
    padding: 3px;
}

QPushButton.SegmentBtn {
    background-color: transparent;
    border: none;
    border-radius: 6px;
    color: #8c9ba5;
    font-weight: 600;
    padding: 8px 14px;
    font-size: 12px;
}
QPushButton.SegmentBtn:hover {
    background-color: #171d2a;
    color: #ffffff;
}
QPushButton.SegmentBtn[profileKey="ultra_gaming"]:checked {
    background-color: #27141d;
    color: #ff3366;
    font-weight: bold;
    border: 1px solid #ff3366;
}
QPushButton.SegmentBtn[profileKey="balanced"]:checked {
    background-color: #10212e;
    color: #00e5ff;
    font-weight: bold;
    border: 1px solid #00e5ff;
}
QPushButton.SegmentBtn[profileKey="eco_quiet"]:checked {
    background-color: #122419;
    color: #00e676;
    font-weight: bold;
    border: 1px solid #00e676;
}
QPushButton.SegmentBtn[profileKey="custom"]:checked {
    background-color: #202736;
    color: #f6ad55;
    font-weight: bold;
    border: 1px solid #f6ad55;
}

/* Sliders */
QSlider::groove:horizontal {
    height: 6px;
    background: #19202c;
    border-radius: 3px;
}
QSlider::sub-page:horizontal {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0091ea, stop:1 #00e5ff);
    border-radius: 3px;
}
QSlider::handle:horizontal {
    background: #ffffff;
    border: 2px solid #00e5ff;
    width: 14px;
    height: 14px;
    margin: -4px 0;
    border-radius: 7px;
}
QSlider::handle:horizontal:hover {
    background: #00e5ff;
    border: 2px solid #ffffff;
}

/* SpinBox */
QSpinBox {
    background-color: #161c26;
    color: #00e5ff;
    font-weight: bold;
    border: 1px solid #233147;
    border-radius: 4px;
    padding: 3px;
    font-size: 12px;
}
QSpinBox:focus {
    border: 1px solid #00e5ff;
}

/* ToolButtons */
QToolButton.SettingReset {
    background-color: #1a2230;
    color: #718096;
    border: 1px solid #233147;
    border-radius: 4px;
    font-weight: bold;
    padding: 3px 6px;
}
QToolButton.SettingReset:hover {
    color: #00e5ff;
    border: 1px solid #00e5ff;
    background-color: #202b3d;
}

QToolButton.SectionToggle {
    border: none;
    font-weight: bold;
    font-size: 13px;
    color: #ffffff;
    text-align: left;
    background: transparent;
    padding: 2px 0px;
}
QToolButton.SectionToggle:hover {
    color: #00e5ff;
}

/* Checkboxes */
QCheckBox {
    spacing: 8px;
    font-weight: 500;
}
QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border-radius: 4px;
    border: 1px solid #2a3446;
    background-color: #141822;
}
QCheckBox::indicator:checked {
    background-color: #00e5ff;
    border: 1px solid #00e5ff;
}

/* Combo Box */
QComboBox {
    background-color: #151923;
    border: 1px solid #232c3d;
    border-radius: 6px;
    padding: 6px 12px;
    color: #e0e6ed;
    font-weight: 500;
}
QComboBox:hover {
    border: 1px solid #00e5ff;
}
QComboBox QAbstractItemView {
    background-color: #151923;
    border: 1px solid #232c3d;
    selection-background-color: #00e5ff;
    selection-color: #0b0d11;
}

/* Action Buttons */
QPushButton.ApplyButton {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0091ea, stop:1 #00e5ff);
    color: #06090e;
    font-weight: bold;
    font-size: 13px;
    border: none;
    border-radius: 6px;
    padding: 8px 20px;
}
QPushButton.ApplyButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #00b0ff, stop:1 #18ffff);
}
QPushButton.ApplyButton:disabled {
    background: #1c2331;
    color: #556275;
}

QPushButton.SecondaryButton {
    background-color: #171c26;
    border: 1px solid #242e40;
    border-radius: 6px;
    padding: 8px 16px;
    color: #a0aec0;
    font-weight: 600;
}
QPushButton.SecondaryButton:hover {
    background-color: #1f2736;
    border: 1px solid #4a5568;
    color: #ffffff;
}

/* Text & Accent Labels */
QLabel.CardUnitAccent {
    font-size: 13px;
    color: #00e5ff;
    font-weight: 600;
    margin-bottom: 4px;
}
QLabel.CoolingFanAccent {
    color: #00e5ff;
    font-weight: bold;
}

/* Text Edit / Logs */
QTextEdit {
    background-color: #0b0d11;
    color: #a0aec0;
    font-family: monospace;
    font-size: 11px;
    border: 1px solid #1f2736;
    border-radius: 6px;
}

/* Code Block */
QLabel.CodeBlock {
    background: #0f1218;
    padding: 10px;
    border-radius: 6px;
    font-family: monospace;
    color: #00e5ff;
    font-size: 11px;
    border: 1px solid #1a2230;
}

/* Warning alert box */
QFrame.WarningBox {
    background-color: #241318;
    border: 1px solid #5a1c2a;
    border-radius: 8px;
    padding: 10px;
}
"""

# ==============================================================================
# 2. OBSIDIAN NEON (OLED PITCH BLACK + VIOLET / MAGENTA NEON)
# ==============================================================================
OBSIDIAN_NEON_THEME = """
QMainWindow {
    background-color: #030305;
    color: #f1f5f9;
}

QWidget {
    font-family: "Inter", "Segoe UI", "Cantarell", "Ubuntu", sans-serif;
    color: #e2e8f0;
    font-size: 13px;
}

QDialog {
    background-color: #08080d;
    color: #e2e8f0;
}

/* Sidebar */
QFrame#SidebarFrame {
    background-color: #08080c;
    border-right: 1px solid #1a1628;
}

QPushButton.MenuCollapseBtn {
    background: transparent;
    border: none;
    font-weight: 800;
    color: #94a3b8;
    text-align: left;
    padding: 8px 12px;
    font-size: 13px;
}
QPushButton.MenuCollapseBtn:hover {
    color: #c084fc;
}

QPushButton.NavBtn {
    background-color: transparent;
    border: none;
    border-radius: 8px;
    padding: 10px 14px;
    font-weight: 600;
    font-size: 13px;
    color: #94a3b8;
    text-align: left;
}
QPushButton.NavBtn:hover {
    background-color: #171124;
    color: #ffffff;
}

QPushButton.NavBtnActive {
    background-color: #221438;
    border-left: 3px solid #c084fc;
    border-radius: 6px;
    padding: 10px 14px;
    font-weight: bold;
    font-size: 13px;
    color: #c084fc;
    text-align: left;
}

/* Scroll area */
QScrollArea {
    background-color: transparent;
    border: none;
}
QScrollBar:vertical {
    background: #08080c;
    width: 6px;
    margin: 0px;
    border-radius: 3px;
}
QScrollBar::handle:vertical {
    background: #2a1f44;
    min-height: 20px;
    border-radius: 3px;
}
QScrollBar::handle:vertical:hover {
    background: #c084fc;
}

/* Card Containers */
QFrame.CardFrame {
    background-color: #0c0a14;
    border: 1px solid #1f1830;
    border-radius: 10px;
    padding: 14px;
}
QFrame.CardFrame:hover {
    border: 1px solid #362955;
}

/* Segmented Profile Bar */
QFrame.SegmentedControlFrame {
    background-color: #08060f;
    border: 1px solid #1f1830;
    border-radius: 8px;
    padding: 3px;
}

QPushButton.SegmentBtn {
    background-color: transparent;
    border: none;
    border-radius: 6px;
    color: #94a3b8;
    font-weight: 600;
    padding: 8px 14px;
    font-size: 12px;
}
QPushButton.SegmentBtn:hover {
    background-color: #171124;
    color: #ffffff;
}
QPushButton.SegmentBtn[profileKey="ultra_gaming"]:checked {
    background-color: #2d1020;
    color: #ff3366;
    font-weight: bold;
    border: 1px solid #ff3366;
}
QPushButton.SegmentBtn[profileKey="balanced"]:checked {
    background-color: #221438;
    color: #c084fc;
    font-weight: bold;
    border: 1px solid #c084fc;
}
QPushButton.SegmentBtn[profileKey="eco_quiet"]:checked {
    background-color: #0f2416;
    color: #00e676;
    font-weight: bold;
    border: 1px solid #00e676;
}
QPushButton.SegmentBtn[profileKey="custom"]:checked {
    background-color: #271d34;
    color: #f6ad55;
    font-weight: bold;
    border: 1px solid #f6ad55;
}

/* Sliders */
QSlider::groove:horizontal {
    height: 6px;
    background: #171226;
    border-radius: 3px;
}
QSlider::sub-page:horizontal {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #9333ea, stop:1 #c084fc);
    border-radius: 3px;
}
QSlider::handle:horizontal {
    background: #ffffff;
    border: 2px solid #c084fc;
    width: 14px;
    height: 14px;
    margin: -4px 0;
    border-radius: 7px;
}
QSlider::handle:horizontal:hover {
    background: #c084fc;
    border: 2px solid #ffffff;
}

/* SpinBox */
QSpinBox {
    background-color: #120d20;
    color: #c084fc;
    font-weight: bold;
    border: 1px solid #2b1d46;
    border-radius: 4px;
    padding: 3px;
    font-size: 12px;
}
QSpinBox:focus {
    border: 1px solid #c084fc;
}

/* ToolButtons */
QToolButton.SettingReset {
    background-color: #161026;
    color: #94a3b8;
    border: 1px solid #2d1f4b;
    border-radius: 4px;
    font-weight: bold;
    padding: 3px 6px;
}
QToolButton.SettingReset:hover {
    color: #c084fc;
    border: 1px solid #c084fc;
    background-color: #241940;
}

QToolButton.SectionToggle {
    border: none;
    font-weight: bold;
    font-size: 13px;
    color: #ffffff;
    text-align: left;
    background: transparent;
    padding: 2px 0px;
}
QToolButton.SectionToggle:hover {
    color: #c084fc;
}

/* Checkboxes */
QCheckBox {
    spacing: 8px;
    font-weight: 500;
}
QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border-radius: 4px;
    border: 1px solid #332352;
    background-color: #120d20;
}
QCheckBox::indicator:checked {
    background-color: #c084fc;
    border: 1px solid #c084fc;
}

/* Combo Box */
QComboBox {
    background-color: #120e20;
    border: 1px solid #281d42;
    border-radius: 6px;
    padding: 6px 12px;
    color: #f1f5f9;
    font-weight: 500;
}
QComboBox:hover {
    border: 1px solid #c084fc;
}
QComboBox QAbstractItemView {
    background-color: #120e20;
    border: 1px solid #281d42;
    selection-background-color: #c084fc;
    selection-color: #08080c;
}

/* Action Buttons */
QPushButton.ApplyButton {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #7e22ce, stop:1 #c084fc);
    color: #ffffff;
    font-weight: bold;
    font-size: 13px;
    border: none;
    border-radius: 6px;
    padding: 8px 20px;
}
QPushButton.ApplyButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #9333ea, stop:1 #e9d5ff);
}
QPushButton.ApplyButton:disabled {
    background: #1c152d;
    color: #584877;
}

QPushButton.SecondaryButton {
    background-color: #161026;
    border: 1px solid #2d1f4b;
    border-radius: 6px;
    padding: 8px 16px;
    color: #c4b5fd;
    font-weight: 600;
}
QPushButton.SecondaryButton:hover {
    background-color: #241940;
    border: 1px solid #7c3aed;
    color: #ffffff;
}

/* Text & Accent Labels */
QLabel.CardUnitAccent {
    font-size: 13px;
    color: #c084fc;
    font-weight: 600;
    margin-bottom: 4px;
}
QLabel.CoolingFanAccent {
    color: #c084fc;
    font-weight: bold;
}

/* Text Edit / Logs */
QTextEdit {
    background-color: #06050a;
    color: #c4b5fd;
    font-family: monospace;
    font-size: 11px;
    border: 1px solid #1f1830;
    border-radius: 6px;
}

/* Code Block */
QLabel.CodeBlock {
    background: #08060f;
    padding: 10px;
    border-radius: 6px;
    font-family: monospace;
    color: #c084fc;
    font-size: 11px;
    border: 1px solid #1f1830;
}

/* Warning alert box */
QFrame.WarningBox {
    background-color: #2a0e18;
    border: 1px solid #63192e;
    border-radius: 8px;
    padding: 10px;
}
"""

# ==============================================================================
# 3. BREEZE DARK NATIVE (KDE PLASMA PALETTE)
# ==============================================================================
BREEZE_DARK_THEME = """
QMainWindow {
    background-color: #232629;
    color: #eff0f1;
}

QWidget {
    font-family: "Noto Sans", "Cantarell", "Ubuntu", sans-serif;
    color: #eff0f1;
    font-size: 13px;
}

QDialog {
    background-color: #232629;
    color: #eff0f1;
}

/* Sidebar */
QFrame#SidebarFrame {
    background-color: #1e2023;
    border-right: 1px solid #31363b;
}

QPushButton.MenuCollapseBtn {
    background: transparent;
    border: none;
    font-weight: 800;
    color: #bdc3c7;
    text-align: left;
    padding: 8px 12px;
    font-size: 13px;
}
QPushButton.MenuCollapseBtn:hover {
    color: #3daee9;
}

QPushButton.NavBtn {
    background-color: transparent;
    border: none;
    border-radius: 6px;
    padding: 10px 14px;
    font-weight: 600;
    font-size: 13px;
    color: #bdc3c7;
    text-align: left;
}
QPushButton.NavBtn:hover {
    background-color: #2a2e32;
    color: #ffffff;
}

QPushButton.NavBtnActive {
    background-color: #2a3540;
    border-left: 3px solid #3daee9;
    border-radius: 4px;
    padding: 10px 14px;
    font-weight: bold;
    font-size: 13px;
    color: #3daee9;
    text-align: left;
}

/* Scroll area */
QScrollArea {
    background-color: transparent;
    border: none;
}
QScrollBar:vertical {
    background: #1e2023;
    width: 8px;
    margin: 0px;
    border-radius: 4px;
}
QScrollBar::handle:vertical {
    background: #474e54;
    min-height: 20px;
    border-radius: 4px;
}
QScrollBar::handle:vertical:hover {
    background: #3daee9;
}

/* Card Containers */
QFrame.CardFrame {
    background-color: #2a2e32;
    border: 1px solid #393f45;
    border-radius: 8px;
    padding: 14px;
}
QFrame.CardFrame:hover {
    border: 1px solid #4f5861;
}

/* Segmented Profile Bar */
QFrame.SegmentedControlFrame {
    background-color: #1e2023;
    border: 1px solid #31363b;
    border-radius: 8px;
    padding: 3px;
}

QPushButton.SegmentBtn {
    background-color: transparent;
    border: none;
    border-radius: 6px;
    color: #bdc3c7;
    font-weight: 600;
    padding: 8px 14px;
    font-size: 12px;
}
QPushButton.SegmentBtn:hover {
    background-color: #2a2e32;
    color: #ffffff;
}
QPushButton.SegmentBtn[profileKey="ultra_gaming"]:checked {
    background-color: #3d232a;
    color: #ff3366;
    font-weight: bold;
    border: 1px solid #ff3366;
}
QPushButton.SegmentBtn[profileKey="balanced"]:checked {
    background-color: #1e3545;
    color: #3daee9;
    font-weight: bold;
    border: 1px solid #3daee9;
}
QPushButton.SegmentBtn[profileKey="eco_quiet"]:checked {
    background-color: #1d3326;
    color: #00e676;
    font-weight: bold;
    border: 1px solid #00e676;
}
QPushButton.SegmentBtn[profileKey="custom"]:checked {
    background-color: #363228;
    color: #f6ad55;
    font-weight: bold;
    border: 1px solid #f6ad55;
}

/* Sliders */
QSlider::groove:horizontal {
    height: 6px;
    background: #1e2023;
    border-radius: 3px;
}
QSlider::sub-page:horizontal {
    background: #3daee9;
    border-radius: 3px;
}
QSlider::handle:horizontal {
    background: #eff0f1;
    border: 2px solid #3daee9;
    width: 14px;
    height: 14px;
    margin: -4px 0;
    border-radius: 7px;
}
QSlider::handle:horizontal:hover {
    background: #3daee9;
    border: 2px solid #ffffff;
}

/* SpinBox */
QSpinBox {
    background-color: #1e2023;
    color: #3daee9;
    font-weight: bold;
    border: 1px solid #393f45;
    border-radius: 4px;
    padding: 3px;
    font-size: 12px;
}
QSpinBox:focus {
    border: 1px solid #3daee9;
}

/* ToolButtons */
QToolButton.SettingReset {
    background-color: #2a2e32;
    color: #bdc3c7;
    border: 1px solid #393f45;
    border-radius: 4px;
    font-weight: bold;
    padding: 3px 6px;
}
QToolButton.SettingReset:hover {
    color: #3daee9;
    border: 1px solid #3daee9;
    background-color: #31363b;
}

QToolButton.SectionToggle {
    border: none;
    font-weight: bold;
    font-size: 13px;
    color: #eff0f1;
    text-align: left;
    background: transparent;
    padding: 2px 0px;
}
QToolButton.SectionToggle:hover {
    color: #3daee9;
}

/* Checkboxes */
QCheckBox {
    spacing: 8px;
    font-weight: 500;
}
QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border-radius: 4px;
    border: 1px solid #474e54;
    background-color: #1e2023;
}
QCheckBox::indicator:checked {
    background-color: #3daee9;
    border: 1px solid #3daee9;
}

/* Combo Box */
QComboBox {
    background-color: #2a2e32;
    border: 1px solid #393f45;
    border-radius: 6px;
    padding: 6px 12px;
    color: #eff0f1;
    font-weight: 500;
}
QComboBox:hover {
    border: 1px solid #3daee9;
}
QComboBox QAbstractItemView {
    background-color: #2a2e32;
    border: 1px solid #393f45;
    selection-background-color: #3daee9;
    selection-color: #1e2023;
}

/* Action Buttons */
QPushButton.ApplyButton {
    background-color: #3daee9;
    color: #1b1e20;
    font-weight: bold;
    font-size: 13px;
    border: none;
    border-radius: 6px;
    padding: 8px 20px;
}
QPushButton.ApplyButton:hover {
    background-color: #55b9ec;
}
QPushButton.ApplyButton:disabled {
    background: #31363b;
    color: #61676d;
}

QPushButton.SecondaryButton {
    background-color: #31363b;
    border: 1px solid #474e54;
    border-radius: 6px;
    padding: 8px 16px;
    color: #bdc3c7;
    font-weight: 600;
}
QPushButton.SecondaryButton:hover {
    background-color: #3d4349;
    border: 1px solid #61676d;
    color: #ffffff;
}

/* Text & Accent Labels */
QLabel.CardUnitAccent {
    font-size: 13px;
    color: #3daee9;
    font-weight: 600;
    margin-bottom: 4px;
}
QLabel.CoolingFanAccent {
    color: #3daee9;
    font-weight: bold;
}

/* Text Edit / Logs */
QTextEdit {
    background-color: #1e2023;
    color: #bdc3c7;
    font-family: monospace;
    font-size: 11px;
    border: 1px solid #31363b;
    border-radius: 6px;
}

/* Code Block */
QLabel.CodeBlock {
    background: #1e2023;
    padding: 10px;
    border-radius: 6px;
    font-family: monospace;
    color: #3daee9;
    font-size: 11px;
    border: 1px solid #31363b;
}

/* Warning alert box */
QFrame.WarningBox {
    background-color: #442224;
    border: 1px solid #772b2e;
    border-radius: 8px;
    padding: 10px;
}
"""

THEMES = {
    "Cyberpunk Dark (Default)": CYBER_DARK_THEME,
    "Obsidian Neon": OBSIDIAN_NEON_THEME,
    "Breeze Dark Native": BREEZE_DARK_THEME,
}
