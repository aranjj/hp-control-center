"""
Display and Screen Management for HP Control Center
Integrates with KDE KScreen via kscreen-doctor on Wayland / X11.
Supports:
- Resolution & Refresh rate mode switching
- Fractional and integer display scaling
- Hardware brightness control
- RGB Color Range (Full vs Limited)
- VRR / Adaptive Sync policy
- Color Profile (ICC / EDID)
"""

import os
import json
import shutil
import subprocess
from typing import Optional, Dict, Any, List


class DisplayManager:
    """Manages display settings via kscreen-doctor."""

    def __init__(self):
        self.kscreen_bin = shutil.which("kscreen-doctor")

    def is_available(self) -> bool:
        return self.kscreen_bin is not None

    def get_display_state(self) -> Optional[Dict[str, Any]]:
        """Queries current display configuration from kscreen-doctor JSON."""
        if not self.kscreen_bin:
            return None

        try:
            env = os.environ.copy()
            if env.get("QT_QPA_PLATFORM") == "offscreen":
                env.pop("QT_QPA_PLATFORM", None)

            res = subprocess.run(
                [self.kscreen_bin, "-j"],
                capture_output=True,
                text=True,
                timeout=3,
                check=True,
                env=env,
            )
            data = json.loads(res.stdout)
        except Exception:
            return None

        outputs = data.get("outputs", [])
        if not outputs:
            return None

        # Select primary / internal panel (e.g., eDP-1) or first connected output
        target = None
        for out in outputs:
            if out.get("connected") and out.get("enabled"):
                if "eDP" in out.get("name", ""):
                    target = out
                    break
                elif target is None:
                    target = out

        if not target:
            target = outputs[0]

        output_name = target.get("name", "eDP-1")
        current_mode_id = str(target.get("currentModeId", "1"))
        scale = float(target.get("scale", 1.0))
        b_raw = target.get("brightness", 1.0)
        try:
            b_float = float(b_raw)
            if b_float <= 1.0:
                brightness_pct = int(round(b_float * 100))
            else:
                brightness_pct = int(b_float)
        except Exception:
            brightness_pct = 100

        # Parse modes (deduplicating by resolution & refresh rate)
        raw_modes = target.get("modes", [])
        modes = []
        seen = set()
        for m in raw_modes:
            m_id = str(m.get("id"))
            size = m.get("size", {})
            w = size.get("width", 0)
            h = size.get("height", 0)
            rr = round(float(m.get("refreshRate", 60.0)), 1)
            label = f"{w}x{h} @ {rr:.0f} Hz" if rr.is_integer() else f"{w}x{h} @ {rr} Hz"
            key = (w, h, int(round(rr)))
            modes.append({
                "id": m_id,
                "label": label,
                "width": w,
                "height": h,
                "refresh": rr,
                "is_current": (m_id == current_mode_id),
            })

        # Query human-readable summary for VRR capability and RGB range
        vrr_capable = False
        vrr_policy = "never"
        rgb_range = "automatic"
        try:
            summary = subprocess.run(
                [self.kscreen_bin, "-o"],
                capture_output=True,
                text=True,
                timeout=3,
                env=env,
            ).stdout
            for line in summary.splitlines():
                if "Vrr:" in line:
                    vrr_capable = "incapable" not in line.lower()
                    if vrr_capable:
                        vrr_policy = "automatic" if "automatic" in line.lower() else "never"
                if "RgbRange:" in line:
                    if "full" in line.lower():
                        rgb_range = "full"
                    elif "limited" in line.lower():
                        rgb_range = "limited"
                    else:
                        rgb_range = "automatic"
        except Exception:
            pass

        return {
            "output_name": output_name,
            "connected": target.get("connected", True),
            "current_mode_id": current_mode_id,
            "scale": scale,
            "brightness": brightness_pct,
            "modes": modes,
            "vrr_capable": vrr_capable,
            "vrr_policy": vrr_policy,
            "rgb_range": rgb_range,
            "icc_profile": target.get("iccProfilePath", ""),
        }

    def set_mode(self, output_name: str, mode_id: str) -> bool:
        """Sets resolution and refresh rate mode."""
        return self._run_kscreen([f"output.{output_name}.mode.{mode_id}"])

    def set_scale(self, output_name: str, scale: float) -> bool:
        """Sets display scale factor."""
        return self._run_kscreen([f"output.{output_name}.scale.{scale}"])

    def set_brightness(self, output_name: str, percent: int) -> bool:
        """Sets panel brightness (0 - 100)."""
        val = max(0, min(100, percent))
        return self._run_kscreen([f"output.{output_name}.brightness.{val}"])

    def set_rgb_range(self, output_name: str, range_mode: str) -> bool:
        """Sets RGB Range: 'automatic', 'full', 'limited'."""
        if range_mode not in ("automatic", "full", "limited"):
            return False
        return self._run_kscreen([f"output.{output_name}.rgbrange.{range_mode}"])

    def set_vrr_policy(self, output_name: str, policy: str) -> bool:
        """Sets VRR policy: 'never', 'always', 'automatic'."""
        if policy not in ("never", "always", "automatic"):
            return False
        return self._run_kscreen([f"output.{output_name}.vrrpolicy.{policy}"])

    def set_icc_profile(self, output_name: str, icc_path: str) -> bool:
        """Applies a custom ICC profile file."""
        return self._run_kscreen([
            f'output.{output_name}.iccprofile."{icc_path}"',
            f"output.{output_name}.colorProfileSource.ICC",
        ])

    def set_color_profile_source(self, output_name: str, source: str) -> bool:
        """Sets color profile source: 'sRGB', 'EDID', 'ICC'."""
        if source not in ("sRGB", "EDID", "ICC"):
            return False
        return self._run_kscreen([f"output.{output_name}.colorProfileSource.{source}"])

    def _run_kscreen(self, args: List[str]) -> bool:
        if not self.kscreen_bin:
            return False
        try:
            env = os.environ.copy()
            if env.get("QT_QPA_PLATFORM") == "offscreen":
                env.pop("QT_QPA_PLATFORM", None)
            cmd = [self.kscreen_bin] + args
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=5, env=env)
            return res.returncode == 0
        except Exception:
            return False
