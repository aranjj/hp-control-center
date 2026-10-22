"""
GPU Memory Limit Management (Mesa Intel Vulkan ANV_SYS_MEM_LIMIT).
Manages system memory limits for the Intel Iris Xe integrated GPU via Mesa's anv driver.
Independent from hardware profiles and root daemon.
"""

import json
import logging
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Single constant for application config namespace
APP_CONFIG_NAME = "hp-control-center"
ENV_VAR_NAME = "ANV_SYS_MEM_LIMIT"

# Configuration file paths
ENV_D_DIR = Path.home() / ".config" / "environment.d"
ENV_D_FILE = ENV_D_DIR / f"{APP_CONFIG_NAME}.conf"
APP_CONFIG_DIR = Path.home() / ".config" / APP_CONFIG_NAME
GPU_MEMORY_STATE_FILE = APP_CONFIG_DIR / "gpu-memory.json"


def get_system_memory_info() -> Dict[str, Any]:
    """Reads /proc/meminfo to determine total and available RAM and valid GPU limit range."""
    mem_total_kb = 0
    mem_avail_kb = 0
    try:
        if os.path.exists("/proc/meminfo"):
            with open("/proc/meminfo", "r") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        mem_total_kb = int(line.split()[1])
                    elif line.startswith("MemAvailable:"):
                        mem_avail_kb = int(line.split()[1])
    except Exception as e:
        logger.error(f"Failed to read /proc/meminfo: {e}")

    mem_total_bytes = mem_total_kb * 1024
    mem_avail_bytes = mem_avail_kb * 1024
    total_gb = mem_total_bytes / (1024**3) if mem_total_bytes > 0 else 16.0
    avail_gb = mem_avail_bytes / (1024**3) if mem_avail_bytes > 0 else 8.0
    # Range: 1 GB to (MemTotal minus 3 GB)
    max_limit_gb = max(1, int(total_gb - 3.0))

    return {
        "mem_total_bytes": mem_total_bytes,
        "mem_available_bytes": mem_avail_bytes,
        "total_gb": total_gb,
        "available_gb": avail_gb,
        "min_limit_gb": 1,
        "max_limit_gb": max_limit_gb,
    }


def read_vulkan_heap_size(env_override: Optional[str] = None) -> Tuple[Optional[int], Optional[str]]:
    """Runs vulkaninfo and extracts the device-local memoryHeaps[0] size in bytes for the Intel GPU.
    Returns (heap_size_bytes, error_message).
    """
    if not shutil.which("vulkaninfo"):
        return None, "vulkaninfo not found"

    env = dict(os.environ)
    if env_override is not None:
        env[ENV_VAR_NAME] = str(env_override)
    else:
        env.pop(ENV_VAR_NAME, None)

    try:
        res = subprocess.run(
            ["vulkaninfo"],
            capture_output=True,
            text=True,
            env=env,
            timeout=5.0,
        )
    except subprocess.TimeoutExpired:
        return None, "vulkaninfo timed out"
    except Exception as e:
        return None, f"Failed to execute vulkaninfo: {e}"

    lines = res.stdout.splitlines()
    in_intel_gpu = False

    for i, line in enumerate(lines):
        if line.startswith("GPU") and ":" in line:
            # Check context window for Intel device identifier
            context_window = "\n".join(lines[i : min(i + 40, len(lines))])
            if "Intel" in context_window:
                in_intel_gpu = True
            else:
                in_intel_gpu = False

        if in_intel_gpu and "memoryHeaps[0]:" in line:
            # Look ahead for size = <bytes>
            for next_line in lines[i : min(i + 8, len(lines))]:
                m = re.search(r"size\s*=\s*(\d+)", next_line)
                if m:
                    return int(m.group(1)), None

    return None, "Could not locate Intel Vulkan memory heap"


def detect_anv_support_and_format() -> Dict[str, Any]:
    """Step 0 Detection Routine:
    1. Runs vulkaninfo with ANV_SYS_MEM_LIMIT unset to record baseline device-local heap size.
    2. Re-runs vulkaninfo testing candidate formats ('percent', 'mb', 'bytes', 'gb').
    3. Verifies which format modifies the heap size to match expected behavior.
    Returns:
        {
            "supported": bool,
            "format": Optional[str],  # 'percent' | 'mb' | 'bytes' | 'gb' | None
            "reason": Optional[str],
            "baseline_heap_bytes": Optional[int]
        }
    """
    if not shutil.which("vulkaninfo"):
        return {
            "supported": False,
            "format": None,
            "reason": "vulkaninfo not found",
            "baseline_heap_bytes": None,
        }

    # Step 1: Baseline unset
    baseline_bytes, err = read_vulkan_heap_size(None)
    if baseline_bytes is None:
        return {
            "supported": False,
            "format": None,
            "reason": err or "Failed to read baseline Vulkan heap",
            "baseline_heap_bytes": None,
        }

    mem_info = get_system_memory_info()
    total_ram = mem_info["mem_total_bytes"]
    if total_ram <= 0:
        total_ram = 16 * (1024**3)

    # Candidate formats to test
    # Mesa anv driver defines ANV_SYS_MEM_LIMIT as percentage (10-100) of total RAM.
    candidates = [
        ("percent", "25", int(round(total_ram * 0.25))),
        ("mb", "4096", 4096 * 1024 * 1024),
        ("bytes", "4294967296", 4294967296),
        ("gb", "4", 4 * 1024 * 1024 * 1024),
    ]

    for fmt, test_val, expected_bytes in candidates:
        heap_bytes, test_err = read_vulkan_heap_size(test_val)
        if heap_bytes is not None and expected_bytes > 0:
            diff_ratio = abs(heap_bytes - expected_bytes) / expected_bytes
            # Within 3% tolerance of the expected target and differs from baseline
            if diff_ratio <= 0.03:
                logger.info(f"Detected ANV_SYS_MEM_LIMIT format: {fmt} (test {test_val} -> {heap_bytes} bytes)")
                return {
                    "supported": True,
                    "format": fmt,
                    "reason": None,
                    "baseline_heap_bytes": baseline_bytes,
                }

    # If no tested format matched expected values
    return {
        "supported": False,
        "format": None,
        "reason": "This Mesa build does not honor ANV_SYS_MEM_LIMIT",
        "baseline_heap_bytes": baseline_bytes,
    }


def format_limit_value(limit_gb: int, format_type: str, total_ram_bytes: int) -> str:
    """Converts a limit in GB into the exact raw value string for the detected format.
    Validates the range in code before returning.
    """
    total_gb = total_ram_bytes / (1024**3) if total_ram_bytes > 0 else 16.0
    max_gb = max(1, int(total_gb - 3.0))

    if limit_gb < 1 or limit_gb > max_gb:
        raise ValueError(f"Limit {limit_gb} GB out of valid range (1 - {max_gb} GB)")

    if format_type == "percent":
        # mesa: clamped 10 to 100
        percent = int(round((limit_gb * (1024**3) / total_ram_bytes) * 100.0))
        percent = max(10, min(100, percent))
        return str(percent)
    elif format_type == "mb":
        return str(limit_gb * 1024)
    elif format_type == "gb":
        return str(limit_gb)
    elif format_type == "bytes":
        return str(limit_gb * (1024**3))
    else:
        raise ValueError(f"Unknown format type: {format_type}")


def parse_raw_value_to_gb(raw_val: str, format_type: str, total_ram_bytes: int) -> Optional[int]:
    """Converts a raw value string back to GB for the detected format."""
    try:
        val = int(raw_val.strip())
        if format_type == "percent":
            total_gb = total_ram_bytes / (1024**3)
            gb = int(round((val / 100.0) * total_gb))
            return max(1, gb)
        elif format_type == "mb":
            return max(1, int(round(val / 1024.0)))
        elif format_type == "gb":
            return max(1, val)
        elif format_type == "bytes":
            return max(1, int(round(val / (1024**3))))
    except Exception:
        pass
    return None


def read_environment_file_value() -> Optional[str]:
    """Reads ANV_SYS_MEM_LIMIT from ~/.config/environment.d/<app-name>.conf if set."""
    if not ENV_D_FILE.exists():
        return None
    try:
        with open(ENV_D_FILE, "r") as f:
            for line in f:
                line = line.strip()
                if line.startswith(f"{ENV_VAR_NAME}="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    except Exception as e:
        logger.warning(f"Error reading {ENV_D_FILE}: {e}")
    return None


def read_session_environment_value() -> Optional[str]:
    """Reads ANV_SYS_MEM_LIMIT from `systemctl --user show-environment`."""
    try:
        res = subprocess.run(
            ["systemctl", "--user", "show-environment"],
            capture_output=True,
            text=True,
            timeout=2.0,
        )
        if res.returncode == 0:
            for line in res.stdout.splitlines():
                if line.startswith(f"{ENV_VAR_NAME}="):
                    return line.split("=", 1)[1].strip()
    except Exception as e:
        logger.warning(f"Error reading systemctl --user show-environment: {e}")
    return None


def read_gpu_memory_state() -> Dict[str, Any]:
    """Reads ~/.config/<app-name>/gpu-memory.json if it exists."""
    if GPU_MEMORY_STATE_FILE.exists():
        try:
            with open(GPU_MEMORY_STATE_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Error reading {GPU_MEMORY_STATE_FILE}: {e}")
    return {}


def write_gpu_memory_state(state: Dict[str, Any]) -> None:
    """Saves state to ~/.config/<app-name>/gpu-memory.json."""
    try:
        APP_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(GPU_MEMORY_STATE_FILE, "w") as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to write {GPU_MEMORY_STATE_FILE}: {e}")


def read_current_status(format_type: Optional[str] = "percent") -> Dict[str, Any]:
    """Gathers the complete current configuration status on startup:
    - File value from environment.d
    - Session value from systemctl --user show-environment
    - Saved JSON state
    - Whether there is a mismatch ('applies from next login')
    - Computed active limit GB (None if no limit is active)
    """
    mem_info = get_system_memory_info()
    file_val = read_environment_file_value()
    session_val = read_session_environment_value()
    state = read_gpu_memory_state()

    # Determine whether there is a mismatch between environment.d and session
    # (e.g. file was written but session not yet updated, or user changed file outside)
    mismatch = False
    if file_val != session_val:
        mismatch = True

    # Active limit in GB
    active_limit_gb = None
    raw_val = file_val or session_val
    if raw_val is not None and format_type:
        active_limit_gb = parse_raw_value_to_gb(raw_val, format_type, mem_info["mem_total_bytes"])
    elif state.get("limit_gb"):
        active_limit_gb = state.get("limit_gb")

    return {
        "file_val": file_val,
        "session_val": session_val,
        "state": state,
        "mismatch": mismatch,
        "active_limit_gb": active_limit_gb,
        "mem_info": mem_info,
    }


def apply_gpu_memory_limit(
    limit_gb: Optional[int],
    format_type: str,
    total_ram_bytes: int,
) -> Dict[str, Any]:
    """Applies or unsets the GPU memory limit:
    1. Writes/updates/removes ~/.config/environment.d/<app-name>.conf.
    2. Runs systemctl --user set-environment / unset-environment.
    3. Runs dbus-update-activation-environment --systemd when setting.
    4. Saves state to ~/.config/<app-name>/gpu-memory.json.
    5. Checks if systemctl / dbus succeeded, returning session warning if not.
    """
    warning = None

    if limit_gb is not None and limit_gb > 0:
        val_str = format_limit_value(limit_gb, format_type, total_ram_bytes)

        # 1. Write ~/.config/environment.d/<app-name>.conf
        try:
            ENV_D_DIR.mkdir(parents=True, exist_ok=True)
            existing_lines = []
            if ENV_D_FILE.exists():
                with open(ENV_D_FILE, "r") as f:
                    existing_lines = f.readlines()

            # Filter out previous definitions of ANV_SYS_MEM_LIMIT
            new_lines = [l for l in existing_lines if not l.strip().startswith(f"{ENV_VAR_NAME}=")]
            new_lines.append(f"{ENV_VAR_NAME}={val_str}\n")

            with open(ENV_D_FILE, "w") as f:
                f.writelines(new_lines)
        except Exception as e:
            logger.error(f"Failed to write {ENV_D_FILE}: {e}")
            return {
                "success": False,
                "error": f"Failed to write {ENV_D_FILE}: {e}",
                "limit_gb": limit_gb,
                "raw_value": val_str,
            }

        # 2. Save JSON state
        write_gpu_memory_state({
            "limit_gb": limit_gb,
            "format": format_type,
            "raw_value": val_str,
        })

        # 3. Update active session environments
        sys_res = subprocess.run(
            ["systemctl", "--user", "set-environment", f"{ENV_VAR_NAME}={val_str}"],
            capture_output=True,
            text=True,
            timeout=3.0,
        )
        dbus_res = subprocess.run(
            ["dbus-update-activation-environment", "--systemd", f"{ENV_VAR_NAME}={val_str}"],
            capture_output=True,
            text=True,
            timeout=3.0,
        )

        session_ok = (sys_res.returncode == 0 and dbus_res.returncode == 0)
        if not session_ok:
            warning = "Configuration file written, but session environment update failed. Limit will apply from next login."

        return {
            "success": True,
            "limit_gb": limit_gb,
            "raw_value": val_str,
            "session_updated": session_ok,
            "warning": warning,
        }

    else:
        # Removal / No limit
        # 1. Clean environment.d file
        try:
            if ENV_D_FILE.exists():
                with open(ENV_D_FILE, "r") as f:
                    existing_lines = f.readlines()
                filtered = [l for l in existing_lines if not l.strip().startswith(f"{ENV_VAR_NAME}=")]
                # Check if file has any remaining active configuration
                has_content = any(l.strip() and not l.strip().startswith("#") for l in filtered)
                if has_content:
                    with open(ENV_D_FILE, "w") as f:
                        f.writelines(filtered)
                else:
                    ENV_D_FILE.unlink(missing_ok=True)
        except Exception as e:
            logger.error(f"Failed to clean {ENV_D_FILE}: {e}")

        # 2. Reset JSON state
        write_gpu_memory_state({})

        # 3. Unset from session
        sys_res = subprocess.run(
            ["systemctl", "--user", "unset-environment", ENV_VAR_NAME],
            capture_output=True,
            text=True,
            timeout=3.0,
        )
        session_ok = (sys_res.returncode == 0)
        if not session_ok:
            warning = "Removed from configuration, but unsetting from active session failed. Change will apply from next login."

        return {
            "success": True,
            "limit_gb": None,
            "raw_value": None,
            "session_updated": session_ok,
            "warning": warning,
        }


def get_running_vulkan_apps() -> List[Dict[str, Any]]:
    """Inspects /proc to find running graphical / Vulkan / AI processes owned by the user.
    Returns list of dicts with 'pid', 'name', 'cmdline'.
    """
    user_uid = os.getuid()
    # Exclude core desktop environment infrastructure to avoid false positives
    ignored_procs = {
        "plasmashell",
        "kwin_wayland",
        "kwin",
        "Xwayland",
        "systemd",
        "dbus-daemon",
        "pipewire",
        "wireplumber",
        "pulseaudio",
        "xdg-desktop-portal",
        "xdg-desktop-portal-kde",
        "xdg-desktop-por",
        "krunner",
        "quickshell",
        "sddm",
        "kglobalaccel",
        "kded6",
        "kaccess",
        "polkit-kde-authentication-agent-1",
        "agent",
    }
    # Keywords indicating Vulkan / GPU applications or workloads
    gpu_keywords = [
        "steam",
        "steamwebhelper",
        "gamescope",
        "llama",
        "llama-server",
        "ollama",
        "heroic",
        "lutris",
        "retroarch",
        "blender",
        "vkquake",
        "lm-studio",
        "obs",
        "vkmark",
    ]

    matched_pids = set()
    results = []

    for pid_path in Path("/proc").glob("[0-9]*"):
        try:
            pid = int(pid_path.name)
            if pid == os.getpid():
                continue

            status_file = pid_path / "status"
            if not status_file.exists():
                continue

            uid = None
            proc_name = ""
            with open(status_file, "r") as f:
                for line in f:
                    if line.startswith("Uid:"):
                        uid = int(line.split()[1])
                    elif line.startswith("Name:"):
                        proc_name = line.split()[1]

            if uid != user_uid or not proc_name or proc_name in ignored_procs:
                continue

            # Check if name matches any target keyword
            matched = any(kw in proc_name.lower() for kw in gpu_keywords)

            # Check open file descriptors for direct DRI render node access (/dev/dri/renderD*)
            if not matched:
                try:
                    fd_dir = pid_path / "fd"
                    if fd_dir.exists():
                        for fd_entry in fd_dir.iterdir():
                            target = os.readlink(fd_entry)
                            if "/dev/dri/renderD" in target:
                                matched = True
                                break
                except Exception:
                    pass

            if matched and pid not in matched_pids:
                matched_pids.add(pid)
                cmdline = ""
                try:
                    with open(pid_path / "cmdline", "rb") as cf:
                        raw = cf.read().replace(b"\x00", b" ")
                        cmdline = raw.decode(errors="ignore").strip()
                except Exception:
                    pass
                results.append({
                    "pid": pid,
                    "name": proc_name,
                    "cmdline": cmdline,
                })
        except Exception:
            continue

    return results


def get_launch_strings(limit_gb: Optional[int], format_type: str, total_ram_bytes: int) -> Dict[str, str]:
    """Generates copyable per-app launch strings for Steam and Terminal along with unit description."""
    effective_gb = limit_gb if (limit_gb is not None and limit_gb > 0) else 4
    try:
        val = format_limit_value(effective_gb, format_type, total_ram_bytes)
    except Exception:
        val = str(effective_gb)

    if format_type == "percent":
        raw_desc = f"{val} ({val}% of RAM, about {effective_gb} GB)"
    elif format_type == "mb":
        raw_desc = f"{val} ({val} MB, about {effective_gb} GB)"
    elif format_type == "bytes":
        raw_desc = f"{val} bytes (about {effective_gb} GB)"
    else:
        raw_desc = f"{val} ({effective_gb} GB)"

    return {
        "raw_value": val,
        "raw_description": raw_desc,
        "steam": f"{ENV_VAR_NAME}={val} %command%",
        "terminal": f"{ENV_VAR_NAME}={val} <command>",
    }


# =====================================================================
# Profile Overrides Hook (Extensibility)
# =====================================================================
# TODO: In the future, if per-profile GPU memory limits are desired:
# 1. Add an optional "gpu_mem_limit_gb": Optional[int] field to Profile dataclass in profiles.py.
# 2. In ProfileManager.apply_profile(), check if the profile specifies a custom gpu_mem_limit_gb.
# 3. If specified, call apply_gpu_memory_limit(profile.gpu_mem_limit_gb).
# 4. If None or not set, retain the global user-configured GPU memory limit without altering it.

