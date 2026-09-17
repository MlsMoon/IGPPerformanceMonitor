"""Test: main logging survives PyInstaller windowed mode with no console streams."""

import logging
import os
import tempfile

from src import main as app_main


def run():
    old_stdout = app_main.sys.stdout
    old_stderr = app_main.sys.stderr
    old_orig_stderr = app_main._orig_stderr
    old_frozen = getattr(app_main.sys, "frozen", None)
    old_executable = app_main.sys.executable
    old_root_level = logging.getLogger().level

    with tempfile.TemporaryDirectory() as td:
        try:
            app_main.sys.stdout = None
            app_main.sys.stderr = None
            app_main._orig_stderr = None

            app_main.setup_logging(False)
            logging.getLogger("test_main_logging").info("windowed no-debug")

            app_main.sys.frozen = True
            app_main.sys.executable = os.path.join(td, "IGPPerformanceMonitor.exe")
            app_main.setup_logging(True)
            logging.getLogger("test_main_logging").info("windowed debug")

            log_path = os.path.join(td, "temp", "igp_debug.log")
            assert os.path.exists(log_path), "debug log created beside frozen exe"
            text = open(log_path, encoding="utf-8").read()
            assert "Debug log:" in text
            assert "windowed debug" in text
        finally:
            app_main.sys.stdout = old_stdout
            app_main.sys.stderr = old_stderr
            app_main._orig_stderr = old_orig_stderr
            if old_frozen is None:
                try:
                    delattr(app_main.sys, "frozen")
                except AttributeError:
                    pass
            else:
                app_main.sys.frozen = old_frozen
            app_main.sys.executable = old_executable
            logging.basicConfig(handlers=[], level=old_root_level, force=True)
