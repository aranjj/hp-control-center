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
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from ui.main_window import MainWindow

SOCKET_NAME = f"hp_control_center_gui_{os.getuid()}"


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("HP Performance Control Center")
    app.setOrganizationName("HPControl")

    # ----------------------------------------------------
    # Single-Instance Enforcement
    # If another instance is running, signal it to activate and exit.
    # ----------------------------------------------------
    client = QLocalSocket()
    client.connectToServer(SOCKET_NAME)
    if client.waitForConnected(300):
        client.write(b"ACTIVATE\n")
        client.waitForBytesWritten(500)
        client.disconnectFromServer()
        sys.exit(0)

    # Clean up any stale socket left by an abnormal process termination
    QLocalServer.removeServer(SOCKET_NAME)

    server = QLocalServer()
    if not server.listen(SOCKET_NAME):
        QLocalServer.removeServer(SOCKET_NAME)
        server.listen(SOCKET_NAME)

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

    start_in_tray = any(arg in sys.argv for arg in ("--tray", "--minimized", "-m"))

    window = MainWindow()
    if not icon.isNull():
        window.setWindowIcon(icon)
    if not start_in_tray:
        window.show()

    # Raise and focus running instance when another launch attempt happens
    def handle_activation():
        conn = server.nextPendingConnection()
        if conn:
            conn.waitForReadyRead(300)
            conn.disconnectFromServer()
        window.activate_window_to_front()

    server.newConnection.connect(handle_activation)

    # Clean up socket and tray icon cleanly on exit
    def cleanup():
        server.close()
        QLocalServer.removeServer(SOCKET_NAME)
        if hasattr(window, "tray") and window.tray:
            window.tray.hide()

    app.aboutToQuit.connect(cleanup)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
