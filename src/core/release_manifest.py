"""GitHub Release app_manifest.json helpers.

The packaged app still consumes the same JSON contract as before
(``AppUpdateService``). The publisher is GitHub Releases, not object storage.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from src.core.app_info import (
    APP_EXE_NAME,
    APP_VERSION,
    AUTO_UPDATER_EXE_NAME,
    GITHUB_OWNER,
    GITHUB_REPO,
    github_asset_url,
    github_latest_manifest_url,
)

REQUIRED_MANIFEST_FIELDS = (
    "version",
    "mainExeName",
    "mainExeUrl",
    "mainExeSha256",
    "mainExeSize",
    "updaterExeName",
    "updaterExeUrl",
    "updaterExeSha256",
    "updaterExeSize",
    "updatedAt",
)

_USER_AGENT = (
    f"IGPPerformanceMonitor/{APP_VERSION} "
    f"(+https://github.com/{GITHUB_OWNER}/{GITHUB_REPO})"
)


def http_user_agent() -> str:
    return _USER_AGENT


def open_url(url: str, timeout: float = 20):
    """Open ``url`` with a GitHub-friendly User-Agent."""
    request = Request(url, headers={"User-Agent": _USER_AGENT})
    return urlopen(request, timeout=timeout)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(256 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_manifest(
    *,
    version: str,
    main_exe: Path,
    updater_exe: Path,
    installer_exe: Path | None = None,
    previous: dict[str, Any] | None = None,
    updated_at: str | None = None,
    owner: str = GITHUB_OWNER,
    repo: str = GITHUB_REPO,
) -> dict[str, Any]:
    """Build a release manifest pointing at GitHub Release assets."""
    if not version.strip():
        raise ValueError("version is empty")
    if not main_exe.is_file():
        raise FileNotFoundError(main_exe)
    if not updater_exe.is_file():
        raise FileNotFoundError(updater_exe)

    main_sha = sha256_file(main_exe)
    updater_sha = sha256_file(updater_exe)
    if not main_sha or not updater_sha:
        raise ValueError("SHA256 must not be empty")

    manifest: dict[str, Any] = {
        "version": version,
        "mainExeName": APP_EXE_NAME,
        "mainExeUrl": github_asset_url(version, APP_EXE_NAME, owner=owner, repo=repo),
        "mainExeSha256": main_sha,
        "mainExeSize": main_exe.stat().st_size,
        "updaterExeName": AUTO_UPDATER_EXE_NAME,
        "updaterExeUrl": github_asset_url(
            version, AUTO_UPDATER_EXE_NAME, owner=owner, repo=repo
        ),
        "updaterExeSha256": updater_sha,
        "updaterExeSize": updater_exe.stat().st_size,
        "updatedAt": updated_at or utc_now_iso(),
        "releasePageUrl": f"https://github.com/{owner}/{repo}/releases/tag/v{version}",
    }
    if installer_exe is not None and installer_exe.is_file():
        installer_name = installer_exe.name
        manifest["installerExeName"] = installer_name
        manifest["installerExeUrl"] = github_asset_url(
            version, installer_name, owner=owner, repo=repo
        )
        manifest["installerExeSha256"] = sha256_file(installer_exe)
        manifest["installerExeSize"] = installer_exe.stat().st_size

    if previous:
        manifest["previous"] = dict(previous)
    else:
        manifest["previous"] = None
    return manifest


def write_manifest(path: Path, manifest: dict[str, Any]) -> None:
    """Write UTF-8 JSON without a BOM."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
    path.write_text(payload, encoding="utf-8", newline="\n")


def load_manifest(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def fetch_previous_manifest(
    url: str | None = None,
    timeout: float = 20,
) -> dict[str, Any] | None:
    """Best-effort fetch of the currently published latest manifest."""
    target = url or github_latest_manifest_url()
    try:
        with open_url(target, timeout=timeout) as resp:
            payload = resp.read()
    except (HTTPError, URLError, TimeoutError, OSError):
        return None
    try:
        data = json.loads(payload.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict) or "version" not in data:
        return None
    return data


def snapshot_current_as_previous(manifest: dict[str, Any]) -> dict[str, Any]:
    """Keep the current release metadata as the next release's ``previous`` block."""
    return {key: manifest[key] for key in REQUIRED_MANIFEST_FIELDS if key in manifest}
