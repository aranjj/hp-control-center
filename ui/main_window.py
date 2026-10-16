"""
Main Application Window for HP Performance Control Center
Layout:
- Left collapsible sidebar (Dashboard, Performance, Graphics, Cooling, Settings)
- Persistent top bar: Profile segmented control (Ultra Gaming, Balanced, Eco, Custom)
- Persistent bottom status bar: Daemon dot, AC state, mini telemetry, unsaved count, Reset, Apply
"""

import os
import json
import socket
import glob
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
    QStackedWidget,
    QSystemTrayIcon,
    QMenu,
    QApplication,
    QTextEdit,
    QMessageBox,
)
from PySide6.QtCore import Qt, QTimer, QSettings
from PySide6.QtGui import QIcon

from core.telemetry import TelemetryReader
from core.profiles import ProfileManager, DEFAULT_PROFILES
from ui.styles import CYBER_DARK_THEME
from ui.widgets import StatCard, SliderSetting, CollapsibleSection, SegmentedControl

SOCKET_PATH = "/tmp/hp_control_center.sock"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("HP Performance Control Center • i7-1255U")
        self.setStyleSheet(CYBER_DARK_THEME)

        self.telemetry = TelemetryReader()
        self.profile_mgr = ProfileManager()
        self.daemon_online = False
        self.unsaved_changes_count = 0
        self.sidebar_expanded = True

        # Track base profile / baseline values for dirty check
        self._applied_settings = dict(self.profile_mgr.get_profile(self.profile_mgr.current_profile_key))

        # Restore window geometry from QSettings
        self.settings = QSettings("HPControl", "ControlCenter")
        geometry = self.settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)
        else:
            self.resize(880, 840)

        self._setup_ui()
        self._setup_tray()

        # Telemetry Timer (1 Hz polling)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_telemetry)
        self.timer.start(1000)

        # Initial check & load
        self._check_daemon_status()
        self._load_profile_into_ui(self.profile_mgr.current_profile_key)
        self._update_telemetry()

        # Ensure Dashboard is the default tab on open
        self.tab_stack.setCurrentIndex(0)
        self._update_nav_buttons(0)

    def closeEvent(self, event):
        """Remember window size/position on close."""
        self.settings.setValue("geometry", self.saveGeometry())
        super().closeEvent(event)

    def _setup_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # ==========================================
        # 1. LEFT COLLAPSIBLE SIDEBAR
        # ==========================================
        self.sidebar_frame = QFrame()
        self.sidebar_frame.setObjectName("SidebarFrame")
        self.sidebar_frame.setFixedWidth(200)

        sidebar_layout = QVBoxLayout(self.sidebar_frame)
        sidebar_layout.setContentsMargins(10, 14, 10, 14)
        sidebar_layout.setSpacing(6)

        # Sidebar Header / Collapse Toggle
        self.btn_collapse = QPushButton("☰  Menu")
        self.btn_collapse.setStyleSheet(
            "QPushButton { background: transparent; border: none; font-weight: 800; color: #a0aec0; "
            "text-align: left; padding: 8px 12px; font-size: 13px; }"
            "QPushButton:hover { color: #00e5ff; }"
        )
        self.btn_collapse.clicked.connect(self._toggle_sidebar)
        sidebar_layout.addWidget(self.btn_collapse)

        # Brand subtitle
        self.brand_lbl = QLabel("HP 15 CONTROL")
        self.brand_lbl.setStyleSheet("color: #4a5568; font-size: 10px; font-weight: bold; letter-spacing: 1px; padding-left: 12px;")
        sidebar_layout.addWidget(self.brand_lbl)
        sidebar_layout.addSpacing(6)

        # Navigation Buttons
        self.nav_buttons = []
        nav_items = [
            ("📊", "Dashboard"),
            ("⚡", "Performance"),
            ("🎮", "Graphics"),
            ("❄️", "Cooling"),
            ("⚙️", "Settings"),
        ]
        for idx, (icon, text) in enumerate(nav_items):
            btn = QPushButton(f"{icon}  {text}")
            btn.setProperty("class", "NavBtn")
            btn.clicked.connect(lambda checked, i=idx: self._switch_tab(i))
            self.nav_buttons.append(btn)
            sidebar_layout.addWidget(btn)

        sidebar_layout.addStretch()

        # Mini footer in sidebar
        self.side_footer_lbl = QLabel("v0.2-alpha")
        self.side_footer_lbl.setStyleSheet("color: #4a5568; font-size: 10px; padding-left: 12px;")
        sidebar_layout.addWidget(self.side_footer_lbl)

        root_layout.addWidget(self.sidebar_frame)

        # ==========================================
        # 2. MAIN CONTENT AREA (Header + Stack + Footer)
        # ==========================================
        content_frame = QWidget()
        content_layout = QVBoxLayout(content_frame)
        content_layout.setContentsMargins(18, 14, 18, 14)
        content_layout.setSpacing(12)

        # ------------------------------------------
        # PERSISTENT TOP BAR (Visible on Every Tab)
        # ------------------------------------------
        top_bar = QHBoxLayout()
        top_bar.setSpacing(12)

        # Segmented Profile Switcher
        profile_items = [
            ("ultra_gaming", "Ultra Gaming", "25W"),
            ("balanced", "Daily Balanced", "24W"),
            ("eco_quiet", "Silent Eco", "15W"),
            ("custom", "Custom", ""),
        ]
        self.profile_segmented = SegmentedControl(profile_items)
        self.profile_segmented.selectionChanged.connect(self._on_profile_selected)
        top_bar.addWidget(self.profile_segmented)

        top_bar.addStretch()

        # Power Source Badge
        self.power_src_badge = QLabel("🔌 AC POWER")
        self.power_src_badge.setStyleSheet(
            "background-color: #1a2333; color: #00e5ff; font-weight: bold; "
            "padding: 6px 12px; border-radius: 6px; border: 1px solid #23354d; font-size: 11px;"
        )
        top_bar.addWidget(self.power_src_badge)

        content_layout.addLayout(top_bar)

        # High Temperature Global Warning Banner (> 90°C)
        self.warning_banner = QFrame()
        self.warning_banner.setProperty("class", "WarningBox")
        self.warning_banner.setVisible(False)
        w_layout = QHBoxLayout(self.warning_banner)
        w_layout.setContentsMargins(10, 6, 10, 6)
        self.warning_lbl = QLabel("⚠️ HIGH TEMPERATURE ALERT: Package temperature is above 90°C! Verify fan cooling.")
        self.warning_lbl.setStyleSheet("color: #ff3366; font-weight: bold;")
        w_layout.addWidget(self.warning_lbl)
        content_layout.addWidget(self.warning_banner)

        # ------------------------------------------
        # TAB STACK
        # ------------------------------------------
        self.tab_stack = QStackedWidget()

        # Tab 0: Dashboard
        self.tab_stack.addWidget(self._build_dashboard_tab())
        # Tab 1: Performance
        self.tab_stack.addWidget(self._build_performance_tab())
        # Tab 2: Graphics
        self.tab_stack.addWidget(self._build_graphics_tab())
        # Tab 3: Cooling
        self.tab_stack.addWidget(self._build_cooling_tab())
        # Tab 4: Settings
        self.tab_stack.addWidget(self._build_settings_tab())

        content_layout.addWidget(self.tab_stack, stretch=1)

        # ------------------------------------------
        # PERSISTENT BOTTOM STATUS BAR (Every Tab)
        # ------------------------------------------
        bottom_bar = QHBoxLayout()
        bottom_bar.setSpacing(12)

        # Daemon Dot + Status Text
        self.daemon_dot = QLabel("●")
        self.daemon_dot.setStyleSheet("color: #ff3366; font-size: 14px;")
        bottom_bar.addWidget(self.daemon_dot)

        self.daemon_lbl = QLabel("Daemon Offline")
        self.daemon_lbl.setStyleSheet("font-weight: 600; color: #a0aec0; font-size: 12px;")
        bottom_bar.addWidget(self.daemon_lbl)

        # Mini Live Telemetry Readout
        self.mini_telemetry_lbl = QLabel("•  --°C  |  --W  |  -- RPM")
        self.mini_telemetry_lbl.setStyleSheet("color: #718096; font-size: 11px; font-weight: 500;")
        bottom_bar.addWidget(self.mini_telemetry_lbl)

        bottom_bar.addStretch()

        # "N Unsaved Changes" Label
        self.unsaved_lbl = QLabel("0 unsaved changes")
        self.unsaved_lbl.setStyleSheet("color: #718096; font-size: 11px; font-style: italic;")
        bottom_bar.addWidget(self.unsaved_lbl)

        # Reset to Defaults Button
        self.btn_reset_all = QPushButton("Reset Defaults")
        self.btn_reset_all.setProperty("class", "SecondaryButton")
        self.btn_reset_all.clicked.connect(self._reset_to_defaults)
        bottom_bar.addWidget(self.btn_reset_all)

        # Global Apply Button
        self.btn_apply = QPushButton("Apply Settings")
        self.btn_apply.setProperty("class", "ApplyButton")
        self.btn_apply.setEnabled(False)
        self.btn_apply.clicked.connect(self._apply_settings)
        bottom_bar.addWidget(self.btn_apply)

        content_layout.addLayout(bottom_bar)

        root_layout.addWidget(content_frame, stretch=1)

    # ==============================================
    # TAB BUILDERS
    # ==============================================

    def _build_dashboard_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(12)

        dash_title = QLabel("LIVE TELEMETRY HUD")
        dash_title.setStyleSheet("font-size: 12px; font-weight: bold; color: #718096; letter-spacing: 1px;")
        layout.addWidget(dash_title)

        hud_grid = QGridLayout()
        hud_grid.setSpacing(12)

        # Tile 1: Package Power with Throttle Reason
        self.card_power = StatCard("Package Power", "0.0", "W", "Target: 25.0 W")
        hud_grid.addWidget(self.card_power, 0, 0)

        # Tile 2: Package Temp
        self.card_temp = StatCard("Package Temp", "--", "°C", "Thermal: Normal")
        hud_grid.addWidget(self.card_temp, 0, 1)

        # Tile 3: Cooling Fan
        self.card_fan = StatCard("Cooling Fan", "--", "RPM", "HP EC Automatic")
        hud_grid.addWidget(self.card_fan, 0, 2)

        # Tile 4: Iris Xe Clock
        self.card_gpu = StatCard("Iris Xe Clock", "--", "MHz", "State: Active")
        hud_grid.addWidget(self.card_gpu, 1, 0)

        # Tile 5: P-Core avg clock (dynamic threads count)
        p_count = len(self.telemetry.p_core_threads)
        self.card_pcore = StatCard("P-Cores (Avg)", "--", "GHz", f"{p_count} Threads (cpu0-{p_count-1})")
        hud_grid.addWidget(self.card_pcore, 1, 1)

        # Tile 6: E-Core avg clock (dynamic threads count)
        e_count = len(self.telemetry.e_core_threads)
        self.card_ecore = StatCard("E-Cores (Avg)", "--", "GHz", f"{e_count} Threads")
        hud_grid.addWidget(self.card_ecore, 1, 2)

        layout.addLayout(hud_grid)
        layout.addStretch()
        return widget

    def _build_performance_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 4, 10, 0)
        layout.setSpacing(14)

        card = QFrame()
        card.setProperty("class", "CardFrame")
        c_layout = QVBoxLayout(card)
        c_layout.setSpacing(12)

        title = QLabel("⚡ Intel RAPL & MMIO Turbo Power Limits")
        title.setStyleSheet("font-size: 14px; font-weight: bold; color: #ffffff;")
        c_layout.addWidget(title)

        # Fixed-width, full-width sliders with explicit ranges and per-slider reset
        self.slider_pl1 = SliderSetting("PL1 Sustained Limit (Long-term)", 12, 30, 25, "W")
        self.slider_pl1.valueChanged.connect(self._on_pl1_changed)
        c_layout.addWidget(self.slider_pl1)

        self.slider_pl2 = SliderSetting("PL2 Burst Limit (Short-term)", 15, 35, 28, "W")
        self.slider_pl2.valueChanged.connect(self._on_pl2_changed)
        c_layout.addWidget(self.slider_pl2)

        # Sync MMIO
        self.chk_sync_mmio = QCheckBox("Sync to MMIO (MCHBAR 0x59A0 - Defeats EC lock)")
        self.chk_sync_mmio.setChecked(True)
        self.chk_sync_mmio.toggled.connect(self._on_setting_modified)
        c_layout.addWidget(self.chk_sync_mmio)

        # Turbo & EPP
        row_turbo = QHBoxLayout()
        self.chk_turbo = QCheckBox("Intel Turbo Boost (Up to 4.7 GHz)")
        self.chk_turbo.setChecked(True)
        self.chk_turbo.toggled.connect(self._on_setting_modified)
        row_turbo.addWidget(self.chk_turbo)

        row_turbo.addSpacing(20)
        epp_lbl = QLabel("Energy Bias (EPP):")
        epp_lbl.setStyleSheet("font-weight: 600;")
        self.combo_epp = QComboBox()
        self.combo_epp.addItems(["performance", "balance_performance", "balance_power", "power"])
        self.combo_epp.currentIndexChanged.connect(self._on_setting_modified)
        row_turbo.addWidget(epp_lbl)
        row_turbo.addWidget(self.combo_epp)
        row_turbo.addStretch()
        c_layout.addLayout(row_turbo)

        layout.addWidget(card)

        # Advanced Collapsible Section for BD PROCHOT
        self.advanced_sec = CollapsibleSection("Advanced Settings (BD PROCHOT)", is_expanded=False)

        adv_warn = QLabel("⚠️ WARNING: BD PROCHOT (Bi-directional Processor Hot) protects VRMs from overheating.\n"
                          "Disabling it prevents the 400 MHz lockout bug, but should only be used if temperatures are monitored.")
        adv_warn.setStyleSheet("color: #ff3366; font-size: 11px; font-weight: 500;")
        adv_warn.setWordWrap(True)
        self.advanced_sec.add_widget(adv_warn)

        self.chk_bdprochot = QCheckBox("Disable BD PROCHOT (Emergency Throttling Override)")
        self.chk_bdprochot.setChecked(True)
        self.chk_bdprochot.toggled.connect(self._on_bdprochot_toggled)
        self.advanced_sec.add_widget(self.chk_bdprochot)

        layout.addWidget(self.advanced_sec)
        layout.addStretch()

        scroll.setWidget(content)
        return scroll

    def _build_graphics_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 4, 10, 0)
        layout.setSpacing(14)

        card = QFrame()
        card.setProperty("class", "CardFrame")
        c_layout = QVBoxLayout(card)
        c_layout.setSpacing(12)

        title = QLabel("🎮 Intel Iris Xe Graphics Tuning (Linux xe driver)")
        title.setStyleSheet("font-size: 14px; font-weight: bold; color: #ffffff;")
        c_layout.addWidget(title)

        desc = QLabel("Set GPU frequency floors to eliminate frame-time spikes and stutter in 3D gaming.")
        desc.setStyleSheet("color: #718096; font-size: 12px;")
        c_layout.addWidget(desc)

        self.slider_gpu_min = SliderSetting("Minimum GPU Frequency", 100, 1250, 800, "MHz")
        self.slider_gpu_min.valueChanged.connect(self._on_setting_modified)
        c_layout.addWidget(self.slider_gpu_min)

        self.slider_gpu_max = SliderSetting("Maximum GPU Frequency", 100, 1250, 1250, "MHz")
        self.slider_gpu_max.valueChanged.connect(self._on_setting_modified)
        c_layout.addWidget(self.slider_gpu_max)

        p_row = QHBoxLayout()
        p_lbl = QLabel("GPU Power Mode:")
        p_lbl.setStyleSheet("font-weight: 600;")
        self.combo_gpu_power = QComboBox()
        self.combo_gpu_power.addItems(["base", "power_saving"])
        self.combo_gpu_power.currentIndexChanged.connect(self._on_setting_modified)
        p_row.addWidget(p_lbl)
        p_row.addWidget(self.combo_gpu_power)
        p_row.addStretch()
        c_layout.addLayout(p_row)

        layout.addWidget(card)
        layout.addStretch()

        scroll.setWidget(content)
        return scroll

    def _build_cooling_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(14)

        card = QFrame()
        card.setProperty("class", "CardFrame")
        c_layout = QVBoxLayout(card)
        c_layout.setSpacing(10)

        title = QLabel("❄️ Cooling & Thermal Management")
        title.setStyleSheet("font-size: 14px; font-weight: bold; color: #ffffff;")
        c_layout.addWidget(title)

        self.cooling_fan_lbl = QLabel("Fan Mode: HP EC Automatic (Hardware Governed)")
        self.cooling_fan_lbl.setStyleSheet("color: #00e5ff; font-weight: bold;")
        c_layout.addWidget(self.cooling_fan_lbl)

        info = QLabel(
            "HP 15 chassis firmware hardwires fan tachometer control to internal EC thermal sensors.\n"
            "Fan automatically scales up to ~3,500+ RPM when sustained 25W load is active."
        )
        info.setStyleSheet("color: #718096; font-size: 12px;")
        c_layout.addWidget(info)

        c_layout.addSpacing(10)
        placeholder_title = QLabel("Custom Fan Curve Editor (Placeholder)")
        placeholder_title.setStyleSheet("color: #4a5568; font-weight: bold; font-size: 12px;")
        c_layout.addWidget(placeholder_title)

        placeholder_box = QFrame()
        placeholder_box.setStyleSheet("background-color: #0f131a; border: 1px dashed #233147; border-radius: 8px; padding: 20px;")
        p_box_layout = QVBoxLayout(placeholder_box)
        p_msg = QLabel("Future Feature: NoteBook Fan Control (NBFC) / Direct EC Register Curve Hook")
        p_msg.setAlignment(Qt.AlignCenter)
        p_msg.setStyleSheet("color: #4a5568; font-style: italic;")
        p_box_layout.addWidget(p_msg)
        c_layout.addWidget(placeholder_box)

        layout.addWidget(card)
        layout.addStretch()
        return widget

    def _build_settings_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 4, 10, 0)
        layout.setSpacing(14)

        card = QFrame()
        card.setProperty("class", "CardFrame")
        c_layout = QVBoxLayout(card)
        c_layout.setSpacing(12)

        title = QLabel("⚙️ Application Settings")
        title.setStyleSheet("font-size: 14px; font-weight: bold; color: #ffffff;")
        c_layout.addWidget(title)

        # Autostart Toggle
        self.chk_autostart = QCheckBox("Start HP Control Center on System Login")
        self.chk_autostart.setChecked(self._is_autostart_enabled())
        self.chk_autostart.toggled.connect(self._toggle_autostart)
        c_layout.addWidget(self.chk_autostart)

        # Theme selector
        theme_row = QHBoxLayout()
        theme_lbl = QLabel("Color Theme:")
        theme_lbl.setStyleSheet("font-weight: 600;")
        self.combo_theme = QComboBox()
        self.combo_theme.addItems(["Cyberpunk Dark (Default)", "Obsidian Neon", "Breeze Dark Native"])
        theme_row.addWidget(theme_lbl)
        theme_row.addWidget(self.combo_theme)
        theme_row.addStretch()
        c_layout.addLayout(theme_row)

        layout.addWidget(card)

        # Daemon Status & Instructions Card
        d_card = QFrame()
        d_card.setProperty("class", "CardFrame")
        d_layout = QVBoxLayout(d_card)

        d_title = QLabel("🔌 Hardware Sync Daemon (Root Service)")
        d_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #ffffff;")
        d_layout.addWidget(d_title)

        self.daemon_detail_lbl = QLabel("Status: Checking...")
        self.daemon_detail_lbl.setStyleSheet("color: #a0aec0; font-size: 12px;")
        d_layout.addWidget(self.daemon_detail_lbl)

        d_cmds = QLabel("To enable the background daemon:\n"
                        "  sudo cp /home/aran/Projects/Github/hp-control-center/daemon/hp-control-daemon.service /etc/systemd/system/\n"
                        "  sudo systemctl daemon-reload\n"
                        "  sudo systemctl enable --now hp-control-daemon")
        d_cmds.setStyleSheet("background: #0f1218; padding: 10px; border-radius: 6px; font-family: monospace; color: #00e5ff; font-size: 11px;")
        d_layout.addWidget(d_cmds)

        layout.addWidget(d_card)

        # Log Viewer Section
        self.log_section = CollapsibleSection("Recent System & Daemon Logs", is_expanded=False)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFixedHeight(160)
        self.log_text.setStyleSheet("background-color: #0b0d11; color: #a0aec0; font-family: monospace; font-size: 11px; border: 1px solid #1f2736;")
        self.log_text.setPlainText("HP Control Center v0.2-alpha started.\nPolling sensors every 1000ms.\n")
        self.log_section.add_widget(self.log_text)
        layout.addWidget(self.log_section)

        layout.addStretch()
        scroll.setWidget(content)
        return scroll

    # ==============================================
    # NAVIGATION & SIDEBAR
    # ==============================================

    def _switch_tab(self, index: int):
        self.tab_stack.setCurrentIndex(index)
        self._update_nav_buttons(index)

    def _update_nav_buttons(self, active_index: int):
        for idx, btn in enumerate(self.nav_buttons):
            if idx == active_index:
                btn.setProperty("class", "NavBtnActive")
            else:
                btn.setProperty("class", "NavBtn")
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def _toggle_sidebar(self):
        self.sidebar_expanded = not self.sidebar_expanded
        nav_texts = ["Dashboard", "Performance", "Graphics", "Cooling", "Settings"]
        nav_icons = ["📊", "⚡", "🎮", "❄️", "⚙️"]

        if self.sidebar_expanded:
            self.sidebar_frame.setFixedWidth(200)
            self.btn_collapse.setText("☰  Menu")
            self.brand_lbl.setVisible(True)
            self.side_footer_lbl.setVisible(True)
            for idx, btn in enumerate(self.nav_buttons):
                btn.setText(f"{nav_icons[idx]}  {nav_texts[idx]}")
        else:
            self.sidebar_frame.setFixedWidth(64)
            self.btn_collapse.setText("☰")
            self.brand_lbl.setVisible(False)
            self.side_footer_lbl.setVisible(False)
            for idx, btn in enumerate(self.nav_buttons):
                btn.setText(nav_icons[idx])

    # ==============================================
    # SLIDER & PROFILE LOGIC
    # ==============================================

    def _on_pl1_changed(self, val: int):
        # Rule: PL2 should never be set below PL1
        if self.slider_pl2.get_value() < val:
            self.slider_pl2.set_value(val)
        self._on_setting_modified()

    def _on_pl2_changed(self, val: int):
        # Rule: PL2 should never be set below PL1
        if val < self.slider_pl1.get_value():
            self.slider_pl1.set_value(val)
        self._on_setting_modified()

    def _on_bdprochot_toggled(self, checked: bool):
        if checked:
            # Confirmation dialog for safety
            reply = QMessageBox.warning(
                self,
                "Disable BD PROCHOT?",
                "Disabling BD PROCHOT overrides motherboard/charger thermal throttling.\n\n"
                "Are you sure you want to disable BD PROCHOT?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                self.chk_bdprochot.blockSignals(True)
                self.chk_bdprochot.setChecked(False)
                self.chk_bdprochot.blockSignals(False)
                return
        self._on_setting_modified()

    def _on_setting_modified(self):
        """Called whenever any setting is altered in UI."""
        # Switch profile highlight to Custom
        self.profile_segmented.set_selected("custom")
        self._recalculate_unsaved_changes()

    def _on_profile_selected(self, key: str):
        if key == "custom":
            return
        self.profile_mgr.set_active_profile(key)
        self._load_profile_into_ui(key)
        self._recalculate_unsaved_changes()

    def _load_profile_into_ui(self, key: str):
        p = self.profile_mgr.get_profile(key)
        self.profile_segmented.set_selected(key)

        # Update sliders & settings without triggering false custom flag
        self.slider_pl1.set_value(int(p.get("pl1_w", 24)))
        self.slider_pl2.set_value(int(p.get("pl2_w", 25)))
        self.chk_sync_mmio.setChecked(bool(p.get("sync_mmio", True)))

        self.chk_bdprochot.blockSignals(True)
        self.chk_bdprochot.setChecked(bool(p.get("disable_bdprochot", True)))
        self.chk_bdprochot.blockSignals(False)

        self.slider_gpu_min.set_value(int(p.get("gpu_min_mhz", 100)))
        self.slider_gpu_max.set_value(int(p.get("gpu_max_mhz", 1250)))

        self.chk_turbo.setChecked(bool(p.get("turbo_boost", True)))

        idx_epp = self.combo_epp.findText(p.get("cpu_epp", "balance_performance"))
        if idx_epp >= 0:
            self.combo_epp.setCurrentIndex(idx_epp)

        idx_gpu_p = self.combo_gpu_power.findText(p.get("gpu_power_mode", "base"))
        if idx_gpu_p >= 0:
            self.combo_gpu_power.setCurrentIndex(idx_gpu_p)

        self._recalculate_unsaved_changes()

    def _collect_ui_settings(self) -> dict:
        return {
            "pl1_w": float(self.slider_pl1.get_value()),
            "pl2_w": float(self.slider_pl2.get_value()),
            "sync_mmio": self.chk_sync_mmio.isChecked(),
            "disable_bdprochot": self.chk_bdprochot.isChecked(),
            "gpu_min_mhz": self.slider_gpu_min.get_value(),
            "gpu_max_mhz": self.slider_gpu_max.get_value(),
            "gpu_power_mode": self.combo_gpu_power.currentText(),
            "turbo_boost": self.chk_turbo.isChecked(),
            "cpu_epp": self.combo_epp.currentText(),
            "cpu_governor": "performance" if self.combo_epp.currentText() == "performance" else "powersave",
        }

    def _recalculate_unsaved_changes(self):
        current = self._collect_ui_settings()
        diffs = 0
        for k, v in current.items():
            if self._applied_settings.get(k) != v:
                diffs += 1
        self.unsaved_changes_count = diffs

        if diffs > 0:
            self.unsaved_lbl.setText(f"{diffs} unsaved change{'s' if diffs > 1 else ''}")
            self.unsaved_lbl.setStyleSheet("color: #f6ad55; font-size: 11px; font-weight: bold;")
        else:
            self.unsaved_lbl.setText("0 unsaved changes")
            self.unsaved_lbl.setStyleSheet("color: #718096; font-size: 11px; font-style: italic;")

        # Enable Apply only when daemon is online AND changes exist
        self.btn_apply.setEnabled(self.daemon_online and diffs > 0)

    def _reset_to_defaults(self):
        """Resets current profile and sliders to Daily Balanced baseline."""
        self._load_profile_into_ui("balanced")

    def _apply_settings(self):
        """Sends changes to daemon."""
        settings = self._collect_ui_settings()
        resp = self._send_to_daemon({"cmd": "apply", "settings": settings})
        if resp.get("status") == "ok":
            self._applied_settings = dict(settings)
            self._recalculate_unsaved_changes()
            self.log_text.append("[+] Applied settings successfully.")

    # ==============================================
    # DAEMON COMMUNICATION
    # ==============================================

    def _check_daemon_status(self):
        if os.path.exists(SOCKET_PATH):
            resp = self._send_to_daemon({"cmd": "ping"})
            self.daemon_online = resp.get("status") == "ok"
        else:
            self.daemon_online = False

        if self.daemon_online:
            self.daemon_dot.setStyleSheet("color: #00e676; font-size: 14px;")
            self.daemon_lbl.setText("Daemon Connected")
            self.daemon_detail_lbl.setText("Status: Online (Active Unix Socket)")
            self.daemon_detail_lbl.setStyleSheet("color: #00e676; font-weight: bold;")
        else:
            self.daemon_dot.setStyleSheet("color: #ff3366; font-size: 14px;")
            self.daemon_lbl.setText("Daemon Offline")
            self.daemon_detail_lbl.setText("Status: Offline (Start service to enable applying limits)")
            self.daemon_detail_lbl.setStyleSheet("color: #ff3366;")

        self._recalculate_unsaved_changes()

    def _send_to_daemon(self, msg: dict) -> dict:
        if not os.path.exists(SOCKET_PATH):
            return {}
        try:
            client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            client.settimeout(1.0)
            client.connect(SOCKET_PATH)
            client.sendall(json.dumps(msg).encode("utf-8"))
            data = client.recv(4096).decode("utf-8")
            client.close()
            return json.loads(data)
        except Exception:
            return {}

    # ==============================================
    # TELEMETRY & TRAY
    # ==============================================

    def _update_telemetry(self):
        data = self.telemetry.get_all()

        # Check socket status every cycle
        self._check_daemon_status()

        # Power
        watts = data["power_watts"] if data["power_watts"] is not None else 0.0
        target = self.slider_pl1.get_value()
        # Throttle reason on power card
        gpu_th = data["gpu"]["throttle_reasons"].upper()
        th_reason = "NONE" if gpu_th in ("", "NONE") else gpu_th
        self.card_power.update_value(f"{watts:.1f}", f"Target PL1: {target}.0 W", badge_text=f"THROTTLE: {th_reason}")

        # Temp
        temp = data["temp_c"] if data["temp_c"] is not None else 0
        temp_color = "#00e676" if temp < 70 else ("#ffaa00" if temp < 85 else "#ff3366")
        self.card_temp.update_value(f"{temp}" if temp else "--", "Core Temp Sensor", color=temp_color)

        # Global High Temp Alert
        if temp >= 90:
            self.warning_banner.setVisible(True)
            self.warning_lbl.setText(f"⚠️ HIGH TEMPERATURE ALERT: Package temperature is {temp}°C! Fan cooling active.")
        else:
            self.warning_banner.setVisible(False)

        # Fan
        fan_rpm = data["fan_rpm"] if data["fan_rpm"] is not None else 0
        self.card_fan.update_value(f"{fan_rpm:,}" if fan_rpm > 0 else "--", "HP EC Automatic")

        # Iris Xe GPU
        gpu = data["gpu"]
        reasons = gpu["throttle_reasons"]
        gpu_color = "#ff3366" if gpu["is_throttling"] else "#ffffff"
        self.card_gpu.update_value(f"{gpu['act_mhz']}" if gpu['act_mhz'] else "--", f"Reasons: {reasons.upper()}", color=gpu_color)

        # CPU Clocks
        cpu = data["cpu_freq"]
        p_ghz = (cpu["p_core_mhz"] / 1000.0) if cpu["p_core_mhz"] else 0.0
        e_ghz = (cpu["e_core_mhz"] / 1000.0) if cpu["e_core_mhz"] else 0.0
        self.card_pcore.update_value(f"{p_ghz:.2f}", f"{cpu['p_threads_count']} Threads Active")
        self.card_ecore.update_value(f"{e_ghz:.2f}", f"{cpu['e_threads_count']} Threads Active")

        # Power source badge
        if data["ac_connected"]:
            self.power_src_badge.setText("🔌 AC POWER")
            self.power_src_badge.setStyleSheet(
                "background-color: #1a2333; color: #00e5ff; font-weight: bold; "
                "padding: 6px 12px; border-radius: 6px; border: 1px solid #23354d; font-size: 11px;"
            )
        else:
            self.power_src_badge.setText("🔋 ON BATTERY")
            self.power_src_badge.setStyleSheet(
                "background-color: #2b2214; color: #ffaa00; font-weight: bold; "
                "padding: 6px 12px; border-radius: 6px; border: 1px solid #4a381a; font-size: 11px;"
            )

        # Mini readout on bottom bar
        self.mini_telemetry_lbl.setText(f"•  {temp}°C  |  {watts:.1f}W  |  {fan_rpm} RPM")

        # Tray Tooltip
        self.tray.setToolTip(f"HP Control Center: {watts:.1f}W • {temp}°C • Fan: {fan_rpm} RPM")

    def _setup_tray(self):
        self.tray = QSystemTrayIcon(self)
        self.tray.setIcon(self.style().standardIcon(self.style().StandardPixmap.SP_ComputerIcon))

        tray_menu = QMenu()
        act_gaming = tray_menu.addAction("🚀 Ultra Gaming (25W)")
        act_gaming.triggered.connect(lambda: self._on_profile_selected("ultra_gaming"))

        act_balanced = tray_menu.addAction("⚡ Daily Balanced (24W)")
        act_balanced.triggered.connect(lambda: self._on_profile_selected("balanced"))

        act_eco = tray_menu.addAction("🍃 Silent & Eco (15W)")
        act_eco.triggered.connect(lambda: self._on_profile_selected("eco_quiet"))

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

    # ==============================================
    # AUTOSTART HELPER
    # ==============================================

    def _is_autostart_enabled(self) -> bool:
        autostart_path = os.path.expanduser("~/.config/autostart/hp-control-center.desktop")
        return os.path.exists(autostart_path)

    def _toggle_autostart(self, enabled: bool):
        autostart_dir = os.path.expanduser("~/.config/autostart")
        autostart_path = os.path.join(autostart_dir, "hp-control-center.desktop")
        app_desktop = os.path.expanduser("~/.local/share/applications/hp-control-center.desktop")

        if enabled:
            os.makedirs(autostart_dir, exist_ok=True)
            if os.path.exists(app_desktop):
                try:
                    with open(app_desktop, "r") as src, open(autostart_path, "w") as dst:
                        dst.write(src.read())
                except OSError:
                    pass
        else:
            if os.path.exists(autostart_path):
                try:
                    os.remove(autostart_path)
                except OSError:
                    pass
