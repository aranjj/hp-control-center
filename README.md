# HP Performance Control Center (Alpha) ⚡

A native Linux gaming and hardware tuning center for **HP Laptops with Intel 12th Gen Processors (Core i7-1255U & Iris Xe Graphics)**.

Designed to eliminate Intel TDP power decay (forcing 25W sustained indefinitely) and replicate the functionality of tools like **ThrottleStop**, **Lenovo Vantage**, and **ASUS Armoury Crate** on Linux.

---

## Features

* 🚀 **1-Click Gaming Profiles:**
  * **Ultra Gaming:** 25W sustained PL1, 28W burst PL2, Iris Xe GPU floor locked at 800 MHz – 1250 MHz (zero stutter), Turbo Boost enabled.
  * **Daily Balanced:** 24W envelope with adaptive thermal scaling.
  * **Silent & Eco:** 15W stock power, Turbo disabled (1.7 GHz base clock), whisper-quiet.
* ⚡ **Dual MSR & MMIO Synchronization:**
  * Writes to both `MSR 0x610` (`MSR_PKG_POWER_LIMIT`) and physical memory `MCHBAR + 0x59A0`.
  * Defeats the HP Embedded Controller (EC) 15W decay timer.
* 🎮 **Intel Iris Xe GPU Clock Tuner:**
  * Direct integration with the modern Linux `xe` kernel driver.
  * Adjust min/max GPU frequencies (100 MHz – 1250 MHz).
  * Real-time GPU throttle diagnosis (`reason_pl1`, `reason_thermal`, `reason_prochot`).
* 📊 **Zero-Overhead Live Telemetry HUD:**
  * Real-time package power (Watts) calculated via RAPL energy counters.
  * Live cooling fan tachometer (RPM from `hp-wmi`).
  * Package & core temperatures.
  * P-Core and E-Core average clocks.
* 🛡️ **BD PROCHOT Protection:**
  * Toggle bit 0 in `0x1FC` to protect against the 400 MHz (0.39 GHz) lock bug caused by third-party chargers or warm battery sensors.
* 🖥️ **Native KDE Plasma System Tray:**
  * Minimizes to the taskbar tray with live wattage and temperature tooltip.
  * Quick-switch profiles from the tray menu.

---

## Requirements

* **OS:** Linux (Arch / CachyOS / Fedora / Ubuntu)
* **Python 3.10+** with `PySide6`
* Intel 12th Gen Alder Lake CPU (`i7-1255U` or compatible)

---

## Quick Start

### 1. Test Telemetry via CLI (No Root Needed)
```bash
python3 cli.py status
```

### 2. Launch the Desktop GUI
```bash
python3 app.py
```

### 3. Enable the Background Daemon (Root Sync)
To keep the 25W limit locked continuously every 5 seconds:
```bash
sudo cp daemon/hp-control-daemon.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now hp-control-daemon
```

Or run the daemon directly in a terminal:
```bash
sudo python3 daemon/service.py
```

---

## Project Structure

```
hp-control-center/
├── app.py                     # Main PySide6 GUI Entry Point
├── cli.py                     # CLI quick-switcher & status tool
├── core/
│   ├── hardware.py            # Low-level MSR, MMIO, GPU sysfs, Turbo controls
│   ├── telemetry.py           # Live Watts, Temp, Fan RPM, GPU clock reader
│   └── profiles.py            # Presets and JSON configuration manager
├── daemon/
│   ├── service.py             # Root background daemon (socket listener & 5s loop)
│   └── hp-control-daemon.service # Systemd service unit
├── ui/
│   ├── main_window.py         # Main HUD Window & Tray integration
│   ├── widgets.py             # Custom StatCard and SliderSetting widgets
│   └── styles.py              # Dark Gaming & Cyberpunk QSS Theme
├── hp-control-center.desktop  # Desktop launcher
└── install.sh                 # Installer script
```
