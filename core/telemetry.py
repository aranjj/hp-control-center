"""
Telemetry Reader for Intel Hybrid Systems & HP Laptops.
Dynamically discovers all sysfs paths at startup without hardcoded paths.
Zero root privileges required.
"""

import os
import glob
import time


def parse_cpu_list(path: str) -> list[int]:
    """Parses sysfs cpu list format (e.g., '0-3,5' -> [0, 1, 2, 3, 5])."""
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r") as f:
            text = f.read().strip()
        cpus = []
        for part in text.split(","):
            part = part.strip()
            if "-" in part:
                s, e = part.split("-")
                cpus.extend(range(int(s), int(e) + 1))
            elif part.isdigit():
                cpus.append(int(part))
        return cpus
    except Exception:
        return []


class TelemetryReader:
    def __init__(self):
        self._last_energy = None
        self._last_time = None
        self._current_watts = 0.0

        # Dynamic Discovery
        self.rapl_energy_path = self._discover_rapl()
        self.gpu_path = self._discover_gpu()
        self.fan_paths = self._discover_fans()
        self.temp_paths = self._discover_temps()
        self.power_supply_paths = self._discover_power_supplies()

        # Core topology discovery
        self.p_core_threads = parse_cpu_list("/sys/devices/cpu_core/cpus")
        self.e_core_threads = parse_cpu_list("/sys/devices/cpu_atom/cpus")

        # Fallback if cpu_core / cpu_atom are not present
        if not self.p_core_threads and not self.e_core_threads:
            all_cpus = [
                int(os.path.basename(p)[3:])
                for p in glob.glob("/sys/devices/system/cpu/cpu[0-9]*")
                if os.path.basename(p)[3:].isdigit()
            ]
            all_cpus.sort()
            # Default heuristic fallback
            self.p_core_threads = all_cpus[:4] if len(all_cpus) >= 4 else all_cpus
            self.e_core_threads = all_cpus[4:] if len(all_cpus) > 4 else []

    def _discover_rapl(self) -> str | None:
        candidates = glob.glob("/sys/class/powercap/intel-rapl/intel-rapl:0/energy_uj") + \
                     glob.glob("/sys/devices/virtual/powercap/intel-rapl/intel-rapl:0/energy_uj")
        return candidates[0] if candidates else None

    def _discover_gpu(self) -> str | None:
        # Check Intel Xe driver first, then standard i915 and drm
        candidates = (
            glob.glob("/sys/bus/pci/drivers/xe/*/tile0/gt0/freq0") +
            glob.glob("/sys/bus/pci/drivers/xe/*/gt0/freq0") +
            glob.glob("/sys/class/drm/card*/device/tile0/gt0/freq0") +
            glob.glob("/sys/bus/pci/devices/*/tile0/gt0/freq0") +
            glob.glob("/sys/bus/pci/devices/0000:00:02.0/tile0/gt0/freq0") +
            glob.glob("/sys/class/drm/card0/gt")
        )
        return candidates[0] if candidates else None

    def _discover_fans(self) -> list[str]:
        # Search hp-wmi hwmon and all hwmon for fan*_input
        candidates = glob.glob("/sys/devices/platform/hp-wmi/hwmon/hwmon*/fan*_input") + \
                     glob.glob("/sys/class/hwmon/hwmon*/fan*_input")
        # Deduplicate while preserving order
        seen = set()
        res = []
        for p in candidates:
            real = os.path.realpath(p)
            if real not in seen:
                seen.add(real)
                res.append(p)
        return res

    def _discover_temps(self) -> list[str]:
        # Prefer coretemp / x86_pkg_temp
        candidates = []
        for hwmon in glob.glob("/sys/class/hwmon/hwmon*"):
            name_file = os.path.join(hwmon, "name")
            if os.path.exists(name_file):
                try:
                    with open(name_file, "r") as f:
                        name = f.read().strip()
                    if name in ("coretemp", "x86_pkg_temp"):
                        inputs = glob.glob(os.path.join(hwmon, "temp*_input"))
                        candidates.extend(inputs)
                except Exception:
                    pass
        if not candidates:
            candidates.extend(glob.glob("/sys/class/thermal/thermal_zone*/temp"))
        return candidates

    def _discover_power_supplies(self) -> list[str]:
        return glob.glob("/sys/class/power_supply/*/online")

    def get_package_power_watts(self) -> float | None:
        """Calculates real-time package power from RAPL energy counter."""
        if not self.rapl_energy_path or not os.path.exists(self.rapl_energy_path):
            return None

        try:
            with open(self.rapl_energy_path, "r") as f:
                current_energy = int(f.read().strip())
            now = time.time()

            if self._last_energy is None or self._last_time is None:
                self._last_energy = current_energy
                self._last_time = now
                time.sleep(0.05)
                with open(self.rapl_energy_path, "r") as f:
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
            return None

    def get_package_temp(self) -> int | None:
        """Returns CPU package temperature in degrees Celsius."""
        for path in self.temp_paths:
            if os.path.exists(path):
                try:
                    with open(path, "r") as f:
                        val = int(f.read().strip())
                    return val // 1000 if val > 1000 else val
                except (OSError, ValueError):
                    pass
        return None

    def get_fan_rpm(self) -> int | None:
        """Returns active cooling fan RPM."""
        for path in self.fan_paths:
            if os.path.exists(path):
                try:
                    with open(path, "r") as f:
                        val = int(f.read().strip())
                    if val >= 0:
                        return val
                except (OSError, ValueError):
                    pass
        return None

    def get_gpu_telemetry(self) -> dict:
        """Returns Iris Xe live frequency and throttle diagnostic."""
        data = {
            "act_mhz": None,
            "min_mhz": None,
            "max_mhz": None,
            "throttle_reasons": "none",
            "is_throttling": False,
        }
        if not self.gpu_path or not os.path.exists(self.gpu_path):
            return data

        try:
            act_file = os.path.join(self.gpu_path, "act_freq")
            min_file = os.path.join(self.gpu_path, "min_freq")
            max_file = os.path.join(self.gpu_path, "max_freq")
            reasons_file = os.path.join(self.gpu_path, "throttle", "reasons")

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
                    data["throttle_reasons"] = reasons if reasons else "none"
                    data["is_throttling"] = reasons not in ("", "none")
        except (OSError, ValueError):
            pass

        return data

    def get_cpu_frequencies(self) -> dict:
        """Returns P-core average, and E-core average clocks (MHz) dynamically."""
        freq_map = {}
        for path in glob.glob("/sys/devices/system/cpu/cpu[0-9]*/cpufreq/scaling_cur_freq"):
            cpu_num = os.path.basename(os.path.dirname(os.path.dirname(path)))[3:]
            if cpu_num.isdigit():
                try:
                    with open(path, "r") as f:
                        freq_map[int(cpu_num)] = int(f.read().strip()) // 1000
                except (OSError, ValueError):
                    pass

        p_vals = [freq_map[c] for c in self.p_core_threads if c in freq_map]
        e_vals = [freq_map[c] for c in self.e_core_threads if c in freq_map]
        all_vals = list(freq_map.values())

        return {
            "avg_mhz": sum(all_vals) // len(all_vals) if all_vals else None,
            "p_core_mhz": sum(p_vals) // len(p_vals) if p_vals else None,
            "e_core_mhz": sum(e_vals) // len(e_vals) if e_vals else None,
            "p_threads_count": len(self.p_core_threads),
            "e_threads_count": len(self.e_core_threads),
        }

    def is_ac_connected(self) -> bool:
        """Detects whether the laptop is on AC power or Battery."""
        for path in self.power_supply_paths:
            try:
                with open(path, "r") as f:
                    if f.read().strip() == "1":
                        return True
            except (OSError, ValueError):
                pass
        return False if self.power_supply_paths else True

    def get_online_cores(self) -> dict[int, bool]:
        """Returns online status map for all CPUs."""
        res = {}
        for path in glob.glob("/sys/devices/system/cpu/cpu[0-9]*"):
            num_str = os.path.basename(path)[3:]
            if num_str.isdigit():
                cpu = int(num_str)
                online_file = os.path.join(path, "online")
                if os.path.exists(online_file):
                    try:
                        with open(online_file, "r") as f:
                            res[cpu] = (f.read().strip() == "1")
                    except OSError:
                        res[cpu] = True
                else:
                    # cpu0 is always online
                    res[cpu] = True
        return res

    def get_all(self) -> dict:
        """Polls full telemetry snapshot."""
        return {
            "power_watts": self.get_package_power_watts(),
            "temp_c": self.get_package_temp(),
            "fan_rpm": self.get_fan_rpm(),
            "gpu": self.get_gpu_telemetry(),
            "cpu_freq": self.get_cpu_frequencies(),
            "online_cores": self.get_online_cores(),
            "ac_connected": self.is_ac_connected(),
        }
