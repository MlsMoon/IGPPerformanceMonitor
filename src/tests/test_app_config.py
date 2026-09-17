"""Test: app_config — real JSON config file in a temp APPDATA (no fakes)."""

import os
import tempfile

from src.core import app_config


def run():
    saved = os.environ.get("APPDATA")
    with tempfile.TemporaryDirectory() as td:
        os.environ["APPDATA"] = td
        try:
            # First get triggers migration from the registry -> a valid theme.
            assert app_config.get("theme", "dark") in ("dark", "light"), "valid theme"

            # String round-trip (theme).
            app_config.set("theme", "light")
            assert app_config.get("theme") == "light"

            # Dict round-trip (chart_visibility).
            app_config.set("chart_visibility", {"fps": True, "cpu": False})
            assert app_config.get("chart_visibility") == {"fps": True, "cpu": False}

            # The file materialized on disk.
            assert app_config.config_path().exists()
        finally:
            if saved is None:
                os.environ.pop("APPDATA", None)
            else:
                os.environ["APPDATA"] = saved
