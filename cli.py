#!/usr/bin/env python3
"""
HP Performance Control Center - CLI Tool
Allows quick terminal switching between performance modes.
Usage:
    python3 cli.py status
    python3 cli.py profile ultra_gaming
    python3 cli.py profile balanced
    python3 cli.py profile eco_quiet
"""

import sys
import os
import json
import socket
import argparse

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from core.telemetry import TelemetryReader
from core.profiles import DEFAULT_PROFILES, ProfileManager
from core.sysinfo import get_cpu_display_names, get_gpu_display_names
from core.powerprofiles import is_ppd_available, get_ppd_profile, set_ppd_profile, map_app_to_ppd

SOCKET_PATH = "/tmp/hp_control_center.sock"


def send_daemon_cmd(cmd_dict):
    if not os.path.exists(SOCKET_PATH):
        sys.exit("Error: Daemon is not running. Start with: sudo python3 daemon/service.py")

    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        client.connect(SOCKET_PATH)
        client.sendall(json.dumps(cmd_dict).encode("utf-8"))
        data = client.recv(4096).decode("utf-8")
        return json.loads(data)
    finally:
        client.close()


def show_status():
    t = TelemetryReader()
    data = t.get_all()
    _, cpu_short = get_cpu_display_names()
    _, gpu_short = get_gpu_display_names()
    gpu_label = f"{gpu_short} GPU Clock" if gpu_short != "GPU" else "GPU Clock"

    print("=" * 55)
    print(f" ⚡ PERFORMANCE STATUS ({cpu_short})")
    print("=" * 55)
    print(f" Package Power:      {data['power_watts']} W")
    print(f" Package Temp:       {data['temp_c']} °C")
    print(f" Cooling Fan:        {data['fan_rpm']} RPM")
    print(f" {gpu_label:19}: {data['gpu']['act_mhz']} MHz (Min: {data['gpu']['min_mhz']}, Max: {data['gpu']['max_mhz']})")
    print(f" GPU Throttling:     {data['gpu']['throttle_reasons'].upper()}")
    print(f" CPU Clocks:         P-Cores: {data['cpu_freq']['p_core_mhz']} MHz | E-Cores: {data['cpu_freq']['e_core_mhz']} MHz")
    print(f" Power Source:       {'AC Connected' if data['ac_connected'] else 'On Battery'}")
    if is_ppd_available():
        ppd_mode = get_ppd_profile()
        print(f" System Profile:     {ppd_mode} (powerprofilesctl)")
    print(f" Daemon Active:      {'Yes' if os.path.exists(SOCKET_PATH) else 'No (Offline)'}")
    print("=" * 55)


def apply_profile(name):
    alias_map = {
        "gaming": "ultra_gaming",
        "ultra": "ultra_gaming",
        "ultra_gaming": "ultra_gaming",
        "balanced": "balanced",
        "normal": "balanced",
        "eco": "eco_quiet",
        "quiet": "eco_quiet",
        "silent": "eco_quiet",
        "eco_quiet": "eco_quiet",
    }
    key = alias_map.get(name.lower())
    if not key or key not in DEFAULT_PROFILES:
        sys.exit(f"Unknown profile: {name}. Available: gaming, balanced, eco")

    p = DEFAULT_PROFILES[key]
    print(f"[+] Applying profile: {p['name']} ({p['icon']})")
    print(f"    PL1: {p['pl1_w']}W | PL2: {p['pl2_w']}W | GPU Min: {p['gpu_min_mhz']}MHz | Turbo: {p['turbo_boost']}")

    resp = send_daemon_cmd({"cmd": "apply", "settings": p, "profile": key})
    if resp.get("status") == "ok":
        try:
            ProfileManager().set_active_profile(key)
        except Exception:
            pass
        if is_ppd_available():
            ppd_mode = map_app_to_ppd(key)
            if ppd_mode:
                set_ppd_profile(ppd_mode)
                print(f"[+] System power profile synced: {ppd_mode} (KDE / GNOME)")
        print("[+] Success!")
    else:
        print(f"[!] Error: {resp.get('message')}")


def main():
    parser = argparse.ArgumentParser(description="HP Control Center CLI")
    subparsers = parser.add_subparsers(dest="command")

    # Status
    subparsers.add_parser("status", help="Print live system telemetry")

    # Profile
    p_parser = subparsers.add_parser("profile", help="Apply a performance profile")
    p_parser.add_argument("name", choices=["gaming", "balanced", "eco", "ultra_gaming", "eco_quiet"], help="Profile name")

    args = parser.parse_args()
    if args.command == "status":
        show_status()
    elif args.command == "profile":
        apply_profile(args.name)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
