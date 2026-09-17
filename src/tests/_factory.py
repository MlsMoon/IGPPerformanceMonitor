"""Shared test fixtures.

REAL captured data is the default (do not fake it if real data exists): :func:`load_real_frames`
and friends load — and auto-generate on first use — a REAL headless capture at
``temp/real_capture.csv``. That file is **gitignored** (machine-specific session
data is never committed); if it can't be generated (no admin/UAC), tests that
need it SKIP via :class:`SkipTest` rather than fabricate data.

The ``make_*`` builders below are an ESCAPE HATCH — only for tests that need a
controlled value real data can't provide. Add a one-line justification at the
call site. See the ``test-design`` skill.
"""

import os
import subprocess
import sys
import time

from src.core.csv_importer import import_file, group_frames_by_app
from src.models import (
    FrameData, SystemInfo, SystemSnapshot, PerProcessSnapshot,
)


class SkipTest(Exception):
    """Raised to SKIP a test (not fail) — e.g. the real capture couldn't be generated."""


# temp/ is gitignored — the real capture is machine-specific, auto-generated.
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_REAL_CAPTURE = os.path.join(_PROJECT_ROOT, "temp", "real_capture.csv")
_GEN_TIMEOUT_S = 120  # headless capture (~12s) + UAC/poll headroom

_SKIP_MSG = (
    "Could not generate temp/real_capture.csv (needs admin/UAC or PresentMon). Manual:\n"
    "  python -m src.main --headless --all-processes --timed 10 -o temp/real_capture.csv"
)

_gen_failed = False  # once generation fails, don't retry on every test


def _ensure_real_capture() -> str:
    """Return the path to temp/real_capture.csv, auto-generating it if absent.

    Generation spawns a headless ``--all-processes`` capture (PresentMon needs
    admin). As admin the subprocess runs inline and writes the CSV; as non-admin
    ``main.py`` relaunches elevated (UAC) and writes it asynchronously (polled).
    On failure, latches ``_gen_failed`` (so later tests skip fast) and raises
    SkipTest.
    """
    global _gen_failed
    if _gen_failed:
        raise SkipTest(_SKIP_MSG)
    if os.path.exists(_REAL_CAPTURE) and os.path.getsize(_REAL_CAPTURE) > 0:
        return _REAL_CAPTURE

    os.makedirs(os.path.dirname(_REAL_CAPTURE), exist_ok=True)
    cmd = [sys.executable, "-m", "src.main", "--headless", "--all-processes",
           "--timed", "10", "-o", _REAL_CAPTURE]
    try:
        subprocess.run(cmd, cwd=_PROJECT_ROOT, timeout=_GEN_TIMEOUT_S,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        pass

    # Poll for the file (covers the non-admin UAC relaunch writing asynchronously).
    deadline = time.time() + _GEN_TIMEOUT_S
    while time.time() < deadline:
        if os.path.exists(_REAL_CAPTURE) and os.path.getsize(_REAL_CAPTURE) > 0:
            size = os.path.getsize(_REAL_CAPTURE)
            time.sleep(2)
            if os.path.getsize(_REAL_CAPTURE) == size:  # write settled
                return _REAL_CAPTURE
        time.sleep(1)

    _gen_failed = True
    raise SkipTest(_SKIP_MSG)


def load_real_frames() -> list[FrameData]:
    """REAL captured frames (auto-generates temp/real_capture.csv if missing)."""
    return import_file(_ensure_real_capture()).frames


def load_real_system_info() -> SystemInfo:
    """REAL SystemInfo parsed from the capture's '# System:' line."""
    info = import_file(_ensure_real_capture()).system_info
    assert info is not None, "real_capture.csv missing a # System: line"
    return info


def load_real_frames_by_app() -> dict[str, list[FrameData]]:
    """REAL frames grouped by application (uses the real group_frames_by_app)."""
    return group_frames_by_app(load_real_frames())


# ===========================================================================
# ESCAPE HATCH — fabricated builders. Prefer real captured data.
#
# Prefer load_real_frames() / load_real_system_info() / load_real_frames_by_app()
# above. Reach for make_* ONLY when a test genuinely needs a controlled value
# that real captured data cannot provide, and add a one-line justification at
# the call site whenever you use these.
# ===========================================================================

_DEFAULT_APP = "TestApp.exe"
_DEFAULT_PID = 200
_DEFAULT_FPS = 60.0
_DEFAULT_FRAME_TIME = 16.667


def make_frame(application: str = _DEFAULT_APP, process_id: int = _DEFAULT_PID,
               fps: float = _DEFAULT_FPS, **overrides) -> FrameData:
    """A fabricated ~60 FPS frame with every meaningful field populated.

    ESCAPE HATCH — prefer load_real_frames(). Override any field via **overrides.
    """
    defaults = dict(
        application=application,
        process_id=process_id,
        swap_chain_address="0x1234ABCD",
        present_runtime="DXGI",
        sync_interval=1,
        present_flags="0",
        allows_tearing=1,
        present_mode="Hardware: Independent Flip",
        frame_type="0",
        cpu_start_time=1.5,
        ms_cpu_busy=8.0,
        ms_cpu_wait=1.5,
        ms_gpu_latency=0.5,
        ms_gpu_time=10.2,
        ms_gpu_busy=8.5,
        ms_gpu_wait=0.1,
        video_busy=0.0,
        display_latency=4.0,
        displayed_time=16.7,
        ms_animation_error=0.2,
        ms_click_to_photon_latency=7.0,
        ms_all_input_to_photon_latency=8.0,
        ms_between_presents=_DEFAULT_FRAME_TIME,
        ms_in_present_api=0.1,
        ms_between_display_change=16.7,
        ms_until_displayed=17.0,
        ms_render_present_latency=6.0,
        ms_between_simulation_start=0.0,
        ms_pc_latency=9.0,
        ms_between_app_start=0.0,
        dropped=0,
        time_in_seconds=0.0,
        app_memory_mb=2048.0,
        app_cpu_percent=25.0,
        app_cpu_cores=4.0,
        app_gpu_percent=80.0,
        total_cpu_percent=50.0,
        total_gpu_percent=70.0,
        total_ram_used_gb=12.5,
        gpu_vram_total_mb=8192.0,
        gpu_vram_used_mb=4096.0,
        gpu_vram_percent=50.0,
        fps=fps,
    )
    defaults.update(overrides)
    return FrameData(**defaults)


def make_system_info(**overrides) -> SystemInfo:
    """Fabricated dual-display system info. ESCAPE HATCH — prefer load_real_system_info()."""
    defaults = dict(
        cpu_name="TestCPU",
        gpu_name="TestGPU",
        ram_total_gb=32.0,
        display_resolution="3840x2160",
        display_refresh_hz=59,
        display_outputs=["3840x2160@59Hz", "1920x1080@280Hz"],
        vram_total_gb=8.0,
    )
    defaults.update(overrides)
    return SystemInfo(**defaults)


def make_system_snapshot(timestamp: float = 0.0, **overrides) -> SystemSnapshot:
    """Fabricated system snapshot (incl. 0.3.0 snapshot-only fields). ESCAPE HATCH."""
    defaults = dict(
        timestamp=timestamp,
        total_cpu_percent=45.0,
        total_gpu_percent=72.0,
        total_ram_used_gb=16.0,
        vram_total_mb=8192.0,
        vram_used_mb=4096.0,
        vram_percent=50.0,
        per_core_cpu_percent=[10.0, 20.0, 15.0, 25.0],
        gpu_power_w=150.0,
        gpu_temp_c=65.0,
        gpu_power_limit_w=170.0,
    )
    defaults.update(overrides)
    return SystemSnapshot(**defaults)


def make_per_process_snapshot(process_name: str = _DEFAULT_APP,
                              process_id: int = _DEFAULT_PID,
                              timestamp: float = 0.0, **overrides) -> PerProcessSnapshot:
    """Fabricated per-process snapshot. ESCAPE HATCH."""
    defaults = dict(
        timestamp=timestamp,
        process_name=process_name,
        process_id=process_id,
        memory_mb=2048.0,
        cpu_percent=25.0,
        cpu_cores=4.0,
        gpu_percent=80.0,
        vram_mb=512.0,
    )
    defaults.update(overrides)
    return PerProcessSnapshot(**defaults)
