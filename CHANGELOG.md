# Changelog

User-facing release notes for IGP Performance Monitor. English is canonical;
Simplified Chinese is in [CHANGELOG.zh-CN.md](CHANGELOG.zh-CN.md).

Help → Changelog shows the file that matches the UI language. GitHub Release
bodies are generated from **both** files (`Scripts/extract_release_notes.py`).
Do not ship a release whose notes are only the auto-generated
`Full Changelog: vA...vB` compare link.

Headings must stay `## X.Y.Z` — the in-app dialog splits on those lines.
Use `### Added` / `### Changed` / `### Fixed` / `### For contributors` as needed.

## 0.1.3

Released 2026-09-18.

System information is a real collapsible section, source builds are marked as
development, and Qt's libpng warnings no longer spam the console.

### Added

- Source (unpackaged) runs show a **[dev]** marker in the window title and a
  permanent badge in the status bar, so a development session is obvious at a
  glance. Packaged EXEs show neither.

### Changed

- Live CPU, GPU, RAM, and display readouts are key/value rows inside the same
  collapsible section as the rest of that chrome. Collapsing the section no
  longer hides the header — only the rows fold away.
- Help → User Manual uses a heading tree (pages plus H2/H3) with
  theme-colored links, instead of a flat list and Qt's default blue URLs.

### Fixed

- Qt's bundled icons print libpng iCCP warnings to the C stderr stream. Those
  lines no longer appear in the console (wrapping Python's `sys.stderr` never
  hid them).

### For contributors

- Verification is `Scripts/check.py` plus `-t` self-check areas a planner
  selects from `AREA.touches`, instead of a large assertion suite.
- An unspecified `release` bump now increments the patch (`X.Y.Z` →
  `X.Y.(Z+1)`) instead of inferring minor or major from the commit list.

## 0.1.2

Released 2026-09-17.

The user manual ships inside the app. Overlays dismiss when capture stops.
Update downloads no longer freeze the window for the whole transfer.

### Added

- Help → User Manual opens the bundled guide for the current UI language
  (`docs/en` or `docs/zh-CN`). The same `docs/` tree is packed into the
  portable EXE and copied next to it by the installer. Traditional Chinese
  and Japanese copies stay on disk and are linked from those pages.
- Check for Updates and rollback run on a worker thread behind a progress
  dialog: bytes and percent, an indeterminate bar when the server sends no
  `Content-Length`, progress through the SHA256 pass (hashing ~55 MB used to
  look like a hang), and Cancel. A cancelled download discards the partial
  file after the handle is closed so Windows can delete it.

### Fixed

- Stopping a capture now hides overlays. The follow timer used to call
  `show()` every 33 ms, so Stop, auto-stop, or the target process exiting
  left the last FPS frozen on screen.
- Long GPU and display names in the system-info chips no longer clip their
  own text or stretch the window. Chip height comes from the label (stylesheet
  padding is part of the contents margins, which font metrics do not include);
  width has a couple of pixels of slack so the last glyph is not sheared.

## 0.1.1

Released 2026-09-17.

A flat visual pass: denser chrome, a dark native title bar, less motion, and
an icon that is actually transparent.

### Changed

- Flatter interface: no shadows or surface outlines. Corner radii cap at 6 px.
  The ten stacked stats tiles are one table of hairline-separated rows.
- Dark native title bar on Windows, so a dark theme no longer shows a white
  strip above the window.
- Motion is micro-interactions only: no startup fade, hover feedback at 90 ms,
  exits at 75% of the entrance duration, and nothing animates a layout
  property (the chip-panel height animation used to reflow the charts every
  frame).
- Side panel, process lists, and the stats/charts divider use the full window
  height. Long process and GPU names are elided instead of forcing the window
  wider than 1100 px.
- App icon redrawn: real transparency (the area outside the rounded tile used
  to be opaque white, which framed the desktop/taskbar icon and the README
  logo on dark backgrounds), a tighter corner radius, and a simplified
  three-bar variant at 16–32 px where the trend line was unreadable.

### For contributors

- UI self-checks no longer write theme, chart visibility, or splitter state
  into the developer's real `%APPDATA%`.

## 0.1.0

Released 2026-09-17.

First public GitHub release. A Windows desktop app that wraps Intel PresentMon
2.4.1, enriches every frame with system and process metrics, and draws live
charts.

### Added

- Windows installer (`IGPPerformanceMonitor-Setup-0.1.0.exe`) and a portable
  one-file EXE. Both require Administrator (PresentMon uses ETW).
- In-app updates from GitHub Releases: `app_manifest.json`, SHA256-verified
  portable EXE and updater, with rollback to the previous published version.
- Live multi-app capture via Intel PresentMon 2.4.1: FPS, frame time, CPU,
  GPU, RAM, VRAM, plus an always-on-top overlay that follows the target
  window.
- CSV export and import, including offline stutter analysis.
- Dark and light themes. English and Simplified Chinese UI (`IGP_LANG=en` or
  `zh_CN`).

### For contributors

- Project skills, source comments, and contributor docs are English. UI copy
  lives in `src/i18n/zh_CN.py`.
