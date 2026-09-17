# 08 · Build / installer / GitHub Release

## Key files

- `VERSION` — semver single source
- `CHANGELOG.md` — Help → Changelog
- `docs/` — Help → User Manual (all locales)
- `assets/icon.png` / `assets/icon.ico` / `assets/logo.png` — window, EXE, installer, README
- `Scripts/make_icons.py` — cuts the tiles against transparency and rebuilds `icon.ico`
- `Scripts/build.bat` — PyInstaller (main + updater)
- `Scripts/build_installer.bat` + `Scripts/installer.iss` — Inno Setup 6
- `Scripts/generate_manifest.py` — `app_manifest.json`
- `.github/workflows/ci.yml` — offscreen tests
- `.github/workflows/release.yml` — tag `vX.Y.Z` → artifacts + GitHub Release

## Responsibilities

Build the portable EXE, updater, Windows installer, and publish them on GitHub Releases. CI is the production publisher.

## Pitfalls

- **`build.bat` reads `VERSION`**, writes `build/generated/build_info.txt` = timestamp-gitsha (`APP_BUILD`, **not** the version).
- **Bundle:** PresentMon, `VERSION`, `CHANGELOG.md`, `docs/`, `build_info.txt`, `assets/icon.png` (+ ico). New resources need `--add-data`. The installer also copies `docs\` next to the EXE for browsing on disk; the onefile EXE still reads them from `_MEIPASS`.
- **EXE icon** is `assets/icon.ico`. Window icon is `assets/icon.png`. Update **both** (and `logo.png` if the brand mark changes).
- **Icon art must be transparent outside the tile.** The generated PNGs shipped as opaque white in the corners, which drew a white frame around the desktop/taskbar icon and around the README logo on GitHub's dark theme. After replacing any art, run `python Scripts/make_icons.py` — it re-cuts the rounded tile against alpha and regenerates `icon.ico` at all seven sizes (16→256; Windows rescales badly if a size is missing). It is idempotent, so re-running is safe. Verify with `Image.open(p).convert("RGBA").getpixel((1, 1))[3] == 0`.
- **`--uac-admin`** + installer `PrivilegesRequired=admin`. PresentMon needs elevation.
- **Installer does not ship `auto_updater.exe`.** The client downloads it on update.
- **CI sets `CI=true`** so `build.bat` skips `pause`.
- **Inno Setup 6** (`ISCC.exe`) is required for the installer. CI installs it with Chocolatey.
- **Publish path:** bump VERSION on `develop` → changelog → tests → fast-forward `release` → annotated tag `vX.Y.Z` → `release.yml`. Do not upload to object storage.
- **Branches:** `develop` (default) and `release` (tags). Both are protected: no force-push, no delete.
- **Tag must match VERSION.** The workflow fails if `github.ref_name != v$(VERSION)`.
- **Manifest hashes must be non-empty** 64-char hex. `generate_manifest.py` hashes local `dist\` files and points URLs at the **upcoming** tag assets.
- **`previous`:** `generate_manifest.py` fetches the current latest manifest (best-effort) and embeds it when the version differs. First GitHub Release may have `previous: null`.
- **GitHub `User-Agent`:** required for fetch/download.
- **No secrets in scripts.** Release uses `GITHUB_TOKEN` only.
- **Do not commit `third-party/ossutil.exe`.**

## Checklist

- [ ] New resource files → `--add-data` + frozen `resource_root()` path (docs go in both the EXE and `installer.iss`)
- [ ] Icon change → `Scripts/make_icons.py`, then check the corners are transparent on a dark background
- [ ] Version → only `VERSION`
- [ ] Release → VERSION + CHANGELOG + tests + annotated tag + Actions green
- [ ] Release assets include portable EXE, updater, Setup EXE, `app_manifest.json`

---
last_updated: 2026-09-17

