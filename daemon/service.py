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

from core.hardware import HardwareController, get_cpu_topology_info
from core.telemetry import TelemetryReader
from core.profiles import DEFAULT_PROFILES

SOCKET_PATH = "/tmp/hp_control_center.sock"

# Hardware Safety Constraints for i7-1255U & HP 15 Chassis
HARDWARE_LIMITS = {
    "pl1_min_w": 10.0,
    "pl1_max_w": 30.0,
    "pl2_min_w": 10.0,
    "pl2_max_w": 45.0,
    "gpu_min_mhz": 100,
    "gpu_max_mhz": 1250,
    "valid_epp": ["performance", "balance_performance", "balance_power", "power", "default"],
    "valid_gpu_modes": ["base", "power_saving"],
}


class DaemonService:
    def __init__(self):
        self.hw = HardwareController()
        self.telemetry = TelemetryReader()
        self.running = True
        self.active_settings = dict(DEFAULT_PROFILES["balanced"])
        self.lock = threading.Lock()

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

        return clamped

    def apply_current_settings(self):
        """Applies the validated profile settings directly to the hardware."""
        with self.lock:
            s = self.active_settings
            try:
                # 1. Package Power Limits (MSR + MMIO)
                self.hw.set_package_power_limits(s["pl1_w"], s["pl2_w"], sync_mmio=s["sync_mmio"])

                # 2. BD PROCHOT
                self.hw.set_bdprochot_disabled(s["disable_bdprochot"])

                # 3. Intel Iris Xe GPU Clocks
                self.hw.set_gpu_clocks(s["gpu_min_mhz"], s["gpu_max_mhz"], s["gpu_power_mode"])

                # 4. CPU Turbo Boost
                self.hw.set_cpu_turbo(s["turbo_boost"])

                # 5. CPU Governor & EPP
                self.hw.set_cpu_epp(s["cpu_epp"])
                self.hw.set_cpu_governor(s["cpu_governor"])

                # 6. CPU Clock Frequencies (P-core & E-core)
                self.hw.set_cpu_frequencies(
                    p_max_mhz=s.get("p_core_max_mhz"),
                    e_max_mhz=s.get("e_core_max_mhz"),
                    p_min_mhz=s.get("p_core_min_mhz"),
                    e_min_mhz=s.get("e_core_min_mhz"),
                )

            except Exception as e:
                print(f"[!] Error applying settings: {e}", file=sys.stderr)

    def power_loop(self):
        """Continuously re-asserts power limits every 5s on AC (25s on Battery)."""
        while self.running:
            is_ac = self.telemetry.is_ac_connected()
            sleep_time = 5.0 if is_ac else 25.0

            self.apply_current_settings()
            time.sleep(sleep_time)

    def handle_client(self, conn):
        try:
            data = conn.recv(4096).decode("utf-8")
            if not data:
                return

            msg = json.loads(data)
            cmd = msg.get("cmd")

            if cmd == "apply":
                raw_settings = msg.get("settings", {})
                validated = self.clamp_and_validate_settings(raw_settings)
                with self.lock:
                    self.active_settings.update(validated)
                self.apply_current_settings()
                resp = {
                    "status": "ok",
                    "message": "Settings clamped, validated, and applied successfully.",
                    "applied_settings": self.active_settings,
                }
            elif cmd == "get_limits":
                resp = {
                    "status": "ok",
                    "hardware_limits": HARDWARE_LIMITS,
                    "default_profiles": DEFAULT_PROFILES,
                }
            elif cmd == "get_status":
                with self.lock:
                    resp = {
                        "status": "ok",
                        "active_settings": self.active_settings,
                        "telemetry": self.telemetry.get_all(),
                    }
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

        # Start background hardware enforcement loop
        thread = threading.Thread(target=self.power_loop, daemon=True)
        thread.start()

        print(f"[+] HP Control Center Daemon started. Listening on {SOCKET_PATH}")

        def sig_handler(sig, frame):
            print("\n[!] Shutting down daemon...")
            self.running = False
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
