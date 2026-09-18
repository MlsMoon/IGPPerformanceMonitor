"""Independent low-frequency sampler for system & per-process metrics.

psutil's ``cpu_percent(interval=None)`` returns ``0.0`` when called too
frequently — intervals below the Windows timer granularity (~15.6ms) cannot
produce a meaningful delta. When metrics were sampled per-frame inside
``PresentMonWrapper._enrich_frame`` this poisoned ~88% of frames (observed:
exported TotalCPU% 88% zero, AppCPU% 91% NA). Sampling here on a fixed
~500ms cadence yields accurate CPU% and decouples slow-varying system
metrics from the high-frequency frame stream.

The sampler writes ``SystemSnapshot`` / ``PerProcessSnapshot`` into the
DataStore (the source for live charts) and keeps a ``_latest`` cache that
``PresentMonWrapper._enrich_frame`` reads to stamp each frame with the most
recent valid metrics, so CSV exports stay consistent with the live view.
"""

import logging
import threading
import time

import psutil
from PyQt5.QtCore import QThread, pyqtSignal

from src.models import SessionConfig, SystemSnapshot, PerProcessSnapshot
from src.core.data_store import DataStore
from src.core import system_metrics as mc

logger = logging.getLogger(__name__)


class SystemMetricsSampler(QThread):
    """Samples system-wide and per-process metrics on a fixed interval."""

    metrics_sampled = pyqtSignal()  # optional hook for direct UI refresh

    def __init__(self, data_store: DataStore, interval_ms: int = 500, parent=None):
        super().__init__(parent)
        self._data_store = data_store
        self._interval = interval_ms / 1000.0
        self._config: SessionConfig | None = None
        self._proc_handles: dict[int, psutil.Process] = {}
        self._known_pids: set[int] = set()
        self._process_names: list[str] = []
        self._running = False
        self._lock = threading.Lock()
        self._latest_system: dict[str, float | None] = {}
        self._latest_per_process: dict[int, dict[str, float | None]] = {}

    def configure(self, config: SessionConfig):
        """Cache target PIDs and prime psutil cpu_percent baselines.

        psutil needs two samples to compute a CPU delta; priming here means
        the first real sample (one interval later) already returns a value.
        """
        self._config = config
        self._process_names = list(config.process_names)
        with self._lock:
            self._known_pids.clear()
            self._proc_handles.clear()
            self._latest_system.clear()
            self._latest_per_process.clear()
        for pid in config.process_ids:
            self.track_pid(pid)
        for name in config.process_names:
            self._track_process_name(name)

    def track_pid(self, pid: int) -> bool:
        """Start sampling a PID if it is not already tracked.

        This only creates/warms a psutil.Process handle. Actual metric sampling
        still happens in the sampler loop, never in the frame ingestion path.
        """
        if pid <= 0:
            return False
        with self._lock:
            if pid in self._proc_handles:
                return True
        try:
            proc = psutil.Process(pid)
            proc.cpu_percent()  # prime baseline
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            with self._lock:
                self._known_pids.add(pid)
            return False
        with self._lock:
            self._known_pids.add(pid)
            self._proc_handles[pid] = proc
        logger.info("SystemMetricsSampler tracking pid=%s", pid)
        return True

    def _track_process_name(self, name: str) -> None:
        for pid in mc.find_pids_by_name(name):
            self.track_pid(pid)

    def _refresh_dynamic_pids(self) -> None:
        for name in self._process_names:
            self._track_process_name(name)

    @property
    def latest_system(self) -> dict[str, float | None]:
        with self._lock:
            return dict(self._latest_system)

    def latest_per_process(self, pid: int) -> dict[str, float | None]:
        with self._lock:
            return dict(self._latest_per_process.get(pid, {}))

    def run(self):
        self._running = True
        logger.info(
            "SystemMetricsSampler started (interval=%.3fs, pids=%s)",
            self._interval, sorted(self._known_pids),
        )
        while self._running:
            t0 = time.time()
            try:
                self._refresh_dynamic_pids()
                self._sample_once()
            except Exception:
                logger.exception("SystemMetricsSampler sample failed")
            # Interruptible sleep for the remainder of the interval
            end = time.time() + max(0.0, self._interval - (time.time() - t0))
            while time.time() < end and self._running:
                time.sleep(0.05)
        logger.info("SystemMetricsSampler stopped")

    def _sample_once(self):
        # --- System-wide ---
        sys_m = mc.sample_system()
        sys_cpu = sys_m.get("total_cpu_percent")
        sys_gpu = sys_m.get("total_gpu_percent")
        if sys_gpu is not None and sys_gpu < 0:
            sys_gpu = None  # normalize NVML -1 sentinel -> None
        sys_ram = sys_m.get("total_ram_used_gb")
        vram_total = sys_m.get("vram_total_mb")
        vram_used = sys_m.get("vram_used_mb")
        vram_pct = sys_m.get("vram_percent")
        # Snapshot-only metrics (not enriched onto frames / not in _latest_system):
        per_core = sys_m.get("per_core_cpu_percent")
        gpu_power = sys_m.get("gpu_power_w")
        gpu_temp = sys_m.get("gpu_temp_c")
        gpu_power_limit = sys_m.get("gpu_power_limit_w")

        with self._lock:
            self._latest_system = {
                "total_cpu_percent": sys_cpu,
                "total_gpu_percent": sys_gpu,
                "total_ram_used_gb": sys_ram,
                "gpu_vram_total_mb": vram_total,
                "gpu_vram_used_mb": vram_used,
                "gpu_vram_percent": vram_pct,
            }

        elapsed = self._data_store.get_elapsed_seconds()
        self._data_store.add_system_snapshot(SystemSnapshot(
            timestamp=elapsed,
            total_cpu_percent=sys_cpu,
            total_gpu_percent=sys_gpu,
            total_ram_used_gb=sys_ram,
            vram_total_mb=vram_total,
            vram_used_mb=vram_used,
            vram_percent=vram_pct,
            per_core_cpu_percent=per_core,
            gpu_power_w=gpu_power,
            gpu_temp_c=gpu_temp,
            gpu_power_limit_w=gpu_power_limit,
        ))

        # --- Per-process ---
        # Per-process VRAM via the Windows GPU perf counter (WDDP-safe; one
        # query covers all PIDs — NVML's per-process VRAM is empty on WDDP).
        vram_map = mc.sample_all_process_vram_mb()
        with self._lock:
            proc_items = list(self._proc_handles.items())
        for pid, proc in proc_items:
            try:
                app_mem = mc.process_memory_mb(proc)
                if app_mem is None:
                    continue
                raw_cpu = proc.cpu_percent()
                app_cpu = round(raw_cpu / mc.LOGICAL_CORES, 1)   # total share, Task Manager-style
                app_cpu_cores = round(raw_cpu / 100.0, 2)        # cores used
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                with self._lock:
                    self._proc_handles.pop(pid, None)
                    self._latest_per_process.pop(pid, None)
                continue

            gpu_data = mc.sample_process_gpu(pid)
            app_gpu = gpu_data.get("app_gpu_percent", -1.0)
            if app_gpu is not None and app_gpu < 0:
                app_gpu = None
            app_vram = vram_map.get(pid)

            with self._lock:
                self._latest_per_process[pid] = {
                    "app_memory_mb": app_mem,
                    "app_cpu_percent": app_cpu,
                    "app_cpu_cores": app_cpu_cores,
                    "app_gpu_percent": app_gpu,
                    "app_vram_mb": app_vram,
                }

            try:
                name = proc.name()
            except Exception:
                name = ""
            key = f"{name}|{pid}" if pid else (name or f"pid_{pid}")
            self._data_store.add_per_process_snapshot(key, PerProcessSnapshot(
                timestamp=elapsed,
                process_name=name,
                process_id=pid,
                memory_mb=app_mem,
                cpu_percent=app_cpu,
                cpu_cores=app_cpu_cores,
                gpu_percent=app_gpu,
                vram_mb=app_vram,
            ))

        self.metrics_sampled.emit()

    def stop(self):
        """Signal the sampling loop to exit (called from the main thread)."""
        self._running = False
