"""Test GitHub Release manifest helpers.

These tests use tiny temp files (not capture data) because they only need
stable bytes for SHA256 / size. Real frames would not exercise this path.
"""

import json
from pathlib import Path

from src.core.app_info import (
    APP_EXE_NAME,
    AUTO_UPDATER_EXE_NAME,
    DEFAULT_APP_MANIFEST_URL,
    github_asset_url,
    github_latest_manifest_url,
    parse_version,
)
from src.core.release_manifest import (
    REQUIRED_MANIFEST_FIELDS,
    build_manifest,
    load_manifest,
    snapshot_current_as_previous,
    write_manifest,
)


def _touch_exe(path: Path, payload: bytes) -> Path:
    path.write_bytes(payload)
    return path


def run():
    assert DEFAULT_APP_MANIFEST_URL.startswith(
        "https://github.com/MlsMoon/IGPPerformanceMonitor/releases/latest/download/"
    )
    assert github_latest_manifest_url().endswith("/app_manifest.json")
    assert github_asset_url("1.2.3", APP_EXE_NAME).endswith(
        "/releases/download/v1.2.3/IGPPerformanceMonitor.exe"
    )
    assert parse_version("1.2.10") > parse_version("1.2.9")

    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        main_exe = _touch_exe(root / APP_EXE_NAME, b"main-bytes")
        updater_exe = _touch_exe(root / AUTO_UPDATER_EXE_NAME, b"updater-bytes")
        installer_exe = _touch_exe(root / "IGPPerformanceMonitor-Setup-1.2.3.exe", b"setup")

        previous = {
            "version": "1.2.2",
            "mainExeName": APP_EXE_NAME,
            "mainExeUrl": github_asset_url("1.2.2", APP_EXE_NAME),
            "mainExeSha256": "a" * 64,
            "mainExeSize": 10,
            "updaterExeName": AUTO_UPDATER_EXE_NAME,
            "updaterExeUrl": github_asset_url("1.2.2", AUTO_UPDATER_EXE_NAME),
            "updaterExeSha256": "b" * 64,
            "updaterExeSize": 11,
            "updatedAt": "2026-01-01T00:00:00Z",
        }
        manifest = build_manifest(
            version="1.2.3",
            main_exe=main_exe,
            updater_exe=updater_exe,
            installer_exe=installer_exe,
            previous=previous,
            updated_at="2026-09-17T00:00:00Z",
        )
        for key in REQUIRED_MANIFEST_FIELDS:
            assert key in manifest, key
        assert manifest["version"] == "1.2.3"
        assert manifest["mainExeUrl"].endswith("/v1.2.3/IGPPerformanceMonitor.exe")
        assert manifest["installerExeName"] == "IGPPerformanceMonitor-Setup-1.2.3.exe"
        assert len(manifest["mainExeSha256"]) == 64
        assert manifest["previous"]["version"] == "1.2.2"

        out = root / "app_manifest.json"
        write_manifest(out, manifest)
        raw = out.read_bytes()
        assert not raw.startswith(b"\xef\xbb\xbf"), "manifest must be UTF-8 without BOM"
        loaded = load_manifest(out)
        assert loaded["version"] == "1.2.3"
        snap = snapshot_current_as_previous(loaded)
        assert set(REQUIRED_MANIFEST_FIELDS) <= set(snap)
        assert json.loads(out.read_text(encoding="utf-8"))["previous"]["version"] == "1.2.2"
