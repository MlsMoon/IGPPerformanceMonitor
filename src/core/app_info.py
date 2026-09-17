"""Application identity and version info."""

import sys
from pathlib import Path

APP_DISPLAY_NAME = "IGP Performance Monitor"
APP_EXE_NAME = "IGPPerformanceMonitor.exe"
AUTO_UPDATER_EXE_NAME = "auto_updater.exe"
GITHUB_OWNER = "MlsMoon"
GITHUB_REPO = "IGPPerformanceMonitor"
GITHUB_REPO_URL = f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}"


def github_asset_url(
    version: str,
    filename: str,
    *,
    owner: str = GITHUB_OWNER,
    repo: str = GITHUB_REPO,
) -> str:
    """Direct download URL for a GitHub Release asset (`vX.Y.Z` tag)."""
    return f"https://github.com/{owner}/{repo}/releases/download/v{version}/{filename}"


def github_latest_manifest_url(
    *,
    owner: str = GITHUB_OWNER,
    repo: str = GITHUB_REPO,
) -> str:
    """Stable URL for the latest published `app_manifest.json`."""
    return f"https://github.com/{owner}/{repo}/releases/latest/download/app_manifest.json"


DEFAULT_APP_MANIFEST_URL = github_latest_manifest_url()


def is_dev_mode() -> bool:
    """True when running from source, not the packaged EXE."""
    return not getattr(sys, "frozen", False)


def resource_root() -> Path:
    """Resource root: PyInstaller _MEIPASS when frozen, else project root."""
    if getattr(sys, "frozen", False):
        bundle_root = getattr(sys, "_MEIPASS", "")
        if bundle_root:
            return Path(bundle_root)
    return Path(__file__).resolve().parents[2]


def _load_version() -> str:
    """Read semantic version from the VERSION file (single source of truth)."""
    version_file = resource_root() / "VERSION"
    try:
        v = version_file.read_text(encoding="utf-8").strip()
    except OSError:
        return "0.0.0"
    return v or "0.0.0"


def _load_build_metadata() -> str | None:
    """Read build metadata (timestamp+sha) from build_info.txt, or None if absent (dev)."""
    build_info = resource_root() / "build" / "generated" / "build_info.txt"
    try:
        b = build_info.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return b or None


def parse_version(v: str) -> tuple[int, int, int]:
    """Parse a semver string into a comparable (major, minor, patch) tuple.

    Strips build metadata (+...) and pre-release (-...). Non-numeric / missing
    segments fall back to 0, so 'dev' or malformed values compare as (0, 0, 0).
    """
    core = str(v).split('+', 1)[0].split('-', 1)[0].strip()
    parts = core.split('.')
    nums = [int(p) if p.isdigit() else 0 for p in parts]
    while len(nums) < 3:
        nums.append(0)
    return (nums[0], nums[1], nums[2])


APP_VERSION = _load_version()
APP_BUILD = _load_build_metadata()
