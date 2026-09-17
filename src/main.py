"""IGP Performance Monitor — entry point. Requires admin privileges.

Usage:
    python -m src.main             # normal
    python -m src.main --debug     # write igp_debug.log
"""

import sys
import os
import ctypes
import logging
import argparse
import subprocess
from collections import Counter

# Suppress libpng iCCP sRGB warnings from Qt's internal PNG resources.
# Qt built-in icons (QStyle standard pixmaps, QMessageBox icons, etc.) are
# compiled into Qt resources with bad iCCP colour-profile chunks, and libpng
# warns once per icon load (harmless but noisy).  Filter them at the stderr
# level because the warnings come from C-level libpng, not Python logging.
_orig_stderr = sys.stderr


class _LibPngSilencer:
    def write(self, s):
        if 'libpng warning: iCCP' not in s:
            if _orig_stderr is not None:
                _orig_stderr.write(s)

    def flush(self):
        if _orig_stderr is not None:
            _orig_stderr.flush()


sys.stderr = _LibPngSilencer()

from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtCore import Qt

from src.i18n import tr
from src.models import SessionConfig
from src.ui.dpi import configure_high_dpi
from src.ui.main_window import MainWindow


def is_admin() -> bool:
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def relaunch_as_admin() -> bool:
    """Re-launch the current process elevated via ShellExecuteW('runas').

    Returns True if the elevation request was issued (caller should exit),
    False if it could not be attempted. Distinguishes PyInstaller frozen
    mode (re-launch the exe) from dev mode (re-launch `python -m src.main`).
    """
    ShellExecuteW = ctypes.windll.shell32.ShellExecuteW
    ShellExecuteW.restype = ctypes.c_void_p
    ShellExecuteW.argtypes = [
        ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_wchar_p,
        ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_int,
    ]

    params = []
    if not getattr(sys, "frozen", False):
        # Dev: python -m src.main [args...]
        params.extend(["-m", "src.main"])
    params.extend(sys.argv[1:])
    param_str = subprocess.list2cmdline(params)

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    hinst = ShellExecuteW(None, "runas", sys.executable, param_str, project_root, 1)
    return int(hinst or 0) > 32


def _debug_log_path() -> str:
    """Resolve the debug log path under a writable temp/ dir.

    Dev: <project_root>/temp/igp_debug.log.
    Frozen (PyInstaller): <exe_dir>/temp/igp_debug.log, since the bundled
    _MEIPASS extraction dir is read-only / ephemeral.
    """
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    temp_dir = os.path.join(base, "temp")
    os.makedirs(temp_dir, exist_ok=True)
    return os.path.join(temp_dir, "igp_debug.log")


def setup_logging(debug: bool = False):
    handlers = []
    if sys.stdout is not None:
        handlers.append(logging.StreamHandler(sys.stdout))
    if debug:
        log_path = _debug_log_path()
        handlers.append(logging.FileHandler(log_path, mode="w", encoding="utf-8"))
    if not handlers:
        handlers.append(logging.NullHandler())
    logging.basicConfig(
        level=logging.DEBUG if debug else logging.INFO,
        format="%(asctime)s [%(levelname)-7s] %(name)s: %(message)s",
        handlers=handlers,
        force=True,
    )
    if debug:
        logging.getLogger().info(f"Debug log: {log_path}")


def show_admin_required_and_exit():
    """Show a clean error dialog and exit when not running as admin."""
    configure_high_dpi()
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    msg = QMessageBox()
    msg.setIcon(QMessageBox.Critical)
    msg.setWindowTitle(tr("admin_required_title"))
    msg.setText(tr("admin_required_text"))
    msg.setDetailedText(tr("admin_required_detail"))
    msg.setStandardButtons(QMessageBox.Ok)
    msg.exec_()
    sys.exit(1)


def _default_headless_output(process_names: list[str]) -> str:
    """Default CSV output path under temp/."""
    from datetime import datetime
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    temp_dir = os.path.join(base, "temp")
    os.makedirs(temp_dir, exist_ok=True)
    app = (process_names[0] if process_names else "capture").replace(".exe", "").replace(" ", "_")
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    return os.path.join(temp_dir, f"igpmon-{app}-{ts}.csv")


def run_headless_capture(args) -> int:
    """Headless capture: PresentMon + metrics sampler → CSV + stats file (no UI).

    Reuses the same core modules as the GUI (PresentMonWrapper, DataStore,
    SystemMetricsSampler, csv_export helpers). Supports timed runs and, with
    ``--timed 0``, continuous capture until Ctrl+C.
    """
    import csv
    from src.core.capture_session import CaptureSession
    from src.ui.dialogs.csv_export import (
        CSV_EXPORT_HEADER_V2, _frame_to_row, _build_sys_info_rows,
        _write_comment_row, write_stats,
    )

    session = CaptureSession()
    data_store = session.data_store

    process_names = [] if args.all_processes else args.process_name
    timed = max(0, args.timed)
    config = SessionConfig(
        process_names=process_names,
        process_ids=args.process_id,
        exclude_names=args.exclude or [],
        timed_seconds=timed,
        track_display=not args.no_track_display,
        track_input=not args.no_track_input,
        track_gpu=not args.no_track_gpu,
    )

    target = "all processes" if not process_names and not args.process_id else f"{process_names or args.process_id}"
    logging.info("Headless capture target: %s (timed=%ss)", target, timed or "continuous")

    output_path = args.output or _default_headless_output(process_names)

    try:
        # Blocks until PresentMon exits (timed) or Ctrl+C (continuous)
        session.run_blocking(config)
    except KeyboardInterrupt:
        logging.info("Interrupted by user (Ctrl+C) — flushing captured data...")
    finally:
        session.stop()

    frames = data_store.get_all_frames()
    print(f"Captured frames: {len(frames)}")
    if not frames:
        print("No frames parsed. Check temp/igp_debug.log for PresentMon stderr.")
        return 2

    # Write CSV (system info header + column header + frame rows)
    with open(output_path, "w", newline="") as f:
        writer = csv.writer(f)
        for row in _build_sys_info_rows(data_store):
            _write_comment_row(f, row)
        writer.writerow(CSV_EXPORT_HEADER_V2)
        for frame in frames:
            writer.writerow(_frame_to_row(frame))
    write_stats(output_path, data_store, frames)

    counts = Counter(frame.application or f"pid_{frame.process_id}" for frame in frames)
    print(f"Wrote {len(frames)} frames + stats -> {output_path}")
    for name, count in counts.most_common(5):
        print(f"  {name}: {count}")
    return 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--headless", action="store_true",
                        help="headless capture to CSV (no UI)")
    parser.add_argument("--capture-debug", action="store_true",
                        help="(legacy alias for --headless)")
    parser.add_argument("--process-name", action="append", default=[])
    parser.add_argument("--process-id", action="append", type=int, default=[])
    parser.add_argument("--exclude", action="append", default=[])
    parser.add_argument("--all-processes", action="store_true")
    parser.add_argument("--timed", type=int, default=5,
                        help="capture seconds (0 = continuous, Ctrl+C to stop)")
    parser.add_argument("--output", "-o", default="", help="output CSV path (headless)")
    parser.add_argument("--no-track-display", action="store_true")
    parser.add_argument("--no-track-input", action="store_true")
    parser.add_argument("--no-track-gpu", action="store_true")
    args = parser.parse_args()

    headless = args.headless or args.capture_debug
    setup_logging(args.debug or headless)

    # Admin check — must come before QApplication for main UI
    if not is_admin():
        if relaunch_as_admin():
            sys.exit(0)
        show_admin_required_and_exit()

    if headless:
        sys.exit(run_headless_capture(args))

    configure_high_dpi()
    app = QApplication(sys.argv)
    app.setApplicationName(tr("window_title"))
    app.setOrganizationName("IGP")
    app.setStyle("Fusion")

    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
