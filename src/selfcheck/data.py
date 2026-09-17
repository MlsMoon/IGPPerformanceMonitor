"""Access to a real capture for the self-checks and the contract tests.

There is deliberately no fabricated-frame builder anywhere in this project. If
a check needs frames it uses frames PresentMon actually produced, because a
hand-written ``FrameData(fps=60.0)`` only ever proves that the constructor
accepts 60.0 — it cannot catch a column that silently stopped being populated,
which is the bug this codebase keeps having.

``temp/real_capture.csv`` is gitignored (it is machine-specific session data)
and auto-generated on first use.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time

from src.core.csv_importer import import_file
from src.models import FrameData, SystemInfo

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REAL_CAPTURE = os.path.join(_PROJECT_ROOT, "temp", "real_capture.csv")

_GEN_TIMEOUT_S = 120  # headless capture (~12s) + UAC/poll headroom

MISSING_MSG = (
    "temp/real_capture.csv is missing and could not be generated (needs admin/UAC "
    "or PresentMon). Generate it manually with:\n"
    "  Scripts\\capture_debug.bat --all-processes --timed 10 -o temp\\real_capture.csv"
)

_gen_failed = False  # latch: once generation fails, do not retry per call


class NoRealCapture(Exception):
    """Raised when a real capture is needed but cannot be produced."""


def ensure_real_capture() -> str:
    """Path to ``temp/real_capture.csv``, generating it if absent.

    As admin the headless subprocess runs inline and writes the CSV. As
    non-admin ``main.py`` relaunches itself elevated (UAC) and writes it
    asynchronously, so the file has to be polled for rather than waited on.
    """
    global _gen_failed
    if _gen_failed:
        raise NoRealCapture(MISSING_MSG)
    if os.path.exists(REAL_CAPTURE) and os.path.getsize(REAL_CAPTURE) > 0:
        return REAL_CAPTURE

    # CI has no GPU presenting frames and no way to elevate, so generation can
    # only burn the full poll timeout before giving up. Let it say so at once.
    if os.environ.get("IGP_SKIP_CAPTURE_GEN"):
        _gen_failed = True
        raise NoRealCapture(
            "IGP_SKIP_CAPTURE_GEN is set and temp/real_capture.csv is absent")

    os.makedirs(os.path.dirname(REAL_CAPTURE), exist_ok=True)
    cmd = [sys.executable, "-m", "src.main", "--headless", "--all-processes",
           "--timed", "10", "-o", REAL_CAPTURE]
    try:
        subprocess.run(cmd, cwd=_PROJECT_ROOT, timeout=_GEN_TIMEOUT_S,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        pass

    deadline = time.time() + _GEN_TIMEOUT_S
    while time.time() < deadline:
        if os.path.exists(REAL_CAPTURE) and os.path.getsize(REAL_CAPTURE) > 0:
            size = os.path.getsize(REAL_CAPTURE)
            time.sleep(2)
            if os.path.getsize(REAL_CAPTURE) == size:  # write settled
                return REAL_CAPTURE
        time.sleep(1)

    _gen_failed = True
    raise NoRealCapture(MISSING_MSG)


def load_real_frames() -> list[FrameData]:
    """Real captured frames."""
    return import_file(ensure_real_capture()).frames


def load_real_system_info() -> SystemInfo:
    """Real SystemInfo parsed from the capture's ``# System:`` line."""
    info = import_file(ensure_real_capture()).system_info
    if info is None:
        raise NoRealCapture("real_capture.csv has no '# System:' line")
    return info


def load_frames_if_available() -> list[FrameData]:
    """Real frames, or an empty list when no capture can be produced.

    For the UI area, which is worth running on a machine that cannot capture.
    """
    try:
        return load_real_frames()
    except Exception:
        return []
