# CLAUDE.md

Guidance for agents working in this repository.

Codex also reads this file through `project_doc_fallback_filenames = ["CLAUDE.md"]`. Treat the Claude skills as repository-local workflow docs:

- `.claude/skills/dev-guide/SKILL.md`
- `.claude/skills/test-after-changes/SKILL.md`
- `.claude/skills/release/SKILL.md`
- `.claude/skills/verify-metrics/SKILL.md`
- `.claude/skills/test-design/SKILL.md`

## Development guide

Before changing any `src/` module, read `.claude/skills/dev-guide/SKILL.md` and the matching `modules/0N-*.md` (key files / responsibilities / pitfalls / checklist).

After a **large change** (data flow, module interface, new pitfall/module), update the matching module note — that is the project's semi-automatic doc loop (skill rule + this file + Stop hook). If you change metric fields, run `verify-metrics`.

**Test after coding**: follow `.claude/skills/test-after-changes/SKILL.md` (static `py_compile` / import / offscreen + real headless capture). Headless needs admin — use `Scripts\capture_debug.bat` (self-elevates, writes `temp/`). Do not run `python -m src.main --headless` from a non-admin agent (UAC relaunch drops the output).

## Skills (when to use)

Project **workflow** skills (required):

| Skill | When |
|---|---|
| `dev-guide` | Before editing `src/` |
| `test-after-changes` | After editing `src/` |
| `test-design` | Writing / changing `src/tests/` |
| `verify-metrics` | Any FrameData / snapshot / CSV / sampler field change |
| `release` | Shipping a version (tag → GitHub Actions → GitHub Release) |

Third-party **reference** skills (PyQt5; already English):

| Scene | Skill |
|---|---|
| QSS / `theme.py` / dark-light / `ChartCard` | `pyqt-styling` |
| New / changed QWidget | `pyqt-widgets` |
| QThread (`PresentMonWrapper`, sampler, overlay poll) | `pyqt-threading` |
| signals/slots, `QTimer`, `QSettings` | `pyqt-core` |
| Dialogs | `pyqt-dialogs` |
| `src/tests/` / qtbot | `pyqt-testing` |
| General PyQt5 | `pyqt` (hub) |
| UI/UX audit | `qt-ui-design` |

> Third-party skills are a **reference library**, not project workflow. `pyqt*` comes from `CodeAtCode/oss-ai-skills` (GPL-3.0); `qt-ui-design` from `TheQtCompanyRnD/agent-skills` (BSD-3-Clause / Qt-Commercial).

**Language rule:** project-owned skills, `CLAUDE.md`, source comments, changelog, and commit messages are English. Do not add Chinese comments or skill text. User-visible UI stays bilingual (`en` / `zh_CN`); `src/i18n/zh_CN.py` is the only Chinese file.

## Commands

```bat
Scripts\run_dev.bat
python -m src.main --debug
python -m src.main --headless --process-name Unity.exe --timed 10
Scripts\run_build.bat
Scripts\build.bat
Scripts\build_installer.bat
python Scripts\generate_manifest.py
python -m src.tests
```

**Always run as Administrator.** Elevation is handled at every entry: `main.py` relaunches via `ShellExecuteW("runas")`; `Scripts\run_dev.bat` uses `Start-Process -Verb RunAs`; the packaged EXE declares `requireAdministrator` (`--uac-admin`).

## Architecture

The app wraps Intel PresentMon 2.4.1 as a subprocess, parses CSV stdout, enriches frames with system metrics (psutil + NVML), and draws live charts with PyQt5 + pyqtgraph.

```
PresentMon.exe --stdout--> CsvParser.parse_line() --> FrameData
  PresentMonWrapper._enrich_frame()
    stamps system/process fields FROM the sampler cache
  DataStore.add_frame()   # thread-safe (frames + fps history)
  MonitorView / CsvExport / --headless / OverlayWindow

SystemMetricsSampler (QThread, ~500ms) --> DataStore snapshots + _latest cache
```

Packaged self-update:

```
GitHub Release (tag vX.Y.Z)
  assets: IGPPerformanceMonitor.exe, auto_updater.exe,
          IGPPerformanceMonitor-Setup-X.Y.Z.exe, app_manifest.json
AppUpdateService fetches
  https://github.com/MlsMoon/IGPPerformanceMonitor/releases/latest/download/app_manifest.json
  downloads + SHA256 verifies EXEs, launches auto_updater.exe
```

Do **not** publish updates through object storage. Do **not** put cloud keys in the repo.

## Release / version / update

- **Version source:** root `VERSION` (semver). Bump it for every release.
- **Branches:** `develop` (default, PRs) and `release` (tags). Both are protected. There is no `main`.
- **Tag:** annotated `vX.Y.Z` on `release` that **equals** `v` + `VERSION`. CI refuses a mismatch.
- **Changelog:** `CHANGELOG.md` is bundled and shown in Help → Changelog.
- **Build metadata:** `Scripts\build.bat` writes `build/generated/build_info.txt` as `yyyyMMdd-HHmmss-gitsha` (`APP_BUILD`, not the version).
- **Publisher:** GitHub Actions `.github/workflows/release.yml` on tag `v*.*.*`.
- **Client URL:** `DEFAULT_APP_MANIFEST_URL` in `src/core/app_info.py` (latest-release download). Compare versions with `parse_version()`, never string compare.
- **Installer:** Inno Setup `Scripts/installer.iss` → `IGPPerformanceMonitor-Setup-<version>.exe`.
- **Dev mode never self-updates.**

## PresentMon CLI quirks

- Must **not** use `--restart_as_admin` — Python already elevates; the flag spawns a process the wrapper cannot stop.
- Must use `--stop_existing_session`.
- `--terminate_on_proc_exit` was removed (PresentMon exited immediately if the target was not running).
- v2.4.1 column names are short (`CPUBusy`, `GPUTime`, `Runtime`), not `MsCPUBusy`.

## Known pitfalls

- **psutil `cpu_percent()` at frame rate returns 0.** Sample in `SystemMetricsSampler` (~500ms), never in `_enrich_frame`.
- **NVML total vs process GPU are different APIs.** Per-process can briefly exceed total; that is expected.
- **Unlocked-FPS instant FPS is noisy.** Charts use EMA; CSV keeps raw values.
- **Missing values are `None`** (including GPU; no `-1` sentinel). Consumers use `is not None`.
- **QSS cannot theme the title bar.** It is DWM's non-client area, so a dark app shows a white strip on top until `src/ui/win_chrome.py` sets the immersive-dark-mode attribute. `setWindowFlags` recreates the HWND and drops it — re-apply in `showEvent`.
- **The UI is flat on purpose, and "flat" is a budget, not a mood.** No shadows or surface outlines; corner radii only from `theme.RADIUS_*` (6/6/4/3, capped at 6 by `test_theme`); prefer one rounded container with hairline rows over a stack of rounded tiles. Motion is micro-interactions only — no entrance animations anywhere, hover ≤ 90ms, exits at 75% of the entrance, and never animate a layout property (animate colour or opacity and let the layout snap). All of it goes through `src/ui/motion.py`.
- **`temp/` holds debug artifacts.** Already gitignored.
- **CSV export** uses the system default encoding; import has a multi-codec fallback.
- **GitHub downloads need a User-Agent.** Use `release_manifest.open_url`.
- **Manifest is UTF-8 without BOM.** Read with `utf-8-sig`; write with UTF-8 and no BOM.
- **No secrets in git.** `upload_oss.bat` is gone. History was replaced with an orphan branch so old keys are not on the default branch.

## PyInstaller

`config.py` and `app_info.resource_root()` use `sys._MEIPASS` when frozen. Bundle PresentMon, `VERSION`, `CHANGELOG.md`, `build_info.txt`, and `assets/icon.png`. Hidden imports: psutil, pynvml, win32api, win32con, win32pdh. EXE icon: `assets/icon.ico`.
