# 06 · Version and self-update

## Key files

- `src/core/app_info.py` — `VERSION` (semver single source), `APP_BUILD`, `parse_version`, `GITHUB_*`, `DEFAULT_APP_MANIFEST_URL`, `github_asset_url`
- `src/core/release_manifest.py` — build / write / fetch `app_manifest.json` (UTF-8, no BOM, User-Agent)
- `src/core/app_update_service.py` — fetch latest GitHub Release manifest, compare, download, verify, launch updater
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

## Checklist

- [ ] Version bump → only `VERSION` (then release skill)
- [ ] Version compare → `parse_version`
- [ ] Manifest → no BOM, non-empty hashes, GitHub asset URLs
- [ ] Update flow → tested with a packaged EXE (old → new) after a real GitHub Release
- [ ] No credentials or alternate CDN URLs added

---
last_updated: 2026-09-17
