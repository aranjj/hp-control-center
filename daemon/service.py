"""
HP Control Center Background Daemon
Runs as root to enforce MSR/MMIO limits and prevent HP EC power decay.
Listens on a local Unix socket for commands from the user GUI.
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

from core.hardware import HardwareController
from core.telemetry import TelemetryReader
from core.profiles import DEFAULT_PROFILES

SOCKET_PATH = "/tmp/hp_control_center.sock"


class DaemonService:
    def __init__(self):
        self.hw = HardwareController()
        self.telemetry = TelemetryReader()
        self.running = True
        self.active_settings = dict(DEFAULT_PROFILES["balanced"])
        self.lock = threading.Lock()

    def apply_current_settings(self):
        """Applies the current profile settings to the hardware."""
        with self.lock:
            s = self.active_settings
            try:
                # 1. Package Power Limits (MSR + MMIO)
                pl1 = float(s.get("pl1_w", 24.0))
                pl2 = float(s.get("pl2_w", 25.0))
                sync_mmio = bool(s.get("sync_mmio", True))
                self.hw.set_package_power_limits(pl1, pl2, sync_mmio=sync_mmio)

                # 2. BD PROCHOT
                disable_bd = bool(s.get("disable_bdprochot", True))
                self.hw.set_bdprochot_disabled(disable_bd)

                # 3. Intel Iris Xe GPU Clocks
                min_mhz = int(s.get("gpu_min_mhz", 100))
                max_mhz = int(s.get("gpu_max_mhz", 1250))
                p_mode = str(s.get("gpu_power_mode", "base"))
                self.hw.set_gpu_clocks(min_mhz, max_mhz, p_mode)

                # 4. CPU Turbo Boost
                turbo = bool(s.get("turbo_boost", True))
                self.hw.set_cpu_turbo(turbo)

                # 5. CPU Governor & EPP
                epp = str(s.get("cpu_epp", "balance_performance"))
                self.hw.set_cpu_epp(epp)
                gov = str(s.get("cpu_governor", "powersave"))
                self.hw.set_cpu_governor(gov)

            except Exception as e:
                print(f"[!] Error applying settings: {e}", file=sys.stderr)

    def power_loop(self):
        """Continuously re-asserts power limits to defeat EC decay."""
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
                new_settings = msg.get("settings", {})
                with self.lock:
                    self.active_settings.update(new_settings)
                self.apply_current_settings()
                resp = {"status": "ok", "message": "Settings applied successfully."}
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
