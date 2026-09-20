# 06 · Version and self-update

## Key files

- `src/core/app_info.py` — `VERSION` (semver single source), `APP_BUILD`, `parse_version`, `GITHUB_*`, `DEFAULT_APP_MANIFEST_URL`, `github_asset_url`
- `src/core/release_manifest.py` — build / write / fetch `app_manifest.json` (UTF-8, no BOM, User-Agent)
- `src/core/app_update_service.py` — fetch latest GitHub Release manifest, compare, download, verify, launch updater
- `src/ui/dialogs/update_progress.py` — `UpdateProgressDialog` + `_InstallWorker` (download/install) + `ManifestWorker` (check / fetch JSON)
- `src/auto_updater/*` — standalone swapper (wait for parent → replace exe → restart)
- `Scripts/generate_manifest.py` — local/CI helper after `build.bat` / installer

## Responsibilities

Version numbers, and check / download / install updates **only** from GitHub Releases.

## Conventions (must keep)

- **Publisher is GitHub Releases.** Asset set for tag `vX.Y.Z`:
  - `IGPPerformanceMonitor.exe` (portable; in-app update target)
  - `auto_updater.exe`
  - `IGPPerformanceMonitor-Setup-X.Y.Z.exe` (installer; humans, not the updater)
  - `app_manifest.json` (client contract)
- **Client URL is latest-download**, not the REST API (avoids unauthenticated rate limits):
  `https://github.com/MlsMoon/IGPPerformanceMonitor/releases/latest/download/app_manifest.json`
- **Asset URLs are versioned:** `.../releases/download/vX.Y.Z/<file>`
- **Never** add object-storage upload scripts, access keys, or a second update channel.
- **`VERSION` is the only semver source.** Tag must be `v` + that value.
- **`APP_BUILD` ≠ version.** It comes from `build/generated/build_info.txt`.
- **Compare with `parse_version()` tuples**, never string `>` (`1.2.10` vs `1.2.9`).
- **Manifest is UTF-8 without BOM.** Read `utf-8-sig`; write UTF-8 no BOM. Empty SHA256 is a hard failure.
- **HTTP needs a User-Agent.** Use `release_manifest.open_url`.
- **`previous` block** is the last published current (same required fields). Rollback UI calls `install_update(previous)` and bypasses the downgrade guard. `previous` null → "no previous version".
- **Updater flow:** download main + updater, verify size/sha256, copy updater to `%APPDATA%/IGPPerformanceMonitor/auto_updater.exe`, start it, exit. Updater waits, backups, replaces, writes `app_state.json`, restarts.
- **Startup check** is packaged-only, delayed 1.5s, silent unless an update exists.
- **Dev never self-updates.**
- **`install_update` must not run on the GUI thread.** It is ~55 MB over the network; inline it froze the window for the whole download behind a status-bar string. Both entry points (update and rollback) go through `MainWindow._run_install` → `UpdateProgressDialog`, which runs the install on a `QThread` and drives a real bar.
- **`check_for_update` / `fetch_manifest` must not run on the GUI thread either.** urllib's 20s timeout froze Help → Check for Updates. `ManifestWorker` (same file as `_InstallWorker`) does the JSON fetch. `MainWindow` sets the status bar to `update_checking`, disables the two Help actions while in flight, and shows the existing `QMessageBox` results on the GUI thread. Ignore a second click while a check is running. Do **not** add a progress dialog for a JSON fetch. Dev-mode early return (no network) stays on the GUI thread. Silent startup check uses the same worker; still no modal unless an update exists.
- **Progress is bytes, not strings.** `install_update(progress=...)` emits `UpdateProgress(stage, received, total)`. `total` is 0 when the server sends no `Content-Length`; show that as an indeterminate bar, never as 0%. Verification reports progress too — SHA256 over 55 MB looks like a hang on its own.
- **Cancellation deletes the partial file outside the `with` block.** Windows refuses to unlink a file whose handle is still open, so `_download` catches `AppUpdateCancelled` after the context manager closes and only then discards.

## Checklist

- [ ] Version bump → only `VERSION` (then release skill)
- [ ] Version compare → `parse_version`
- [ ] Manifest → no BOM, non-empty hashes, GitHub asset URLs
- [ ] Update flow → tested with a packaged EXE (old → new) after a real GitHub Release
- [ ] Long-running update work → off the GUI thread, reporting bytes, cancellable
- [ ] Manifest fetch / version check → off the GUI thread (`ManifestWorker`); Help actions stay disabled while in flight
- [ ] No credentials or alternate CDN URLs added

---
last_updated: 2026-09-18
