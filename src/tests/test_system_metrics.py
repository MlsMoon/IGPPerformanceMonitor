"""Test: system_metrics — key functions exist and return expected types.

Environment-tolerant: the ".exe" suffix and non-empty display list are only
asserted where they hold (Windows / has a display), so this passes on headless
or non-Windows CI too.
"""

import sys

from src.core import system_metrics


def run():
    # gpu_available returns bool (meaningful on any platform).
    gpu = system_metrics.gpu_available()
    assert isinstance(gpu, bool), f"gpu_available returned {type(gpu)}"

    # get_running_process_names returns a non-empty list of strings.
    names = system_metrics.get_running_process_names()
    assert isinstance(names, list), "expected list"
    assert len(names) > 0, "no running processes — is psutil working?"
    assert all(isinstance(n, str) for n in names), "process names must be strings"
    # The ".exe" suffix is a Windows convention.
    if sys.platform == "win32":
        assert all(n.endswith(".exe") for n in names), \
            "Windows process names must end with .exe"

    # get_system_info returns a dict with expected keys.
    info = system_metrics.get_system_info()
    assert isinstance(info, dict)
    for key in ("cpu_name", "gpu_name", "ram_total_gb", "display_resolution",
                "display_refresh_hz", "display_outputs"):
        assert key in info, f"get_system_info missing key {key!r}"
    assert isinstance(info["cpu_name"], str) and len(info["cpu_name"]) > 0
    assert isinstance(info["ram_total_gb"], (int, float)) and info["ram_total_gb"] > 0
    assert isinstance(info["display_refresh_hz"], (int, float))
    assert isinstance(info["display_outputs"], list)
    # Display outputs may be empty on headless CI — only assert content when present.
    if info["display_outputs"]:
        assert all(isinstance(d, str) and d for d in info["display_outputs"])

    # VRAM semantics: an unavailable process must return vram_mb=None, NOT 0.0.
    # Keep real 0.0; missing stays None — guards against `if x else None`
    # that silently nulled real 0.0 and left the App VRAM chart empty.)
    d = system_metrics.sample_process_gpu(999999999)  # bogus pid → unavailable
    assert d["vram_mb"] is None, "unavailable per-process VRAM must be None, not 0.0"

    # Per-process VRAM via the Windows GPU perf counter (WDDP-safe source).
    # Non-empty on a Windows GPU box; may be {} on headless/CI — assert shape only.
    vmap = system_metrics.sample_all_process_vram_mb()
    assert isinstance(vmap, dict)
    for v in vmap.values():
        assert isinstance(v, (int, float)) and v >= 0, "VRAM values must be non-negative"
    # Real-collection smoke: with an NVIDIA GPU, dwm (always present) holds
    # resident VRAM, so the perf-counter source must return some >0 value. This
    # was empty via the broken NVML path, leaving the App VRAM chart blank — the
    # exact failure mode this guard catches. Skipped off-NVIDIA / headless.
    if system_metrics.gpu_available() and vmap:
        assert any(v > 0 for v in vmap.values()), (
            "GPU present but per-process VRAM all-zero — collection source broken")
