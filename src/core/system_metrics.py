"""Hardware metrics collector — system info + per-process metrics.

Uses psutil for CPU/RAM, pynvml (NVIDIA) for GPU utilization,
pywin32 for display info, with fallbacks at every step.
"""

import logging
import re

logger = logging.getLogger(__name__)

# ---- GPU backend detection ----
_GPU_BACKEND = None  # "nvml" | "gputil" | None

try:
    import pynvml
    pynvml.nvmlInit()
    _GPU_BACKEND = "nvml"
    logger.info("GPU backend: NVML (NVIDIA)")
except Exception:
    try:
        import GPUtil
        _GPU_BACKEND = "gputil"
        logger.info("GPU backend: GPUtil (nvidia-smi wrapper)")
    except Exception:
        logger.warning("No GPU backend available — GPU metrics disabled")

import psutil
import win32api
import win32con
try:
    import win32pdh
except Exception:
    win32pdh = None
import platform

# Logical CPU count; process cpu_percent() is per-core, so divide by this to
# match Task Manager's total-share CPU% and to derive "cores used".
LOGICAL_CORES = psutil.cpu_count(logical=True) or 1


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def gpu_available() -> bool:
    """Whether GPU utilization monitoring is available."""
    return _GPU_BACKEND is not None


def get_system_info() -> dict[str, object]:
    """Gather hardware info: CPU, GPU, RAM, display, refresh rate.
    Returns a dict suitable for SystemInfo construction.
    """
    vram = {}
    if _GPU_BACKEND == "nvml":
        vram = _get_gpu_memory_info_nvml()
    elif _GPU_BACKEND == "gputil":
        vram = _get_gpu_memory_info_gputil()
    display_outputs = _get_display_outputs()
    primary_resolution, primary_refresh = _get_primary_display(display_outputs)
    return {
        "cpu_name": _get_cpu_name(),
        "gpu_name": _get_gpu_name(),
        "ram_total_gb": round(psutil.virtual_memory().total / (1024**3), 1),
        "display_resolution": primary_resolution,
        "display_refresh_hz": primary_refresh,
        "display_outputs": [d["label"] for d in display_outputs],
        "vram_total_gb": round(vram.get("vram_total_mb", 0) / 1024, 1),
    }


def _get_gpu_memory_info_nvml() -> dict[str, float]:
    """Return VRAM info from NVML. Returns zeros if unavailable."""
    result = {"vram_total_mb": 0.0, "vram_used_mb": 0.0, "vram_percent": 0.0}
    if _GPU_BACKEND != "nvml":
        return result
    try:
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
        result["vram_total_mb"] = round(mem.total / (1024 ** 2), 1)
        result["vram_used_mb"] = round(mem.used / (1024 ** 2), 1)
        result["vram_percent"] = round((mem.used / mem.total) * 100, 1) if mem.total > 0 else 0.0
    except Exception:
        pass
    return result


def _get_gpu_memory_info_gputil() -> dict[str, float]:
    """Return VRAM info from GPUtil. Returns zeros if unavailable."""
    result = {"vram_total_mb": 0.0, "vram_used_mb": 0.0, "vram_percent": 0.0}
    try:
        gpus = GPUtil.getGPUs()
        if gpus:
            g = gpus[0]
            result["vram_total_mb"] = round(g.memoryTotal, 1)
            result["vram_used_mb"] = round(g.memoryUsed, 1)
            result["vram_percent"] = round(g.memoryUtil * 100, 1)
    except Exception:
        pass
    return result


def sample_process_gpu(pid: int) -> dict[str, float]:
    """Sample per-process GPU utilization via NVML.

    Returns dict with keys: app_gpu_percent, vram_mb.
    - app_gpu_percent: -1.0 when NVML doesn't report the process (→ None upstream).
    - vram_mb: None when unavailable; a real value only when NVML lists the process.
      NOTE: NVML per-process VRAM (nvmlDeviceGetGraphicsRunningProcesses) is
      unreliable/empty under Windows WDDP — the sampler uses
      sample_all_process_vram_mb() (Windows GPU perf counter) instead.
    """
    result = {"app_gpu_percent": -1.0, "vram_mb": None}
    if _GPU_BACKEND != "nvml":
        return result
    try:
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)

        # Per-process SM utilization
        try:
            procs_util = pynvml.nvmlDeviceGetProcessUtilization(handle, 0)
            for p in procs_util:
                if p.pid == pid:
                    result["app_gpu_percent"] = round(float(p.smUtil), 1)
                    break
        except Exception:
            pass

        # Per-process VRAM
        try:
            for fn in (pynvml.nvmlDeviceGetGraphicsRunningProcesses,
                        pynvml.nvmlDeviceGetComputeRunningProcesses):
                try:
                    running = fn(handle)
                    for p in running:
                        if p.pid == pid:
                            used = getattr(p, "usedGpuMemory", 0) or 0
                            result["vram_mb"] = round(used / (1024 ** 2), 1)
                            break
                except Exception:
                    pass
        except Exception:
            pass
    except Exception:
        pass
    return result


_PID_RE = re.compile(r"pid_(\d+)")


def sample_all_process_vram_mb() -> dict[int, float]:
    """Per-process resident VRAM (MB) via the Windows 'GPU Process Memory\\Local
    Usage' performance counter — the same source Task Manager uses. Works under
    WDDP, where NVML's GetGraphicsRunningProcesses returns nothing.

    Uses **Local Usage** (memory resident in adapter memory), NOT Dedicated Usage:
    the latter counts committed address space and over-reports wildly (a process
    can show >10x the card's physical VRAM). Local Usage is bounded by card
    capacity and matches "VRAM actually in use".

    Returns {pid: local_mb} summed across all GPU adapter instances for each PID.
    Empty dict if win32pdh or the counter is unavailable (→ callers treat
    per-process VRAM as NA).
    """
    if win32pdh is None:
        return {}
    try:
        q = win32pdh.OpenQuery()
        try:
            h = win32pdh.AddCounter(q, r"\GPU Process Memory(*)\Local Usage")
            win32pdh.CollectQueryData(q)
            arr = win32pdh.GetFormattedCounterArray(h, win32pdh.PDH_FMT_DOUBLE)
        finally:
            win32pdh.CloseQuery(q)
    except Exception:
        logger.debug("GPU Process Memory perf counter read failed", exc_info=True)
        return {}
    # Instance names look like "pid_23864_luid_0x.._phys_0"; sum per PID.
    totals: dict[int, float] = {}
    for inst, val in arr.items():
        m = _PID_RE.search(inst)
        if m:
            pid = int(m.group(1))
            totals[pid] = totals.get(pid, 0.0) + float(val)
    return {pid: round(b / 1048576.0, 1) for pid, b in totals.items()}


def process_memory_mb(proc) -> float | None:
    """Memory (MB) matching Task Manager's default "Memory" column.

    Prefers USS (private working set via memory_full_info); falls back to
    RSS (working set via memory_info) when full info is unavailable.
    """
    try:
        full = proc.memory_full_info()
        uss = getattr(full, "uss", None)
        if uss is not None:
            return round(uss / (1024 ** 2), 1)
    except Exception:
        pass
    try:
        return round(proc.memory_info().rss / (1024 ** 2), 1)
    except Exception:
        return None


def sample_process(pid: int) -> dict[str, float]:
    """Sample memory and CPU for a process by PID.

    Returns dict with keys: memory_mb, cpu_percent.
    The first call for a new PID returns cpu_percent=0.0 (psutil needs
    two samples to compute a delta). Subsequent calls return valid values.
    """
    result = {"memory_mb": 0.0, "cpu_percent": 0.0}
    try:
        proc = psutil.Process(pid)
        mem = process_memory_mb(proc)
        if mem is not None:
            result["memory_mb"] = mem
        result["cpu_percent"] = round(proc.cpu_percent() / LOGICAL_CORES, 1)
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass
    return result


def sample_system() -> dict[str, object]:
    """Sample total CPU%, per-core CPU%, GPU%, GPU power/temp, and RAM usage.

    Returns dict with keys: total_cpu_percent (aggregate = mean of per-core),
    per_core_cpu_percent (list, one % per logical core), total_gpu_percent
    (-1 if N/A), total_ram_used_gb, vram_*, gpu_power_w, gpu_temp_c,
    gpu_power_limit_w.

    Note: per-core and GPU power/temp are snapshot-only — they are NOT stamped
    onto FrameData or exported to CSV (see ``SystemSnapshot``).
    """
    per_core = psutil.cpu_percent(interval=None, percpu=True)
    # Aggregate total = mean of per-core (psutil's cpu_percent() is the same
    # average); deriving here avoids a second psutil call with a divergent window.
    if per_core:
        total_cpu = sum(per_core) / len(per_core)
    else:
        total_cpu = 0.0

    total_gpu = -1.0
    if _GPU_BACKEND == "nvml":
        total_gpu = _get_gpu_usage_nvml()
    elif _GPU_BACKEND == "gputil":
        total_gpu = _get_gpu_usage_gputil()

    ram = psutil.virtual_memory()
    ram_used_gb = round(ram.used / (1024**3), 2)

    vram = {}
    if _GPU_BACKEND == "nvml":
        vram = _get_gpu_memory_info_nvml()
    elif _GPU_BACKEND == "gputil":
        vram = _get_gpu_memory_info_gputil()

    gpu_pt = _get_gpu_power_temp_nvml() if _GPU_BACKEND == "nvml" else {}

    return {
        "total_cpu_percent": total_cpu,
        "per_core_cpu_percent": [round(x, 1) for x in per_core],
        "total_gpu_percent": round(total_gpu, 1) if total_gpu >= 0 else -1.0,
        "total_ram_used_gb": ram_used_gb,
        "vram_total_mb": vram.get("vram_total_mb", 0.0),
        "vram_used_mb": vram.get("vram_used_mb", 0.0),
        "vram_percent": vram.get("vram_percent", 0.0),
        "gpu_power_w": gpu_pt.get("gpu_power_w"),
        "gpu_temp_c": gpu_pt.get("gpu_temp_c"),
        "gpu_power_limit_w": gpu_pt.get("gpu_power_limit_w"),
    }


def get_running_process_names() -> list[str]:
    """Return sorted list of unique .exe names currently running."""
    seen: set[str] = set()
    for proc in psutil.process_iter(["name"]):
        try:
            name = proc.info["name"]
            if name and name.lower().endswith(".exe") and name not in seen:
                seen.add(name)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return sorted(seen)


def find_pids_by_name(name: str) -> list[int]:
    """Find all PIDs for a given process name (case-insensitive)."""
    pids: list[int] = []
    name_lower = name.lower()
    for proc in psutil.process_iter(["pid", "name"]):
        try:
            if proc.info["name"] and proc.info["name"].lower() == name_lower:
                pids.append(proc.info["pid"])
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return pids


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_cpu_name() -> str:
    """Return CPU model name."""
    try:
        import subprocess
        result = subprocess.run(
            ["wmic", "cpu", "get", "name"],
            capture_output=True, text=True, timeout=5
        )
        lines = [l.strip() for l in result.stdout.splitlines() if l.strip() and l.strip() != "Name"]
        if lines:
            return lines[0]
    except Exception:
        pass
    return platform.processor() or "Unknown CPU"


def _get_gpu_name() -> str:
    """Return GPU name via NVML or fallback."""
    if _GPU_BACKEND == "nvml":
        try:
            handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            name = pynvml.nvmlDeviceGetName(handle)
            if isinstance(name, bytes):
                name = name.decode("utf-8")
            return name
        except Exception:
            pass
    if _GPU_BACKEND == "gputil":
        try:
            gpus = GPUtil.getGPUs()
            if gpus:
                return gpus[0].name
        except Exception:
            pass
    # Fallback: WMI
    try:
        import subprocess
        result = subprocess.run(
            ["wmic", "path", "Win32_VideoController", "get", "name"],
            capture_output=True, text=True, timeout=5
        )
        lines = [l.strip() for l in result.stdout.splitlines() if l.strip() and l.strip() != "Name"]
        if lines:
            return lines[0]
    except Exception:
        pass
    return "Unknown GPU"


def _get_display_outputs() -> list[dict[str, object]]:
    """Return attached desktop displays, primary first.

    Each item contains a stable label like ``3840x2160@59Hz`` plus metadata
    used only for sorting. Falls back to the legacy primary display query.
    """
    outputs: list[dict[str, object]] = []
    try:
        for index in range(32):
            try:
                device = win32api.EnumDisplayDevices(None, index, 0)
            except Exception:
                break

            flags = int(device.StateFlags)
            if not (flags & win32con.DISPLAY_DEVICE_ATTACHED_TO_DESKTOP):
                continue

            settings = win32api.EnumDisplaySettings(
                device.DeviceName, win32con.ENUM_CURRENT_SETTINGS)
            refresh = int(getattr(settings, "DisplayFrequency", 0) or 0)
            width = int(getattr(settings, "PelsWidth", 0) or 0)
            height = int(getattr(settings, "PelsHeight", 0) or 0)
            if width <= 0 or height <= 0:
                continue
            x = int(getattr(settings, "Position_x", 0) or 0)
            y = int(getattr(settings, "Position_y", 0) or 0)
            outputs.append({
                "label": f"{width}x{height}@{refresh}Hz",
                "resolution": f"{width}x{height}",
                "refresh_hz": refresh,
                "primary": bool(flags & win32con.DISPLAY_DEVICE_PRIMARY_DEVICE),
                "x": x,
                "y": y,
                "index": index,
            })
    except Exception:
        outputs = []

    if not outputs:
        settings = _get_primary_display_settings()
        if settings is None:
            return [{
                "label": "Unknown",
                "resolution": "Unknown",
                "refresh_hz": 0,
                "primary": True,
                "x": 0,
                "y": 0,
                "index": 0,
            }]
        refresh = int(getattr(settings, "DisplayFrequency", 0) or 0)
        width = int(getattr(settings, "PelsWidth", 0) or 0)
        height = int(getattr(settings, "PelsHeight", 0) or 0)
        return [{
            "label": f"{width}x{height}@{refresh}Hz",
            "resolution": f"{width}x{height}",
            "refresh_hz": refresh,
            "primary": True,
            "x": 0,
            "y": 0,
            "index": 0,
        }]

    return sorted(outputs, key=lambda d: (
        0 if d["primary"] else 1,
        int(d["x"]),
        int(d["y"]),
        int(d["index"]),
    ))


def _get_primary_display(outputs: list[dict[str, object]]) -> tuple[str, int]:
    """Return legacy primary resolution / refresh fields from display outputs."""
    if not outputs:
        return "Unknown", 0
    primary = outputs[0]
    return str(primary["resolution"]), int(primary["refresh_hz"])


def _get_primary_display_settings():
    """Return primary monitor settings or None."""
    try:
        return win32api.EnumDisplaySettings(None, win32con.ENUM_CURRENT_SETTINGS)
    except Exception:
        return None


def _get_gpu_usage_nvml() -> float:
    """Return total GPU utilization % from NVML (first GPU)."""
    try:
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        util = pynvml.nvmlDeviceGetUtilizationRates(handle)
        return float(util.gpu)
    except Exception:
        return -1.0


def _get_gpu_power_temp_nvml() -> dict[str, float | None]:
    """Return GPU power draw (W), temperature (°C), and power limit (W).

    Each value is None when the NVML call fails — some GPUs / older drivers
    don't expose power or temperature. Power values come back in milliwatts,
    so divide by 1000.
    """
    result: dict[str, float | None] = {
        "gpu_power_w": None,
        "gpu_temp_c": None,
        "gpu_power_limit_w": None,
    }
    if _GPU_BACKEND != "nvml":
        return result
    try:
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        try:
            result["gpu_power_w"] = round(
                pynvml.nvmlDeviceGetPowerUsage(handle) / 1000.0, 1)
        except Exception:
            pass
        try:
            result["gpu_temp_c"] = float(
                pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU))
        except Exception:
            pass
        try:
            result["gpu_power_limit_w"] = round(
                pynvml.nvmlDeviceGetPowerManagementLimit(handle) / 1000.0, 1)
        except Exception:
            pass
    except Exception:
        pass
    return result


def _get_gpu_usage_gputil() -> float:
    """Return total GPU utilization % from GPUtil (first GPU)."""
    try:
        gpus = GPUtil.getGPUs()
        if gpus:
            return gpus[0].load * 100.0
    except Exception:
        pass
    return -1.0
