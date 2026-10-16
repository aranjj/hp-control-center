"""
Dark Gaming & Cyberpunk QSS Stylesheet for HP Control Center
"""

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

/* Sidebar */
QFrame#SidebarFrame {
    background-color: #0d1017;
    border-right: 1px solid #1a2230;
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

/* Primary Action Buttons */
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

/* Warning alert box */
QFrame.WarningBox {
    background-color: #241318;
    border: 1px solid #5a1c2a;
    border-radius: 8px;
    padding: 10px;
}
"""
