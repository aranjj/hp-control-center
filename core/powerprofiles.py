"""
Integration helper with system powerprofilesctl (power-profiles-daemon).
Allows bidirectional synchronization between desktop environment power profiles
(KDE Plasma, GNOME, etc.) and HP Control Center presets.
"""

import shutil
import subprocess
from typing import Optional

# Mapping between HP Control Center presets and power-profiles-daemon
APP_TO_PPD_MAP = {
    "ultra_gaming": "performance",
    "balanced": "balanced",
    "eco_quiet": "power-saver",
}

PPD_TO_APP_MAP = {
    "performance": "ultra_gaming",
    "balanced": "balanced",
    "power-saver": "eco_quiet",
}


def is_ppd_available() -> bool:
    """Checks whether powerprofilesctl binary is installed on the host system."""
    return shutil.which("powerprofilesctl") is not None


def get_ppd_profile() -> Optional[str]:
    """Returns the currently active power-profiles-daemon profile string, or None."""
    if not is_ppd_available():
        return None
    try:
        res = subprocess.run(
            ["powerprofilesctl", "get"],
            capture_output=True,
            text=True,
            timeout=1.0,
        )
        if res.returncode == 0:
            return res.stdout.strip()
    except Exception:
        pass
    return None


def set_ppd_profile(profile: str) -> bool:
    """Sets the system power-profiles-daemon profile via powerprofilesctl."""
    if not is_ppd_available() or not profile:
        return False
    try:
        # Check current to avoid redundant execution
        current = get_ppd_profile()
        if current == profile:
            return True

        res = subprocess.run(
            ["powerprofilesctl", "set", profile],
            capture_output=True,
            text=True,
            timeout=2.0,
        )
        return res.returncode == 0
    except Exception:
        return False


def map_app_to_ppd(app_profile: str, epp: str = None) -> Optional[str]:
    """Maps HP Control Center profile key to powerprofilesctl profile name."""
    if app_profile in APP_TO_PPD_MAP:
        return APP_TO_PPD_MAP[app_profile]
    if app_profile == "custom":
        if epp == "performance":
            return "performance"
        elif epp in ("power", "balance_power"):
            return "power-saver"
        return "balanced"
    return None


def map_ppd_to_app(ppd_profile: str) -> Optional[str]:
    """Maps powerprofilesctl profile name to HP Control Center preset key."""
    return PPD_TO_APP_MAP.get(ppd_profile)
