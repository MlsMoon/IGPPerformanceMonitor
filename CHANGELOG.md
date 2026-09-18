# Changelog

## 0.1.3

System info layout, a quieter console, and a smaller test loop.

- System info is now key/value rows in the same collapsible section as the rest of the chrome, so collapsing no longer hides the header.
- Source builds show a development badge in the title and status bar.
- Qt's bundled-icon libpng iCCP warnings no longer print to the console.
- Verification is a static script plus `-t` self-checks a planner selects, instead of a large assertion suite.

## 0.1.2

User manual, overlay teardown, and a few UI fixes since 0.1.1.

- Help → User Manual opens the bundled multilingual guide. The same `docs/` tree ships in the portable EXE and the installer.
- Stopping a capture now dismisses overlays. The follow timer used to call `show()` every 33ms, so Stop / auto-stop / process exit left the last FPS frozen on screen.
- Long GPU and display names in the system info chips no longer stretch the window; update downloads show a progress bar.

## 0.1.1

Flat visual pass and an icon rebuild.

- Flatter interface: no shadows or surface outlines, corner radii tightened to a 6px ceiling, and the ten stats tiles replaced by one table with hairline-separated rows.
- Dark native title bar on Windows, so a dark theme no longer shows a white strip above the window.
- Motion reduced to micro-interactions: no startup animation, 90ms hover feedback, and no animation of layout properties.
- App icon redrawn: real transparency (it used to have opaque white corners that framed the icon on dark backgrounds), a tighter corner radius, and a simplified three-bar variant at 16-32px where the trend line was unreadable.
- Side panel, process lists and the stats/charts divider now use the full window height, with long process and GPU names elided instead of forcing the window wider.

## 0.1.0

First public GitHub release.

- Windows installer (`IGPPerformanceMonitor-Setup-0.1.0.exe`) and portable EXE.
- In-app updates from GitHub Releases (`app_manifest.json`, SHA256-verified).
- Live multi-app capture via Intel PresentMon 2.4.1 (FPS, frame time, CPU, GPU, VRAM).
- Dark / light themed charts, overlay, CSV export/import, and offline stutter analysis.
- English and Simplified Chinese UI.
- English-only project skills, source comments, and contributor docs. UI copy in `zh_CN.py` stays translated.
