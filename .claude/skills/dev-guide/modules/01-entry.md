# 01 · Entry and main frame

## Key files

- `src/main.py` — process entry; admin elevation; `--debug` / `--headless` / `-t`; `run_headless_capture`
- `src/selfcheck/` — `-t` areas (auto-discovered `*_area.py`), `plan` (`python -m src.selfcheck plan`), report object
- `src/core/capture_session.py` — `CaptureSession`; shared DataStore + wrapper + sampler lifetime
- `src/ui/main_window.py` — menus (File / View / Settings / Help), overlay, update check, GitHub link, Help → User Manual
- `src/ui/dialogs/language_dialog.py` — first-run picker (`bilingual()` from JSON catalogs, not `tr()`)
- `src/config.py` — intervals, history window, PresentMon path

## Responsibilities

Start the app (GUI or headless), guarantee admin, and let `CaptureSession` own PresentMon + sampler. `MainWindow` owns UI / overlay / menus / updates only.

## Pitfalls

- **Three elevation paths** must stay consistent: `main.py` `relaunch_as_admin()` (`ShellExecuteW runas`), `Scripts/run_dev.bat` (`Start-Process -Verb RunAs`), EXE manifest (`--uac-admin` / `uac_admin=True`).
- **`-t` self-checks run before the admin gate.** Only the `capture` area needs PresentMon; forcing UAC on `ui` / `update` would put them out of reach of an agent, which is who the reports are written for. If you add an area that needs admin, add it to `selfcheck._NEEDS_ADMIN`, not to the global gate.
- **Short flags are aliases, not new options:** `-a` is `--process-name`, `-s` is `--timed`, so one spelling works for both headless capture and `-t capture`. Do not add a parallel pair.
- **Verify with the planner, not a habit.** `python -m src.selfcheck plan` selects areas from `AREA.touches`. Do not spawn a subagent unless it says `subagent: yes`. A new `*_area.py` is picked up automatically; a new `src/<pkg>/` with no `touches` prints `UNCOVERED`.
- **Headless uses `CaptureSession.run_blocking(config)`.** Do not hand-assemble DataStore/wrapper/sampler. Headless must start the sampler or CSV will lack system/process columns (`_enrich_frame` reads `_latest`).
- **GUI start/stop uses `CaptureSession.start/stop`.** The window may connect `session.wrapper` signals and read `session.data_store`, but must not call `wrapper.configure` + `sampler.configure` + `start` itself.
- **Menus are built by `_build_file_menu` / `_build_view_menu` / `_build_settings_menu` / `_build_help_menu`** via the `_add_action` / `_add_toggle` helpers. New shortcuts must also land in `shortcuts_dialog._SHORTCUTS`. View is visibility (charts, overlays). Settings is preferences (dark mode, always on top, click-through, Language submenu).
- **Menu-bar titles carry 16×16 monochrome glyphs** painted in `_GlyphMenuBar.paintEvent` from `theme.text_secondary` (`menu_kind` on each `menuAction()`). Fusion paints `CE_MenuBarItem` as **icon or text, never both**, so do **not** `setIcon` on the bar actions — that hides File / 文件. Leave room with `QMenuBar::item` left padding (26px). Refresh via `update()` in `_on_theme_changed`. No PNG assets and no colorful `QStyle.standardIcon`.
- **First-run language:** `ensure_ui_locale()` runs after Fusion + `win_chrome.install` + QSS, **before** `MainWindow()`. Skip when `IGP_LANG` or config `locale` is already set. `-t` / headless never reach this path (they build their own QApp). Switching later persists `locale`, `set_locale`, and replaces `MainWindow` in the same `QApplication` (`app._igp_main_window`); `closeEvent` already stops capture/overlays. Do not UAC-relaunch just to change language.
- **A first-run dialog is the last window.** Default `quitOnLastWindowClosed` plus `WA_QuitOnClose` treats OK on `LanguageDialog` as "the user quit", queues `QApplication.quit()`, and `MainWindow.show()` after `exec_()` never appears. The dialog sets `WA_QuitOnClose` False; `main.py` keeps `quitOnLastWindowClosed` False until the real window is shown. The same race hits Settings → Language (`_replace_main_window`): disable it around the swap, show the replacement, then close the old window.
- **Startup update check:** `QTimer.singleShot(1500, self._auto_check_update)`; skip in dev; silent unless an update exists. Source is GitHub Releases (`DEFAULT_APP_MANIFEST_URL`). The JSON fetch itself is on `ManifestWorker` (see `06-version-update.md`); Help → Check for Updates / Version History are disabled while it runs.
- **Window icon:** `setWindowIcon(QIcon(str(_resolve_icon_path())))` → `assets/icon.png` (bundled when frozen). Do not add a menu-bar corner widget.
- **libpng iCCP spam is Qt's, not ours.** `assets/icon.png` has no iCCP chunk. Qt's bundled style/message-box PNGs do, and libpng `fprintf`s to C stderr. Wrapping `sys.stderr` does not catch that. `src.core.libpng_silence.install()` (called in `main.py` before the PyQt import) dup2s fd 2. Do not "fix" it by stripping our icon again.
- **Dev mode marker:** `is_dev_mode()` is `not sys.frozen`. Source runs must show it on the window title (`window_title_dev`) **and** a permanent status-bar badge (`dev_badge`). Packaged EXE shows neither. Do not rely on the update-dialog copy alone — users never open that on a normal launch.
- **`win_chrome.install(app)` runs right after `setStyle("Fusion")`**, before the first window exists, so dialogs and message boxes get a themed title bar too. Details and the `setWindowFlags` caveat are in `04-live-ui.md`.
- **`closeEvent`:** stop+wait wrapper and sampler, and `overlay.shutdown()` (otherwise overlays leak). Capture-time overlay hide is `set_capture_active(False)` from `_on_state_changed`, not a bare `hide()` in `_stop_capture`.

## Checklist

- [ ] Startup / elevation changed → verify `run_dev.bat` and the packaged EXE
- [ ] Headless still goes through `CaptureSession`; sampler starts; CSV has system header + stats
- [ ] GUI capture lifetime is only started/stopped by `CaptureSession`
- [ ] `closeEvent` closes overlays and joins worker threads

---
last_updated: 2026-09-20
