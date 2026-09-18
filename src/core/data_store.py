"""Thread-safe data store for captured frame data and system metrics."""

import threading
import time
from collections import defaultdict
from src.models import (
    FrameData, ProcessStats, SystemInfo, SystemSnapshot, PerProcessSnapshot,
    frame_series_key, pretty_series_key,
)
from src.config import DEFAULT_MAX_FRAMES_BUFFER, DEFAULT_CHART_HISTORY_SECONDS
from src.core.filters import iqr_filter_series


class DataStore:
    """Stores captured frames, system info, and metrics snapshots.

    Thread-safe: write from capture thread, read from UI thread.
    """

    def __init__(self, max_frames: int = DEFAULT_MAX_FRAMES_BUFFER):
        self._lock = threading.Lock()
        self._frames: list[FrameData] = []
        self._max_frames = max_frames
        self._session_start_time: float | None = None

        # System info (set once at session start)
        self._system_info: SystemInfo | None = None

        # Configured (target) series keys — distinct from get_process_names()
        # which only lists keys that have produced ≥1 frame. Idle apps (picked
        # but not yet presenting) still show in the stats list.
        self._monitored_apps: list[str] = []
        # Optional pretty labels for series keys (window title, etc.).
        self._process_labels: dict[str, str] = {}

        # Time-series snapshots for charts
        self._system_snapshots: list[SystemSnapshot] = []
        self._per_process_snapshots: dict[str, list[PerProcessSnapshot]] = defaultdict(list)
        self._max_snapshots = 5000
        # Frame-driven chart histories are trimmed by TIME (cover the chart
        # window), not count. Count-trim to _max_snapshots dropped the front
        # segment at high FPS (>~83 @ 60s window), leaving the older charts
        # (fps/frametime/mem/cpu/gpu/cores/vram) with a blank front while the
        # system-snapshot charts stayed full. +5s margin covers refresh skew.
        self._history_keep_s = DEFAULT_CHART_HISTORY_SECONDS + 5
        self._max_history_points = self._max_frames  # count backstop for extreme FPS

        # FPS history by process (for legacy chart compatibility)
        self._fps_history: dict[str, list[tuple[float, float]]] = defaultdict(list)
        # Per-process metric history keyed by frame_series_key (exe|pid),
        # sourced from enriched FrameData fields. Two instances of the same
        # exe must not share a curve. Do not key off psutil proc.name().
        self._cpu_history: dict[str, list[tuple[float, float]]] = defaultdict(list)
        self._mem_history: dict[str, list[tuple[float, float]]] = defaultdict(list)
        self._gpu_history: dict[str, list[tuple[float, float]]] = defaultdict(list)
        # Per-process "cores used" history (frame-based, same key as fps history).
        self._cpu_cores_history: dict[str, list[tuple[float, float]]] = defaultdict(list)
        self._app_vram_history: dict[str, list[tuple[float, float]]] = defaultdict(list)
        self._frame_count_by_process: dict[str, int] = defaultdict(int)

    # ------------------------------------------------------------------
    # Session management
    # ------------------------------------------------------------------

    def start_session(self):
        """Mark session start time, clear all data."""
        with self._lock:
            self._session_start_time = time.time()
            self._frames.clear()
            self._system_snapshots.clear()
            self._per_process_snapshots.clear()
            self._fps_history.clear()
            self._cpu_history.clear()
            self._mem_history.clear()
            self._gpu_history.clear()
            self._cpu_cores_history.clear()
            self._app_vram_history.clear()
            self._frame_count_by_process.clear()
            self._monitored_apps.clear()
            self._process_labels.clear()

    def set_system_info(self, info: SystemInfo):
        """Store hardware system info."""
        with self._lock:
            self._system_info = info

    def get_system_info(self) -> SystemInfo | None:
        with self._lock:
            return self._system_info

    def set_monitored_apps(self, names: list[str]) -> None:
        """Store the configured (target) series keys for this session."""
        with self._lock:
            self._monitored_apps = list(names)

    def get_monitored_apps(self) -> list[str]:
        """Configured series keys (may include idle apps with 0 frames)."""
        with self._lock:
            return list(self._monitored_apps)

    def set_process_labels(self, labels: dict[str, str]) -> None:
        """Map series key → UI label (window title / exe (pid))."""
        with self._lock:
            self._process_labels = dict(labels)

    def display_name(self, key: str) -> str:
        """Label for charts/stats. Collapses ``exe|pid`` when that exe is unique."""
        with self._lock:
            mapped = self._process_labels.get(key)
            if mapped:
                return mapped
            if "|" in key:
                app = key.rsplit("|", 1)[0]
                siblings = [
                    k for k in self._frame_count_by_process
                    if k == app or k.startswith(app + "|")
                ]
                configured = [
                    k for k in self._monitored_apps
                    if k == app or k.startswith(app + "|")
                ]
                if max(len(siblings), len(configured)) <= 1:
                    return app
            return pretty_series_key(key)

    # ------------------------------------------------------------------
    # Frame data
    # ------------------------------------------------------------------

    def add_frame(self, frame: FrameData):
        """Add a captured frame (called from capture thread).

        System / per-process snapshots are written separately by
        SystemMetricsSampler on a fixed cadence (see metrics_sampler.py),
        so this method only stores the frame + fps history.
        """
        with self._lock:
            if self._session_start_time is None:
                self._session_start_time = time.time()

            self._frames.append(frame)
            key = frame_series_key(frame)
            self._frame_count_by_process[key] += 1

            elapsed = time.time() - self._session_start_time
            if frame.fps is not None and frame.fps > 0:
                self._fps_history[key].append((elapsed, frame.fps))
            # Per-process mem/cpu/gpu from enriched frame fields (same key as fps)
            if frame.app_cpu_percent is not None:
                self._cpu_history[key].append((elapsed, frame.app_cpu_percent))
            if frame.app_cpu_cores is not None:
                self._cpu_cores_history[key].append((elapsed, frame.app_cpu_cores))
            if frame.app_vram_mb is not None:
                self._app_vram_history[key].append((elapsed, frame.app_vram_mb))
            if frame.app_memory_mb is not None:
                self._mem_history[key].append((elapsed, frame.app_memory_mb))
            if frame.app_gpu_percent is not None:
                self._gpu_history[key].append((elapsed, frame.app_gpu_percent))

            # Trim frames
            while len(self._frames) > self._max_frames:
                old = self._frames.pop(0)
                old_key = frame_series_key(old)
                self._frame_count_by_process[old_key] = max(0, self._frame_count_by_process[old_key] - 1)

            # Trim per-process frame histories by TIME (cover the chart window),
            # not count. Points are appended in ascending elapsed order, so
            # popping from the front is O(1). _max_history_points is a backstop
            # for extreme FPS only.
            cutoff = elapsed - self._history_keep_s
            for hist in (self._fps_history, self._cpu_history, self._mem_history,
                         self._gpu_history, self._cpu_cores_history, self._app_vram_history):
                for k in list(hist.keys()):
                    while hist[k] and hist[k][0][0] < cutoff:
                        hist[k].pop(0)
                    while len(hist[k]) > self._max_history_points:
                        hist[k].pop(0)
                    if not hist[k]:
                        del hist[k]

    def add_system_snapshot(self, snapshot: SystemSnapshot):
        """Append a system-wide snapshot (called by SystemMetricsSampler)."""
        with self._lock:
            self._system_snapshots.append(snapshot)
            while len(self._system_snapshots) > self._max_snapshots:
                self._system_snapshots.pop(0)

    def add_per_process_snapshot(self, key: str, snapshot: PerProcessSnapshot):
        """Append a per-process snapshot (called by SystemMetricsSampler)."""
        with self._lock:
            self._per_process_snapshots[key].append(snapshot)
            while len(self._per_process_snapshots[key]) > self._max_snapshots:
                self._per_process_snapshots[key].pop(0)

    def get_frame_count(self) -> int:
        with self._lock:
            return len(self._frames)

    def get_elapsed_seconds(self) -> float:
        with self._lock:
            if self._session_start_time is None:
                return 0.0
            return time.time() - self._session_start_time

    def get_all_frames(self) -> list[FrameData]:
        with self._lock:
            return list(self._frames)

    # ------------------------------------------------------------------
    # Process queries
    # ------------------------------------------------------------------

    def get_process_names(self) -> list[str]:
        with self._lock:
            return list(self._frame_count_by_process.keys())

    def get_monitored_apps_display(self) -> str:
        """Return comma-separated pretty names of series that have frames."""
        with self._lock:
            keys = list(self._frame_count_by_process.keys())
        return ", ".join(self.display_name(k) for k in keys) if keys else ""

    def get_fps_history(self, process_name: str = "") -> list[tuple[float, float]]:
        with self._lock:
            if not process_name:
                if not self._frame_count_by_process:
                    return []
                process_name = max(self._frame_count_by_process, key=self._frame_count_by_process.get)
            return list(self._fps_history.get(process_name, []))

    # ------------------------------------------------------------------
    # Time-series queries (for charts)
    # ------------------------------------------------------------------

    def get_system_snapshots(self) -> list[SystemSnapshot]:
        with self._lock:
            return list(self._system_snapshots)

    def get_per_process_snapshots(self, process_name: str = "") -> list[PerProcessSnapshot]:
        with self._lock:
            if not process_name:
                if not self._per_process_snapshots:
                    return []
                process_name = max(self._per_process_snapshots, key=lambda k: len(self._per_process_snapshots[k]))
            return list(self._per_process_snapshots.get(process_name, []))

    def get_memory_history(self, process_name: str = "") -> list[tuple[float, float]]:
        """Return list of (elapsed_seconds, memory_mb) for a process (frame-based)."""
        with self._lock:
            if not process_name:
                if not self._mem_history:
                    return []
                process_name = max(self._mem_history, key=lambda k: len(self._mem_history[k]))
            return list(self._mem_history.get(process_name, []))

    def get_cpu_history(self, process_name: str = "") -> list[tuple[float, float]]:
        """Return list of (elapsed_seconds, app_cpu_pct) for a process (frame-based)."""
        with self._lock:
            if not process_name:
                if not self._cpu_history:
                    return []
                process_name = max(self._cpu_history, key=lambda k: len(self._cpu_history[k]))
            return list(self._cpu_history.get(process_name, []))

    def get_cpu_cores_history(self, process_name: str = "") -> list[tuple[float, float]]:
        """Return list of (elapsed_seconds, app_cpu_cores) for a process (frame-based)."""
        with self._lock:
            if not process_name:
                if not self._cpu_cores_history:
                    return []
                process_name = max(self._cpu_cores_history,
                                   key=lambda k: len(self._cpu_cores_history[k]))
            return list(self._cpu_cores_history.get(process_name, []))

    def get_app_vram_history(self, process_name: str = "") -> list[tuple[float, float]]:
        """Return list of (elapsed_seconds, app_vram_mb) for a process (frame-based)."""
        with self._lock:
            if not process_name:
                if not self._app_vram_history:
                    return []
                process_name = max(self._app_vram_history,
                                   key=lambda k: len(self._app_vram_history[k]))
            return list(self._app_vram_history.get(process_name, []))

    def get_gpu_history(self, process_name: str = "") -> list[tuple[float, float]]:
        """Return list of (elapsed_seconds, app_gpu_percent) for a process (frame-based)."""
        with self._lock:
            if not process_name:
                if not self._gpu_history:
                    return []
                process_name = max(self._gpu_history, key=lambda k: len(self._gpu_history[k]))
            return list(self._gpu_history.get(process_name, []))

    def get_vram_history(self) -> list[tuple[float, float]]:
        """Return list of (elapsed_seconds, vram_percent) system-wide."""
        with self._lock:
            return [(s.timestamp, s.vram_percent) for s in self._system_snapshots]

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    def compute_stats(self, process_name: str = "") -> ProcessStats | None:
        """Compute aggregate statistics for a process."""
        with self._lock:
            if not self._frames:
                return None

            if process_name:
                frames = [
                    f for f in self._frames
                    if frame_series_key(f) == process_name
                    or f.application == process_name
                ]
            else:
                frames = list(self._frames)

            if not frames:
                return None

            fps_values = sorted([f.fps for f in frames if f.fps is not None and f.fps > 0])
            if not fps_values:
                return None

            # Filter extreme outliers before computing percentiles
            if len(fps_values) >= 10:
                fps_pairs = [(i, v) for i, v in enumerate(fps_values)]
                filtered = iqr_filter_series(fps_pairs, multiplier=3.0)
                if filtered:
                    fps_values = [v for _, v in filtered]

            n = len(fps_values)
            avg_fps = sum(fps_values) / n
            p99_idx = int(n * 0.01)
            p95_idx = int(n * 0.05)

            frame_times = [f.ms_between_presents for f in frames if f.ms_between_presents and f.ms_between_presents > 0]
            # Filter extreme frame-time outliers
            if len(frame_times) >= 10:
                ft_pairs = [(i, v) for i, v in enumerate(frame_times)]
                filtered_ft = iqr_filter_series(ft_pairs, multiplier=3.0)
                if filtered_ft:
                    frame_times = [v for _, v in filtered_ft]
            avg_ft = sum(frame_times) / len(frame_times) if frame_times else 0.0

            cpu_vals = [f.ms_cpu_busy for f in frames if f.ms_cpu_busy is not None]
            gpu_vals = [f.ms_gpu_time for f in frames if f.ms_gpu_time is not None]
            display_vals = [f.display_latency for f in frames if f.display_latency is not None]
            mem_vals = [f.app_memory_mb for f in frames if f.app_memory_mb is not None]
            app_cpu_vals = [f.app_cpu_percent for f in frames if f.app_cpu_percent is not None]
            app_gpu_vals = [f.app_gpu_percent for f in frames if f.app_gpu_percent is not None]
            vram_vals = [f.app_vram_mb for f in frames if f.app_vram_mb is not None]

            elapsed = (time.time() - self._session_start_time) if self._session_start_time else 0

            return ProcessStats(
                process_name=process_name or frames[0].application,
                process_id=frames[0].process_id,
                frame_count=n,
                avg_fps=round(avg_fps, 1),
                min_fps=round(fps_values[0], 1),
                max_fps=round(fps_values[-1], 1),
                p99_fps=round(fps_values[p99_idx] if p99_idx < n else fps_values[0], 1),
                p95_fps=round(fps_values[p95_idx] if p95_idx < n else fps_values[0], 1),
                avg_frame_time_ms=round(avg_ft, 2),
                avg_cpu_busy_ms=round(sum(cpu_vals) / len(cpu_vals), 2) if cpu_vals else None,
                avg_gpu_time_ms=round(sum(gpu_vals) / len(gpu_vals), 2) if gpu_vals else None,
                avg_display_latency_ms=round(sum(display_vals) / len(display_vals), 2) if display_vals else None,
                avg_app_memory_mb=round(sum(mem_vals) / len(mem_vals), 1) if mem_vals else 0.0,
                avg_app_cpu_percent=round(sum(app_cpu_vals) / len(app_cpu_vals), 1) if app_cpu_vals else 0.0,
                avg_app_gpu_percent=round(sum(app_gpu_vals) / len(app_gpu_vals), 1) if app_gpu_vals else None,
                avg_app_vram_mb=round(sum(vram_vals) / len(vram_vals), 1) if vram_vals else 0.0,
                capture_duration_s=round(elapsed, 1),
            )

    def clear(self):
        """Reset all data."""
        with self._lock:
            self._frames.clear()
            self._frame_count_by_process.clear()
            self._fps_history.clear()
            self._cpu_history.clear()
            self._mem_history.clear()
            self._gpu_history.clear()
            self._cpu_cores_history.clear()
            self._app_vram_history.clear()
            self._system_snapshots.clear()
            self._per_process_snapshots.clear()
            self._session_start_time = None
            self._system_info = None
            self._monitored_apps.clear()
            self._process_labels.clear()
