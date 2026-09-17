"""IGP offscreen test suite.

Run all tests:  python -m src.tests   (QT_QPA_PLATFORM=offscreen is auto-set below)

A module's ``run()`` may raise ``SkipTest`` (from ``src.tests._factory``) to SKIP
instead of fail — used by real-data tests when the capture can't be generated.
"""

import sys
import os
import tempfile
import traceback

from src.tests._factory import SkipTest

# Force the offscreen Qt platform so the suite runs without a display server.
# A caller-set value wins (setdefault). Must precede any QApplication creation.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# Redirect the config file into a throwaway directory. The UI tests build a real
# MainWindow and call real slots, several of which persist (theme, chart
# visibility, splitter state), so without this the suite quietly rewrites the
# developer's own settings — it has already flipped a machine to the light theme
# once. app_config reads APPDATA on every call, so setting it here is enough.
_CONFIG_SANDBOX = tempfile.TemporaryDirectory(prefix="igp-tests-appdata-")
os.environ["APPDATA"] = _CONFIG_SANDBOX.name

# ── Suppress libpng iCCP noise during tests (same as main.py) ──
_orig_stderr = sys.stderr


class _LibPngSilencer:
    def write(self, s):
        if "libpng warning: iCCP" not in s:
            _orig_stderr.write(s)

    def flush(self):
        _orig_stderr.flush()


sys.stderr = _LibPngSilencer()

# ── Test order ──────────────────────────────────────────────────
# Qt-free first (no QApplication needed), then Qt-dependent tests
# that share a single QApplication instance.

NON_QT = [
    "test_models",
    "test_i18n",
    "test_data_store",
    "test_csv",
    "test_app_config",
    "test_main_logging",
    "test_metrics_sampler",
    "test_capture_session",
    "test_filters",
    "test_stutter_analysis",
    "test_system_metrics",
    "test_release_manifest",
    "test_app_update_service",
]

QT = [
    "test_theme",
    "test_ui_main",
    "test_ui_overlay",
    "test_ui_process_panel",
    "test_ui_csv_analysis",
    "test_user_manual",
]


def _run_module(name: str) -> tuple[str, str | None]:
    """Run *name*'s ``run()``; return (status, detail).

    status is "pass", "skip" (SkipTest), or "fail" (other exception).
    """
    mod = __import__(f"src.tests.{name}", fromlist=["run"])
    try:
        mod.run()
    except SkipTest as exc:
        return ("skip", str(exc))
    except Exception as exc:
        return ("fail", f"{exc}\n{traceback.format_exc()}")
    return ("pass", None)


def main() -> int:
    print("=== IGP Offscreen Smoke Tests ===\n")

    passed = skipped = failed = 0
    skipped_names: list[str] = []
    failed_names: list[str] = []

    def run_list(names: list[str]) -> None:
        nonlocal passed, skipped, failed
        for name in names:
            status, detail = _run_module(name)
            if status == "pass":
                print(f"  PASS  {name}")
                passed += 1
            elif status == "skip":
                print(f"  SKIP  {name}")
                skipped += 1
                skipped_names.append(name)
            else:
                first = (detail or "").split(chr(10))[0]
                print(f"  FAIL  {name}: {first}")
                failed += 1
                failed_names.append(name)

    # ── Non-Qt ──
    run_list(NON_QT)

    # ── Qt (single QApplication) ──
    from PyQt5.QtWidgets import QApplication
    from src.ui.dpi import configure_high_dpi
    configure_high_dpi()
    app = QApplication.instance() or QApplication(sys.argv)
    run_list(QT)

    # ── Summary ──
    total = len(NON_QT) + len(QT)
    print(f"\n{passed} passed, {skipped} skipped, {failed} failed  ({total} total)")
    if skipped_names:
        print(f"SKIPPED: {', '.join(skipped_names)}")
    if failed:
        print(f"FAILED: {', '.join(failed_names)}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
