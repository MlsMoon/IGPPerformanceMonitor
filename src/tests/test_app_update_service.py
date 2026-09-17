"""Test AppUpdateService validation and version compare (no network)."""

from src.core.app_update_service import AppUpdateError, AppUpdateService
from src.core.release_manifest import REQUIRED_MANIFEST_FIELDS


def _valid_manifest() -> dict:
    return {
        "version": "1.2.3",
        "mainExeName": "IGPPerformanceMonitor.exe",
        "mainExeUrl": "https://github.com/MlsMoon/IGPPerformanceMonitor/releases/download/v1.2.3/IGPPerformanceMonitor.exe",
        "mainExeSha256": "a" * 64,
        "mainExeSize": 100,
        "updaterExeName": "auto_updater.exe",
        "updaterExeUrl": "https://github.com/MlsMoon/IGPPerformanceMonitor/releases/download/v1.2.3/auto_updater.exe",
        "updaterExeSha256": "b" * 64,
        "updaterExeSize": 50,
        "updatedAt": "2026-09-17T00:00:00Z",
    }


def run():
    service = AppUpdateService({"app_manifest_url": "https://example.invalid/app_manifest.json"})
    assert service.manifest_url.endswith("app_manifest.json")

    ok = service._validate(_valid_manifest())
    assert ok["version"] == "1.2.3"

    try:
        service._validate({"version": "1.0.0"})
        raise AssertionError("expected missing-field error")
    except AppUpdateError as exc:
        assert "Missing fields" in str(exc)

    try:
        service._validate(["not", "an", "object"])  # type: ignore[arg-type]
        raise AssertionError("expected type error")
    except AppUpdateError as exc:
        assert "object" in str(exc)

    for key in REQUIRED_MANIFEST_FIELDS:
        broken = _valid_manifest()
        del broken[key]
        try:
            service._validate(broken)
            raise AssertionError(f"expected missing {key}")
        except AppUpdateError:
            pass
