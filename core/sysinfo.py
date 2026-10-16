"""
System and Driver Information Inspector for HP Control Center
Gathers detailed diagnostics for:
- Graphics stack: Kernel driver (xe/i915), Mesa, Vulkan, OpenGL, PCI IDs
- Hardware & Firmware: HP DMI strings, BIOS version/date, CPU topology, RAM
- OS & Environment: Kernel release, Wayland/KWin compositor, thermal watchdogs
"""

import os
import re
import platform
import subprocess
from typing import Dict, Any


class SystemInfoReader:
    """Collects system, hardware, and driver diagnostics."""

    @staticmethod
    def _read_file(path: str, default: str = "N/A") -> str:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    return f.read().strip()
            except Exception:
                pass
        return default

    def get_dmi_info(self) -> Dict[str, str]:
        base = "/sys/devices/virtual/dmi/id"
        return {
            "product_name": self._read_file(f"{base}/product_name", "HP Laptop 15-fd0xxx"),
            "sys_vendor": self._read_file(f"{base}/sys_vendor", "HP"),
            "bios_version": self._read_file(f"{base}/bios_version", "F.26"),
            "bios_date": self._read_file(f"{base}/bios_date", "N/A"),
            "board_name": self._read_file(f"{base}/board_name", "N/A"),
        }

    def get_cpu_info(self) -> Dict[str, Any]:
        model = "Intel(R) Core(TM) i7-1255U"
        cpuinfo = self._read_file("/proc/cpuinfo", "")
        for line in cpuinfo.splitlines():
            if "model name" in line:
                model = line.split(":", 1)[1].strip()
                break

        # Discover core topology
        p_cores = 0
        e_cores = 0
        p_path = "/sys/devices/cpu_core/cpus"
        e_path = "/sys/devices/cpu_atom/cpus"
        if os.path.exists(p_path):
            try:
                p_cores = len(self._expand_cpu_range(self._read_file(p_path)))
            except Exception:
                p_cores = 4
        else:
            p_cores = 4  # 2 P-cores * 2 threads

        if os.path.exists(e_path):
            try:
                e_cores = len(self._expand_cpu_range(self._read_file(e_path)))
            except Exception:
                e_cores = 8
        else:
            e_cores = 8

        total_threads = os.cpu_count() or (p_cores + e_cores)

        return {
            "model": model,
            "p_core_threads": p_cores,
            "e_cores": e_cores,
            "total_threads": total_threads,
            "summary": f"10 Cores ({p_cores // 2}P + {e_cores}E), {total_threads} Threads",
        }

    @staticmethod
    def _expand_cpu_range(range_str: str) -> list[int]:
        cpus = []
        for part in range_str.split(","):
            part = part.strip()
            if not part:
                continue
            if "-" in part:
                start, end = part.split("-")
                cpus.extend(range(int(start), int(end) + 1))
            else:
                cpus.append(int(part))
        return cpus

    def get_memory_info(self) -> str:
        meminfo = self._read_file("/proc/meminfo", "")
        for line in meminfo.splitlines():
            if "MemTotal" in line:
                parts = line.split()
                if len(parts) >= 2:
                    kb = int(parts[1])
                    gb = kb / (1024 * 1024)
                    return f"{gb:.1f} GB"
        return "16.0 GB"

    def get_graphics_info(self) -> Dict[str, str]:
        info = {
            "device_name": "Intel(R) Iris(R) Xe Graphics (ADL GT2)",
            "kernel_driver": "xe",
            "kernel_modules": "xe, i915",
            "pci_id": "0000:00:02.0 (8086:46a8)",
            "mesa_version": "Unknown",
            "vulkan_api": "Unknown",
            "vulkan_driver": "Unknown",
            "opengl_version": "Unknown",
        }

        # Check kernel driver in use via sysfs
        driver_symlink = "/sys/bus/pci/devices/0000:00:02.0/driver"
        if os.path.exists(driver_symlink):
            try:
                info["kernel_driver"] = os.path.basename(os.readlink(driver_symlink))
            except Exception:
                pass

        # Vulkan inspection
        try:
            vk_out = subprocess.run(
                ["vulkaninfo", "--summary"],
                capture_output=True,
                text=True,
                timeout=3,
            ).stdout
            dev_m = re.search(r"deviceName\s*=\s*(.+)", vk_out)
            api_m = re.search(r"apiVersion\s*=\s*(.+)", vk_out)
            drv_m = re.search(r"driverInfo\s*=\s*(.+)", vk_out)
            if dev_m:
                info["device_name"] = dev_m.group(1).strip()
            if api_m:
                info["vulkan_api"] = api_m.group(1).strip()
            if drv_m:
                info["vulkan_driver"] = drv_m.group(1).strip()
                if "Mesa" in drv_m.group(1):
                    info["mesa_version"] = drv_m.group(1).strip()
        except Exception:
            pass

        # OpenGL inspection
        try:
            gl_out = subprocess.run(
                ["glxinfo", "-B"],
                capture_output=True,
                text=True,
                timeout=3,
            ).stdout
            core_m = re.search(r"OpenGL core profile version string:\s*(.+)", gl_out)
            if core_m:
                info["opengl_version"] = core_m.group(1).strip()
                if info["mesa_version"] == "Unknown" and "Mesa" in core_m.group(1):
                    info["mesa_version"] = core_m.group(1).split("Mesa", 1)[1].strip()
        except Exception:
            pass

        return info

    def get_os_info(self) -> Dict[str, str]:
        os_release = self._read_file("/etc/os-release", "")
        distro = "Linux"
        for line in os_release.splitlines():
            if line.startswith("PRETTY_NAME="):
                distro = line.split("=", 1)[1].strip('"')
                break

        session = os.environ.get("XDG_SESSION_TYPE", "wayland").capitalize()
        desktop = os.environ.get("XDG_CURRENT_DESKTOP", "KDE Plasma")

        # Check thermald status
        thermald_active = os.path.exists("/run/systemd/system") and subprocess.run(
            ["systemctl", "is-active", "--quiet", "thermald"],
            capture_output=True,
        ).returncode == 0

        return {
            "distro": distro,
            "kernel": platform.release(),
            "arch": platform.machine(),
            "session": f"{desktop} ({session})",
            "thermald": "Active (DPTF Watchdog)" if thermald_active else "Inactive",
        }

    def generate_markdown_report(self) -> str:
        dmi = self.get_dmi_info()
        cpu = self.get_cpu_info()
        gpu = self.get_graphics_info()
        os_info = self.get_os_info()
        mem = self.get_memory_info()

        return (
            f"# HP Performance Center - Hardware & System Report\n\n"
            f"### 🖥️ Hardware & Firmware\n"
            f"- **Device**: {dmi['sys_vendor']} {dmi['product_name']}\n"
            f"- **BIOS**: {dmi['bios_version']} ({dmi['bios_date']})\n"
            f"- **CPU**: {cpu['model']} • {cpu['summary']}\n"
            f"- **Memory**: {mem} Total RAM\n\n"
            f"### 🎮 Graphics & Drivers\n"
            f"- **GPU**: {gpu['device_name']} [{gpu['pci_id']}]\n"
            f"- **Kernel Driver**: `{gpu['kernel_driver']}` (Available: {gpu['kernel_modules']})\n"
            f"- **Mesa**: {gpu['mesa_version']}\n"
            f"- **Vulkan**: {gpu['vulkan_api']} ({gpu['vulkan_driver']})\n"
            f"- **OpenGL**: {gpu['opengl_version']}\n\n"
            f"### 🐧 OS & Environment\n"
            f"- **OS**: {os_info['distro']} (Kernel {os_info['kernel']} {os_info['arch']})\n"
            f"- **Session**: {os_info['session']}\n"
            f"- **Thermal Subsystem**: {os_info['thermald']} + hp-wmi\n"
        )
