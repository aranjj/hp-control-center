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

/* Scroll area */
QScrollArea {
    background-color: transparent;
    border: none;
}
QScrollBar:vertical {
    background: #11141a;
    width: 8px;
    margin: 0px;
    border-radius: 4px;
}
QScrollBar::handle:vertical {
    background: #252b36;
    min-height: 20px;
    border-radius: 4px;
}
QScrollBar::handle:vertical:hover {
    background: #00e5ff;
}

/* Card Containers */
QFrame.CardFrame {
    background-color: #12161f;
    border: 1px solid #1e2430;
    border-radius: 10px;
    padding: 14px;
}

QFrame.CardFrame:hover {
    border: 1px solid #283344;
}

QFrame.HeroCard {
    background-color: #10141d;
    border: 1px solid #1a2230;
    border-radius: 12px;
}

/* Profile Buttons */
QPushButton.ProfileBtn {
    background-color: #141822;
    border: 1px solid #222938;
    border-radius: 10px;
    padding: 12px 16px;
    font-weight: bold;
    font-size: 14px;
    color: #a4b2c6;
    text-align: left;
}

QPushButton.ProfileBtn:hover {
    background-color: #1b212f;
    border: 1px solid #00e5ff;
    color: #ffffff;
}

QPushButton.ProfileBtnActiveGaming {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #221215, stop:1 #1c1420);
    border: 2px solid #ff3366;
    border-radius: 10px;
    color: #ffffff;
    font-weight: bold;
    padding: 12px 16px;
}

QPushButton.ProfileBtnActiveBalanced {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #10202b, stop:1 #131d27);
    border: 2px solid #00e5ff;
    border-radius: 10px;
    color: #ffffff;
    font-weight: bold;
    padding: 12px 16px;
}

QPushButton.ProfileBtnActiveEco {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #112218, stop:1 #131d17);
    border: 2px solid #00e676;
    border-radius: 10px;
    color: #ffffff;
    font-weight: bold;
    padding: 12px 16px;
}

/* Sliders */
QSlider::groove:horizontal {
    height: 6px;
    background: #1b212c;
    border-radius: 3px;
}

QSlider::sub-page:horizontal {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #00b0ff, stop:1 #00e5ff);
    border-radius: 3px;
}

QSlider::handle:horizontal {
    background: #ffffff;
    border: 2px solid #00e5ff;
    width: 16px;
    height: 16px;
    margin: -5px 0;
    border-radius: 8px;
}

QSlider::handle:horizontal:hover {
    background: #00e5ff;
    border: 2px solid #ffffff;
}

/* Checkboxes & Radios */
QCheckBox {
    spacing: 8px;
    font-weight: 500;
}
QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border-radius: 5px;
    border: 1px solid #2d3849;
    background-color: #141822;
}
QCheckBox::indicator:checked {
    background-color: #00e5ff;
    border: 1px solid #00e5ff;
    image: none;
}

/* Combo Box */
QComboBox {
    background-color: #161a24;
    border: 1px solid #252d3d;
    border-radius: 6px;
    padding: 6px 12px;
    color: #e0e6ed;
    font-weight: 500;
}
QComboBox:hover {
    border: 1px solid #00e5ff;
}
QComboBox QAbstractItemView {
    background-color: #161a24;
    border: 1px solid #252d3d;
    selection-background-color: #00e5ff;
    selection-color: #0b0d11;
}

/* Progress Bar */
QProgressBar {
    background-color: #141822;
    border: 1px solid #1e2634;
    border-radius: 6px;
    height: 12px;
    text-align: center;
    font-size: 10px;
    font-weight: bold;
}
QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #00b0ff, stop:1 #00e5ff);
    border-radius: 5px;
}

/* Primary Action Buttons */
QPushButton.ApplyButton {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0091ea, stop:1 #00e5ff);
    color: #07090d;
    font-weight: bold;
    font-size: 14px;
    border: none;
    border-radius: 8px;
    padding: 10px 24px;
}
QPushButton.ApplyButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #00b0ff, stop:1 #18ffff);
}
"""
