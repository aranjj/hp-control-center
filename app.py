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
from ui.main_window import MainWindow


def main():
    # Enable High DPI scaling
    app = QApplication(sys.argv)
    app.setApplicationName("HP Performance Control Center")
    app.setOrganizationName("HPControl")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
