"""Test: models — FrameData / SystemInfo / ProcessStats defaults + format helpers."""

from src.models import (
    FrameData, SystemInfo, SystemSnapshot, PerProcessSnapshot,
    ProcessStats, format_display_outputs, format_multi_float, format_multi_str,
)


def run():
    # --- FrameData defaults ---
    f = FrameData()
    assert f.fps is None, "fps default"
    assert f.application == "", "application default"
    assert f.process_id == 0, "pid default"
    assert f.app_cpu_percent is None, "cpu default"
    assert f.app_memory_mb is None, "mem default"
    assert f.app_gpu_percent is None, "gpu default"

    # --- Settable fields ---
    f.application = "Unity.exe"
    f.process_id = 1234
    f.fps = 60.0
    f.ms_between_presents = 16.667
    f.app_cpu_percent = 25.5
    f.app_cpu_cores = 4.1
    f.app_memory_mb = 2048.0
    f.app_gpu_percent = 80.0
    assert f.application == "Unity.exe"

    # --- SystemInfo ---
    si = SystemInfo()
    assert si.cpu_name == ""
    assert si.display_outputs == []
    si.cpu_name = "Intel Core i7"
    assert si.cpu_name == "Intel Core i7"
    si.display_resolution = "1920x1080"
    si.display_refresh_hz = 60
    assert format_display_outputs(si) == "1920x1080@60Hz"
    si.display_outputs = ["3840x2160@59Hz", "1920x1080@280Hz"]
    assert format_display_outputs(si) == "3840x2160@59Hz / 1920x1080@280Hz"

    # --- SystemSnapshot ---
    ss = SystemSnapshot()
    ss.total_cpu_percent = 45.0
    ss.total_gpu_percent = 72.0
    assert ss.total_cpu_percent == 45.0

    # --- PerProcessSnapshot ---
    ps = PerProcessSnapshot()
    ps.process_name = "Unity.exe"
    ps.process_id = 1234
    ps.cpu_percent = 25.0
    ps.memory_mb = 2048.0
    assert ps.process_name == "Unity.exe"

    # --- ProcessStats ---
    st = ProcessStats()
    st.frame_count = 100
    st.avg_fps = 59.5
    assert st.frame_count == 100

    # --- format helpers ---
    assert format_multi_float([60.0, 30.0]) == "60.0 / 30.0", "two values"
    assert format_multi_float([0.0]) == "0.0", "zero"
    assert format_multi_float([60.0]) == "60.0", "single"
    assert format_multi_str(["A", "B"]) == "A / B", "two strings"
