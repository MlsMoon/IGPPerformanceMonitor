"""Replay a real capture into a live window so charts show PresentMon's clock.

``add_frame`` stamps history with wall-clock elapsed. Dumping a capture in a
tight loop therefore draws a single spike at t=0. After the dump we rewrite
the histories from accumulated ``MsBetweenPresents`` — imported
``time_in_seconds`` is 0 — so the session that was actually captured is what
the screenshots show.

Shared by the UI self-check and the user-manual shot catalog.
"""

from __future__ import annotations

from collections import defaultdict

from src.core.data_store import DataStore
from src.models import SystemSnapshot, frame_series_key
from src.selfcheck import data

# Long enough for a restyle, a relayout and any motion to finish before a grab.
SETTLE_MS = 400


def spin(ms: int) -> None:
    """Pump the event loop for *ms* so timers and animations actually run."""
    from PyQt5.QtCore import QElapsedTimer
    from PyQt5.QtWidgets import QApplication

    clock = QElapsedTimer()
    clock.start()
    while clock.elapsed() < ms:
        QApplication.processEvents()


def seed_store(store: DataStore, frames, series_keys=None) -> float:
    """Load *frames* into *store* and replay the timeline. Returns span in seconds."""
    store.start_session()
    try:
        store.set_system_info(data.load_real_system_info())
    except Exception:
        pass
    for frame in frames:
        store.add_frame(frame)
    if series_keys is None:
        series_keys = sorted(
            {frame_series_key(f) for f in frames if f.application or f.process_id}
        )
    store.set_monitored_apps(series_keys)
    return replay_timeline(store, frames)


def apply_replay(window, span: float) -> None:
    """Refresh the window's monitor view after ``seed_store``."""
    view = window._monitor_view
    view._refresh_charts()
    view._refresh_stats()
    if span > 0 and hasattr(view, "_set_chart_xrange"):
        view._set_chart_xrange(list(view._plots.values()), max(span, 10.0))


def seed_window(window, frames, series_keys=None) -> float:
    """Seed *window*'s own store and refresh its charts. Returns span in seconds."""
    span = seed_store(window._data_store, frames, series_keys)
    apply_replay(window, span)
    return span


def replay_timeline(store: DataStore, frames) -> float:
    """Rebuild chart histories on PresentMon's timeline. Returns span in seconds."""
    by_app: dict[str, list] = defaultdict(list)
    for frame in frames:
        by_app[frame_series_key(frame)].append(frame)
    if not by_app:
        return 0.0

    histories = (
        store._fps_history, store._cpu_history, store._mem_history,
        store._gpu_history, store._cpu_cores_history, store._app_vram_history,
    )
    for hist in histories:
        hist.clear()

    last_snap = -1.0
    span = 0.0
    for key, group in by_app.items():
        elapsed = 0.0
        for frame in group:
            elapsed += (frame.ms_between_presents or 0.0) / 1000.0
            if elapsed > span:
                span = elapsed
            if frame.fps is not None and frame.fps > 0:
                store._fps_history[key].append((elapsed, frame.fps))
            if frame.app_cpu_percent is not None:
                store._cpu_history[key].append((elapsed, frame.app_cpu_percent))
            if frame.app_cpu_cores is not None:
                store._cpu_cores_history[key].append((elapsed, frame.app_cpu_cores))
            if frame.app_vram_mb is not None:
                store._app_vram_history[key].append((elapsed, frame.app_vram_mb))
            if frame.app_memory_mb is not None:
                store._mem_history[key].append((elapsed, frame.app_memory_mb))
            if frame.app_gpu_percent is not None:
                store._gpu_history[key].append((elapsed, frame.app_gpu_percent))
            if elapsed - last_snap >= 0.5:
                store.add_system_snapshot(SystemSnapshot(
                    timestamp=elapsed,
                    total_cpu_percent=frame.total_cpu_percent,
                    total_gpu_percent=frame.total_gpu_percent,
                    total_ram_used_gb=frame.total_ram_used_gb,
                    vram_total_mb=frame.gpu_vram_total_mb,
                    vram_used_mb=frame.gpu_vram_used_mb,
                    vram_percent=frame.gpu_vram_percent,
                ))
                last_snap = elapsed
    for hist in histories:
        for key, points in hist.items():
            points.sort(key=lambda pair: pair[0])
    return span
