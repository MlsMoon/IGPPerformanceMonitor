"""Self-checks driven by launch flags, written to be read by an agent.

    python -m src.main -t ui                    # build the real window, dump PNGs
    python -m src.main -t capture -a Unity.exe -s 8
    python -m src.main -t update
    python -m src.main -t all
    python -m src.selfcheck plan            # what to run for the current diff

Areas are discovered from ``*_area.py`` (each exports ``AREA`` + ``run``).
Adding a file is enough — ``-t all`` and the planner pick it up.

Each area exercises real code and prints what it observed. The exit code only
reflects things that are provably broken (an exception, a corrupted download, a
capture that produced nothing). Judgement calls — whether a fill rate, a layout
or a frame count looks right — are printed as facts and SUSPECT lines for the
caller to weigh, because they have no machine-checkable threshold.

Output lands in ``temp/selfcheck/`` (gitignored), including screenshots.
"""

from __future__ import annotations

import os
import sys

from src.selfcheck.discover import area_names, get as load_area, discover
from src.selfcheck.report import Report

# Qt warnings raised during a run (stylesheet parse failures, layout
# complaints). Collected rather than printed so they land in the report.
qt_messages: list[str] = []

# Noise from the offscreen platform and a font-less Qt install — not our code.
_QT_NOISE = (
    "QFontDatabase",
    "Qt no longer ships fonts",
    "This plugin does not support",
    "propagateSizeHints",
)


def output_dir() -> str:
    """``temp/selfcheck`` next to the project (or the exe when frozen)."""
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    path = os.path.join(base, "temp", "selfcheck")
    os.makedirs(path, exist_ok=True)
    return path


def run(areas: list[str], *, app: list[str] | None = None, seconds: int = 8) -> int:
    """Run *areas* and return a process exit code."""
    if "all" in areas:
        areas = list(area_names())

    # The report is the product here, and per-frame parser logging buries it.
    import logging
    logging.getLogger().setLevel(logging.WARNING)

    # The report carries translated UI strings; a GBK console mangles them.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError):
            pass

    out_dir = output_dir()
    report_path = os.path.join(out_dir, "report.txt")
    failed = 0
    tee = _Tee(sys.stdout, report_path)
    sys.stdout = tee

    specs = {spec.name: spec for spec, _run in discover()}
    if any(specs[name].needs_qt for name in areas if name in specs):
        _start_qt()

    try:
        for area in areas:
            print(f"\n{'=' * 66}\n=== selfcheck: {area} ===\n{'=' * 66}")
            report = Report(area)
            try:
                _spec, run_area = load_area(area)
                run_area(report, out_dir, app=app, seconds=seconds)
            except Exception as exc:
                import traceback
                report.error(f"{area} aborted: {type(exc).__name__}: {exc}")
                print(traceback.format_exc())
            failed |= report.summary()

        print(f"\noutput: {out_dir}")
        print(f"report: {report_path}")
    finally:
        sys.stdout = tee.restore()
        tee.close()
    return failed


class _Tee:
    """Write the report to a file as well as stdout, so a later reader can find it."""

    def __init__(self, stream, path: str) -> None:
        self._stream = stream
        self._file = open(path, "w", encoding="utf-8")

    def write(self, data):
        self._stream.write(data)
        self._file.write(data)

    def flush(self):
        self._stream.flush()
        self._file.flush()

    def restore(self):
        return self._stream

    def close(self):
        self._file.close()


def _start_qt() -> None:
    """Offscreen QApplication, with the real config sandboxed away.

    The UI area builds a real MainWindow and calls real slots, several of which
    persist theme and layout. Without redirecting APPDATA a self-check rewrites
    the developer's own settings — it has flipped a machine to the light theme
    before.
    """
    import tempfile

    # Deliberately NOT forcing offscreen. That platform ships no fonts here, so
    # every label grabs as blank and the screenshots — the whole point of this
    # area — become unreadable. Windows always has a session, and the window is
    # grabbed without ever being shown, so nothing flashes on screen. CI can
    # still opt in by exporting QT_QPA_PLATFORM=offscreen.
    global _CONFIG_SANDBOX
    _CONFIG_SANDBOX = tempfile.TemporaryDirectory(prefix="igp-selfcheck-appdata-")
    os.environ["APPDATA"] = _CONFIG_SANDBOX.name

    from PyQt5.QtCore import qInstallMessageHandler
    from PyQt5.QtWidgets import QApplication

    def _collect(_mode, _context, message):
        if not any(noise in message for noise in _QT_NOISE):
            qt_messages.append(message)

    qInstallMessageHandler(_collect)

    from src.ui.dpi import configure_high_dpi
    configure_high_dpi()
    # Must stay referenced: a QApplication that goes out of scope is collected,
    # and the next QWidget aborts the process with "Must construct a
    # QApplication before a QWidget".
    global _APP
    _APP = QApplication.instance() or QApplication(sys.argv)


def needs_admin(areas: list[str]) -> bool:
    if "all" in areas:
        areas = list(area_names())
    specs = {spec.name: spec for spec, _run in discover()}
    return any(specs[name].needs_admin for name in areas if name in specs)


def __getattr__(name: str):
    # Older call sites used ``selfcheck.AREAS`` as a tuple. Keep that working
    # without importing every area at package import time.
    if name == "AREAS":
        return area_names()
    raise AttributeError(name)
