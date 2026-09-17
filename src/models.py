"""Data models for PresentMon metrics and system monitoring."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class FrameData:
    """A single frame captured by PresentMon (v2 metrics), enriched with system metrics."""

    # --- PresentMon identity fields ---
    application: str = ""
    process_id: int = 0
    swap_chain_address: str = ""
    present_runtime: str = ""
    sync_interval: int = 0
    present_flags: str = ""
    allows_tearing: int = 0
    present_mode: str = ""
    frame_type: str = ""

    # --- PresentMon timing fields (all ms) ---
    cpu_start_time: float = 0.0
    ms_cpu_busy: Optional[float] = None
    ms_cpu_wait: Optional[float] = None
    ms_gpu_latency: Optional[float] = None
    ms_gpu_time: Optional[float] = None
    ms_gpu_busy: Optional[float] = None
    ms_gpu_wait: Optional[float] = None
    video_busy: Optional[float] = None
    display_latency: Optional[float] = None
    displayed_time: Optional[float] = None
    ms_animation_error: Optional[float] = None
    animation_time: Optional[float] = None
    ms_click_to_photon_latency: Optional[float] = None
    ms_all_input_to_photon_latency: Optional[float] = None
    ms_between_presents: Optional[float] = None
    ms_in_present_api: Optional[float] = None
    ms_until_displayed: Optional[float] = None
    ms_render_present_latency: Optional[float] = None
    ms_between_display_change: Optional[float] = None
    ms_between_simulation_start: Optional[float] = None
    ms_pc_latency: Optional[float] = None
    ms_between_app_start: Optional[float] = None
    dropped: int = 0
    time_in_seconds: float = 0.0

    # --- Enriched: per-process system metrics (None = not yet sampled) ---
    app_memory_mb: Optional[float] = None
    app_cpu_percent: Optional[float] = None
    app_cpu_cores: Optional[float] = None   # cores used = raw per-core cpu% / 100

    # --- Enriched: per-process GPU utilization ---
    app_gpu_percent: Optional[float] = None
    app_vram_mb: Optional[float] = None     # per-process VRAM (NVML usedGpuMemory)

    # --- Enriched: system-wide metrics (sampled by SystemMetricsSampler) ---
    total_cpu_percent: Optional[float] = None
    total_gpu_percent: Optional[float] = None
    total_ram_used_gb: Optional[float] = None

    # --- Enriched: VRAM (system-wide) ---
    gpu_vram_total_mb: Optional[float] = None
    gpu_vram_used_mb: Optional[float] = None
    gpu_vram_percent: Optional[float] = None

    # --- Derived (None = could not be computed, e.g. no ms_between_presents) ---
    fps: Optional[float] = None

    @classmethod
    def field_names_v2(cls) -> list[str]:
        """Return expected CSV column names for v2 metrics."""
        return [
            "Application", "ProcessID", "SwapChainAddress",
            "PresentRuntime", "SyncInterval", "PresentFlags",
            "AllowsTearing", "PresentMode", "FrameType",
            "CPUStartTime",
            "MsCPUBusy", "MsCPUWait",
            "MsGPULatency", "MsGPUTime", "MsGPUBusy", "MsGPUWait",
            "VideoBusy", "DisplayLatency", "DisplayedTime",
            "MsAnimationError", "AnimationTime",
            "MsClickToPhotonLatency", "MsAllInputToPhotonLatency",
            "MsBetweenPresents", "MsInPresentAPI",
            "MsBetweenDisplayChange", "MsUntilDisplayed",
            "MsRenderPresentLatency",
            "MsBetweenSimulationStart",
            "MsPCLatency", "MsBetweenAppStart",
        ]


@dataclass
class SystemInfo:
    """Hardware system information gathered at session start."""
    cpu_name: str = ""
    gpu_name: str = ""
    ram_total_gb: float = 0.0
    display_resolution: str = ""
    display_refresh_hz: int = 0
    display_outputs: list[str] = field(default_factory=list)
    vram_total_gb: float = 0.0


@dataclass
class SystemSnapshot:
    """System-wide metrics at a point in time."""
    timestamp: float = 0.0       # seconds since session start
    total_cpu_percent: Optional[float] = None
    total_gpu_percent: Optional[float] = None
    total_ram_used_gb: Optional[float] = None
    vram_total_mb: Optional[float] = None
    vram_used_mb: Optional[float] = None
    vram_percent: Optional[float] = None
    # Snapshot-only metrics — NOT enriched onto FrameData, NOT exported to CSV.
    per_core_cpu_percent: Optional[list[float]] = None
    gpu_power_w: Optional[float] = None
    gpu_temp_c: Optional[float] = None
    gpu_power_limit_w: Optional[float] = None


@dataclass
class PerProcessSnapshot:
    """Per-process metrics at a point in time."""
    timestamp: float = 0.0
    process_name: str = ""
    process_id: int = 0
    memory_mb: Optional[float] = None
    cpu_percent: Optional[float] = None
    cpu_cores: Optional[float] = None
    gpu_percent: Optional[float] = None
    vram_mb: Optional[float] = None


@dataclass
class ProcessStats:
    """Aggregated statistics for a monitored process."""
    process_name: str = ""
    process_id: int = 0
    frame_count: int = 0
    avg_fps: float = 0.0
    min_fps: float = 0.0
    max_fps: float = 0.0
    p99_fps: float = 0.0
    p95_fps: float = 0.0
    avg_frame_time_ms: float = 0.0
    avg_cpu_busy_ms: Optional[float] = None
    avg_gpu_time_ms: Optional[float] = None
    avg_display_latency_ms: Optional[float] = None
    avg_app_memory_mb: float = 0.0
    avg_app_cpu_percent: float = 0.0
    avg_app_gpu_percent: Optional[float] = None
    avg_app_vram_mb: float = 0.0
    capture_duration_s: float = 0.0


@dataclass
class SessionConfig:
    """Configuration for a monitoring session."""
    process_names: list[str] = field(default_factory=list)
    process_ids: list[int] = field(default_factory=list)
    exclude_names: list[str] = field(default_factory=list)
    timed_seconds: int = 0
    output_file: str = ""
    hotkey: str = ""
    use_v1_metrics: bool = False
    track_display: bool = True
    track_input: bool = True
    track_gpu: bool = True


# ---------------------------------------------------------------------------
# Multi-app display helpers
# ---------------------------------------------------------------------------

def format_multi_str(values: list[str]) -> str:
    """Join multiple string values with ' / ' separator."""
    return " / ".join(values)


def format_display_outputs(info: SystemInfo) -> str:
    """Return display outputs as 'WxH@HzHz / ...' with legacy fallback."""
    if info.display_outputs:
        return " / ".join(info.display_outputs)
    if info.display_resolution:
        return f"{info.display_resolution}@{info.display_refresh_hz}Hz"
    return "Unknown"


def format_multi_float(values: list[float], suffix: str = "", precision: int = 1) -> str:
    """Format multiple float values as 'v1 / v2 suffix' or 'v1 suffix' for single."""
    formatted = []
    for v in values:
        if precision == 0:
            formatted.append(f"{int(round(v))}{suffix}")
        else:
            formatted.append(f"{v:.{precision}f}{suffix}")
    return " / ".join(formatted)
