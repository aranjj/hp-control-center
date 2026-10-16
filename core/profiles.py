"""
Profile Definitions & Configuration Management
"""

import os
import json

CONFIG_DIR = os.path.expanduser("~/.config/hp-control-center")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")

DEFAULT_PROFILES = {
    "ultra_gaming": {
        "name": "Ultra Gaming",
        "icon": "🚀",
        "description": "Max sustained 25W+ envelope, GPU floor locked at 800 MHz, Turbo enabled.",
        "pl1_w": 25.0,
        "pl2_w": 28.0,
        "sync_mmio": True,
        "disable_bdprochot": True,
        "gpu_min_mhz": 800,
        "gpu_max_mhz": 1250,
        "gpu_power_mode": "base",
        "turbo_boost": True,
        "cpu_epp": "performance",
        "cpu_governor": "powersave",
        "p_core_max_mhz": 4700,
        "e_core_max_mhz": 3500,
    },
    "balanced": {
        "name": "Daily Balanced",
        "icon": "⚡",
        "description": "Sustained 24W for smooth all-around responsiveness with adaptive cooling.",
        "pl1_w": 24.0,
        "pl2_w": 25.0,
        "sync_mmio": True,
        "disable_bdprochot": True,
        "gpu_min_mhz": 100,
        "gpu_max_mhz": 1250,
        "gpu_power_mode": "base",
        "turbo_boost": True,
        "cpu_epp": "balance_performance",
        "cpu_governor": "powersave",
        "p_core_max_mhz": 4700,
        "e_core_max_mhz": 3500,
    },
    "eco_quiet": {
        "name": "Silent & Eco",
        "icon": "🍃",
        "description": "15W stock power, Turbo disabled (1.7 GHz base), whisper-quiet thermals.",
        "pl1_w": 15.0,
        "pl2_w": 18.0,
        "sync_mmio": False,
        "disable_bdprochot": False,
        "gpu_min_mhz": 100,
        "gpu_max_mhz": 800,
        "gpu_power_mode": "power_saving",
        "turbo_boost": False,
        "cpu_epp": "power",
        "cpu_governor": "powersave",
        "p_core_max_mhz": 2400,
        "e_core_max_mhz": 2000,
    },
}


class ProfileManager:
    def __init__(self):
        self.profiles = dict(DEFAULT_PROFILES)
        self.current_profile_key = "balanced"
        self.load_config()

    def get_profile(self, key: str) -> dict:
        return self.profiles.get(key, self.profiles["balanced"])

    def set_active_profile(self, key: str):
        if key in self.profiles:
            self.current_profile_key = key
            self.save_config()

    def update_custom_profile(self, custom_settings: dict):
        self.profiles["custom"] = {
            "name": "Custom",
            "icon": "🛠️",
            "description": "User-tuned manual parameters.",
            **custom_settings,
        }
        self.current_profile_key = "custom"
        self.save_config()

    def load_config(self):
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, "r") as f:
                    data = json.load(f)
                    self.current_profile_key = data.get("active_profile", "balanced")
                    if "custom" in data:
                        self.profiles["custom"] = data["custom"]
            except Exception:
                pass

    def save_config(self):
        os.makedirs(CONFIG_DIR, exist_ok=True)
        try:
            with open(CONFIG_PATH, "w") as f:
                json.dump(
                    {
                        "active_profile": self.current_profile_key,
                        "custom": self.profiles.get("custom", {}),
                    },
                    f,
                    indent=2,
                )
        except OSError:
            pass
