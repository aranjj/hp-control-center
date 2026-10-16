"""
Main Application Window for HP Performance Control Center
Built with PySide6 (Qt6)
"""

import os
import json
import socket
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QPushButton,
    QCheckBox,
    QComboBox,
    QFrame,
    QScrollArea,
    QSystemTrayIcon,
    QMenu,
    QApplication,
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QIcon, QAction

from core.telemetry import TelemetryReader
from core.profiles import ProfileManager, DEFAULT_PROFILES
from ui.styles import CYBER_DARK_THEME
from ui.widgets import StatCard, SliderSetting

SOCKET_PATH = "/tmp/hp_control_center.sock"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("HP Performance Control Center • i7-1255U")
        self.resize(780, 820)
        self.setStyleSheet(CYBER_DARK_THEME)

        self.telemetry = TelemetryReader()
        self.profile_mgr = ProfileManager()
        self.daemon_connected = False

        self._setup_ui()
        self._setup_tray()

        # Telemetry Timer (1 Hz polling)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_telemetry)
        self.timer.start(1000)

        # Apply current loaded profile to UI
        self._load_profile_into_ui(self.profile_mgr.current_profile_key)
        self._update_telemetry()

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(16)

        # 1. Header Bar
        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("HP PERFORMANCE CONTROL CENTER")
        title.setStyleSheet("font-size: 18px; font-weight: 800; color: #ffffff; letter-spacing: 1px;")
        subtitle = QLabel("Intel® Core™ i7-1255U • Iris® Xe Graphics • HP 15-fd0xxx")
        subtitle.setStyleSheet("color: #718096; font-size: 12px; font-weight: 500;")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header.addLayout(title_box)
        header.addStretch()

        self.power_src_badge = QLabel("🔌 AC POWER")
        self.power_src_badge.setStyleSheet(
            "background-color: #1a2333; color: #00e5ff; font-weight: bold; "
            "padding: 6px 12px; border-radius: 6px; border: 1px solid #23354d;"
        )
        header.addWidget(self.power_src_badge)
        main_layout.addLayout(header)

        # 2. Hero Profile Selection Buttons
        profile_box = QHBoxLayout()
        profile_box.setSpacing(12)

        self.btn_gaming = QPushButton("🚀  Ultra Gaming\n25W Sustained • Turbo")
        self.btn_gaming.setProperty("class", "ProfileBtn")
        self.btn_gaming.clicked.connect(lambda: self._select_profile("ultra_gaming"))
        profile_box.addWidget(self.btn_gaming)

        self.btn_balanced = QPushButton("⚡  Daily Balanced\n24W Envelope • Smooth")
        self.btn_balanced.setProperty("class", "ProfileBtn")
        self.btn_balanced.clicked.connect(lambda: self._select_profile("balanced"))
        profile_box.addWidget(self.btn_balanced)

        self.btn_eco = QPushButton("🍃  Silent & Eco\n15W Stock • Quiet Fan")
        self.btn_eco.setProperty("class", "ProfileBtn")
        self.btn_eco.clicked.connect(lambda: self._select_profile("eco_quiet"))
        profile_box.addWidget(self.btn_eco)

        main_layout.addLayout(profile_box)

        # 3. Live Telemetry HUD Grid
        hud_grid = QGridLayout()
        hud_grid.setSpacing(12)

        self.card_power = StatCard("Package Power", "0.0", "W", "Target: 25.0 W")
        hud_grid.addWidget(self.card_power, 0, 0)

        self.card_temp = StatCard("Package Temp", "--", "°C", "Cooling: Fan Active")
        hud_grid.addWidget(self.card_temp, 0, 1)

        self.card_fan = StatCard("Cooling Fan", "--", "RPM", "Status: Auto (EC)")
        hud_grid.addWidget(self.card_fan, 0, 2)

        self.card_gpu = StatCard("Iris Xe Clock", "--", "MHz", "Throttle: None")
        hud_grid.addWidget(self.card_gpu, 1, 0)

        self.card_pcore = StatCard("P-Cores (Avg)", "--", "GHz", "2 Performance Cores")
        hud_grid.addWidget(self.card_pcore, 1, 1)

        self.card_ecore = StatCard("E-Cores (Avg)", "--", "GHz", "8 Efficient Cores")
        hud_grid.addWidget(self.card_ecore, 1, 2)

        main_layout.addLayout(hud_grid)

        # Scrollable Control Area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(14)

        # 4. Power & TPL Settings Card
        tpl_card = QFrame()
        tpl_card.setProperty("class", "CardFrame")
        tpl_layout = QVBoxLayout(tpl_card)

        tpl_title = QLabel("⚡ Intel RAPL & MMIO Turbo Power Limits (TPL)")
        tpl_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #ffffff; margin-bottom: 6px;")
        tpl_layout.addWidget(tpl_title)

        self.slider_pl1 = SliderSetting("PL1 Sustained Limit (Long-term)", 12, 30, 25, "W")
        self.slider_pl1.valueChanged.connect(self._on_custom_change)
        tpl_layout.addWidget(self.slider_pl1)

        self.slider_pl2 = SliderSetting("PL2 Burst Limit (Short-term)", 15, 35, 28, "W")
        self.slider_pl2.valueChanged.connect(self._on_custom_change)
        tpl_layout.addWidget(self.slider_pl2)

        tpl_toggles = QHBoxLayout()
        self.chk_sync_mmio = QCheckBox("Sync to MMIO (MCHBAR 0x59A0 - Defeats EC lock)")
        self.chk_sync_mmio.setChecked(True)
        self.chk_sync_mmio.toggled.connect(self._on_custom_change)
        tpl_toggles.addWidget(self.chk_sync_mmio)

        self.chk_bdprochot = QCheckBox("Disable BD PROCHOT (Prevents 400 MHz lockout)")
        self.chk_bdprochot.setChecked(True)
        self.chk_bdprochot.toggled.connect(self._on_custom_change)
        tpl_toggles.addWidget(self.chk_bdprochot)
        tpl_layout.addLayout(tpl_toggles)

        scroll_layout.addWidget(tpl_card)

        # 5. Iris Xe GPU Tuning Card
        gpu_card = QFrame()
        gpu_card.setProperty("class", "CardFrame")
        gpu_layout = QVBoxLayout(gpu_card)

        gpu_title = QLabel("🎮 Intel Iris Xe Graphics Frequency Control (Kernel xe driver)")
        gpu_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #ffffff; margin-bottom: 6px;")
        gpu_layout.addWidget(gpu_title)

        self.slider_gpu_min = SliderSetting("Minimum GPU Frequency (Higher = Zero Stutter)", 100, 1250, 800, "MHz")
        self.slider_gpu_min.valueChanged.connect(self._on_custom_change)
        gpu_layout.addWidget(self.slider_gpu_min)

        self.slider_gpu_max = SliderSetting("Maximum GPU Frequency", 100, 1250, 1250, "MHz")
        self.slider_gpu_max.valueChanged.connect(self._on_custom_change)
        gpu_layout.addWidget(self.slider_gpu_max)

        scroll_layout.addWidget(gpu_card)

        # 6. CPU Governor & Turbo Settings
        cpu_card = QFrame()
        cpu_card.setProperty("class", "CardFrame")
        cpu_layout = QVBoxLayout(cpu_card)

        cpu_title = QLabel("🧠 CPU Turbo Boost & Energy Profile")
        cpu_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #ffffff; margin-bottom: 6px;")
        cpu_layout.addWidget(cpu_title)

        cpu_row = QHBoxLayout()
        self.chk_turbo = QCheckBox("Intel Turbo Boost (Up to 4.7 GHz)")
        self.chk_turbo.setChecked(True)
        self.chk_turbo.toggled.connect(self._on_custom_change)
        cpu_row.addWidget(self.chk_turbo)

        epp_box = QHBoxLayout()
        epp_lbl = QLabel("Energy Bias (EPP):")
        epp_lbl.setStyleSheet("font-weight: 600;")
        self.combo_epp = QComboBox()
        self.combo_epp.addItems(["performance", "balance_performance", "balance_power", "power"])
        self.combo_epp.currentIndexChanged.connect(self._on_custom_change)
        epp_box.addWidget(epp_lbl)
        epp_box.addWidget(self.combo_epp)
        cpu_row.addLayout(epp_box)

        gov_box = QHBoxLayout()
        gov_lbl = QLabel("Governor:")
        gov_lbl.setStyleSheet("font-weight: 600;")
        self.combo_gov = QComboBox()
        self.combo_gov.addItems(["performance", "powersave"])
        self.combo_gov.currentIndexChanged.connect(self._on_custom_change)
        gov_box.addWidget(gov_lbl)
        gov_box.addWidget(self.combo_gov)
        cpu_row.addLayout(gov_box)

        cpu_layout.addLayout(cpu_row)
        scroll_layout.addWidget(cpu_card)

        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll)

        # 7. Bottom Status & Action Bar
        bottom_bar = QHBoxLayout()
        self.daemon_status_lbl = QLabel("● Checking Daemon...")
        self.daemon_status_lbl.setStyleSheet("color: #a0aec0; font-weight: 500;")
        bottom_bar.addWidget(self.daemon_status_lbl)
        bottom_bar.addStretch()

        self.btn_apply = QPushButton("⚡ Apply Settings")
        self.btn_apply.setProperty("class", "ApplyButton")
        self.btn_apply.clicked.connect(self._apply_current_ui_settings)
        bottom_bar.addWidget(self.btn_apply)

        main_layout.addLayout(bottom_bar)

    def _setup_tray(self):
        """Sets up the KDE system tray icon with quick profile actions."""
        self.tray = QSystemTrayIcon(self)
        # Use a standard Qt system icon or theme icon
        self.tray.setIcon(self.style().standardIcon(self.style().StandardPixmap.SP_ComputerIcon))

        tray_menu = QMenu()
        act_gaming = tray_menu.addAction("🚀 Ultra Gaming (25W)")
        act_gaming.triggered.connect(lambda: self._select_profile("ultra_gaming"))

        act_balanced = tray_menu.addAction("⚡ Daily Balanced (24W)")
        act_balanced.triggered.connect(lambda: self._select_profile("balanced"))

        act_eco = tray_menu.addAction("🍃 Silent & Eco (15W)")
        act_eco.triggered.connect(lambda: self._select_profile("eco_quiet"))

        tray_menu.addSeparator()
        act_show = tray_menu.addAction("Open Control Center")
        act_show.triggered.connect(self.showNormal)

        act_quit = tray_menu.addAction("Quit")
        act_quit.triggered.connect(QApplication.instance().quit)

        self.tray.setContextMenu(tray_menu)
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            if self.isVisible():
                self.hide()
            else:
                self.showNormal()

    def _select_profile(self, profile_key: str):
        self.profile_mgr.set_active_profile(profile_key)
        self._load_profile_into_ui(profile_key)
        self._apply_current_ui_settings()

    def _load_profile_into_ui(self, profile_key: str):
        p = self.profile_mgr.get_profile(profile_key)

        # Highlight Buttons
        self.btn_gaming.setStyleSheet("")
        self.btn_balanced.setStyleSheet("")
        self.btn_eco.setStyleSheet("")

        if profile_key == "ultra_gaming":
            self.btn_gaming.setStyleSheet(
                "background: #2a111a; border: 2px solid #ff3366; color: #ffffff; font-weight: bold;"
            )
        elif profile_key == "balanced":
            self.btn_balanced.setStyleSheet(
                "background: #0f2430; border: 2px solid #00e5ff; color: #ffffff; font-weight: bold;"
            )
        elif profile_key == "eco_quiet":
            self.btn_eco.setStyleSheet(
                "background: #11281b; border: 2px solid #00e676; color: #ffffff; font-weight: bold;"
            )

        # Update sliders & checkboxes
        self.slider_pl1.set_value(int(p.get("pl1_w", 24)))
        self.slider_pl2.set_value(int(p.get("pl2_w", 25)))
        self.chk_sync_mmio.setChecked(bool(p.get("sync_mmio", True)))
        self.chk_bdprochot.setChecked(bool(p.get("disable_bdprochot", True)))

        self.slider_gpu_min.set_value(int(p.get("gpu_min_mhz", 100)))
        self.slider_gpu_max.set_value(int(p.get("gpu_max_mhz", 1250)))

        self.chk_turbo.setChecked(bool(p.get("turbo_boost", True)))

        idx_epp = self.combo_epp.findText(p.get("cpu_epp", "balance_performance"))
        if idx_epp >= 0:
            self.combo_epp.setCurrentIndex(idx_epp)

        idx_gov = self.combo_gov.findText(p.get("cpu_governor", "powersave"))
        if idx_gov >= 0:
            self.combo_gov.setCurrentIndex(idx_gov)

    def _on_custom_change(self):
        # User tweaked a slider manually
        pass

    def _collect_ui_settings(self) -> dict:
        return {
            "pl1_w": float(self.slider_pl1.get_value()),
            "pl2_w": float(self.slider_pl2.get_value()),
            "sync_mmio": self.chk_sync_mmio.isChecked(),
            "disable_bdprochot": self.chk_bdprochot.isChecked(),
            "gpu_min_mhz": self.slider_gpu_min.get_value(),
            "gpu_max_mhz": self.slider_gpu_max.get_value(),
            "turbo_boost": self.chk_turbo.isChecked(),
            "cpu_epp": self.combo_epp.currentText(),
            "cpu_governor": self.combo_gov.currentText(),
        }

    def _apply_current_ui_settings(self):
        settings = self._collect_ui_settings()
        self._send_to_daemon({"cmd": "apply", "settings": settings})

    def _send_to_daemon(self, msg: dict) -> dict:
        """Sends command via Unix domain socket to the background root daemon."""
        if not os.path.exists(SOCKET_PATH):
            self.daemon_status_lbl.setText("⚠️ Daemon Not Running (Start with sudo systemctl start hp-control-daemon)")
            self.daemon_status_lbl.setStyleSheet("color: #ff9900; font-weight: 500;")
            return {}

        try:
            client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            client.settimeout(1.0)
            client.connect(SOCKET_PATH)
            client.sendall(json.dumps(msg).encode("utf-8"))
            data = client.recv(4096).decode("utf-8")
            client.close()
            resp = json.loads(data)
            self.daemon_status_lbl.setText("● Daemon Active (5s Re-assertion Syncing)")
            self.daemon_status_lbl.setStyleSheet("color: #00e676; font-weight: bold;")
            return resp
        except Exception as e:
            self.daemon_status_lbl.setText(f"⚠️ Socket Error: {e}")
            self.daemon_status_lbl.setStyleSheet("color: #ff3366;")
            return {}

    def _update_telemetry(self):
        """Polls non-root hardware telemetry and updates UI."""
        data = self.telemetry.get_all()

        # Power
        watts = data["power_watts"]
        target = self.slider_pl1.get_value()
        self.card_power.update_value(f"{watts:.1f}", f"Target PL1: {target}.0 W")

        # Temp
        temp = data["temp_c"]
        temp_color = "#00e676" if temp < 70 else ("#ffaa00" if temp < 85 else "#ff3366")
        self.card_temp.update_value(f"{temp}", "Thermal State: OK", color=temp_color)

        # Fan
        fan_rpm = data["fan_rpm"]
        self.card_fan.update_value(f"{fan_rpm:,}" if fan_rpm > 0 else "0", "HP EC Automatic")

        # Iris Xe GPU
        gpu = data["gpu"]
        reasons = gpu["throttle_reasons"]
        gpu_color = "#ff3366" if gpu["is_throttling"] else "#ffffff"
        self.card_gpu.update_value(f"{gpu['act_mhz']}", f"Throttle: {reasons.upper()}", color=gpu_color)

        # CPU Clocks
        cpu = data["cpu_freq"]
        p_ghz = cpu["p_core_mhz"] / 1000.0
        e_ghz = cpu["e_core_mhz"] / 1000.0
        self.card_pcore.update_value(f"{p_ghz:.2f}", "P-Cores (Cores 0-1)")
        self.card_ecore.update_value(f"{e_ghz:.2f}", "E-Cores (Cores 2-9)")

        # Power source badge
        if data["ac_connected"]:
            self.power_src_badge.setText("🔌 AC POWER")
            self.power_src_badge.setStyleSheet(
                "background-color: #1a2333; color: #00e5ff; font-weight: bold; "
                "padding: 6px 12px; border-radius: 6px; border: 1px solid #23354d;"
            )
        else:
            self.power_src_badge.setText("🔋 ON BATTERY")
            self.power_src_badge.setStyleSheet(
                "background-color: #2b2214; color: #ffaa00; font-weight: bold; "
                "padding: 6px 12px; border-radius: 6px; border: 1px solid #4a381a;"
            )

        # System tray tooltip
        self.tray.setToolTip(f"HP Control Center: {watts:.1f}W • {temp}°C • Fan: {fan_rpm} RPM")

        # Check socket ping occasionally
        if os.path.exists(SOCKET_PATH):
            self.daemon_status_lbl.setText("● Daemon Active (5s Re-assertion Syncing)")
            self.daemon_status_lbl.setStyleSheet("color: #00e676; font-weight: bold;")
        else:
            self.daemon_status_lbl.setText("⚠️ Daemon Offline (Run sudo systemctl start hp-control-daemon)")
            self.daemon_status_lbl.setStyleSheet("color: #ff9900; font-weight: 500;")
