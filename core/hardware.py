"""
Hardware Controller for Intel Alder Lake-U (Core i7-1255U) & HP 15
Handles:
- MSR Package Power Limits (0x610)
- MMIO RAPL (MCHBAR + 0x59A0)
- BD PROCHOT (0x1FC)
- Intel Iris Xe GPU Clocks (Xe driver gt0/freq0)
- CPU Turbo Boost & EPP Bias
"""

import os
import sys
import glob
import json
import mmap
import struct
import subprocess

# MSR Register Definitions
MSR_TEMPERATURE_TARGET = 0x1A2
MSR_POWER_CTL = 0x1FC
MSR_PKG_POWER_LIMIT = 0x610
MCHBAR_RAPL_OFFSET = 0x59A0
MCHBAR_MASK = 0x00007FFFFFE0000  # Alder Lake Host Bridge 0x4601 mask

def discover_xe_gpu_path() -> str:
    """Discovers the Intel Xe / i915 GPU sysfs frequency control path dynamically."""
    candidates = (
        glob.glob("/sys/bus/pci/drivers/xe/*/tile0/gt0/freq0") +
        glob.glob("/sys/bus/pci/drivers/xe/*/gt0/freq0") +
        glob.glob("/sys/class/drm/card*/device/tile0/gt0/freq0") +
        glob.glob("/sys/bus/pci/devices/*/tile0/gt0/freq0") +
        glob.glob("/sys/bus/pci/devices/0000:00:02.0/tile0/gt0/freq0")
    )
    for c in candidates:
        if os.path.exists(c):
            return c
    return "/sys/bus/pci/devices/0000:00:02.0/tile0/gt0/freq0"


def get_gpu_hardware_limits() -> tuple[int, int]:
    """Returns (min_mhz, max_mhz) dynamically read from GPU driver sysfs."""
    min_mhz = 100
    max_mhz = 1250
    p = discover_xe_gpu_path()
    if p and os.path.exists(p):
        rp0 = os.path.join(p, "rp0_freq")
        rpn = os.path.join(p, "rpn_freq")
        if os.path.exists(rp0):
            try:
                with open(rp0, "r") as f:
                    max_mhz = int(f.read().strip())
            except Exception:
                pass
        if os.path.exists(rpn):
            try:
                with open(rpn, "r") as f:
                    min_mhz = int(f.read().strip())
            except Exception:
                pass
    return min_mhz, max_mhz


# GPU Driver sysfs path for Intel Xe driver (dynamically resolved)
XE_GPU_PATH = discover_xe_gpu_path()
INTEL_TURBO_PATH = "/sys/devices/system/cpu/intel_pstate/no_turbo"


class HardwareController:
    def __init__(self):
        self._mchbar_base = None

    def unlock_msr(self):
        """Allows user-space MSR writes in the Linux kernel."""
        path = "/sys/module/msr/parameters/allow_writes"
        if os.path.exists(path):
            try:
                with open(path, "w") as f:
                    f.write("on\n")
            except OSError:
                pass

    def get_mchbar_base(self):
        """Reads Host Bridge (00:00.0) registers 0x48/0x4C to locate MCHBAR."""
        if self._mchbar_base is not None:
            return self._mchbar_base

        try:
            low = subprocess.check_output(
                ["setpci", "-s", "0000:00:00.0", "48.l"], stderr=subprocess.DEVNULL
            ).decode().strip()
            high = subprocess.check_output(
                ["setpci", "-s", "0000:00:00.0", "4c.l"], stderr=subprocess.DEVNULL
            ).decode().strip()
            raw = int(low, 16) | (int(high, 16) << 32)
            if (raw & 1) == 0:  # Bit 0 is the enable bit
                return None
            self._mchbar_base = raw & MCHBAR_MASK
            return self._mchbar_base
        except Exception:
            return None

    def encode_power_limit(self, pl1_w: float, pl2_w: float, max_time_window: bool = True):
        """Encodes PL1 and PL2 into Intel's 64-bit PKG_POWER_LIMIT bitfield."""
        # Intel RAPL uses 1/8 Watt increments
        pl1_raw = int(pl1_w * 8) & 0x7FFF
        pl2_raw = int(pl2_w * 8) & 0x7FFF

        # Max time window: Y=31, Z=3 gives ~10,234s (disables decay)
        tw = (31 | (3 << 5)) if max_time_window else (10 | (0 << 5))

        # Bits:
        # [0:14]  PL1 Power Limit
        # [15]     PL1 Enable
        # [16]     PL1 Clamping Limit
        # [17:23] PL1 Time Window
        # [32:46] PL2 Power Limit
        # [47]     PL2 Enable
        # [48]     PL2 Clamping Limit
        # [49:55] PL2 Time Window
        low_32 = pl1_raw | (1 << 15) | (1 << 16) | (tw << 17)
        high_32 = pl2_raw | (1 << 15) | (1 << 16) | (tw << 17)
        return low_32 | (high_32 << 32)

    def write_msr(self, reg: int, val_64: int):
        """Writes a 64-bit value to an MSR register on CPU 0."""
        self.unlock_msr()
        path = "/dev/cpu/0/msr"
        if not os.path.exists(path):
            subprocess.run(["modprobe", "msr"], check=False)

        fd = os.open(path, os.O_WRONLY)
        try:
            os.lseek(fd, reg, os.SEEK_SET)
            os.write(fd, struct.pack("<Q", val_64))
        finally:
            os.close(fd)

    def write_mmio(self, val_64: int):
        """Writes the power limit directly into MCHBAR MMIO physical RAM."""
        base = self.get_mchbar_base()
        if not base:
            return False

        target_addr = base + MCHBAR_RAPL_OFFSET
        pagesize = os.sysconf(os.sysconf_names["SC_PAGESIZE"])
        aligned_addr = target_addr - (target_addr % pagesize)
        offset_in_page = target_addr - aligned_addr

        fd = os.open("/dev/mem", os.O_RDWR | os.O_SYNC)
        try:
            mem = mmap.mmap(fd, pagesize, offset=aligned_addr)
            mem[offset_in_page : offset_in_page + 8] = struct.pack("<Q", val_64)
            mem.close()
            return True
        finally:
            os.close(fd)

    def set_package_power_limits(self, pl1_w: float, pl2_w: float, sync_mmio: bool = True):
        """Sets both MSR and MMIO package power limits."""
        val = self.encode_power_limit(pl1_w, pl2_w)
        self.write_msr(MSR_PKG_POWER_LIMIT, val)
        if sync_mmio:
            self.write_mmio(val)

    def set_bdprochot_disabled(self, disable: bool = True):
        """Clears bit 0 in MSR 0x1FC (POWER_CTL) to disable BD PROCHOT."""
        self.unlock_msr()
        path = "/dev/cpu/0/msr"
        if not os.path.exists(path):
            return

        fd = os.open(path, os.O_RDWR)
        try:
            os.lseek(fd, MSR_POWER_CTL, os.SEEK_SET)
            val = struct.unpack("<Q", os.read(fd, 8))[0]
            if disable:
                # Clear bit 0 (BDPROCHOT disable)
                new_val = val & ~1
            else:
                new_val = val | 1
            os.lseek(fd, MSR_POWER_CTL, os.SEEK_SET)
            os.write(fd, struct.pack("<Q", new_val))
        finally:
            os.close(fd)

    def set_gpu_clocks(self, min_mhz: int, max_mhz: int, power_mode: str = "base"):
        """Sets Intel Iris Xe GPU minimum and maximum frequencies."""
        if not os.path.exists(XE_GPU_PATH):
            return False

        min_file = os.path.join(XE_GPU_PATH, "min_freq")
        max_file = os.path.join(XE_GPU_PATH, "max_freq")
        profile_file = os.path.join(XE_GPU_PATH, "power_profile")

        try:
            # Set max first if expanding, or min first if lowering
            if os.path.exists(max_file):
                with open(max_file, "w") as f:
                    f.write(f"{int(max_mhz)}\n")
            if os.path.exists(min_file):
                with open(min_file, "w") as f:
                    f.write(f"{int(min_mhz)}\n")
            if os.path.exists(profile_file) and power_mode in ("base", "power_saving"):
                with open(profile_file, "w") as f:
                    f.write(f"{power_mode}\n")
            return True
        except OSError:
            return False

    def set_cpu_turbo(self, enable: bool):
        """Enables (0) or disables (1) Intel CPU Turbo Boost."""
        if os.path.exists(INTEL_TURBO_PATH):
            try:
                with open(INTEL_TURBO_PATH, "w") as f:
                    f.write("0\n" if enable else "1\n")
                return True
            except OSError:
                return False
        return False

    def set_cpu_epp(self, epp_mode: str):
        """Sets Energy Performance Preference (EPP) across all online CPU cores."""
        valid_modes = {"performance", "balance_performance", "balance_power", "power", "default"}
        if epp_mode not in valid_modes:
            return False

        success = True
        for path in glob.glob("/sys/devices/system/cpu/cpu*/cpufreq/energy_performance_preference"):
            try:
                with open(path, "w") as f:
                    f.write(f"{epp_mode}\n")
            except OSError:
                success = False
        return success

    def set_cpu_governor(self, governor: str):
        """Sets scaling governor (e.g., performance or powersave)."""
        success = True
        for path in glob.glob("/sys/devices/system/cpu/cpu*/cpufreq/scaling_governor"):
            try:
                with open(path, "w") as f:
                    f.write(f"{governor}\n")
            except OSError:
                success = False
        return success

    def set_cpu_frequencies(
        self,
        p_max_mhz: int = None,
        e_max_mhz: int = None,
        p_min_mhz: int = None,
        e_min_mhz: int = None,
    ) -> bool:
        """Sets scaling_max_freq (and optional scaling_min_freq) for P-cores and E-cores."""
        topo = get_cpu_topology_info()
        success = True

        def write_freq(cpus, filename, mhz):
            if mhz is None:
                return
            khz_str = f"{int(mhz * 1000)}\n"
            for cpu in cpus:
                p = f"/sys/devices/system/cpu/cpu{cpu}/cpufreq/{filename}"
                if os.path.exists(p):
                    try:
                        with open(p, "w") as f:
                            f.write(khz_str)
                    except OSError:
                        pass

        if p_max_mhz is not None:
            write_freq(topo["p_cpus"], "scaling_max_freq", p_max_mhz)
        if e_max_mhz is not None:
            write_freq(topo["e_cpus"], "scaling_max_freq", e_max_mhz)
        if p_min_mhz is not None:
            write_freq(topo["p_cpus"], "scaling_min_freq", p_min_mhz)
        if e_min_mhz is not None:
            write_freq(topo["e_cpus"], "scaling_min_freq", e_min_mhz)

        return success

    def _set_cpu_online(self, cpu: int, online: bool) -> bool:
        """Writes 0 or 1 to cpuN/online sysfs. CPU 0 is never offlined."""
        if cpu == 0:
            return True
        path = f"/sys/devices/system/cpu/cpu{cpu}/online"
        if os.path.exists(path):
            try:
                with open(path, "w") as f:
                    f.write("1\n" if online else "0\n")
                return True
            except OSError as e:
                print(f"[!] _set_cpu_online failed for CPU {cpu} online={online}: {e}", file=sys.stderr)
                return False
        return False

    def set_online_cores(self, active_p_threads: int = None, active_e_cores: int = None):
        """Enforces daemon core parking rules:
        - CPU 0 is never offlined;
        - At least one P-core thread always stays online;
        - P-core siblings are offlined together as pairs from highest CPU down;
        - E-cores are offlined from highest CPU down;
        - When re-enabling cores, onlining executes first to avoid unneeded drops.
        """
        details = get_core_topology_details()
        p_pairs = sorted(details["p_pairs"], key=lambda pair: max(pair), reverse=True)
        e_cpus = sorted(details["e_cpus"], reverse=True)

        # 1. P-core threads offlining (pairs kept together)
        if active_p_threads is not None and p_pairs:
            total_p_threads = sum(len(pair) for pair in p_pairs)
            min_p = len(p_pairs[0]) if len(p_pairs) > 1 else 1
            desired_p = max(min_p, min(total_p_threads, active_p_threads))
            threads_per_pair = len(p_pairs[0]) if p_pairs else 1
            pairs_to_keep = max(1, (desired_p + threads_per_pair - 1) // threads_per_pair)

            # Sort pairs highest down: e.g. [[2, 3], [0, 1]]
            pairs_to_offline = p_pairs[: max(0, len(p_pairs) - pairs_to_keep)]
            pairs_to_online = p_pairs[max(0, len(p_pairs) - pairs_to_keep) :]

            # First online cores from lowest up
            for pair in reversed(pairs_to_online):
                for cpu in sorted(pair):
                    if cpu != 0:
                        self._set_cpu_online(cpu, True)

            # Then offline cores from highest down
            for pair in pairs_to_offline:
                for cpu in sorted(pair, reverse=True):
                    if cpu != 0:
                        self._set_cpu_online(cpu, False)

        # 2. E-core offlining
        if active_e_cores is not None and e_cpus:
            total_e = len(e_cpus)
            desired_e = max(0, min(total_e, active_e_cores))
            e_to_offline = e_cpus[: max(0, total_e - desired_e)]
            e_to_online = e_cpus[max(0, total_e - desired_e) :]

            # First online needed cores from lowest up
            for cpu in sorted(e_to_online):
                self._set_cpu_online(cpu, True)

            # Then offline unneeded cores from highest down
            for cpu in sorted(e_to_offline, reverse=True):
                self._set_cpu_online(cpu, False)

    def restore_all_cores(self):
        """Brings all CPU cores back online on Reset Defaults or daemon shutdown."""
        paths = sorted(
            glob.glob("/sys/devices/system/cpu/cpu*/online"),
            key=lambda p: int(os.path.basename(os.path.dirname(p))[3:])
        )
        for path in paths:
            try:
                with open(path, "w") as f:
                    f.write("1\n")
            except OSError as e:
                print(f"[!] restore_all_cores failed for {path}: {e}", file=sys.stderr)

    def check_tcc_offset_writable(self) -> bool:
        """Checks if MSR_TEMPERATURE_TARGET (0x1A2) is writable and unlocked."""
        path = "/dev/cpu/0/msr"
        if not os.path.exists(path):
            return False
        try:
            self.unlock_msr()
            fd = os.open(path, os.O_RDONLY)
            os.lseek(fd, MSR_TEMPERATURE_TARGET, os.SEEK_SET)
            raw = struct.unpack("<Q", os.read(fd, 8))[0]
            os.close(fd)
            # Bit 30 is TCC Offset Lock bit
            is_locked = bool((raw >> 30) & 1)
            return not is_locked
        except Exception:
            return False

    def set_hardware_tcc_offset(self, target_c: int) -> bool:
        """Sets MSR_TEMPERATURE_TARGET (0x1A2) TCC offset if unlocked."""
        if not self.check_tcc_offset_writable():
            return False
        path = "/dev/cpu/0/msr"
        try:
            self.unlock_msr()
            fd = os.open(path, os.O_RDWR)
            os.lseek(fd, MSR_TEMPERATURE_TARGET, os.SEEK_SET)
            raw = struct.unpack("<Q", os.read(fd, 8))[0]
            tj_max = (raw >> 16) & 0xFF
            if tj_max <= 0:
                tj_max = 100
            offset = max(0, min(63, tj_max - target_c))
            # Clear bits 29:24 and set new offset
            new_val = (raw & ~(0x3F << 24)) | ((offset & 0x3F) << 24)
            os.lseek(fd, MSR_TEMPERATURE_TARGET, os.SEEK_SET)
            os.write(fd, struct.pack("<Q", new_val))
            os.close(fd)
            return True
        except Exception:
            return False


TOPOLOGY_CACHE_FILE = "/tmp/hp_cpu_topology_cache.json"
_STATIC_CPU_TOPOLOGY = None


def save_topology_cache(topo: dict):
    try:
        tmp_file = f"{TOPOLOGY_CACHE_FILE}.tmp.{os.getpid()}"
        with open(tmp_file, "w") as f:
            json.dump(topo, f, indent=2)
        try:
            os.chmod(tmp_file, 0o644)
        except OSError:
            pass
        os.replace(tmp_file, TOPOLOGY_CACHE_FILE)
    except Exception:
        pass


def load_topology_cache() -> dict | None:
    if os.path.exists(TOPOLOGY_CACHE_FILE):
        try:
            with open(TOPOLOGY_CACHE_FILE, "r") as f:
                data = json.load(f)
                if data.get("p_cpus") and ("e_cpus" in data) and data.get("p_pairs"):
                    return data
        except Exception:
            pass
    return None


def parse_sysfs_cpulist(path: str) -> list[int]:
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


def get_cpu_topology_info(force_refresh: bool = False) -> dict:
    """Discovers core types (P-core, E-core) and frequency bounds at runtime without hardcoded CPU numbers.
    Caches the static physical topology so dynamically offlining cores never corrupts core discovery.
    """
    global _STATIC_CPU_TOPOLOGY
    if not force_refresh:
        if _STATIC_CPU_TOPOLOGY is not None:
            return _STATIC_CPU_TOPOLOGY
        cached = load_topology_cache()
        if cached:
            _STATIC_CPU_TOPOLOGY = cached
            return cached

    # Parse PMU CPU masks (which in Linux kernel only list currently-online cores)
    p_cpus = parse_sysfs_cpulist("/sys/devices/cpu_core/cpus")
    e_cpus = parse_sysfs_cpulist("/sys/devices/cpu_atom/cpus")

    possible_cpus = parse_sysfs_cpulist("/sys/devices/system/cpu/possible")
    if not possible_cpus:
        possible_cpus = [
            int(os.path.basename(p)[3:])
            for p in glob.glob("/sys/devices/system/cpu/cpu[0-9]*")
            if os.path.basename(p)[3:].isdigit()
        ]
        possible_cpus.sort()

    # If some CPUs are currently offline, PMU sysfs only includes the online ones!
    known_cpus = set(p_cpus + e_cpus)
    missing_cpus = [c for c in possible_cpus if c not in known_cpus]
    if missing_cpus:
        # Check if we have write access to bring them online temporarily
        can_write_online = any(os.access(f"/sys/devices/system/cpu/cpu{c}/online", os.W_OK) for c in missing_cpus)
        if can_write_online:
            for c in missing_cpus:
                try:
                    with open(f"/sys/devices/system/cpu/cpu{c}/online", "w") as f:
                        f.write("1\n")
                except OSError:
                    pass
            # Re-read PMUs with all cores online
            p_cpus = parse_sysfs_cpulist("/sys/devices/cpu_core/cpus")
            e_cpus = parse_sysfs_cpulist("/sys/devices/cpu_atom/cpus")
        else:
            # Non-root fallback:
            if e_cpus:
                min_e = min(e_cpus)
                e_cpus = sorted(list(set(e_cpus + [c for c in possible_cpus if c >= min_e])))
                p_cpus = sorted(list(set(p_cpus + [c for c in possible_cpus if c < min_e])))
            elif p_cpus:
                max_p = max(p_cpus)
                p_cpus = sorted(list(set(p_cpus + [c for c in possible_cpus if c <= max_p])))
                e_cpus = sorted([c for c in possible_cpus if c > max_p])
            else:
                p_cpus = possible_cpus[:4] if len(possible_cpus) >= 4 else possible_cpus
                e_cpus = possible_cpus[4:] if len(possible_cpus) > 4 else []

    def get_freq_bounds(cpus: list[int], fallback_min: int, fallback_max: int) -> tuple[int, int]:
        if not cpus:
            return fallback_min, fallback_max
        for cpu in cpus:
            min_path = f"/sys/devices/system/cpu/cpu{cpu}/cpufreq/cpuinfo_min_freq"
            max_path = f"/sys/devices/system/cpu/cpu{cpu}/cpufreq/cpuinfo_max_freq"
            if os.path.exists(min_path) and os.path.exists(max_path):
                try:
                    with open(min_path, "r") as f:
                        min_khz = int(f.read().strip())
                    with open(max_path, "r") as f:
                        max_khz = int(f.read().strip())
                    return min_khz, max_khz
                except (OSError, ValueError):
                    pass
        return fallback_min, fallback_max

    p_min_khz, p_max_khz = get_freq_bounds(p_cpus, 400000, 4700000)
    e_min_khz, e_max_khz = get_freq_bounds(e_cpus, 400000, 3500000)

    # Discover thread sibling pairs for physical P-cores
    p_pairs = []
    seen = set()
    for cpu in p_cpus:
        if cpu in seen:
            continue
        sib_path = f"/sys/devices/system/cpu/cpu{cpu}/topology/thread_siblings_list"
        sibs = parse_sysfs_cpulist(sib_path) if os.path.exists(sib_path) else [cpu]
        sibs = [c for c in sibs if c in p_cpus]
        if not sibs:
            sibs = [cpu]
        for c in sibs:
            seen.add(c)
        p_pairs.append(sorted(sibs))

    topo = {
        "p_cpus": p_cpus,
        "e_cpus": e_cpus,
        "p_pairs": p_pairs,
        "p_min_khz": p_min_khz,
        "p_max_khz": p_max_khz,
        "e_min_khz": e_min_khz,
        "e_max_khz": e_max_khz,
        "p_min_mhz": p_min_khz // 1000,
        "p_max_mhz": p_max_khz // 1000,
        "e_min_mhz": e_min_khz // 1000,
        "e_max_mhz": e_max_khz // 1000,
        "p_supported": len(p_cpus) > 0,
        "e_supported": len(e_cpus) > 0,
    }

    _STATIC_CPU_TOPOLOGY = topo
    save_topology_cache(topo)
    return topo


def get_core_topology_details() -> dict:
    """Discovers thread sibling pairs and online status for all CPUs.
    p_cpus, e_cpus, and p_pairs represent the complete physical hardware layout.
    online_map and writable_map represent live dynamic status.
    """
    topo = get_cpu_topology_info()
    p_cpus = list(topo["p_cpus"])
    e_cpus = list(topo["e_cpus"])
    p_pairs = [list(pair) for pair in topo.get("p_pairs", [])]
    all_cpus = sorted(list(set(p_cpus + e_cpus)))

    # Read live online states & writability
    online_map = {}
    writable_map = {}
    for c in all_cpus:
        p = f"/sys/devices/system/cpu/cpu{c}/online"
        if os.path.exists(p):
            try:
                with open(p, "r") as f:
                    online_map[c] = (f.read().strip() == "1")
            except OSError:
                online_map[c] = True
            writable_map[c] = os.access(p, os.W_OK)
        else:
            online_map[c] = True
            writable_map[c] = False

    return {
        "all_cpus": all_cpus,
        "p_cpus": p_cpus,
        "e_cpus": e_cpus,
        "p_pairs": p_pairs,
        "online_map": online_map,
        "writable_map": writable_map,
    }
