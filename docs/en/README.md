# IGP Performance Monitor

<p align="center">
  <img src="../../assets/logo.png" alt="IGP Performance Monitor" width="128" height="128">
</p>

<p align="center">
  Windows desktop monitor for real-time graphics performance.
</p>

<p align="center">
  <a href="https://github.com/MlsMoon/IGPPerformanceMonitor/releases/latest"><strong>Download</strong></a>
  &nbsp;·&nbsp;
  <a href="user-guide.md"><strong>User guide</strong></a>
  &nbsp;·&nbsp;
  <a href="troubleshooting.md"><strong>Troubleshooting</strong></a>
  &nbsp;·&nbsp;
  <a href="../../CHANGELOG.md"><strong>Changelog</strong></a>
</p>

<p align="center">
  <a href="README.md">English</a>
  ·
  <a href="../zh-CN/README.md">简体中文</a>
  ·
  <a href="../zh-TW/README.md">繁體中文</a>
  ·
  <a href="../ja/README.md">日本語</a>
</p>

<p align="center">
  <a href="https://github.com/MlsMoon/IGPPerformanceMonitor/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/MlsMoon/IGPPerformanceMonitor/actions/workflows/ci.yml/badge.svg"></a>
  <a href="https://github.com/MlsMoon/IGPPerformanceMonitor/releases/latest"><img alt="Release" src="https://img.shields.io/github/v/release/MlsMoon/IGPPerformanceMonitor"></a>
  <a href="user-guide.md"><img alt="User guide" src="https://img.shields.io/badge/docs-user%20guide-4dabf7"></a>
  <a href="../../LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/License-MIT-blue.svg"></a>
</p>

The app wraps [Intel PresentMon](https://github.com/GameTechDev/PresentMon) 2.4.1, enriches every frame with system and process metrics (CPU, RAM, NVIDIA GPU / VRAM), and draws live charts in PyQt5.

**Requires Administrator** (or membership in the Windows *Performance Log Users* group). PresentMon uses ETW.

The in-app UI is English or Simplified Chinese. This folder is the English manual.

## Install

Download the latest **installer** or portable EXE from [GitHub Releases](https://github.com/MlsMoon/IGPPerformanceMonitor/releases/latest):

| Asset | Use |
|---|---|
| `IGPPerformanceMonitor-Setup-x.y.z.exe` | Recommended. Installs to Program Files, Start Menu shortcut, uninstaller. Requests admin. |
| `IGPPerformanceMonitor.exe` | Portable one-file build (also used by in-app updates). |
| `auto_updater.exe` | Internal swapper used by Help → Check for Updates. You do not run this yourself. |

Packaged builds check GitHub Releases shortly after launch and can roll back to the previous published version.

## Documentation

| | Link |
|---|---|
| How to capture, read charts, export CSV, and use the overlay | **[User guide](user-guide.md)** |
| When something fails | **[Troubleshooting](troubleshooting.md)** |
| What changed | **[Changelog](../../CHANGELOG.md)** |
| Other languages | [Documentation index](../README.md) |

The same user guide is in the app under **Help → User Manual**.

## Features

- Multi-app capture (several instances at once, including two copies of the same exe)
- Live charts: FPS, frame time, CPU / GPU / RAM / VRAM, per-app and system
- Always-on-top overlay that follows the target window
- CSV export / import with offline stutter analysis
- English and Simplified Chinese UI (`IGP_LANG=en` or `zh_CN`)
- Dark / light theme
- In-app self-update from GitHub Releases (SHA256 verified)

## Requirements

- Windows 10 or 11 (64-bit)
- Administrator, or the *Performance Log Users* group
- A game or app that actually presents frames (not a background service)
- NVIDIA GPU recommended for GPU / VRAM / power / temperature charts (NVML). AMD and Intel GPUs still get PresentMon frame timing.

## Run from source

```bat
pip install -r requirements.txt
Scripts\run_dev.bat
```

```bat
python -m src.main --debug
```

Headless capture (admin). Prefer `Scripts\capture_debug.bat` so a UAC relaunch still writes `temp\`:

```bat
Scripts\capture_debug.bat --process-name Unity.exe --timed 10
python -m src.main --headless --process-name Unity.exe --timed 10
```

## Build

```bat
pip install -r requirements-dev.txt
Scripts\build.bat
Scripts\build_installer.bat
python Scripts\generate_manifest.py
```

Outputs in `dist\`:

- `IGPPerformanceMonitor.exe`
- `auto_updater.exe`
- `IGPPerformanceMonitor-Setup-<version>.exe` (needs [Inno Setup 6](https://jrsoftware.org/isinfo.php))
- `app_manifest.json` (GitHub Release metadata)

Default branch is **`develop`**. Stabilization and tags live on **`release`**. Both are protected.

Tagging `vX.Y.Z` on `release` (must match `VERSION`) runs `.github/workflows/release.yml`, which publishes those files as a GitHub Release.

## Tests

```bat
python Scripts/check.py
python -m src.main -t ui
python -m src.main -t update
python -m src.tests
```

The `capture` area needs admin: `Scripts\selfcheck.bat capture -a App.exe -s 8`. See `.claude/skills/test-after-changes/SKILL.md`.

## Contributing / security

- [CONTRIBUTING.md](../../CONTRIBUTING.md)
- [SECURITY.md](../../SECURITY.md)
- [CODE_OF_CONDUCT.md](../../CODE_OF_CONDUCT.md)
- [CHANGELOG.md](../../CHANGELOG.md) · [CHANGELOG.zh-CN.md](../../CHANGELOG.zh-CN.md)

## License

MIT. PresentMon is bundled under its own license from Intel; see [third-party notices](../../THIRD_PARTY_NOTICES.md).
