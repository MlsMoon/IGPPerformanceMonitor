"""App update service — check, download, verify, install from GitHub Releases."""

import hashlib
import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from src.core.app_info import (
    APP_VERSION,
    AUTO_UPDATER_EXE_NAME,
    DEFAULT_APP_MANIFEST_URL,
    parse_version,
)
from src.core.release_manifest import REQUIRED_MANIFEST_FIELDS, open_url

try:
    from urllib.error import HTTPError, URLError
except ImportError:
    from urllib.error import HTTPError, URLError  # type: ignore[no-redef]

ProgressCallback = Callable[[str], None]


class AppUpdateError(RuntimeError):
    pass


@dataclass(frozen=True)
class AppUpdateCheckResult:
    status: str
    message: str
    current_version: str
    remote_version: str
    remote_manifest: dict | None = None
    can_install: bool = False


@dataclass(frozen=True)
class AppUpdateInstallResult:
    success: bool
    message: str
    target_version: str
    should_exit: bool = False


def _app_data_dir() -> Path:
    base = os.environ.get("APPDATA", os.path.expanduser("~"))
    return Path(base) / "IGPPerformanceMonitor"


def current_executable_path() -> Path | None:
    import sys
    if getattr(sys, "frozen", False):
        return Path(sys.executable)
    return None


class AppUpdateService:
    def __init__(self, config: dict | None = None) -> None:
        self.config = dict(config or {})
        self.manifest_url = str(
            self.config.get("app_manifest_url", DEFAULT_APP_MANIFEST_URL)
        ).strip()
        self._app_data = _app_data_dir()

    @property
    def downloads_dir(self) -> Path:
        return self._app_data / "downloads"

    @property
    def temp_dir(self) -> Path:
        return self._app_data / "temp"

    @property
    def updater_path(self) -> Path:
        return self._app_data / AUTO_UPDATER_EXE_NAME

    @property
    def state_path(self) -> Path:
        return self._app_data / "app_state.json"

    @property
    def log_path(self) -> Path:
        return self._app_data / "update.log"

    def ensure_dirs(self) -> None:
        for d in (self._app_data, self.downloads_dir, self.temp_dir):
            d.mkdir(parents=True, exist_ok=True)

    def can_self_update(self) -> bool:
        return current_executable_path() is not None

    def fetch_manifest(self) -> dict:
        if not self.manifest_url:
            raise AppUpdateError("Manifest URL is empty.")
        try:
            with open_url(self.manifest_url, timeout=20) as resp:
                payload = resp.read()
        except HTTPError as e:
            raise AppUpdateError(f"HTTP {e.code}") from e
        except URLError as e:
            raise AppUpdateError(f"Network error: {e.reason}") from e
        try:
            manifest = json.loads(payload.decode("utf-8-sig"))
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            raise AppUpdateError("Invalid JSON") from e
        return self._validate(manifest)

    def check_for_update(self) -> AppUpdateCheckResult:
        self.ensure_dirs()
        remote = self.fetch_manifest()
        remote_ver = str(remote["version"])
        local_v = parse_version(APP_VERSION)
        remote_v = parse_version(remote_ver)
        if local_v == remote_v:
            return AppUpdateCheckResult(
                status="up_to_date",
                message=f"Already up to date ({remote_ver}).",
                current_version=APP_VERSION,
                remote_version=remote_ver,
                remote_manifest=remote,
                can_install=self.can_self_update(),
            )
        # Prevent downgrade: if local is newer (e.g. test build), don't offer update
        if local_v > remote_v:
            return AppUpdateCheckResult(
                status="up_to_date",
                message=(
                    f"Local version ({APP_VERSION}) is newer than remote "
                    f"({remote_ver}) — skipping update."
                ),
                current_version=APP_VERSION,
                remote_version=remote_ver,
                remote_manifest=remote,
                can_install=False,
            )
        return AppUpdateCheckResult(
            status="update_available",
            message=f"Update available: {APP_VERSION} -> {remote_ver}",
            current_version=APP_VERSION,
            remote_version=remote_ver,
            remote_manifest=remote,
            can_install=self.can_self_update(),
        )

    def install_update(
        self, manifest: dict, progress: ProgressCallback | None = None
    ) -> AppUpdateInstallResult:
        self.ensure_dirs()
        if not self.can_self_update():
            raise AppUpdateError("Self-update only works in packaged EXE.")

        manifest = self._validate(manifest)
        target_exe = current_executable_path()
        if target_exe is None:
            raise AppUpdateError("Cannot determine current exe path.")

        version = str(manifest["version"])

        main_path = self.temp_dir / f"IGPPerformanceMonitor-{version}.exe"
        self._emit(progress, "Downloading...")
        self._download(str(manifest["mainExeUrl"]), main_path)
        self._emit(progress, "Verifying...")
        self._verify(main_path, int(manifest["mainExeSize"]), str(manifest["mainExeSha256"]))

        updater_path = self.temp_dir / f"auto_updater-{version}.exe"
        self._emit(progress, "Downloading updater...")
        self._download(str(manifest["updaterExeUrl"]), updater_path)
        self._verify(
            updater_path,
            int(manifest["updaterExeSize"]),
            str(manifest["updaterExeSha256"]),
        )

        self.updater_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(updater_path, self.updater_path)
        if updater_path.exists():
            updater_path.unlink()

        backup = target_exe.with_name(f"{target_exe.name}.bak")
        cmd = [
            str(self.updater_path),
            "--parent-pid", str(os.getpid()),
            "--source-exe", str(main_path),
            "--target-exe", str(target_exe),
            "--backup-exe", str(backup),
            "--state-path", str(self.state_path),
            "--target-version", version,
            "--updated-at", str(manifest["updatedAt"]),
            "--log-path", str(self.log_path),
            "--restart", "true",
        ]
        self._emit(progress, "Installing...")
        subprocess.Popen(cmd, close_fds=True)

        return AppUpdateInstallResult(
            success=True,
            message=f"Updating to {version}...",
            target_version=version,
            should_exit=True,
        )

    def _validate(self, m: dict) -> dict:
        if not isinstance(m, dict):
            raise AppUpdateError("Manifest must be an object.")
        missing = [k for k in REQUIRED_MANIFEST_FIELDS if k not in m]
        if missing:
            raise AppUpdateError(f"Missing fields: {missing}")
        return dict(m)

    def _download(self, url: str, dest: Path) -> None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            dest.unlink()
        try:
            with open_url(url, timeout=120) as resp, dest.open("wb") as out:
                while True:
                    chunk = resp.read(256 * 1024)
                    if not chunk:
                        break
                    out.write(chunk)
        except HTTPError as e:
            raise AppUpdateError(f"Download HTTP {e.code}") from e
        except URLError as e:
            raise AppUpdateError(f"Download failed: {e.reason}") from e

    def _verify(self, path: Path, size: int, sha256: str) -> None:
        if not path.exists():
            raise AppUpdateError("Download missing.")
        actual_size = path.stat().st_size
        if actual_size != size:
            raise AppUpdateError(f"Size mismatch: expected {size}, got {actual_size}.")
        h = hashlib.sha256()
        with path.open("rb") as f:
            while True:
                chunk = f.read(256 * 1024)
                if not chunk:
                    break
                h.update(chunk)
        if h.hexdigest().lower() != sha256.lower():
            raise AppUpdateError("SHA256 mismatch.")

    def _emit(self, cb: ProgressCallback | None, msg: str) -> None:
        if cb:
            cb(msg)
