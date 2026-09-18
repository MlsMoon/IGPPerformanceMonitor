"""Capture session coordinator shared by GUI and headless entry points."""

from __future__ import annotations

import logging

from src.config import DEFAULT_METRICS_INTERVAL_MS
from src.core import system_metrics as mc
from src.core.data_store import DataStore
from src.core.metrics_sampler import SystemMetricsSampler
from src.core.presentmon import PresentMonWrapper
from src.models import SessionConfig, SystemInfo, series_key_for_pid

logger = logging.getLogger(__name__)


class CaptureSession:
    """Owns the core capture objects and their lifecycle.

    UI code can connect to ``wrapper`` signals and read ``data_store`` directly,
    but start/stop sequencing stays in one place for GUI and headless paths.
    """

    def __init__(
        self,
        data_store: DataStore | None = None,
        interval_ms: int = DEFAULT_METRICS_INTERVAL_MS,
    ) -> None:
        self._data_store = data_store or DataStore()
        self._data_store.set_system_info(_gather_system_info())
        self._wrapper = PresentMonWrapper(self._data_store)
        self._sampler = SystemMetricsSampler(self._data_store, interval_ms)
        self._wrapper.set_metrics_sampler(self._sampler)
        self._config: SessionConfig | None = None

    @property
    def data_store(self) -> DataStore:
        return self._data_store

    @property
    def wrapper(self) -> PresentMonWrapper:
        return self._wrapper

    @property
    def sampler(self) -> SystemMetricsSampler:
        return self._sampler

    @property
    def config(self) -> SessionConfig | None:
        return self._config

    def start(self, config: SessionConfig) -> None:
        """Start a new capture session with fresh DataStore state."""
        self._config = config
        self._data_store.start_session()
        self._data_store.set_system_info(_gather_system_info())
        _apply_session_targets(self._data_store, config)
        self._wrapper.configure(config)
        self._sampler.configure(config)
        self._sampler.start()
        self._wrapper.start()

    def run_blocking(self, config: SessionConfig) -> None:
        """Run PresentMon in the current thread for headless capture."""
        self._config = config
        self._data_store.start_session()
        self._data_store.set_system_info(_gather_system_info())
        _apply_session_targets(self._data_store, config)
        self._wrapper.configure(config)
        self._sampler.configure(config)
        self._sampler.start()
        self._wrapper.run()

    def stop(self, wait_ms: int = 3000) -> None:
        """Stop wrapper and sampler, waiting briefly for thread shutdown."""
        self._wrapper.stop()
        if self._wrapper.isRunning():
            self._wrapper.wait(wait_ms)
        self._sampler.stop()
        if self._sampler.isRunning():
            self._sampler.wait(wait_ms)


def _gather_system_info() -> SystemInfo:
    try:
        sys_info_dict = mc.get_system_info()
        return SystemInfo(
            cpu_name=sys_info_dict["cpu_name"],
            gpu_name=sys_info_dict["gpu_name"],
            ram_total_gb=sys_info_dict["ram_total_gb"],
            display_resolution=sys_info_dict["display_resolution"],
            display_refresh_hz=sys_info_dict["display_refresh_hz"],
            display_outputs=list(sys_info_dict.get("display_outputs", [])),
            vram_total_gb=sys_info_dict.get("vram_total_gb", 0.0),
        )
    except Exception:
        logger.exception("Failed to gather system info")
        return SystemInfo()


def _apply_session_targets(store: DataStore, config: SessionConfig) -> None:
    """Stamp series keys + window-title labels so two Unity.exe stay distinct."""
    keys: list[str] = []
    labels: dict[str, str] = {}
    for pid in config.process_ids:
        exe = config.process_id_names.get(pid) or "unknown"
        key = series_key_for_pid(exe, pid)
        keys.append(key)
        label = config.process_labels.get(pid)
        if label:
            labels[key] = label
    for name in config.process_names:
        if name not in keys:
            keys.append(name)
    store.set_monitored_apps(keys)
    store.set_process_labels(labels)
