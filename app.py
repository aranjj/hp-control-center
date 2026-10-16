#!/usr/bin/env python3
"""
HP Performance Control Center
Application Entry Point (PySide6 / Qt6)
"""

import sys
import os

# Ensure the project root is in Python's path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon
from ui.main_window import MainWindow


def main():
    # Enable High DPI scaling
    app = QApplication(sys.argv)
    app.setApplicationName("HP Performance Control Center")
    app.setOrganizationName("HPControl")

    # Set Application Icon
    app_dir = os.path.dirname(os.path.abspath(__file__))
    icon = QIcon.fromTheme("hp-control-center")
    if icon.isNull():
        # Fallback to local hicolor paths
        svg_path = os.path.join(app_dir, "hicolor", "scalable", "apps", "hp-control-center.svg")
        png_path = os.path.join(app_dir, "hicolor", "256x256", "apps", "hp-control-center.png")
        if os.path.exists(svg_path):
            icon = QIcon(svg_path)
        elif os.path.exists(png_path):
            icon = QIcon(png_path)
    if not icon.isNull():
        app.setWindowIcon(icon)

    window = MainWindow()
    if not icon.isNull():
        window.setWindowIcon(icon)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
