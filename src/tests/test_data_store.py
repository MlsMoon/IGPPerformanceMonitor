"""Test: data_store — frames, snapshots, stats, history, multi-app, clear.

Driven by REAL captured frames (load_real_frames) with STRUCTURAL stats
assertions: real fps varies and compute_stats IQR-filters ≥10 values, so we
assert min≤avg≤max / frame_count rather than hardcoding exact numbers (which
would just duplicate the store's own math).
"""

from src.core.data_store import DataStore
from src.core.csv_importer import group_frames_by_app
from src.tests._factory import (
    load_real_frames, make_frame, make_system_snapshot, make_per_process_snapshot,
)


def run():
    ds = DataStore()
    ds.start_session()

    real_frames = load_real_frames()
    by_app = group_frames_by_app(real_frames)
    app_name = next(iter(by_app))        # first real app
    app_frames = by_app[app_name]

    # --- Single app: add its real frames ---
    for f in app_frames:
        ds.add_frame(f)
    assert ds.get_frame_count() == len(app_frames)
    assert len(ds.get_all_frames()) == len(app_frames)
    assert len(ds.get_fps_history(app_name)) > 0, "fps history populated"
    # cpu/mem history may be sparse for the first real app — just exercise the getters.
    ds.get_cpu_history(app_name)
    ds.get_memory_history(app_name)

    # --- Stats: structural (not hardcoded) ---
    stats = ds.compute_stats(app_name)
    assert stats is not None, "stats not None"
    assert 0 < stats.frame_count <= len(app_frames)  # IQR may drop outlier frames
    assert stats.avg_fps > 0
    assert stats.min_fps <= stats.avg_fps <= stats.max_fps, (
        f"avg {stats.avg_fps} not within [{stats.min_fps}, {stats.max_fps}]")

    # --- Snapshots: the headless CSV doesn't persist snapshots, so escape hatch. ---
    # ESCAPE HATCH make_*: snapshot plumbing needs objects the real CSV doesn't carry.
    ds.add_system_snapshot(make_system_snapshot(
        total_cpu_percent=45.0, total_gpu_percent=72.0, vram_percent=50.0,
        per_core_cpu_percent=[10.0, 20.0]))
    ds.add_per_process_snapshot(app_name, make_per_process_snapshot(
        process_name=app_name, process_id=app_frames[0].process_id,
        cpu_percent=25.0, memory_mb=2000.0))
    assert len(ds.get_system_snapshots()) == 1
    assert len(ds.get_per_process_snapshots(app_name)) == 1

    # --- Multi-app: add the rest of the real frames ---
    for f in real_frames:
        if f.application != app_name:
            ds.add_frame(f)
    assert ds.get_frame_count() == len(real_frames)
    all_stats = ds.compute_stats()
    assert all_stats is not None
    assert 0 < all_stats.frame_count <= len(real_frames)  # IQR may drop outlier frames

    # --- Clear ---
    ds.clear()
    assert ds.get_frame_count() == 0, "clear frames"
    assert ds.compute_stats() is None, "clear stats"

    # --- High-FPS history window coverage (regression) ---
    # Frame-driven histories used to be count-trimmed to 5000, so at >83fps they
    # couldn't hold 60s and the charts lost their front segment. Now time-trimmed
    # to the chart window. Feed 200fps x 70s of elapsed time and assert the fps
    # history still covers the full window (old count-trim would retain ~25s).
    import time as _time
    from unittest.mock import patch
    from src.config import DEFAULT_CHART_HISTORY_SECONDS
    ds2 = DataStore()
    clock = {"t": _time.time()}
    with patch("src.core.data_store.time.time", side_effect=lambda: clock["t"]):
        ds2.start_session()
        for _ in range(14000):  # 200 fps * 70s
            ds2.add_frame(make_frame(application="HiFPS.exe", process_id=4, fps=200.0))
            clock["t"] += 0.005  # 5ms/frame -> 200fps
    h = ds2.get_fps_history("HiFPS.exe")
    span = h[-1][0] - h[0][0]
    assert span >= DEFAULT_CHART_HISTORY_SECONDS, (
        f"frame history must cover the {DEFAULT_CHART_HISTORY_SECONDS}s chart window; "
        f"only {span:.1f}s retained")
    assert len(h) <= ds2._max_history_points, "history exceeded count backstop"
