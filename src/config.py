"""Application configuration constants."""

import os
import sys


def _get_base_dir() -> str:
    """Get the application base directory, works in dev and PyInstaller frozen modes."""
    if getattr(sys, "frozen", False):
        # Running as PyInstaller bundle
        return sys._MEIPASS
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# Paths
BASE_DIR = _get_base_dir()
THIRD_PARTY_DIR = os.path.join(BASE_DIR, "third-party")
PRESENTMON_EXE = os.path.join(THIRD_PARTY_DIR, "PresentMon-2.4.1-x64.exe")

# Defaults
DEFAULT_MAX_FRAMES_BUFFER = 100000  # max frames to keep in memory
DEFAULT_CHART_HISTORY_SECONDS = 60  # chart shows last N seconds
DEFAULT_REFRESH_INTERVAL_MS = 500   # UI refresh rate
DEFAULT_METRICS_INTERVAL_MS = 500   # system/process metrics sampling rate (psutil/NVML)
