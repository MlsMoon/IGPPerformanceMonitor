# 08 · Build / installer / GitHub Release

## Key files

- `VERSION` — semver single source
- `CHANGELOG.md` / `CHANGELOG.zh-CN.md` — Help → Changelog (UI locale)
- `Scripts/extract_release_notes.py` — bilingual GitHub Release body
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
- **Bundle:** PresentMon, `VERSION`, `CHANGELOG.md`, `CHANGELOG.zh-CN.md`, `docs/`, `src/i18n/locales/`, `build_info.txt`, `assets/icon.png` (+ ico). JSON catalogs go in the EXE via `--add-data` (`src/i18n/locales` → `_MEIPASS/src/i18n/locales`); the installer does not copy them next to the EXE. `docs/` is both `--add-data` and an Inno `Source:` so users can browse the manual on disk.
- **GitHub Release body** is `extract_release_notes.py` output (`body_path`).
  `generate_release_notes: false`. Auto-notes shipped 0.1.0–0.1.3 as only
  `Full Changelog: vA...vB` — do not turn that back on.
- **EXE icon** is `assets/icon.ico`. Window icon is `assets/icon.png`. Update **both** (and `logo.png` if the brand mark changes).
- **Icon art must be transparent outside the tile.** The generated PNGs shipped as opaque white in the corners, which drew a white frame around the desktop/taskbar icon and around the README logo on GitHub's dark theme. After replacing any art, run `python Scripts/make_icons.py` — it re-cuts the rounded tile against alpha and regenerates `icon.ico` at all seven sizes (16→256; Windows rescales badly if a size is missing). It is idempotent, so re-running is safe. Verify with `Image.open(p).convert("RGBA").getpixel((1, 1))[3] == 0`.
- **README docs links sit under the logo, not above it.** Repo and `docs/<locale>/README.md` use a centered `<strong>` action row (Download / User guide / 使用指南 / …) plus a Documentation section. A second ` · ` line next to the language switcher is invisible. Do not put the user-guide link there. All four locale READMEs stay on the same layout (`docs/README.md`).
- **`--uac-admin`** + installer `PrivilegesRequired=admin`. PresentMon needs elevation.
- **Installer does not ship `auto_updater.exe`.** The client downloads it on update.
- **CI sets `CI=true`** so `build.bat` skips `pause`.
- **Inno Setup 6** (`ISCC.exe`) is required for the installer. CI installs it with Chocolatey.
- **Publish path:** bump VERSION on `develop` → changelog → tests → fast-forward `release` → annotated tag `vX.Y.Z` → `release.yml`. Do not upload to object storage.
- **Branches:** develop **only** on `develop`. `release` is tags: fast-forward from `develop`, no feature commits. Both are protected: no force-push, no delete.
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
- [ ] Release → VERSION + both changelog files + extract_release_notes preview + tests + annotated tag + Actions green
- [ ] Release assets include portable EXE, updater, Setup EXE, `app_manifest.json`

---
last_updated: 2026-09-20

