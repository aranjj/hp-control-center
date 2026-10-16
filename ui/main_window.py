"""
Main Application Window for Performance Control Center
Layout:
- Left collapsible sidebar (Dashboard, Performance, Graphics, Display, Cooling, System Info, Settings)
- Persistent top bar: Profile segmented control (Ultra Gaming, Balanced, Eco, Custom) - visible on Dashboard & Performance only
- Persistent bottom status bar: Daemon dot, AC state, mini telemetry, unsaved count, Reset, Apply
Follows active KDE / Qt system palette in real-time with symbolic Breeze icons.
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
    QStackedWidget,
    QSystemTrayIcon,
    QMenu,
    QApplication,
    QTextEdit,
    QMessageBox,
    QLineEdit,
    QFileDialog,
    QSlider,
)
from PySide6.QtCore import Qt, QTimer, QSettings, QEvent
from PySide6.QtGui import QIcon, QColor

from core.telemetry import TelemetryReader
from core.profiles import ProfileManager
from core.display import DisplayManager
from core.sysinfo import SystemInfoReader
from core.hardware import get_cpu_topology_info
from ui.styles import (
    STATUS_OK,
    STATUS_WARN,
    STATUS_CRITICAL,
    get_native_stylesheet,
    THEMES,
)
from ui.widgets import (
    StatCard,
    SliderSetting,
    FreqSliderSetting,
    CollapsibleSection,
    SegmentedControl,
    RevertCountdownDialog,
    make_tinted_icon,
    ToggleSwitch,
)

SOCKET_PATH = "/tmp/hp_control_center.sock"

# Single application name constant
APP_NAME = "Control Center"

# Form layout column constants for two-column grid
LABEL_COL_WIDTH = 240
TRAILING_COL_WIDTH = 124
COMBO_WIDTH = 260


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} - i7-1255U")

        self.telemetry = TelemetryReader()
        self.profile_mgr = ProfileManager()
        self.display_mgr = DisplayManager()
        self.sysinfo_reader = SystemInfoReader()
        self.daemon_online = False
        self.unsaved_changes_count = 0
        self.sidebar_expanded = True
        self._is_loading_profile = False
        self._limits_loaded = False
        self._is_updating_display_ui = False

        # Track base profile / baseline values for dirty check
        self._applied_settings = dict(self.profile_mgr.get_profile(self.profile_mgr.current_profile_key))

        # Restore window geometry and theme from QSettings
        self.settings = QSettings("HPControl", "ControlCenter")
        geometry = self.settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)
        else:
            self.resize(880, 840)

        saved_theme = self.settings.value("theme", "Follow System (KDE / Qt Palette)")
        if saved_theme not in THEMES:
            saved_theme = "Follow System (KDE / Qt Palette)"
        self.current_theme = saved_theme

        self._setup_ui()
        self._apply_theme(self.current_theme)
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
        self.profile_segmented.setVisible(True)

    def closeEvent(self, event):
        """Remember window size/position on close."""
        self.settings.setValue("geometry", self.saveGeometry())
        super().closeEvent(event)

    def changeEvent(self, event):
        """React live to KDE Plasma / Qt system palette changes at runtime."""
        if event.type() in (QEvent.Type.PaletteChange, QEvent.Type.ApplicationPaletteChange, QEvent.Type.ThemeChange):
            if not getattr(self, "_in_palette_change", False):
                self._in_palette_change = True
                try:
                    self._apply_theme()
                finally:
                    self._in_palette_change = False
        super().changeEvent(event)

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

        # Sidebar Header / Collapse Toggle with symbolic Breeze icon
        self.btn_collapse = QPushButton("Menu")
        self.btn_collapse.setProperty("class", "MenuCollapseBtn")
        self.btn_collapse.clicked.connect(self._toggle_sidebar)
        sidebar_layout.addWidget(self.btn_collapse)

        # Brand subtitle using single application name constant
        self.brand_lbl = QLabel(APP_NAME.upper())
        self.brand_lbl.setStyleSheet("color: palette(placeholder-text); font-size: 10px; font-weight: bold; letter-spacing: 1px; padding-left: 12px;")
        sidebar_layout.addWidget(self.brand_lbl)
        sidebar_layout.addSpacing(6)

        # Navigation Buttons with symbolic Breeze icon names
        self.nav_buttons = []
        self.nav_items = [
            ("utilities-system-monitor-symbolic", "Dashboard"),
            ("speedometer-symbolic", "Performance"),
            ("video-display-symbolic", "Graphics"),
            ("preferences-desktop-display-symbolic", "Display"),
            ("temperature-cold-symbolic", "Cooling"),
            ("help-about-symbolic", "System Info"),
            ("preferences-system-symbolic", "Settings"),
        ]
        for idx, (icon_name, text) in enumerate(self.nav_items):
            btn = QPushButton(f"  {text}")
            btn.setProperty("class", "NavBtn")
            btn.clicked.connect(lambda checked, i=idx: self._switch_tab(i))
            self.nav_buttons.append(btn)
            sidebar_layout.addWidget(btn)

        sidebar_layout.addStretch()

        # Mini footer in sidebar
        self.side_footer_lbl = QLabel("v0.2-alpha")
        self.side_footer_lbl.setStyleSheet("color: palette(placeholder-text); font-size: 10px; padding-left: 12px;")
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
        # TOP BAR (Profile Switcher visible only on Dashboard & Performance)
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

        # Power Source Badge (Semantic status indicator, native palette background)
        self.power_src_badge = QLabel("AC POWER")
        self.power_src_badge.setStyleSheet(
            f"background-color: palette(base); color: {STATUS_OK}; font-weight: bold; "
            "padding: 6px 12px; border-radius: 6px; border: 1px solid palette(mid); font-size: 11px;"
        )
        top_bar.addWidget(self.power_src_badge)

        content_layout.addLayout(top_bar)

        # High Temperature Global Warning Banner (> 90°C)
        self.warning_banner = QFrame()
        self.warning_banner.setProperty("class", "WarningBox")
        self.warning_banner.setVisible(False)
        w_layout = QHBoxLayout(self.warning_banner)
        w_layout.setContentsMargins(10, 6, 10, 6)
        w_layout.setSpacing(8)

        self.warning_icon_lbl = QLabel()
        w_layout.addWidget(self.warning_icon_lbl)

        self.warning_lbl = QLabel("HIGH TEMPERATURE ALERT: Package temperature is above 90°C! Verify fan cooling.")
        self.warning_lbl.setStyleSheet(f"color: {STATUS_CRITICAL}; font-weight: bold; font-size: 12px;")
        w_layout.addWidget(self.warning_lbl)
        w_layout.addStretch()
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
        # Tab 3: Display
        self.tab_stack.addWidget(self._build_display_tab())
        # Tab 4: Cooling
        self.tab_stack.addWidget(self._build_cooling_tab())
        # Tab 5: System Info
        self.tab_stack.addWidget(self._build_sysinfo_tab())
        # Tab 6: Settings
        self.tab_stack.addWidget(self._build_settings_tab())

        content_layout.addWidget(self.tab_stack, stretch=1)

        # ------------------------------------------
        # PERSISTENT BOTTOM STATUS BAR (With 1px separator above)
        # ------------------------------------------
        self.status_bar_frame = QFrame()
        self.status_bar_frame.setObjectName("StatusBarFrame")
        bottom_bar = QHBoxLayout(self.status_bar_frame)
        bottom_bar.setContentsMargins(0, 8, 0, 0)
        bottom_bar.setSpacing(12)

        # Daemon Dot + Status Text
        self.daemon_dot = QLabel("●")
        self.daemon_dot.setStyleSheet(f"color: {STATUS_CRITICAL}; font-size: 14px;")
        bottom_bar.addWidget(self.daemon_dot)

        self.daemon_lbl = QLabel("Daemon Offline")
        self.daemon_lbl.setStyleSheet("font-weight: 600; color: palette(window-text); font-size: 12px;")
        bottom_bar.addWidget(self.daemon_lbl)

        # Mini Live Telemetry Readout (12px text)
        self.mini_telemetry_lbl = QLabel("--°C  |  --W  |  -- RPM")
        self.mini_telemetry_lbl.setStyleSheet("color: palette(placeholder-text); font-size: 12px; font-weight: 500;")
        bottom_bar.addWidget(self.mini_telemetry_lbl)

        bottom_bar.addStretch()

        # "N Unsaved Changes" Label
        self.unsaved_lbl = QLabel("0 unsaved changes")
        self.unsaved_lbl.setStyleSheet("color: palette(placeholder-text); font-size: 12px; font-style: italic;")
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

        content_layout.addWidget(self.status_bar_frame)

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
        dash_title.setProperty("class", "SectionTitle")
        layout.addWidget(dash_title)

        hud_grid = QGridLayout()
        hud_grid.setSpacing(12)

        # Tile 1: Package Power with Throttle Reason (Uses system accent)
        self.card_power = StatCard("Package Power", "0.0", "W", "Target: 25.0 W")
        hud_grid.addWidget(self.card_power, 0, 0)

        # Tile 2: Package Temp (warn at 80°C, crit at 90°C)
        self.card_temp = StatCard("Package Temp", "--", "°C", "Thermal: Normal", warn_threshold=80.0, crit_threshold=90.0)
        hud_grid.addWidget(self.card_temp, 0, 1)

        # Tile 3: Cooling Fan (Uses system accent)
        self.card_fan = StatCard("Cooling Fan", "--", "RPM", "Automatic EC Control")
        hud_grid.addWidget(self.card_fan, 0, 2)

        # Tile 4: Iris Xe Clock (Uses system accent)
        self.card_gpu = StatCard("Iris Xe Clock", "--", "MHz", "State: Active")
        hud_grid.addWidget(self.card_gpu, 1, 0)

        # Tile 5: P-Core avg clock (Uses system accent)
        p_count = len(self.telemetry.p_core_threads)
        self.card_pcore = StatCard("P-Cores (Avg)", "--", "GHz", f"{p_count} Threads (cpu0-{p_count-1})")
        hud_grid.addWidget(self.card_pcore, 1, 1)

        # Tile 6: E-Core avg clock (Uses system accent)
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

        # ----------------------------------------------------
        # 1. Power Limits (PL1, PL2, Sync to MMIO)
        # ----------------------------------------------------
        card_pwr = QFrame()
        card_pwr.setProperty("class", "CardFrame")
        grid_pwr = QGridLayout(card_pwr)
        grid_pwr.setContentsMargins(12, 12, 12, 12)
        grid_pwr.setHorizontalSpacing(16)
        grid_pwr.setVerticalSpacing(8)
        grid_pwr.setColumnMinimumWidth(0, LABEL_COL_WIDTH)
        grid_pwr.setColumnStretch(0, 0)
        grid_pwr.setColumnStretch(1, 1)
        grid_pwr.setColumnStretch(2, 0)

        title_pwr = QLabel("Power Limits")
        title_pwr.setProperty("class", "SectionTitle")
        grid_pwr.addWidget(title_pwr, 0, 0, 1, 3)

        self.slider_pl1 = SliderSetting("PL1 Sustained Limit (Long-term)", 10, 30, 25, "W", label_width=LABEL_COL_WIDTH)
        self.slider_pl1.valueChanged.connect(self._on_pl1_changed)
        self.slider_pl1.add_to_grid(grid_pwr, 1)

        self.slider_pl2 = SliderSetting("PL2 Burst Limit (Short-term)", 10, 45, 28, "W", label_width=LABEL_COL_WIDTH)
        self.slider_pl2.valueChanged.connect(self._on_pl2_changed)
        self.slider_pl2.add_to_grid(grid_pwr, 2)

        lbl_mmio = QLabel("MMIO Synchronization:")
        lbl_mmio.setProperty("class", "FormLabel")
        lbl_mmio.setFixedWidth(LABEL_COL_WIDTH)
        self.chk_sync_mmio = ToggleSwitch("Sync to MMIO (MCHBAR 0x59A0 - Defeats EC lock)")
        self.chk_sync_mmio.setChecked(True)
        self.chk_sync_mmio.toggled.connect(self._on_setting_modified)
        grid_pwr.addWidget(lbl_mmio, 3, 0)
        grid_pwr.addWidget(self.chk_sync_mmio, 3, 1, 1, 2)

        layout.addWidget(card_pwr)

        # ----------------------------------------------------
        # 2. CPU Clock Limits (Step 2)
        # ----------------------------------------------------
        self.card_clk = QFrame()
        self.card_clk.setProperty("class", "CardFrame")
        grid_clk = QGridLayout(self.card_clk)
        grid_clk.setContentsMargins(12, 12, 12, 12)
        grid_clk.setHorizontalSpacing(16)
        grid_clk.setVerticalSpacing(8)
        grid_clk.setColumnMinimumWidth(0, LABEL_COL_WIDTH)
        grid_clk.setColumnStretch(0, 0)
        grid_clk.setColumnStretch(1, 1)
        grid_clk.setColumnStretch(2, 0)

        title_clk = QLabel("CPU Clock Limits")
        title_clk.setProperty("class", "SectionTitle")
        grid_clk.addWidget(title_clk, 0, 0, 1, 3)

        topo = get_cpu_topology_info()
        self.cpu_topo = topo

        # P-core max frequency slider
        self.slider_p_max = FreqSliderSetting(
            "P-core max frequency",
            topo["p_min_mhz"],
            topo["p_max_mhz"],
            topo["p_max_mhz"],
            label_width=LABEL_COL_WIDTH,
        )
        self.slider_p_max.valueChanged.connect(self._on_setting_modified)
        self.slider_p_max.add_to_grid(grid_clk, 1)
        if not topo["p_supported"]:
            self.slider_p_max.set_enabled(False, "P-cores not detected on this system")

        # E-core max frequency slider
        self.slider_e_max = FreqSliderSetting(
            "E-core max frequency",
            topo["e_min_mhz"],
            topo["e_max_mhz"],
            topo["e_max_mhz"],
            label_width=LABEL_COL_WIDTH,
        )
        self.slider_e_max.valueChanged.connect(self._on_setting_modified)
        self.slider_e_max.add_to_grid(grid_clk, 2)
        if not topo["e_supported"]:
            self.slider_e_max.set_enabled(False, "E-cores not detected on this system")

        # Optional minimum frequency sliders in an Advanced collapsible inside this card
        self.clk_advanced_sec = CollapsibleSection("Advanced Minimum Frequency Limits", is_expanded=False)
        clk_adv_widget = QWidget()
        clk_adv_grid = QGridLayout(clk_adv_widget)
        clk_adv_grid.setContentsMargins(0, 6, 0, 6)
        clk_adv_grid.setHorizontalSpacing(16)
        clk_adv_grid.setVerticalSpacing(8)
        clk_adv_grid.setColumnMinimumWidth(0, LABEL_COL_WIDTH)
        clk_adv_grid.setColumnStretch(0, 0)
        clk_adv_grid.setColumnStretch(1, 1)
        clk_adv_grid.setColumnStretch(2, 0)

        self.slider_p_min = FreqSliderSetting(
            "P-core min frequency",
            topo["p_min_mhz"],
            topo["p_max_mhz"],
            topo["p_min_mhz"],
            label_width=LABEL_COL_WIDTH,
        )
        self.slider_p_min.valueChanged.connect(self._on_setting_modified)
        self.slider_p_min.add_to_grid(clk_adv_grid, 0)
        if not topo["p_supported"]:
            self.slider_p_min.set_enabled(False, "P-cores not detected on this system")

        self.slider_e_min = FreqSliderSetting(
            "E-core min frequency",
            topo["e_min_mhz"],
            topo["e_max_mhz"],
            topo["e_min_mhz"],
            label_width=LABEL_COL_WIDTH,
        )
        self.slider_e_min.valueChanged.connect(self._on_setting_modified)
        self.slider_e_min.add_to_grid(clk_adv_grid, 1)
        if not topo["e_supported"]:
            self.slider_e_min.set_enabled(False, "E-cores not detected on this system")

        self.clk_advanced_sec.add_widget(clk_adv_widget)
        grid_clk.addWidget(self.clk_advanced_sec, 3, 0, 1, 3)

        layout.addWidget(self.card_clk)

        # ----------------------------------------------------
        # 3. Core Management (Step 3)
        # ----------------------------------------------------
        self.card_core = QFrame()
        self.card_core.setProperty("class", "CardFrame")
        grid_core = QGridLayout(self.card_core)
        grid_core.setContentsMargins(12, 12, 12, 12)
        grid_core.setHorizontalSpacing(16)
        grid_core.setVerticalSpacing(8)
        grid_core.setColumnMinimumWidth(0, LABEL_COL_WIDTH)
        grid_core.setColumnStretch(0, 0)
        grid_core.setColumnStretch(1, 1)
        grid_core.setColumnStretch(2, 0)

        title_core = QLabel("Core Management")
        title_core.setProperty("class", "SectionTitle")
        grid_core.addWidget(title_core, 0, 0, 1, 3)
        layout.addWidget(self.card_core)

        # ----------------------------------------------------
        # 4. Thermal Target (Step 4)
        # ----------------------------------------------------
        self.card_therm = QFrame()
        self.card_therm.setProperty("class", "CardFrame")
        grid_therm = QGridLayout(self.card_therm)
        grid_therm.setContentsMargins(12, 12, 12, 12)
        grid_therm.setHorizontalSpacing(16)
        grid_therm.setVerticalSpacing(8)
        grid_therm.setColumnMinimumWidth(0, LABEL_COL_WIDTH)
        grid_therm.setColumnStretch(0, 0)
        grid_therm.setColumnStretch(1, 1)
        grid_therm.setColumnStretch(2, 0)

        title_therm = QLabel("Thermal Target")
        title_therm.setProperty("class", "SectionTitle")
        grid_therm.addWidget(title_therm, 0, 0, 1, 3)
        layout.addWidget(self.card_therm)

        # ----------------------------------------------------
        # 5. Behavior (Intel Turbo Boost toggle, EPP dropdown)
        # ----------------------------------------------------
        card_beh = QFrame()
        card_beh.setProperty("class", "CardFrame")
        grid_beh = QGridLayout(card_beh)
        grid_beh.setContentsMargins(12, 12, 12, 12)
        grid_beh.setHorizontalSpacing(16)
        grid_beh.setVerticalSpacing(8)
        grid_beh.setColumnMinimumWidth(0, LABEL_COL_WIDTH)
        grid_beh.setColumnStretch(0, 0)
        grid_beh.setColumnStretch(1, 1)
        grid_beh.setColumnStretch(2, 0)

        title_beh = QLabel("CPU Behavior")
        title_beh.setProperty("class", "SectionTitle")
        grid_beh.addWidget(title_beh, 0, 0, 1, 3)

        lbl_turbo = QLabel("Processor Turbo:")
        lbl_turbo.setProperty("class", "FormLabel")
        lbl_turbo.setFixedWidth(LABEL_COL_WIDTH)
        self.chk_turbo = ToggleSwitch("Intel Turbo Boost (Up to 4.7 GHz)")
        self.chk_turbo.setChecked(True)
        self.chk_turbo.toggled.connect(self._on_setting_modified)
        grid_beh.addWidget(lbl_turbo, 1, 0)
        grid_beh.addWidget(self.chk_turbo, 1, 1, 1, 2)

        lbl_epp = QLabel("Energy Bias Preference (EPP):")
        lbl_epp.setProperty("class", "FormLabel")
        lbl_epp.setFixedWidth(LABEL_COL_WIDTH)
        self.combo_epp = QComboBox()
        self.combo_epp.setFixedWidth(COMBO_WIDTH)
        self.combo_epp.addItems(["performance", "balance_performance", "balance_power", "power"])
        self.combo_epp.currentIndexChanged.connect(self._on_setting_modified)
        grid_beh.addWidget(lbl_epp, 2, 0)
        grid_beh.addWidget(self.combo_epp, 2, 1, Qt.AlignLeft)

        layout.addWidget(card_beh)

        # ----------------------------------------------------
        # 6. Advanced (BD PROCHOT, collapsed by default, red warning)
        # ----------------------------------------------------
        self.advanced_sec = CollapsibleSection("Advanced Hardware Settings (BD PROCHOT)", is_expanded=False)

        adv_warn = QLabel("WARNING: BD PROCHOT (Bi-directional Processor Hot) protects VRMs from overheating.\n"
                          "Disabling it prevents the 400 MHz lockout bug, but should only be used if temperatures are monitored.")
        adv_warn.setStyleSheet(f"color: {STATUS_CRITICAL}; font-size: 12px; font-weight: 500;")
        adv_warn.setWordWrap(True)
        self.advanced_sec.add_widget(adv_warn)

        self.chk_bdprochot = ToggleSwitch("Disable BD PROCHOT (Emergency Throttling Override)")
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
        grid = QGridLayout(card)
        grid.setContentsMargins(12, 12, 12, 12)
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(8)
        grid.setColumnMinimumWidth(0, LABEL_COL_WIDTH)
        grid.setColumnStretch(0, 0)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(2, 0)

        title = QLabel("Intel Iris Xe Graphics Tuning (Linux xe driver)")
        title.setProperty("class", "SectionTitle")
        grid.addWidget(title, 0, 0, 1, 3)

        desc = QLabel("Set GPU frequency floors to eliminate frame-time spikes and stutter in 3D gaming.")
        desc.setProperty("class", "Footnote")
        grid.addWidget(desc, 1, 0, 1, 3)

        self.slider_gpu_min = SliderSetting("Minimum GPU Frequency", 100, 1250, 800, "MHz", label_width=LABEL_COL_WIDTH)
        self.slider_gpu_min.valueChanged.connect(self._on_setting_modified)
        self.slider_gpu_min.add_to_grid(grid, 2)

        self.slider_gpu_max = SliderSetting("Maximum GPU Frequency", 100, 1250, 1250, "MHz", label_width=LABEL_COL_WIDTH)
        self.slider_gpu_max.valueChanged.connect(self._on_setting_modified)
        self.slider_gpu_max.add_to_grid(grid, 3)

        lbl_gp = QLabel("GPU Power Mode:")
        lbl_gp.setProperty("class", "FormLabel")
        lbl_gp.setFixedWidth(LABEL_COL_WIDTH)
        self.combo_gpu_power = QComboBox()
        self.combo_gpu_power.setFixedWidth(COMBO_WIDTH)
        self.combo_gpu_power.addItems(["base", "power_saving"])
        self.combo_gpu_power.currentIndexChanged.connect(self._on_setting_modified)
        grid.addWidget(lbl_gp, 4, 0)
        grid.addWidget(self.combo_gpu_power, 4, 1, Qt.AlignLeft)

        layout.addWidget(card)
        layout.addStretch()

        scroll.setWidget(content)
        return scroll

    def _build_display_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 4, 10, 0)
        layout.setSpacing(14)

        disp_state = self.display_mgr.get_display_state()
        self._disp_output_name = disp_state["output_name"] if disp_state else "eDP-1"

        # Card 1: Display Output & Modes (Instant-safe with 15s Revert - no per-row Apply buttons!)
        card_modes = QFrame()
        card_modes.setProperty("class", "CardFrame")
        g1 = QGridLayout(card_modes)
        g1.setContentsMargins(12, 12, 12, 12)
        g1.setHorizontalSpacing(16)
        g1.setVerticalSpacing(8)
        g1.setColumnMinimumWidth(0, LABEL_COL_WIDTH)
        g1.setColumnStretch(0, 0)
        g1.setColumnStretch(1, 1)
        g1.setColumnStretch(2, 0)

        c1_title = QLabel("Display Resolution, Refresh Rate & Scaling")
        c1_title.setProperty("class", "SectionTitle")
        g1.addWidget(c1_title, 0, 0, 1, 3)

        panel_info = QLabel(f"Panel: {self._disp_output_name} (Active Laptop Display)")
        panel_info.setProperty("class", "Footnote")
        g1.addWidget(panel_info, 1, 0, 1, 3)

        lbl_mode = QLabel("Resolution & Refresh Rate:")
        lbl_mode.setProperty("class", "FormLabel")
        lbl_mode.setFixedWidth(LABEL_COL_WIDTH)
        self.combo_disp_mode = QComboBox()
        self.combo_disp_mode.setFixedWidth(COMBO_WIDTH)
        current_idx = 0
        if disp_state and disp_state.get("modes"):
            for idx, m in enumerate(disp_state["modes"]):
                self.combo_disp_mode.addItem(m["label"], m["id"])
                if m.get("is_current"):
                    current_idx = idx
            self.combo_disp_mode.setCurrentIndex(current_idx)
        self._prev_disp_mode = self.combo_disp_mode.currentData()
        self.combo_disp_mode.currentIndexChanged.connect(self._on_disp_mode_changed)
        g1.addWidget(lbl_mode, 2, 0)
        g1.addWidget(self.combo_disp_mode, 2, 1, Qt.AlignLeft)

        lbl_scale = QLabel("Display Scale Factor:")
        lbl_scale.setProperty("class", "FormLabel")
        lbl_scale.setFixedWidth(LABEL_COL_WIDTH)
        self.combo_disp_scale = QComboBox()
        self.combo_disp_scale.setFixedWidth(COMBO_WIDTH)
        scale_options = [("100% (Native 1.0x)", 1.0), ("125% (1.25x)", 1.25), ("150% (1.50x)", 1.5)]
        current_scale = disp_state.get("scale", 1.0) if disp_state else 1.0
        cur_s_idx = 0
        for s_idx, (s_lbl, s_val) in enumerate(scale_options):
            self.combo_disp_scale.addItem(s_lbl, s_val)
            if abs(s_val - current_scale) < 0.05:
                cur_s_idx = s_idx
        self.combo_disp_scale.setCurrentIndex(cur_s_idx)
        self._prev_disp_scale = self.combo_disp_scale.currentData()
        self.combo_disp_scale.currentIndexChanged.connect(self._on_disp_scale_changed)
        g1.addWidget(lbl_scale, 3, 0)
        g1.addWidget(self.combo_disp_scale, 3, 1, Qt.AlignLeft)

        layout.addWidget(card_modes)

        # Card 2: Brightness Control with Sun Icons at each end
        card_bright = QFrame()
        card_bright.setProperty("class", "CardFrame")
        g2 = QGridLayout(card_bright)
        g2.setContentsMargins(12, 12, 12, 12)
        g2.setHorizontalSpacing(16)
        g2.setVerticalSpacing(8)
        g2.setColumnMinimumWidth(0, LABEL_COL_WIDTH)
        g2.setColumnStretch(0, 0)
        g2.setColumnStretch(1, 1)
        g2.setColumnStretch(2, 0)

        c2_title = QLabel("Panel Brightness")
        c2_title.setProperty("class", "SectionTitle")
        g2.addWidget(c2_title, 0, 0, 1, 3)

        lbl_bright = QLabel("Panel Backlight:")
        lbl_bright.setProperty("class", "FormLabel")
        lbl_bright.setFixedWidth(LABEL_COL_WIDTH)

        bright_ctrl = QWidget()
        bright_h = QHBoxLayout(bright_ctrl)
        bright_h.setContentsMargins(0, 0, 0, 0)
        bright_h.setSpacing(8)

        self.sun_low_lbl = QLabel()
        bright_h.addWidget(self.sun_low_lbl)

        self.slider_bright = QSlider(Qt.Horizontal)
        self.slider_bright.setRange(0, 100)
        init_bright = disp_state.get("brightness", 100) if disp_state else 100
        self.slider_bright.setValue(init_bright)
        self.slider_bright.valueChanged.connect(self._on_disp_brightness_slider_changed)
        bright_h.addWidget(self.slider_bright)

        self.sun_high_lbl = QLabel()
        bright_h.addWidget(self.sun_high_lbl)

        self.lbl_bright_val = QLabel(f"{init_bright} %")
        self.lbl_bright_val.setProperty("class", "Value")
        self.lbl_bright_val.setFixedWidth(TRAILING_COL_WIDTH)
        self.lbl_bright_val.setAlignment(Qt.AlignCenter)

        g2.addWidget(lbl_bright, 1, 0)
        g2.addWidget(bright_ctrl, 1, 1)
        g2.addWidget(self.lbl_bright_val, 1, 2)

        layout.addWidget(card_bright)

        # Card 3: Color Range & VRR
        card_color = QFrame()
        card_color.setProperty("class", "CardFrame")
        g3 = QGridLayout(card_color)
        g3.setContentsMargins(12, 12, 12, 12)
        g3.setHorizontalSpacing(16)
        g3.setVerticalSpacing(8)
        g3.setColumnMinimumWidth(0, LABEL_COL_WIDTH)
        g3.setColumnStretch(0, 0)
        g3.setColumnStretch(1, 1)
        g3.setColumnStretch(2, 0)

        c3_title = QLabel("Advanced Color Range & VRR")
        c3_title.setProperty("class", "SectionTitle")
        g3.addWidget(c3_title, 0, 0, 1, 3)

        # RGB Dynamic Range
        lbl_rgb = QLabel("RGB Dynamic Range:")
        lbl_rgb.setProperty("class", "FormLabel")
        lbl_rgb.setFixedWidth(LABEL_COL_WIDTH)
        self.combo_rgb = QComboBox()
        self.combo_rgb.setFixedWidth(COMBO_WIDTH)
        self.combo_rgb.addItem("Automatic (Recommended)", "automatic")
        self.combo_rgb.addItem("Full Dynamic Range (0-255)", "full")
        self.combo_rgb.addItem("Limited Range (16-235)", "limited")
        cur_rgb = disp_state.get("rgb_range", "automatic") if disp_state else "automatic"
        if cur_rgb == "full":
            self.combo_rgb.setCurrentIndex(1)
        elif cur_rgb == "limited":
            self.combo_rgb.setCurrentIndex(2)
        else:
            self.combo_rgb.setCurrentIndex(0)
        self.combo_rgb.currentIndexChanged.connect(self._on_rgb_range_changed)
        g3.addWidget(lbl_rgb, 1, 0)
        g3.addWidget(self.combo_rgb, 1, 1, Qt.AlignLeft)

        # VRR Control: Disabled (greyed out) on internal panel with informative tooltip
        lbl_vrr = QLabel("Variable Refresh Rate (VRR):")
        lbl_vrr.setProperty("class", "FormLabel")
        lbl_vrr.setFixedWidth(LABEL_COL_WIDTH)
        self.combo_vrr = QComboBox()
        self.combo_vrr.setFixedWidth(COMBO_WIDTH)
        self.combo_vrr.addItem("Automatic", "automatic")
        self.combo_vrr.addItem("Always Enabled", "always")
        self.combo_vrr.addItem("Never (Disabled)", "never")
        vrr_capable = disp_state.get("vrr_capable", False) if disp_state else False

        if not vrr_capable:
            self.combo_vrr.setEnabled(False)
            reason = "VRR / Adaptive Sync is not supported by the internal eDP laptop panel. Supported on compatible external FreeSync/G-Sync displays via DisplayPort/HDMI."
            self.combo_vrr.setToolTip(reason)
            lbl_vrr.setEnabled(False)
            lbl_vrr.setToolTip(reason)

        g3.addWidget(lbl_vrr, 2, 0)
        g3.addWidget(self.combo_vrr, 2, 1, Qt.AlignLeft)

        layout.addWidget(card_color)

        # Card 4: Color Profile (ICC)
        card_icc = QFrame()
        card_icc.setProperty("class", "CardFrame")
        g4 = QGridLayout(card_icc)
        g4.setContentsMargins(12, 12, 12, 12)
        g4.setHorizontalSpacing(16)
        g4.setVerticalSpacing(8)
        g4.setColumnMinimumWidth(0, LABEL_COL_WIDTH)
        g4.setColumnStretch(0, 0)
        g4.setColumnStretch(1, 1)
        g4.setColumnStretch(2, 0)

        c4_title = QLabel("ICC Color Profile")
        c4_title.setProperty("class", "SectionTitle")
        g4.addWidget(c4_title, 0, 0, 1, 3)

        lbl_src = QLabel("Profile Source:")
        lbl_src.setProperty("class", "FormLabel")
        lbl_src.setFixedWidth(LABEL_COL_WIDTH)
        self.combo_icc_source = QComboBox()
        self.combo_icc_source.setFixedWidth(COMBO_WIDTH)
        self.combo_icc_source.addItem("EDID Native Panel Curve", "EDID")
        self.combo_icc_source.addItem("Standard sRGB", "sRGB")
        self.combo_icc_source.addItem("Custom ICC Profile", "ICC")
        self.combo_icc_source.currentIndexChanged.connect(self._on_icc_source_changed)
        g4.addWidget(lbl_src, 1, 0)
        g4.addWidget(self.combo_icc_source, 1, 1, Qt.AlignLeft)

        # Custom ICC Path row with trailing Browse button
        lbl_path = QLabel("Custom Profile Path:")
        lbl_path.setProperty("class", "FormLabel")
        lbl_path.setFixedWidth(LABEL_COL_WIDTH)
        self.txt_icc_path = QLineEdit()
        self.txt_icc_path.setPlaceholderText("Select custom .icc / .icm profile file...")
        self.txt_icc_path.setEnabled(False)
        if disp_state and disp_state.get("icc_profile"):
            self.txt_icc_path.setText(disp_state["icc_profile"])
            self.txt_icc_path.setEnabled(True)
            self.combo_icc_source.setCurrentIndex(2)

        self.btn_browse_icc = QPushButton("Browse...")
        self.btn_browse_icc.setProperty("class", "SecondaryButton")
        self.btn_browse_icc.setFixedWidth(TRAILING_COL_WIDTH)
        self.btn_browse_icc.clicked.connect(self._browse_icc_file)

        g4.addWidget(lbl_path, 2, 0)
        g4.addWidget(self.txt_icc_path, 2, 1)
        g4.addWidget(self.btn_browse_icc, 2, 2, Qt.AlignRight)

        layout.addWidget(card_icc)
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

        title = QLabel("Cooling & Thermal Management")
        title.setProperty("class", "SectionTitle")
        c_layout.addWidget(title)

        self.cooling_fan_lbl = QLabel("Fan Mode: Automatic EC Firmware Control (Hardware Governed)")
        self.cooling_fan_lbl.setProperty("class", "CoolingFanAccent")
        c_layout.addWidget(self.cooling_fan_lbl)

        info = QLabel(
            "Chassis firmware hardwires fan tachometer control to internal EC thermal sensors.\n"
            "Fan automatically scales up to ~3,500+ RPM when sustained 25W load is active."
        )
        info.setProperty("class", "Footnote")
        c_layout.addWidget(info)

        c_layout.addSpacing(10)
        placeholder_title = QLabel("Custom Fan Curve Editor (Placeholder)")
        placeholder_title.setProperty("class", "FormLabel")
        c_layout.addWidget(placeholder_title)

        placeholder_box = QFrame()
        placeholder_box.setStyleSheet("background-color: palette(alternate-base); border: 1px dashed palette(mid); border-radius: 8px; padding: 20px;")
        p_box_layout = QVBoxLayout(placeholder_box)
        p_msg = QLabel("Future Feature: NoteBook Fan Control (NBFC) / Direct EC Register Curve Hook")
        p_msg.setAlignment(Qt.AlignCenter)
        p_msg.setProperty("class", "Footnote")
        p_box_layout.addWidget(p_msg)
        c_layout.addWidget(placeholder_box)

        layout.addWidget(card)
        layout.addStretch()
        return widget

    def _build_sysinfo_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 4, 10, 0)
        layout.setSpacing(14)

        # Header with Copy Button
        header_row = QHBoxLayout()
        title_box = QVBoxLayout()
        s_title = QLabel("System & Hardware Diagnostics")
        s_title.setProperty("class", "SectionTitle")
        s_desc = QLabel("Detailed hardware topology, kernel driver, Vulkan, and Mesa stack specifications")
        s_desc.setProperty("class", "Footnote")
        title_box.addWidget(s_title)
        title_box.addWidget(s_desc)
        header_row.addLayout(title_box)
        header_row.addStretch()

        self.btn_copy_report = QPushButton("Copy Report")
        self.btn_copy_report.setProperty("class", "SecondaryButton")
        self.btn_copy_report.clicked.connect(lambda: self._copy_to_clipboard(
            self.sysinfo_reader.generate_markdown_report(), self.btn_copy_report
        ))
        header_row.addWidget(self.btn_copy_report)
        layout.addLayout(header_row)

        dmi = self.sysinfo_reader.get_dmi_info()
        cpu = self.sysinfo_reader.get_cpu_info()
        gpu = self.sysinfo_reader.get_graphics_info()
        os_info = self.sysinfo_reader.get_os_info()
        mem = self.sysinfo_reader.get_memory_info()

        # Card 1: Graphics & Drivers Stack
        card_gpu = QFrame()
        card_gpu.setProperty("class", "CardFrame")
        cg_layout = QVBoxLayout(card_gpu)
        cg_layout.setSpacing(10)

        cg_title = QLabel("Graphics & Driver Stack")
        cg_title.setProperty("class", "SectionTitle")
        cg_layout.addWidget(cg_title)

        cg_layout.addLayout(self._create_spec_row("Active Kernel Driver:", f"<b>{gpu['kernel_driver']}</b> (Modern Intel Xe KMD)", accent=True))
        cg_layout.addLayout(self._create_spec_row("Available Kernel Drivers:", gpu['kernel_modules']))
        cg_layout.addLayout(self._create_spec_row("GPU Device Name:", gpu['device_name']))
        cg_layout.addLayout(self._create_spec_row("PCI Location / IDs:", gpu['pci_id']))
        cg_layout.addLayout(self._create_spec_row("Mesa Driver Version:", gpu['mesa_version'], accent=True))
        cg_layout.addLayout(self._create_spec_row("Vulkan API Support:", f"{gpu['vulkan_api']} ({gpu['vulkan_driver']})"))
        cg_layout.addLayout(self._create_spec_row("OpenGL Core Profile:", gpu['opengl_version']))
        layout.addWidget(card_gpu)

        # Card 2: Hardware & Motherboard
        card_hw = QFrame()
        card_hw.setProperty("class", "CardFrame")
        ch_layout = QVBoxLayout(card_hw)
        ch_layout.setSpacing(10)

        ch_title = QLabel("Hardware & Chassis")
        ch_title.setProperty("class", "SectionTitle")
        ch_layout.addWidget(ch_title)

        ch_layout.addLayout(self._create_spec_row("Device Model:", f"{dmi['sys_vendor']} {dmi['product_name']}"))
        ch_layout.addLayout(self._create_spec_row("BIOS / UEFI Firmware:", f"{dmi['bios_version']} ({dmi['bios_date']})"))
        ch_layout.addLayout(self._create_spec_row("Processor (CPU):", f"{cpu['model']}"))
        ch_layout.addLayout(self._create_spec_row("Cores & Threads:", f"<b>{cpu['summary']}</b>", accent=True))
        ch_layout.addLayout(self._create_spec_row("Total System Memory:", mem))
        layout.addWidget(card_hw)

        # Card 3: Linux Operating System
        card_os = QFrame()
        card_os.setProperty("class", "CardFrame")
        co_layout = QVBoxLayout(card_os)
        co_layout.setSpacing(10)

        co_title = QLabel("Operating System & Environment")
        co_title.setProperty("class", "SectionTitle")
        co_layout.addWidget(co_title)

        co_layout.addLayout(self._create_spec_row("Linux Distribution:", os_info['distro']))
        co_layout.addLayout(self._create_spec_row("Kernel Release:", f"<b>{os_info['kernel']}</b> ({os_info['arch']})", accent=True))
        co_layout.addLayout(self._create_spec_row("Windowing Session:", os_info['session']))
        co_layout.addLayout(self._create_spec_row("Thermal Subsystem:", f"{os_info['thermald']} + hp-wmi"))
        layout.addWidget(card_os)

        layout.addStretch()
        scroll.setWidget(content)
        return scroll

    def _create_spec_row(self, label: str, value: str, accent: bool = False) -> QHBoxLayout:
        row = QHBoxLayout()
        l_lbl = QLabel(label)
        l_lbl.setProperty("class", "FormLabel")
        l_lbl.setFixedWidth(LABEL_COL_WIDTH)
        v_lbl = QLabel(value)
        if accent:
            v_lbl.setProperty("class", "CoolingFanAccent")
        else:
            v_lbl.setProperty("class", "Value")
        v_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        row.addWidget(l_lbl)
        row.addWidget(v_lbl)
        row.addStretch()
        return row

    def _build_settings_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 4, 10, 0)
        layout.setSpacing(14)

        card = QFrame()
        card.setProperty("class", "CardFrame")
        grid = QGridLayout(card)
        grid.setContentsMargins(12, 12, 12, 12)
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(8)
        grid.setColumnMinimumWidth(0, LABEL_COL_WIDTH)
        grid.setColumnStretch(0, 0)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(2, 0)

        title = QLabel("Application Settings")
        title.setProperty("class", "SectionTitle")
        grid.addWidget(title, 0, 0, 1, 3)

        # Autostart Toggle in two-column grid
        lbl_auto = QLabel("Application Autostart:")
        lbl_auto.setProperty("class", "FormLabel")
        lbl_auto.setFixedWidth(LABEL_COL_WIDTH)
        self.chk_autostart = ToggleSwitch("Start on System Login")
        self.chk_autostart.setChecked(self._is_autostart_enabled())
        self.chk_autostart.toggled.connect(self._toggle_autostart)
        grid.addWidget(lbl_auto, 1, 0)
        grid.addWidget(self.chk_autostart, 1, 1, 1, 2)

        # Theme selector in two-column grid
        lbl_th = QLabel("Color Theme:")
        lbl_th.setProperty("class", "FormLabel")
        lbl_th.setFixedWidth(LABEL_COL_WIDTH)
        self.combo_theme = QComboBox()
        self.combo_theme.setFixedWidth(COMBO_WIDTH)
        self.combo_theme.addItems(list(THEMES.keys()))
        self.combo_theme.setCurrentText(self.current_theme)
        self.combo_theme.currentTextChanged.connect(self._on_theme_changed)
        grid.addWidget(lbl_th, 2, 0)
        grid.addWidget(self.combo_theme, 2, 1, Qt.AlignLeft)

        layout.addWidget(card)

        # Daemon Status & Instructions Card
        d_card = QFrame()
        d_card.setProperty("class", "CardFrame")
        d_layout = QVBoxLayout(d_card)
        d_layout.setSpacing(10)

        d_title = QLabel("Hardware Sync Daemon (Root Service)")
        d_title.setProperty("class", "SectionTitle")
        d_layout.addWidget(d_title)

        self.daemon_detail_lbl = QLabel("Status: Checking...")
        self.daemon_detail_lbl.setProperty("class", "Footnote")
        d_layout.addWidget(self.daemon_detail_lbl)

        # Copyable Commands Header & Action
        cmd_hdr = QHBoxLayout()
        cmd_info = QLabel("Enable background service (run from project folder):")
        cmd_info.setProperty("class", "Footnote")
        cmd_hdr.addWidget(cmd_info)
        cmd_hdr.addStretch()

        daemon_cmds_text = (
            "sudo cp daemon/hp-control-daemon.service /etc/systemd/system/\n"
            "sudo systemctl daemon-reload\n"
            "sudo systemctl enable --now hp-control-daemon"
        )

        self.btn_copy_cmds = QPushButton("Copy Commands")
        self.btn_copy_cmds.setProperty("class", "SecondaryButton")
        self.btn_copy_cmds.setFixedHeight(28)
        self.btn_copy_cmds.clicked.connect(lambda: self._copy_to_clipboard(daemon_cmds_text, self.btn_copy_cmds))
        cmd_hdr.addWidget(self.btn_copy_cmds)
        d_layout.addLayout(cmd_hdr)

        d_cmds = QLabel(daemon_cmds_text)
        d_cmds.setProperty("class", "CodeBlock")
        d_cmds.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
        d_layout.addWidget(d_cmds)

        layout.addWidget(d_card)

        # Log Viewer Section
        self.log_section = CollapsibleSection("Recent System & Daemon Logs", is_expanded=False)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFixedHeight(160)
        self.log_text.setPlainText(f"{APP_NAME} v0.2-alpha started.\nPolling sensors every 1000ms.\n")
        self.log_section.add_widget(self.log_text)
        layout.addWidget(self.log_section)

        layout.addStretch()
        scroll.setWidget(content)
        return scroll

    # ==============================================
    # THEME & ICONS APPLICATION
    # ==============================================

    def _on_theme_changed(self, theme_name: str):
        if theme_name in THEMES:
            self.settings.setValue("theme", theme_name)
            self._apply_theme(theme_name)

    def _apply_theme(self, theme_name: str = None):
        if theme_name:
            self.current_theme = theme_name

        pal = QApplication.palette()
        hl = pal.highlight().color()
        accent_tint = f"rgba({hl.red()}, {hl.green()}, {hl.blue()}, 0.15)"
        stylesheet = get_native_stylesheet(accent_tint)

        app = QApplication.instance()
        if app:
            app.setStyleSheet(stylesheet)
        self.setStyleSheet(stylesheet)

        # Recolor symbolic icons
        self._recolor_symbolic_icons()

        # Repolish widgets with dynamic state/theme classes
        if hasattr(self, "profile_segmented"):
            for btn in self.profile_segmented.buttons.values():
                btn.style().unpolish(btn)
                btn.style().polish(btn)
        if hasattr(self, "nav_buttons") and hasattr(self, "tab_stack"):
            active_tab = self.tab_stack.currentIndex()
            self._update_nav_buttons(active_tab)
        if hasattr(self, "btn_collapse"):
            self.btn_collapse.style().unpolish(self.btn_collapse)
            self.btn_collapse.style().polish(self.btn_collapse)
        if hasattr(self, "cooling_fan_lbl"):
            self.cooling_fan_lbl.style().unpolish(self.cooling_fan_lbl)
            self.cooling_fan_lbl.style().polish(self.cooling_fan_lbl)
        if hasattr(self, "card_power"):
            for card in [getattr(self, c, None) for c in ["card_power", "card_temp", "card_fan", "card_gpu", "card_pcore", "card_ecore"]]:
                if card:
                    if hasattr(card, "unit_lbl"):
                        card.unit_lbl.style().unpolish(card.unit_lbl)
                        card.unit_lbl.style().polish(card.unit_lbl)
                    if hasattr(card, "sparkline"):
                        card.sparkline.update()
        self.update()

    def _recolor_symbolic_icons(self):
        """Tint all symbolic Breeze icons with text color (or accent when selected)."""
        pal = self.palette()
        text_color = pal.windowText().color()
        accent_color = pal.highlight().color()
        btn_text_color = pal.buttonText().color()

        # Collapse menu button
        if hasattr(self, "btn_collapse"):
            self.btn_collapse.setIcon(make_tinted_icon("application-menu-symbolic", text_color, 16))

        # Nav sidebar buttons
        active_tab = self.tab_stack.currentIndex() if hasattr(self, "tab_stack") else 0
        if hasattr(self, "nav_buttons") and hasattr(self, "nav_items"):
            for idx, (icon_name, _) in enumerate(self.nav_items):
                c = accent_color if idx == active_tab else text_color
                self.nav_buttons[idx].setIcon(make_tinted_icon(icon_name, c, 18))

        # Slider reset buttons
        for slider in [
            getattr(self, s, None) for s in [
                "slider_pl1", "slider_pl2", "slider_gpu_min", "slider_gpu_max",
                "slider_p_max", "slider_e_max", "slider_p_min", "slider_e_min",
            ]
        ]:
            if slider and hasattr(slider, "recolor_icon"):
                slider.recolor_icon(btn_text_color)

        # Sun icons on brightness slider
        if hasattr(self, "sun_low_lbl") and hasattr(self, "sun_high_lbl"):
            self.sun_low_lbl.setPixmap(make_tinted_icon("brightness-low-symbolic", pal.placeholderText().color(), 16).pixmap(16, 16))
            self.sun_high_lbl.setPixmap(make_tinted_icon("brightness-high-symbolic", pal.placeholderText().color(), 16).pixmap(16, 16))

        # Browse & Copy buttons
        if hasattr(self, "btn_browse_icc"):
            self.btn_browse_icc.setIcon(make_tinted_icon("document-open-symbolic", btn_text_color, 14))
        if hasattr(self, "btn_copy_report"):
            self.btn_copy_report.setIcon(make_tinted_icon("edit-copy-symbolic", btn_text_color, 14))
        if hasattr(self, "btn_copy_cmds"):
            self.btn_copy_cmds.setIcon(make_tinted_icon("edit-copy-symbolic", btn_text_color, 14))
        if hasattr(self, "warning_icon_lbl"):
            self.warning_icon_lbl.setPixmap(make_tinted_icon("dialog-warning-symbolic", QColor(STATUS_CRITICAL), 18).pixmap(18, 18))

    def _copy_to_clipboard(self, text: str, btn: QPushButton = None):
        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(text)
        if btn:
            orig = btn.text()
            btn.setText("Copied!")
            QTimer.singleShot(2000, lambda: btn.setText(orig))

    # ==============================================
    # NAVIGATION & SIDEBAR
    # ==============================================

    def _switch_tab(self, index: int):
        self.tab_stack.setCurrentIndex(index)
        self._update_nav_buttons(index)
        # Show profile bar only on Dashboard (0) and Performance (1)
        self.profile_segmented.setVisible(index in (0, 1))

    def _update_nav_buttons(self, active_index: int):
        pal = self.palette()
        text_color = pal.windowText().color()
        accent_color = pal.highlight().color()

        for idx, btn in enumerate(self.nav_buttons):
            if idx == active_index:
                btn.setProperty("class", "NavBtnActive")
                if hasattr(self, "nav_items"):
                    btn.setIcon(make_tinted_icon(self.nav_items[idx][0], accent_color, 18))
            else:
                btn.setProperty("class", "NavBtn")
                if hasattr(self, "nav_items"):
                    btn.setIcon(make_tinted_icon(self.nav_items[idx][0], text_color, 18))
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def _toggle_sidebar(self):
        self.sidebar_expanded = not self.sidebar_expanded
        nav_texts = ["Dashboard", "Performance", "Graphics", "Display", "Cooling", "System Info", "Settings"]

        if self.sidebar_expanded:
            self.sidebar_frame.setFixedWidth(200)
            self.btn_collapse.setText("Menu")
            self.brand_lbl.setVisible(True)
            self.side_footer_lbl.setVisible(True)
            for idx, btn in enumerate(self.nav_buttons):
                btn.setText(f"  {nav_texts[idx]}")
        else:
            self.sidebar_frame.setFixedWidth(54)
            self.btn_collapse.setText("")
            self.brand_lbl.setVisible(False)
            self.side_footer_lbl.setVisible(False)
            for idx, btn in enumerate(self.nav_buttons):
                btn.setText("")

    # ==============================================
    # SLIDER & PROFILE LOGIC (Staged Hardware Settings)
    # ==============================================

    def _on_pl1_changed(self, val: int):
        if self._is_loading_profile:
            return
        # Rule: PL2 should never be set below PL1
        if self.slider_pl2.get_value() < val:
            self.slider_pl2.set_value(val)
        self._on_setting_modified()

    def _on_pl2_changed(self, val: int):
        if self._is_loading_profile:
            return
        # Rule: PL2 should never be set below PL1
        if val < self.slider_pl1.get_value():
            self.slider_pl1.set_value(val)
        self._on_setting_modified()

    def _on_bdprochot_toggled(self, checked: bool):
        if self._is_loading_profile:
            return
        if checked:
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
        """Called whenever any staged hardware limit is altered in the UI."""
        if self._is_loading_profile:
            return
        # Switch profile highlight to Custom
        self.profile_segmented.set_selected("custom")
        self.profile_mgr.current_profile_key = "custom"
        self._recalculate_unsaved_changes()

    def _on_profile_selected(self, key: str):
        if key == "custom":
            return
        self._load_profile_into_ui(key)

    def _load_profile_into_ui(self, key: str):
        prof = self.profile_mgr.get_profile(key)
        self._is_loading_profile = True

        self.slider_pl1.set_value(int(prof.get("pl1_w", 24)))
        self.slider_pl2.set_value(int(prof.get("pl2_w", 28)))
        self.chk_sync_mmio.setChecked(prof.get("sync_mmio", True))
        self.chk_bdprochot.setChecked(prof.get("disable_bdprochot", True))
        self.slider_gpu_min.set_value(int(prof.get("gpu_min_mhz", 800)))
        self.slider_gpu_max.set_value(int(prof.get("gpu_max_mhz", 1250)))

        idx_gpu_p = self.combo_gpu_power.findText(prof.get("gpu_power_mode", "base"))
        if idx_gpu_p >= 0:
            self.combo_gpu_power.setCurrentIndex(idx_gpu_p)

        self.chk_turbo.setChecked(prof.get("turbo_boost", True))

        idx_epp = self.combo_epp.findText(prof.get("cpu_epp", "balance_performance"))
        if idx_epp >= 0:
            self.combo_epp.setCurrentIndex(idx_epp)

        topo = getattr(self, "cpu_topo", None) or get_cpu_topology_info()
        if hasattr(self, "slider_p_max"):
            self.slider_p_max.set_value(prof.get("p_core_max_mhz", topo["p_max_mhz"]))
        if hasattr(self, "slider_e_max"):
            self.slider_e_max.set_value(prof.get("e_core_max_mhz", topo["e_max_mhz"]))
        if hasattr(self, "slider_p_min"):
            self.slider_p_min.set_value(prof.get("p_core_min_mhz", topo["p_min_mhz"]))
        if hasattr(self, "slider_e_min"):
            self.slider_e_min.set_value(prof.get("e_core_min_mhz", topo["e_min_mhz"]))

        self.profile_segmented.set_selected(key)
        self.profile_mgr.current_profile_key = key
        self._is_loading_profile = False
        self._recalculate_unsaved_changes()

    def _collect_ui_settings(self) -> dict:
        settings = {
            "pl1_w": float(self.slider_pl1.get_value()),
            "pl2_w": float(self.slider_pl2.get_value()),
            "sync_mmio": self.chk_sync_mmio.isChecked(),
            "disable_bdprochot": self.chk_bdprochot.isChecked(),
            "gpu_min_mhz": self.slider_gpu_min.get_value(),
            "gpu_max_mhz": self.slider_gpu_max.get_value(),
            "gpu_power_mode": self.combo_gpu_power.currentText(),
            "turbo_boost": self.chk_turbo.isChecked(),
            "cpu_epp": self.combo_epp.currentText(),
            "cpu_governor": "powersave",
        }
        if hasattr(self, "slider_p_max"):
            settings["p_core_max_mhz"] = self.slider_p_max.get_value()
        if hasattr(self, "slider_e_max"):
            settings["e_core_max_mhz"] = self.slider_e_max.get_value()
        if hasattr(self, "clk_advanced_sec") and self.clk_advanced_sec.is_expanded:
            if hasattr(self, "slider_p_min"):
                settings["p_core_min_mhz"] = self.slider_p_min.get_value()
            if hasattr(self, "slider_e_min"):
                settings["e_core_min_mhz"] = self.slider_e_min.get_value()
        return settings

    def _recalculate_unsaved_changes(self):
        current = self._collect_ui_settings()
        diffs = 0
        for k, v in current.items():
            if self._applied_settings.get(k) != v:
                diffs += 1
        self.unsaved_changes_count = diffs

        if diffs > 0:
            self.unsaved_lbl.setText(f"{diffs} unsaved change{'s' if diffs > 1 else ''}")
            self.unsaved_lbl.setStyleSheet(f"color: {STATUS_WARN}; font-size: 12px; font-weight: bold;")
        else:
            self.unsaved_lbl.setText("0 unsaved changes")
            self.unsaved_lbl.setStyleSheet("color: palette(placeholder-text); font-size: 12px; font-style: italic;")

        # Enable Apply only when daemon is online AND changes exist
        self.btn_apply.setEnabled(self.daemon_online and diffs > 0)

    def _reset_to_defaults(self):
        """Resets current profile and sliders to Daily Balanced baseline."""
        self._load_profile_into_ui("balanced")

    def _apply_settings(self):
        """Sends staged hardware changes to daemon with a 15-second auto-revert countdown."""
        previous_settings = dict(self._applied_settings)
        settings = self._collect_ui_settings()

        resp = self._send_to_daemon({"cmd": "apply", "settings": settings})
        if resp.get("status") == "ok":
            self.log_text.append("[*] Applied limits to hardware. Awaiting confirmation...")
            dlg = RevertCountdownDialog(
                timeout_sec=15,
                title="Hardware Limits Applied",
                message="Keep these hardware power limits? To protect thermal stability, settings will revert in 15 seconds if not confirmed.",
                parent=self,
            )
            dlg.exec()

            if dlg.confirmed:
                self._applied_settings = dict(settings)
                self._recalculate_unsaved_changes()
                self.log_text.append("[+] Hardware settings confirmed by user.")
            else:
                self.log_text.append("[!] Confirmation timed out or reverted. Restoring previous hardware limits...")
                self._send_to_daemon({"cmd": "apply", "settings": previous_settings})
                self._applied_settings = dict(previous_settings)
                self._load_profile_into_ui(self.profile_mgr.current_profile_key)
                self.log_text.append("[OK] Restored previous safe settings.")
        else:
            self.log_text.append(f"[!] Daemon error: {resp.get('message', 'Failed to apply.')}")

    # ==============================================
    # DISPLAY SETTINGS (Instant-Safe with 15s Revert on Modes/Scale)
    # ==============================================

    def _on_disp_brightness_slider_changed(self, val: int):
        self.lbl_bright_val.setText(f"{val} %")
        self.display_mgr.set_brightness(self._disp_output_name, val)

    def _on_disp_mode_changed(self, idx: int):
        if self._is_updating_display_ui:
            return
        new_mode = self.combo_disp_mode.itemData(idx)
        prev_mode = self._prev_disp_mode
        if not new_mode or new_mode == prev_mode:
            return

        mode_text = self.combo_disp_mode.itemText(idx)
        ok = self.display_mgr.set_mode(self._disp_output_name, str(new_mode))
        if ok:
            dlg = RevertCountdownDialog(
                timeout_sec=15,
                title="Keep Display Mode?",
                message=f"Keep display mode '{mode_text}'? Resolution will automatically revert in 15 seconds if not confirmed.",
                parent=self,
            )
            dlg.exec()
            if dlg.confirmed:
                self._prev_disp_mode = new_mode
                self.log_text.append(f"[Display] Confirmed mode: {mode_text}")
            else:
                self.log_text.append("[Display] Reverting display mode...")
                self._is_updating_display_ui = True
                self.display_mgr.set_mode(self._disp_output_name, str(prev_mode))
                idx_prev = self.combo_disp_mode.findData(prev_mode)
                if idx_prev >= 0:
                    self.combo_disp_mode.setCurrentIndex(idx_prev)
                self._is_updating_display_ui = False

    def _on_disp_scale_changed(self, idx: int):
        if self._is_updating_display_ui:
            return
        new_scale = self.combo_disp_scale.itemData(idx)
        prev_scale = self._prev_disp_scale
        if not new_scale or new_scale == prev_scale:
            return

        scale_text = self.combo_disp_scale.itemText(idx)
        ok = self.display_mgr.set_scale(self._disp_output_name, float(new_scale))
        if ok:
            dlg = RevertCountdownDialog(
                timeout_sec=15,
                title="Keep Display Scale?",
                message=f"Keep display scale factor '{scale_text}'? Scale will automatically revert in 15 seconds if not confirmed.",
                parent=self,
            )
            dlg.exec()
            if dlg.confirmed:
                self._prev_disp_scale = new_scale
                self.log_text.append(f"[Display] Confirmed scale: {scale_text}")
            else:
                self.log_text.append("[Display] Reverting display scale...")
                self._is_updating_display_ui = True
                self.display_mgr.set_scale(self._disp_output_name, float(prev_scale))
                idx_prev = self.combo_disp_scale.findData(prev_scale)
                if idx_prev >= 0:
                    self.combo_disp_scale.setCurrentIndex(idx_prev)
                self._is_updating_display_ui = False

    def _on_rgb_range_changed(self, idx: int):
        mode = self.combo_rgb.itemData(idx)
        if mode:
            ok = self.display_mgr.set_rgb_range(self._disp_output_name, str(mode))
            if ok:
                self.log_text.append(f"[Display] RGB Dynamic Range set to {mode}")

    def _on_icc_source_changed(self, idx: int):
        is_custom = (idx == 2)
        self.txt_icc_path.setEnabled(is_custom)
        src = self.combo_icc_source.itemData(idx)
        if src in ("sRGB", "EDID"):
            ok = self.display_mgr.set_color_profile_source(self._disp_output_name, src)
            if ok:
                self.log_text.append(f"[Display] Color profile source set to {src}")

    def _browse_icc_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select ICC Profile", "", "Color Profiles (*.icc *.icm);;All Files (*)"
        )
        if path:
            self.txt_icc_path.setText(path)
            self.combo_icc_source.setCurrentIndex(2)
            ok = self.display_mgr.set_icc_profile(self._disp_output_name, path)
            if ok:
                self.log_text.append(f"[Display] Custom ICC profile applied: {path}")

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
            self.daemon_dot.setStyleSheet(f"color: {STATUS_OK}; font-size: 14px;")
            self.daemon_lbl.setText("Daemon Connected")
            self.daemon_detail_lbl.setText("Status: Online (Active Unix Socket)")
            self.daemon_detail_lbl.setStyleSheet(f"color: {STATUS_OK}; font-weight: bold;")
            if not self._limits_loaded:
                lim_resp = self._send_to_daemon({"cmd": "get_limits"})
                if lim_resp.get("status") == "ok":
                    lim = lim_resp.get("hardware_limits", {})
                    self.slider_pl1.set_range(int(lim.get("pl1_min_w", 10)), int(lim.get("pl1_max_w", 30)))
                    self.slider_pl2.set_range(int(lim.get("pl2_min_w", 10)), int(lim.get("pl2_max_w", 45)))
                    self.slider_gpu_min.set_range(int(lim.get("gpu_min_mhz", 100)), int(lim.get("gpu_max_mhz", 1250)))
                    self.slider_gpu_max.set_range(int(lim.get("gpu_min_mhz", 100)), int(lim.get("gpu_max_mhz", 1250)))
                    self._limits_loaded = True
        else:
            self.daemon_dot.setStyleSheet(f"color: {STATUS_CRITICAL}; font-size: 14px;")
            self.daemon_lbl.setText("Daemon Offline")
            self.daemon_detail_lbl.setText("Status: Offline (Start service to enable applying limits)")
            self.daemon_detail_lbl.setStyleSheet(f"color: {STATUS_CRITICAL};")

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
        if th_reason != "NONE":
            self.card_power.update_value(
                f"{watts:.1f}", f"Target PL1: {target}.0 W", badge_text=f"THROTTLE: {th_reason}", badge_color=STATUS_WARN, numeric_val=watts
            )
        else:
            self.card_power.update_value(
                f"{watts:.1f}", f"Target PL1: {target}.0 W", badge_text="THROTTLE: NONE", numeric_val=watts
            )

        # Temp with semantic fixed status colors
        temp = data["temp_c"] if data["temp_c"] is not None else 0
        if temp >= 90:
            temp_color = STATUS_CRITICAL
        elif temp >= 80:
            temp_color = STATUS_WARN
        else:
            temp_color = STATUS_OK

        self.card_temp.update_value(
            f"{temp}" if temp else "--", "Core Temp Sensor", color=temp_color, numeric_val=float(temp)
        )

        # Global High Temp Alert
        if temp >= 90:
            self.warning_banner.setVisible(True)
            self.warning_lbl.setText(f"HIGH TEMPERATURE ALERT: Package temperature is {temp}°C! Fan cooling active.")
        else:
            self.warning_banner.setVisible(False)

        # Fan
        fan_rpm = data["fan_rpm"] if data["fan_rpm"] is not None else 0
        self.card_fan.update_value(
            f"{fan_rpm:,}" if fan_rpm > 0 else "--", "Automatic EC Control", numeric_val=float(fan_rpm)
        )

        # Iris Xe GPU
        gpu = data["gpu"]
        reasons = gpu["throttle_reasons"]
        gpu_color = STATUS_CRITICAL if gpu["is_throttling"] else None
        self.card_gpu.update_value(
            f"{gpu['act_mhz']}" if gpu['act_mhz'] else "--",
            f"Reasons: {reasons.upper()}",
            color=gpu_color,
            numeric_val=float(gpu["act_mhz"] or 0),
        )

        # CPU Clocks
        cpu = data["cpu_freq"]
        p_ghz = (cpu["p_core_mhz"] / 1000.0) if cpu["p_core_mhz"] else 0.0
        e_ghz = (cpu["e_core_mhz"] / 1000.0) if cpu["e_core_mhz"] else 0.0
        self.card_pcore.update_value(
            f"{p_ghz:.2f}", f"{cpu['p_threads_count']} Threads Active", numeric_val=p_ghz
        )
        self.card_ecore.update_value(
            f"{e_ghz:.2f}", f"{cpu['e_threads_count']} Threads Active", numeric_val=e_ghz
        )

        # Live requested vs actual updates on CPU Clock Limits sliders
        if hasattr(self, "slider_p_max"):
            self.slider_p_max.update_actual_freq(cpu.get("p_core_mhz"))
        if hasattr(self, "slider_e_max"):
            self.slider_e_max.update_actual_freq(cpu.get("e_core_mhz"))
        if hasattr(self, "slider_p_min"):
            self.slider_p_min.update_actual_freq(cpu.get("p_core_mhz"))
        if hasattr(self, "slider_e_min"):
            self.slider_e_min.update_actual_freq(cpu.get("e_core_mhz"))

        # Power source badge
        if data["ac_connected"]:
            self.power_src_badge.setText("AC POWER")
            self.power_src_badge.setStyleSheet(
                f"background-color: palette(base); color: {STATUS_OK}; font-weight: bold; "
                "padding: 6px 12px; border-radius: 6px; border: 1px solid palette(mid); font-size: 11px;"
            )
        else:
            self.power_src_badge.setText("ON BATTERY")
            self.power_src_badge.setStyleSheet(
                f"background-color: palette(base); color: {STATUS_WARN}; font-weight: bold; "
                "padding: 6px 12px; border-radius: 6px; border: 1px solid palette(mid); font-size: 11px;"
            )

        # Mini readout on bottom bar
        self.mini_telemetry_lbl.setText(f"{temp}°C  |  {watts:.1f}W  |  {fan_rpm} RPM")
        if temp >= 90:
            self.mini_telemetry_lbl.setStyleSheet(f"color: {STATUS_CRITICAL}; font-size: 12px; font-weight: bold;")
        else:
            self.mini_telemetry_lbl.setStyleSheet("color: palette(placeholder-text); font-size: 12px; font-weight: 500;")

        # Tray Tooltip
        self.tray.setToolTip(f"{APP_NAME}: {watts:.1f}W | {temp}°C | Fan: {fan_rpm} RPM")

    def _setup_tray(self):
        self.tray = QSystemTrayIcon(self)
        app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        icon = QIcon.fromTheme("hp-control-center")
        if icon.isNull():
            svg_path = os.path.join(app_dir, "hicolor", "scalable", "apps", "hp-control-center.svg")
            png_path = os.path.join(app_dir, "hicolor", "256x256", "apps", "hp-control-center.png")
            if os.path.exists(svg_path):
                icon = QIcon(svg_path)
            elif os.path.exists(png_path):
                icon = QIcon(png_path)
            else:
                icon = self.style().standardIcon(self.style().StandardPixmap.SP_ComputerIcon)
        self.setWindowIcon(icon)
        self.tray.setIcon(icon)

        tray_menu = QMenu()
        pal = self.palette()
        text_color = pal.windowText().color()

        act_gaming = tray_menu.addAction(make_tinted_icon("speedometer-symbolic", text_color, 16), "Ultra Gaming (25W)")
        act_gaming.triggered.connect(lambda: self._on_profile_selected("ultra_gaming"))

        act_balanced = tray_menu.addAction(make_tinted_icon("preferences-system-performance-symbolic", text_color, 16), "Daily Balanced (24W)")
        act_balanced.triggered.connect(lambda: self._on_profile_selected("balanced"))

        act_eco = tray_menu.addAction(make_tinted_icon("battery-profile-performance-symbolic", text_color, 16), "Silent & Eco (15W)")
        act_eco.triggered.connect(lambda: self._on_profile_selected("eco_quiet"))

        tray_menu.addSeparator()
        act_show = tray_menu.addAction(make_tinted_icon("utilities-system-monitor-symbolic", text_color, 16), "Open Control Center")
        act_show.triggered.connect(self.showNormal)

        act_quit = tray_menu.addAction(make_tinted_icon("application-exit-symbolic", text_color, 16), "Quit")
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
