"""User configuration: a JSON file at %APPDATA%/IGPPerformanceMonitor/config.json.

Single editable settings file (theme, locale, chart_visibility, ...). Replaces the old
QSettings (Windows registry) persistence; on first run the legacy registry
values are migrated here so no preference is lost.

Conventions (match the existing AppData usage in app_update_service /
replace_service): flat ``IGPPerformanceMonitor/`` folder, UTF-8 without BOM,
``json.dumps(indent=2)``. Writes are atomic (temp file + os.replace).
"""

import json
import os
import tempfile
from pathlib import Path


def config_dir() -> Path:
    """Directory for config.json. ``IGP_CONFIG_DIR`` overrides (self-check)."""
    override = os.environ.get("IGP_CONFIG_DIR", "").strip()
    if override:
        return Path(override)
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    return Path(base) / "IGPPerformanceMonitor"


def config_path() -> Path:
    """%APPDATA%/IGPPerformanceMonitor/config.json (APPDATA read at call time)."""
    return config_dir() / "config.json"


def load_config() -> dict:
    """Read the config file; on first run migrate from the registry and persist."""
    p = config_path()
    if not p.exists():
        cfg = _migrate_from_registry()
        save_config(cfg)
        return cfg
    try:
        data = json.loads(p.read_text(encoding="utf-8-sig"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_config(cfg: dict) -> None:
    """Write config atomically (temp file in the same dir, then os.replace)."""
    p = config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(cfg, ensure_ascii=False, indent=2)
    fd, tmp = tempfile.mkstemp(dir=str(p.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, p)
    except Exception:
        try:
            os.remove(tmp)
        except Exception:
            pass
        raise


def get(key, default=None):
    return load_config().get(key, default)


def set(key, value):
    cfg = load_config()
    cfg[key] = value
    save_config(cfg)


def _migrate_from_registry() -> dict:
    """Seed config from the legacy QSettings (registry) on first run."""
    from PyQt5.QtCore import QSettings

    s = QSettings("IGP", "IGPPerformanceMonitor")
    theme = s.value("theme", "dark")
    cfg = {"theme": "light" if theme == "light" else "dark"}
    vis_raw = s.value("chart_visibility", "")
    if vis_raw:
        try:
            parsed = json.loads(vis_raw)
            if isinstance(parsed, dict):
                cfg["chart_visibility"] = parsed
        except Exception:
            pass
    return cfg
