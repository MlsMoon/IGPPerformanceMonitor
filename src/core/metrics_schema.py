"""Single source of truth for frame metric CSV columns.

The live PresentMon stream, exported CSV files, and imported offline captures
all map into :class:`src.models.FrameData`.  Keep column names, aliases, value
types, and export formatting here so parser/export/tests do not drift apart.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from src.models import FrameData

MetricKind = Literal["str", "int", "float"]

NA_VALUE = "NA"


@dataclass(frozen=True)
class MetricColumn:
    """CSV column metadata for one FrameData field."""

    export_name: str
    field_name: str | None
    kind: MetricKind = "float"
    aliases: tuple[str, ...] = ()
    export_precision: int | None = None

    @property
    def parse_names(self) -> tuple[str, ...]:
        return (self.export_name, *self.aliases)


CSV_COLUMNS: tuple[MetricColumn, ...] = (
    MetricColumn("Application", "application", "str"),
    MetricColumn("ProcessID", "process_id", "int"),
    MetricColumn("SwapChainAddress", "swap_chain_address", "str"),
    MetricColumn("PresentRuntime", "present_runtime", "str", aliases=("Runtime",)),
    MetricColumn("SyncInterval", "sync_interval", "int"),
    MetricColumn("PresentFlags", "present_flags", "str"),
    MetricColumn("AllowsTearing", "allows_tearing", "int"),
    MetricColumn("PresentMode", "present_mode", "str"),
    MetricColumn("FrameType", "frame_type", "str"),
    MetricColumn("CPUStartTime", "cpu_start_time"),
    MetricColumn("MsCPUBusy", "ms_cpu_busy", aliases=("CPUBusy",)),
    MetricColumn("MsCPUWait", "ms_cpu_wait", aliases=("CPUWait",)),
    MetricColumn("MsGPULatency", "ms_gpu_latency", aliases=("GPULatency",)),
    MetricColumn("MsGPUTime", "ms_gpu_time", aliases=("GPUTime",)),
    MetricColumn("MsGPUBusy", "ms_gpu_busy", aliases=("GPUBusy",)),
    MetricColumn("MsGPUWait", "ms_gpu_wait", aliases=("GPUWait",)),
    MetricColumn("VideoBusy", "video_busy"),
    MetricColumn("DisplayLatency", "display_latency"),
    MetricColumn("DisplayedTime", "displayed_time"),
    MetricColumn("MsAnimationError", "ms_animation_error", aliases=("AnimationError",)),
    MetricColumn("MsClickToPhotonLatency", "ms_click_to_photon_latency", aliases=("ClickToPhotonLatency",)),
    MetricColumn(
        "MsAllInputToPhotonLatency",
        "ms_all_input_to_photon_latency",
        aliases=("AllInputToPhotonLatency",),
    ),
    MetricColumn("MsBetweenPresents", "ms_between_presents", aliases=("FrameTime",)),
    MetricColumn("MsInPresentAPI", "ms_in_present_api"),
    MetricColumn("MsBetweenDisplayChange", "ms_between_display_change"),
    MetricColumn("MsUntilDisplayed", "ms_until_displayed"),
    MetricColumn("MsRenderPresentLatency", "ms_render_present_latency"),
    MetricColumn("MsBetweenSimulationStart", "ms_between_simulation_start"),
    MetricColumn("MsPCLatency", "ms_pc_latency"),
    MetricColumn("MsBetweenAppStart", "ms_between_app_start"),
    MetricColumn("FPS", "fps", export_precision=2),
    MetricColumn("AppMemoryMB", "app_memory_mb"),
    MetricColumn("AppCPU%", "app_cpu_percent"),
    MetricColumn("AppCPUCores", "app_cpu_cores"),
    MetricColumn("TotalCPU%", "total_cpu_percent"),
    MetricColumn("TotalGPU%", "total_gpu_percent"),
    MetricColumn("RamUsedGB", "total_ram_used_gb"),
    MetricColumn("AppGPU%", "app_gpu_percent"),
    MetricColumn("AppVramMB", "app_vram_mb"),
    MetricColumn("VramTotalMB", "gpu_vram_total_mb"),
    MetricColumn("VramUsedMB", "gpu_vram_used_mb"),
    MetricColumn("VramPercent", "gpu_vram_percent"),
)

CSV_EXPORT_HEADER_V2: list[str] = [col.export_name for col in CSV_COLUMNS]

COLUMN_MAP_V2: dict[str, str] = {
    name: col.field_name
    for col in CSV_COLUMNS
    if col.field_name is not None
    for name in col.parse_names
}

COLUMN_BY_PARSE_NAME: dict[str, MetricColumn] = {
    name: col
    for col in CSV_COLUMNS
    if col.field_name is not None
    for name in col.parse_names
}


def parse_value(value: str, column: MetricColumn):
    """Parse a raw CSV value according to *column* type."""
    if column.kind == "str":
        return value
    if column.kind == "int":
        return _safe_int(value)
    return _safe_float(value)


def format_export_value(value, precision: int | None = None):
    """Format a FrameData value for exported CSV, preserving real zeros."""
    if value is None:
        return NA_VALUE
    if precision is not None and isinstance(value, (int, float)):
        return round(value, precision)
    return value


def frame_to_row(frame: FrameData) -> list:
    """Convert a FrameData instance into the canonical export row."""
    row = []
    for col in CSV_COLUMNS:
        if col.field_name is None:
            row.append(NA_VALUE)
            continue
        row.append(format_export_value(
            getattr(frame, col.field_name),
            col.export_precision,
        ))
    return row


def _safe_float(val: str) -> float | None:
    """Convert string to float; returns None for NA or empty values."""
    if not val or val.strip() == "" or val.strip().upper() == NA_VALUE:
        return None
    try:
        return float(val)
    except ValueError:
        return None


def _safe_int(val: str) -> int:
    """Convert string to int; returns 0 for NA or empty values."""
    if not val or val.strip() == "" or val.strip().upper() == NA_VALUE:
        return 0
    try:
        return int(val)
    except ValueError:
        return 0
