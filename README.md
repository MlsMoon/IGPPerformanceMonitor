# IGP Performance Monitor

<p align="center">
  <img src="assets/logo.png" alt="IGP Performance Monitor" width="128" height="128">
</p>

<p align="center">
  Windows desktop monitor for real-time graphics performance.
</p>

<p align="center">
  <a href="https://github.com/MlsMoon/IGPPerformanceMonitor/releases/latest"><strong>Download</strong></a>
  &nbsp;·&nbsp;
  <a href="docs/en/user-guide.md"><strong>User guide</strong></a>
  &nbsp;·&nbsp;
  <a href="docs/zh-CN/user-guide.md"><strong>使用指南</strong></a>
  &nbsp;·&nbsp;
  <a href="docs/en/troubleshooting.md"><strong>Troubleshooting</strong></a>
  &nbsp;·&nbsp;
  <a href="CHANGELOG.md"><strong>Changelog</strong></a>
</p>

<p align="center">
  <a href="docs/en/README.md">English</a>
  ·
  <a href="docs/zh-CN/README.md">简体中文</a>
  ·
  <a href="docs/zh-TW/README.md">繁體中文</a>
  ·
  <a href="docs/ja/README.md">日本語</a>
</p>

<p align="center">
  <a href="https://github.com/MlsMoon/IGPPerformanceMonitor/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/MlsMoon/IGPPerformanceMonitor/actions/workflows/ci.yml/badge.svg"></a>
  <a href="https://github.com/MlsMoon/IGPPerformanceMonitor/releases/latest"><img alt="Release" src="https://img.shields.io/github/v/release/MlsMoon/IGPPerformanceMonitor"></a>
  <a href="docs/en/user-guide.md"><img alt="User guide" src="https://img.shields.io/badge/docs-user%20guide-4dabf7"></a>
  <a href="docs/zh-CN/user-guide.md"><img alt="使用指南" src="https://img.shields.io/badge/docs-%E4%BD%BF%E7%94%A8%E6%8C%87%E5%8D%97-c41e3a"></a>
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/License-MIT-blue.svg"></a>
</p>

The app wraps [Intel PresentMon](https://github.com/GameTechDev/PresentMon) 2.4.1, enriches every frame with system/process metrics (CPU, RAM, NVIDIA GPU/VRAM), and shows live charts in PyQt5.

**Requires Administrator** (or membership in the Windows *Performance Log Users* group). PresentMon uses ETW.

## Install

Download the latest **installer** or portable EXE from [GitHub Releases](https://github.com/MlsMoon/IGPPerformanceMonitor/releases/latest):

| Asset | Use |
|---|---|
| `IGPPerformanceMonitor-Setup-x.y.z.exe` | Recommended. Installs to Program Files, Start Menu shortcut, uninstaller. Requests admin. |
| `IGPPerformanceMonitor.exe` | Portable one-file build (also used by in-app updates). |
| `auto_updater.exe` | Internal swapper used by Help → Check for Updates. |

Packaged builds check GitHub Releases shortly after launch and can roll back to the previous published version.

## Documentation

The same manuals ship in the app under **Help → User Manual**.

| | English | 简体中文 | 繁體中文 | 日本語 |
|---|---|---|---|---|
| How to use the app | [User guide](docs/en/user-guide.md) | [使用指南](docs/zh-CN/user-guide.md) | [使用指南](docs/zh-TW/user-guide.md) | [ユーザーガイド](docs/ja/user-guide.md) |
| When something fails | [Troubleshooting](docs/en/troubleshooting.md) | [排障](docs/zh-CN/troubleshooting.md) | [疑難排解](docs/zh-TW/troubleshooting.md) | [トラブルシューティング](docs/ja/troubleshooting.md) |
| What changed | [Changelog](CHANGELOG.md) | [更新记录](CHANGELOG.zh-CN.md) | | |

Full index: [docs/README.md](docs/README.md).

## Features

- Multi-app capture (several process names at once)
- Live charts: FPS, frame time, CPU/GPU/RAM/VRAM, per-app and system
- Always-on-top overlay that follows the target window
- CSV export / import with offline stutter analysis
- English and Simplified Chinese UI (`IGP_LANG=en` or `zh_CN`)
- Dark / light theme
- In-app self-update from GitHub Releases (SHA256 verified)

## Run from source

```bat
pip install -r requirements.txt
Scripts\run_dev.bat
```

```bat
python -m src.main --debug
```

Headless capture (admin). Prefer `Scripts\capture_debug.bat` so UAC relaunch still writes `temp\`:

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
python Scripts/check.py              :: compile + import + lint
python -m src.main -t ui             :: window + screenshots
python -m src.main -t update         :: download / verify / cancel
python -m src.main -t startup        :: first-run language picker (real child process)
python -m src.tests                  :: i18n / CSV / manifest contracts
```

The `capture` area needs admin: `Scripts\selfcheck.bat capture -a App.exe -s 8`. See `.claude/skills/test-after-changes/SKILL.md`.

## Repository layout

```
src/                  Application, tests, auto-updater
Scripts/              Dev / build / installer / headless helpers
docs/                 Localized README + user manuals (en, zh-CN, zh-TW, ja)
assets/               App icon (PNG + ICO) and README logo
third-party/          Bundled PresentMon 2.4.1 CLI
.claude/skills/       Agent workflow skills (English)
.github/workflows/    CI + Release
```

## Architecture (short)

```
PresentMon.exe --stdout--> CsvParser --> FrameData
  PresentMonWrapper._enrich_frame()   # stamps sampler cache only
  DataStore.add_frame()
SystemMetricsSampler (~500ms) --> DataStore snapshots + _latest cache
```

Do **not** call `psutil.cpu_percent()` per frame — Windows clock granularity makes that return `0.0`. See `CLAUDE.md` and `.claude/skills/dev-guide/`.

## Contributing / security

- [CONTRIBUTING.md](CONTRIBUTING.md)
- [SECURITY.md](SECURITY.md)
- [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)
- [CHANGELOG.md](CHANGELOG.md) · [CHANGELOG.zh-CN.md](CHANGELOG.zh-CN.md)

## License

MIT. PresentMon is bundled under its own license from Intel; see [third-party notices](THIRD_PARTY_NOTICES.md).
