"""
HP Control Center Background Daemon
Runs as root to enforce MSR/MMIO limits and prevent HP EC power decay.
All hardware clamping and validation occurs here.
"""

import os
import sys
import time
import json
import socket
import select
import signal
import threading

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.hardware import HardwareController, get_cpu_topology_info, get_gpu_hardware_limits
from core.telemetry import TelemetryReader
from core.profiles import DEFAULT_PROFILES

SOCKET_PATH = "/tmp/hp_control_center.sock"
DAEMON_STATE_DIR = "/var/lib/hp-control-center"
DAEMON_STATE_FILE = os.path.join(DAEMON_STATE_DIR, "state.json")
DAEMON_FALLBACK_STATE_FILE = os.path.expanduser("~/.config/hp-control-center/daemon_state.json")

# Hardware Safety Constraints
_gpu_min, _gpu_max = get_gpu_hardware_limits()
HARDWARE_LIMITS = {
    "pl1_min_w": 10.0,
    "pl1_max_w": 30.0,
    "pl2_min_w": 10.0,
    "pl2_max_w": 45.0,
    "gpu_min_mhz": _gpu_min,
    "gpu_max_mhz": _gpu_max,
    "valid_epp": ["performance", "balance_performance", "balance_power", "power", "default"],
    "valid_gpu_modes": ["base", "power_saving"],
}


class DaemonService:
    def __init__(self):
        self.hw = HardwareController()
        # Bring all cores back online at startup and cache complete physical topology
        self.hw.restore_all_cores()
        get_cpu_topology_info(force_refresh=True)

        self.telemetry = TelemetryReader()
        self.running = True
        self.active_profile, self.active_settings = self._load_saved_state()
        self.lock = threading.Lock()
        self.tcc_writable = self.hw.check_tcc_offset_writable()
        self.thermal_state = "Holding"
        self.effective_pl1_w = None
        self.hot_counter = 0
        self.cool_counter = 0

    def _get_state_file(self) -> str:
        if os.geteuid() == 0:
            return DAEMON_STATE_FILE
        return DAEMON_FALLBACK_STATE_FILE

    def _load_saved_state(self):
        for path in (DAEMON_STATE_FILE, DAEMON_FALLBACK_STATE_FILE):
            if os.path.exists(path):
                try:
                    with open(path, "r") as f:
                        data = json.load(f)
                    saved_settings = data.get("active_settings", {})
                    profile_key = data.get("active_profile", "balanced")
                    if saved_settings:
                        validated = self.clamp_and_validate_settings(saved_settings)
                        return profile_key, validated
                except Exception as e:
                    print(f"[!] Warning: Failed to load daemon state from {path}: {e}", file=sys.stderr)
        return "balanced", dict(DEFAULT_PROFILES["balanced"])

    def _save_state(self):
        target = self._get_state_file()
        try:
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with open(target, "w") as f:
                json.dump(
                    {
                        "active_profile": self.active_profile,
                        "active_settings": self.active_settings,
                    },
                    f,
                    indent=2,
                )
        except Exception as e:
            print(f"[!] Warning: Failed to save daemon state to {target}: {e}", file=sys.stderr)

    def clamp_and_validate_settings(self, settings: dict) -> dict:
        """Strictly clamps and sanitizes all incoming profile parameters."""
        clamped = {}

        # 1. PL1 Clamping
        raw_pl1 = float(settings.get("pl1_w", 24.0))
        pl1 = max(HARDWARE_LIMITS["pl1_min_w"], min(HARDWARE_LIMITS["pl1_max_w"], raw_pl1))
        clamped["pl1_w"] = round(pl1, 1)

        # 2. PL2 Clamping (PL2 must always be >= PL1)
        raw_pl2 = float(settings.get("pl2_w", 25.0))
        pl2 = max(clamped["pl1_w"], min(HARDWARE_LIMITS["pl2_max_w"], raw_pl2))
        clamped["pl2_w"] = round(pl2, 1)

        # 3. MMIO & BDPROCHOT flags
        clamped["sync_mmio"] = bool(settings.get("sync_mmio", True))
        clamped["disable_bdprochot"] = bool(settings.get("disable_bdprochot", True))

        # 4. Intel Iris Xe GPU Clocks
        raw_gpu_min = int(settings.get("gpu_min_mhz", 100))
        gpu_min = max(HARDWARE_LIMITS["gpu_min_mhz"], min(HARDWARE_LIMITS["gpu_max_mhz"], raw_gpu_min))
        clamped["gpu_min_mhz"] = gpu_min

        raw_gpu_max = int(settings.get("gpu_max_mhz", 1250))
        gpu_max = max(clamped["gpu_min_mhz"], min(HARDWARE_LIMITS["gpu_max_mhz"], raw_gpu_max))
        clamped["gpu_max_mhz"] = gpu_max

        # 5. GPU Power Mode
        p_mode = str(settings.get("gpu_power_mode", "base"))
        clamped["gpu_power_mode"] = p_mode if p_mode in HARDWARE_LIMITS["valid_gpu_modes"] else "base"

        # 6. CPU Turbo Boost
        clamped["turbo_boost"] = bool(settings.get("turbo_boost", True))

        # 7. CPU EPP & Governor
        epp = str(settings.get("cpu_epp", "balance_performance"))
        clamped["cpu_epp"] = epp if epp in HARDWARE_LIMITS["valid_epp"] else "balance_performance"

        gov = str(settings.get("cpu_governor", "powersave"))
        clamped["cpu_governor"] = gov if gov in ("performance", "powersave") else "powersave"

        # 8. CPU Clock Limits (P-core & E-core scaling_max_freq / scaling_min_freq)
        topo = get_cpu_topology_info()
        if "p_core_max_mhz" in settings:
            raw_p = int(settings["p_core_max_mhz"])
            clamped["p_core_max_mhz"] = max(topo["p_min_mhz"], min(topo["p_max_mhz"], raw_p))
        if "e_core_max_mhz" in settings:
            raw_e = int(settings["e_core_max_mhz"])
            clamped["e_core_max_mhz"] = max(topo["e_min_mhz"], min(topo["e_max_mhz"], raw_e))

        if "p_core_min_mhz" in settings:
            raw_p_min = int(settings["p_core_min_mhz"])
            limit_max = clamped.get("p_core_max_mhz", topo["p_max_mhz"])
            clamped["p_core_min_mhz"] = max(topo["p_min_mhz"], min(limit_max, raw_p_min))
        if "e_core_min_mhz" in settings:
            raw_e_min = int(settings["e_core_min_mhz"])
            limit_max = clamped.get("e_core_max_mhz", topo["e_max_mhz"])
            clamped["e_core_min_mhz"] = max(topo["e_min_mhz"], min(limit_max, raw_e_min))

        # 9. Core Management (Active P-core threads & Active E-cores)
        total_p = len(topo["p_cpus"])
        total_e = len(topo["e_cpus"])
        if "active_p_threads" in settings:
            raw_p = int(settings["active_p_threads"])
            clamped["active_p_threads"] = max(2 if total_p > 1 else 1, min(total_p, raw_p))
        if "active_e_cores" in settings:
            raw_e = int(settings["active_e_cores"])
            clamped["active_e_cores"] = max(0, min(total_e, raw_e))

        # 10. Thermal Target
        raw_target = int(settings.get("thermal_target_c", 95))
        clamped["thermal_target_c"] = max(69, min(100, raw_target))
        clamped["use_hardware_tcc"] = bool(settings.get("use_hardware_tcc", False)) and self.tcc_writable

        # 11. Power Limits Re-assertion Interval (seconds, 0 = Disabled)
        try:
            raw_reassert = int(settings.get("reassert_interval_s", 10))
            clamped["reassert_interval_s"] = max(0, min(120, raw_reassert))
        except (ValueError, TypeError):
            clamped["reassert_interval_s"] = 10

        return clamped

    def apply_current_settings(self):
        """Applies the validated profile settings directly to the hardware."""
        with self.lock:
            s = self.active_settings
            try:
                # 1. Package Power Limits (MSR + MMIO)
                pl1 = self.effective_pl1_w if (self.effective_pl1_w is not None and self.thermal_state == "Reducing PL1") else s["pl1_w"]
                self.hw.set_package_power_limits(pl1, max(pl1, s["pl2_w"]), sync_mmio=s["sync_mmio"])

                # 2. BD PROCHOT
                self.hw.set_bdprochot_disabled(s["disable_bdprochot"])

                # 3. Intel Iris Xe GPU Clocks
                self.hw.set_gpu_clocks(s["gpu_min_mhz"], s["gpu_max_mhz"], s["gpu_power_mode"])

                # 4. CPU Turbo Boost
                self.hw.set_cpu_turbo(s["turbo_boost"])

                # 5. CPU Governor & EPP
                self.hw.set_cpu_epp(s["cpu_epp"])
                self.hw.set_cpu_governor(s["cpu_governor"])

                # 6. Core Management (Parking / Unparking Cores) - unpark before setting clocks
                if "active_p_threads" in s or "active_e_cores" in s:
                    self.hw.set_online_cores(
                        active_p_threads=s.get("active_p_threads"),
                        active_e_cores=s.get("active_e_cores"),
                    )

                # 7. CPU Clock Frequencies (P-core & E-core) - applied to all online cores
                self.hw.set_cpu_frequencies(
                    p_max_mhz=s.get("p_core_max_mhz"),
                    e_max_mhz=s.get("e_core_max_mhz"),
                    p_min_mhz=s.get("p_core_min_mhz"),
                    e_min_mhz=s.get("e_core_min_mhz"),
                )

                # 8. Hardware TCC offset (if enabled & writable)
                if s.get("use_hardware_tcc") and self.tcc_writable:
                    target_c = s.get("thermal_target_c", 95)
                    if target_c > 69:
                        self.hw.set_hardware_tcc_offset(target_c)

            except Exception as e:
                print(f"[!] Error applying settings: {e}", file=sys.stderr)

    def _tick_thermal_target(self):
        """1-second software thermal target loop:
        - If temp >= target for 3 consecutive seconds: lower PL1 by 1W (floor 10W)
        - If temp <= target - 5°C for 10 consecutive seconds: raise PL1 by 1W back to user requested value
        - Log every adjustment and track state (Holding, Reducing PL1, Recovering, Off)
        """
        with self.lock:
            s = self.active_settings
            target = s.get("thermal_target_c", 95)
            use_hw_tcc = s.get("use_hardware_tcc", False) and self.tcc_writable

            if target is None or target <= 69:
                self.thermal_state = "Off"
                self.effective_pl1_w = float(s.get("pl1_w", 24.0))
                self.hot_counter = 0
                self.cool_counter = 0
                return

            if use_hw_tcc:
                self.thermal_state = "Hardware TCC"
                return

            temp = self.telemetry.get_package_temp()
            if temp is None:
                return

            requested_pl1 = float(s.get("pl1_w", 24.0))
            if self.effective_pl1_w is None:
                self.effective_pl1_w = requested_pl1

            if temp >= target:
                self.hot_counter += 1
                self.cool_counter = 0
                if self.hot_counter >= 3:
                    if self.effective_pl1_w > 10.0:
                        self.effective_pl1_w = max(10.0, self.effective_pl1_w - 1.0)
                        self.thermal_state = "Reducing PL1"
                        self.hw.set_package_power_limits(
                            self.effective_pl1_w,
                            max(self.effective_pl1_w, float(s.get("pl2_w", 28.0))),
                            sync_mmio=s.get("sync_mmio", True),
                        )
                        print(f"[*] Thermal Target: Temp {temp}°C >= {target}°C for 3s. Lowered PL1 to {self.effective_pl1_w:.1f}W", file=sys.stderr)
                    self.hot_counter = 0
            elif temp <= (target - 5):
                self.cool_counter += 1
                self.hot_counter = 0
                if self.cool_counter >= 10:
                    if self.effective_pl1_w < requested_pl1:
                        self.effective_pl1_w = min(requested_pl1, self.effective_pl1_w + 1.0)
                        self.thermal_state = "Recovering"
                        self.hw.set_package_power_limits(
                            self.effective_pl1_w,
                            max(self.effective_pl1_w, float(s.get("pl2_w", 28.0))),
                            sync_mmio=s.get("sync_mmio", True),
                        )
                        print(f"[*] Thermal Target: Temp {temp}°C <= {target - 5}°C for 10s. Recovered PL1 to {self.effective_pl1_w:.1f}W", file=sys.stderr)
                    else:
                        self.thermal_state = "Holding"
                    self.cool_counter = 0
            else:
                self.hot_counter = 0
                self.cool_counter = 0
                if self.effective_pl1_w < requested_pl1:
                    self.thermal_state = "Recovering"
                else:
                    self.thermal_state = "Holding"

    def reassert_power_limits(self):
        """Quickly re-asserts MSR 0x610 and MMIO RAPL power limits to defeat EC/DPTF resets."""
        with self.lock:
            s = self.active_settings
            pl1 = self.effective_pl1_w if (self.effective_pl1_w is not None and self.thermal_state == "Reducing PL1") else float(s.get("pl1_w", 24.0))
            pl2 = max(pl1, float(s.get("pl2_w", 28.0)))
            sync_mmio = bool(s.get("sync_mmio", True))
            self.hw.set_package_power_limits(pl1, pl2, sync_mmio=sync_mmio)

    def power_loop(self):
        """Periodically re-asserts power limits at the configured interval and manages 1Hz thermal loop."""
        last_reassert = time.time()
        last_ac = None
        while self.running:
            now = time.time()
            is_ac = self.telemetry.is_ac_connected()

            with self.lock:
                interval = int(self.active_settings.get("reassert_interval_s", 10))

            # Trigger reassert if interval elapsed, or immediately on AC/Battery transition
            ac_changed = (last_ac is not None and is_ac != last_ac)
            last_ac = is_ac

            if ac_changed or (interval > 0 and (now - last_reassert >= interval)):
                self.reassert_power_limits()
                last_reassert = now

            self._tick_thermal_target()
            time.sleep(1.0)

    def handle_client(self, conn):
        try:
            data = conn.recv(4096).decode("utf-8")
            if not data:
                return

            msg = json.loads(data)
            cmd = msg.get("cmd")

            if cmd == "apply":
                raw_settings = msg.get("settings", {})
                profile_key = msg.get("profile")
                validated = self.clamp_and_validate_settings(raw_settings)
                with self.lock:
                    if profile_key:
                        self.active_profile = profile_key
                    self.active_settings.update(validated)
                    self._save_state()
                self.apply_current_settings()
                resp = {
                    "status": "ok",
                    "message": "Settings clamped, validated, and applied successfully.",
                    "applied_settings": self.active_settings,
                    "active_profile": self.active_profile,
                }
            elif cmd == "get_limits":
                resp = {
                    "status": "ok",
                    "hardware_limits": HARDWARE_LIMITS,
                    "default_profiles": DEFAULT_PROFILES,
                    "tcc_writable": self.tcc_writable,
                }
            elif cmd == "get_status":
                with self.lock:
                    resp = {
                        "status": "ok",
                        "active_profile": self.active_profile,
                        "active_settings": self.active_settings,
                        "telemetry": self.telemetry.get_all(),
                        "thermal_status": {
                            "state": self.thermal_state,
                            "effective_pl1_w": self.effective_pl1_w if self.effective_pl1_w is not None else self.active_settings.get("pl1_w", 24.0),
                            "target_c": self.active_settings.get("thermal_target_c", 95),
                            "tcc_writable": self.tcc_writable,
                        },
                    }
            elif cmd == "reset_defaults":
                self.hw.restore_all_cores()
                with self.lock:
                    self.active_profile = "balanced"
                    self.active_settings = dict(DEFAULT_PROFILES["balanced"])
                    self._save_state()
                self.apply_current_settings()
                resp = {"status": "ok", "message": "Defaults restored and all cores brought online."}
            elif cmd == "ping":
                resp = {"status": "ok", "daemon_running": True}
            else:
                resp = {"status": "error", "message": f"Unknown command: {cmd}"}

            conn.sendall(json.dumps(resp).encode("utf-8"))
        except Exception as e:
            err_resp = {"status": "error", "message": str(e)}
            conn.sendall(json.dumps(err_resp).encode("utf-8"))
        finally:
            conn.close()

    def start(self):
        if os.geteuid() != 0:
            print("[!] Daemon must run as root to access MSR and MMIO.", file=sys.stderr)
            sys.exit(1)

        # Cleanup stale socket
        if os.path.exists(SOCKET_PATH):
            os.remove(SOCKET_PATH)

        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(SOCKET_PATH)
        # Set permissions so any local user can communicate with the daemon
        os.chmod(SOCKET_PATH, 0o666)
        server.listen(5)

        # Apply saved/initial profile settings directly to hardware on service startup
        self.apply_current_settings()

        # Start background hardware enforcement loop
        thread = threading.Thread(target=self.power_loop, daemon=True)
        thread.start()

        print(f"[+] HP Control Center Daemon started. Listening on {SOCKET_PATH}")

        def sig_handler(sig, frame):
            print("\n[!] Shutting down daemon...")
            self.running = False
            self.hw.restore_all_cores()
            if os.path.exists(SOCKET_PATH):
                os.remove(SOCKET_PATH)
            sys.exit(0)

        signal.signal(signal.SIGINT, sig_handler)
        signal.signal(signal.SIGTERM, sig_handler)

        while self.running:
            try:
                r, _, _ = select.select([server], [], [], 1.0)
                if r:
                    conn, _ = server.accept()
                    client_thread = threading.Thread(target=self.handle_client, args=(conn,), daemon=True)
                    client_thread.start()
            except KeyboardInterrupt:
                break

        if os.path.exists(SOCKET_PATH):
            os.remove(SOCKET_PATH)


if __name__ == "__main__":
    daemon = DaemonService()
    daemon.start()
