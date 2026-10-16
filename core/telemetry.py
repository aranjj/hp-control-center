"""
Telemetry Reader for HP 15 & Intel Core i7-1255U
Requires ZERO root privileges to read.
"""

import os
import glob
import time

XE_GPU_PATH = "/sys/bus/pci/devices/0000:00:02.0/tile0/gt0/freq0"
RAPL_ENERGY_PATH = "/sys/class/powercap/intel-rapl/intel-rapl:0/energy_uj"
FAN_PATH = "/sys/devices/platform/hp-wmi/hwmon/hwmon4/fan1_input"
CORETEMP_PKG_PATH = "/sys/class/hwmon/hwmon5/temp1_input"


class TelemetryReader:
    def __init__(self):
        self._last_energy = None
        self._last_time = None
        self._current_watts = 0.0

    def get_package_power_watts(self) -> float:
        """Calculates real-time package power from the RAPL energy counter."""
        if not os.path.exists(RAPL_ENERGY_PATH):
            return 0.0

        try:
            with open(RAPL_ENERGY_PATH, "r") as f:
                current_energy = int(f.read().strip())
            now = time.time()

            if self._last_energy is None or self._last_time is None:
                self._last_energy = current_energy
                self._last_time = now
                time.sleep(0.06)
                with open(RAPL_ENERGY_PATH, "r") as f:
                    current_energy = int(f.read().strip())
                now = time.time()

            delta_t = now - self._last_time
            if delta_t > 0.04:
                delta_e = current_energy - self._last_energy
                if delta_e >= 0:
                    self._current_watts = (delta_e / delta_t) / 1_000_000.0
                self._last_energy = current_energy
                self._last_time = now

            return round(self._current_watts, 1)
        except (OSError, ValueError):
            return 0.0

    def get_package_temp(self) -> int:
        """Returns CPU package temperature in degrees Celsius."""
        for path in (CORETEMP_PKG_PATH, "/sys/class/thermal/thermal_zone0/temp"):
            if os.path.exists(path):
                try:
                    with open(path, "r") as f:
                        return int(f.read().strip()) // 1000
                except (OSError, ValueError):
                    pass
        return 0

    def get_fan_rpm(self) -> int:
        """Returns active cooling fan RPM from hp-wmi."""
        paths = glob.glob("/sys/devices/platform/hp-wmi/hwmon/hwmon*/fan1_input")
        if paths:
            try:
                with open(paths[0], "r") as f:
                    return int(f.read().strip())
            except (OSError, ValueError):
                pass
        return 0

    def get_gpu_telemetry(self) -> dict:
        """Returns Iris Xe live frequency and active throttle reasons."""
        data = {
            "act_mhz": 0,
            "min_mhz": 100,
            "max_mhz": 1250,
            "throttle_reasons": "none",
            "is_throttling": False,
        }
        if not os.path.exists(XE_GPU_PATH):
            return data

        try:
            act_file = os.path.join(XE_GPU_PATH, "act_freq")
            min_file = os.path.join(XE_GPU_PATH, "min_freq")
            max_file = os.path.join(XE_GPU_PATH, "max_freq")
            reasons_file = os.path.join(XE_GPU_PATH, "throttle", "reasons")

            if os.path.exists(act_file):
                with open(act_file, "r") as f:
                    data["act_mhz"] = int(f.read().strip())
            if os.path.exists(min_file):
                with open(min_file, "r") as f:
                    data["min_mhz"] = int(f.read().strip())
            if os.path.exists(max_file):
                with open(max_file, "r") as f:
                    data["max_mhz"] = int(f.read().strip())
            if os.path.exists(reasons_file):
                with open(reasons_file, "r") as f:
                    reasons = f.read().strip()
                    data["throttle_reasons"] = reasons
                    data["is_throttling"] = reasons not in ("", "none")
        except (OSError, ValueError):
            pass

        return data

    def get_cpu_frequencies(self) -> dict:
        """Returns average, P-core average, and E-core average clocks (MHz)."""
        freqs = []
        for path in sorted(glob.glob("/sys/devices/system/cpu/cpu*/cpufreq/scaling_cur_freq")):
            try:
                with open(path, "r") as f:
                    freqs.append(int(f.read().strip()) // 1000)
            except (OSError, ValueError):
                pass

        if not freqs:
            return {"avg_mhz": 0, "p_core_mhz": 0, "e_core_mhz": 0}

        # i7-1255U: 2 P-Cores (4 threads: cpu0-3), 8 E-Cores (8 threads: cpu4-11)
        p_freqs = freqs[:4] if len(freqs) >= 4 else freqs
        e_freqs = freqs[4:] if len(freqs) > 4 else []

        avg = sum(freqs) // len(freqs)
        p_avg = sum(p_freqs) // len(p_freqs) if p_freqs else 0
        e_avg = sum(e_freqs) // len(e_freqs) if e_freqs else 0

        return {
            "avg_mhz": avg,
            "p_core_mhz": p_avg,
            "e_core_mhz": e_avg,
        }

    def is_ac_connected(self) -> bool:
        """Detects whether the laptop is on AC power or Battery."""
        for path in glob.glob("/sys/class/power_supply/AD*/online") + glob.glob("/sys/class/power_supply/AC*/online"):
            try:
                with open(path, "r") as f:
                    return f.read().strip() == "1"
            except (OSError, ValueError):
                pass
        return True

    def get_all(self) -> dict:
        """Polls full telemetry snapshot."""
        return {
            "power_watts": self.get_package_power_watts(),
            "temp_c": self.get_package_temp(),
            "fan_rpm": self.get_fan_rpm(),
            "gpu": self.get_gpu_telemetry(),
            "cpu_freq": self.get_cpu_frequencies(),
            "ac_connected": self.is_ac_connected(),
        }
